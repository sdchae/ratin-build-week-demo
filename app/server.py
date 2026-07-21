from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

import pypdfium2 as pdfium


APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
DATA_DIR = ROOT / "demo_data"
EVIDENCE_DIR = ROOT / "evidence"
RUNTIME_DIR = ROOT / ".runtime"
INDEX_PATH = APP_DIR / "index.html"
SCHEMA_PATH = APP_DIR / "gpt_decision_schema.json"
PACKET_PATH = DATA_DIR / "demo_evidence_packet.json"
BINDING_PATH = DATA_DIR / "evidence_binding_manifest.public.json"
PROVENANCE_PATH = DATA_DIR / "public_api_provenance.json"
SOURCE_MANIFEST_PATH = DATA_DIR / "source_package_manifest.public.json"
FROZEN_CACHE_PATH = DATA_DIR / "cached_gpt_response.json"
RUNTIME_CACHE_PATH = RUNTIME_DIR / "cached_gpt_response.json"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?(?![A-Za-z])")
EVIDENCE_ID_RE = re.compile(r"EV-[A-Z0-9-]+")
EXPECTED_DECISION_KEYS = {
    "bid_entry_requirements",
    "conflict_judgment",
    "risk_interpretation",
    "required_actions",
    "clarification_question_to_issuer",
    "english_decision_brief",
    "evidence_ids",
}


class PublicDemoError(ValueError):
    pass


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as target:
            json.dump(value, target, ensure_ascii=False, indent=2)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def normalize_number(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", "").strip()).normalize()
    except InvalidOperation as exc:
        raise PublicDemoError(f"invalid numeric token: {value}") from exc


def validate_decision(decision: Any, schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(decision, dict) or set(decision) != EXPECTED_DECISION_KEYS:
        raise PublicDemoError("decision keys do not match the strict public schema")
    for key in (
        "conflict_judgment",
        "risk_interpretation",
        "clarification_question_to_issuer",
        "english_decision_brief",
    ):
        value = decision[key]
        if not isinstance(value, str) or not value.strip():
            raise PublicDemoError(f"{key} must be a non-empty string")
        if len(value) > int(schema["properties"][key].get("maxLength") or 100000):
            raise PublicDemoError(f"{key} exceeds maxLength")

    actions = decision["required_actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 4:
        raise PublicDemoError("required_actions must contain one to four strings")
    if any(not isinstance(item, str) or not item.strip() for item in actions):
        raise PublicDemoError("required_actions contains an invalid item")

    allowed_ids = set(schema["properties"]["evidence_ids"]["items"]["enum"])
    evidence_ids = decision["evidence_ids"]
    if not isinstance(evidence_ids, list) or not evidence_ids:
        raise PublicDemoError("evidence_ids must be a non-empty list")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise PublicDemoError("evidence_ids must be unique")
    if any(item not in allowed_ids for item in evidence_ids):
        raise PublicDemoError("decision contains an unauthorized Evidence ID")

    requirements = decision["bid_entry_requirements"]
    requirement_schema = schema["properties"]["bid_entry_requirements"]["items"]
    required_keys = set(requirement_schema["required"])
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 16:
        raise PublicDemoError("bid_entry_requirements must contain one to sixteen items")
    seen_ids: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict) or set(requirement) != required_keys:
            raise PublicDemoError("requirement keys do not match the strict schema")
        requirement_id = requirement["requirement_id"]
        if not isinstance(requirement_id, str) or not requirement_id or requirement_id in seen_ids:
            raise PublicDemoError("requirement_id is invalid or duplicated")
        seen_ids.add(requirement_id)
        for key in (
            "category",
            "status",
            "required_or_conditional",
            "and_or_relation",
            "valid_at_bid_deadline",
            "joint_venture_supplement_allowed",
        ):
            allowed = set(requirement_schema["properties"][key]["enum"])
            if requirement[key] not in allowed:
                raise PublicDemoError(f"unauthorized requirement value for {key}")
        for key in ("title", "timing"):
            if not isinstance(requirement[key], str) or not requirement[key].strip():
                raise PublicDemoError(f"requirement {key} must be non-empty")
        requirement_evidence = requirement["evidence_ids"]
        if not isinstance(requirement_evidence, list) or len(requirement_evidence) != len(set(requirement_evidence)):
            raise PublicDemoError("requirement evidence_ids is invalid")
        if any(item not in allowed_ids for item in requirement_evidence):
            raise PublicDemoError("requirement contains an unauthorized Evidence ID")
        if requirement["status"] == "Not Found in Package" and requirement_evidence:
            raise PublicDemoError("Not Found in Package must not cite unrelated Evidence")
        if requirement["status"] not in {"Not Found in Package", "Manual Review Required"} and not requirement_evidence:
            raise PublicDemoError("confirmed requirement lacks Evidence IDs")
    return decision


def validate_authorized_numbers(decision: dict[str, Any], allowed_numbers: list[str]) -> None:
    allowed = {normalize_number(str(value)) for value in allowed_numbers}
    numeric_scope = copy.deepcopy(decision)
    for requirement in numeric_scope.get("bid_entry_requirements") or []:
        if isinstance(requirement, dict):
            requirement["requirement_id"] = ""
    text = json.dumps(numeric_scope, ensure_ascii=False, separators=(",", ":"))
    text = EVIDENCE_ID_RE.sub("", text)
    unauthorized = sorted(
        {token for token in NUMBER_RE.findall(text) if normalize_number(token) not in allowed}
    )
    if unauthorized:
        raise PublicDemoError("unauthorized number(s): " + ", ".join(unauthorized))


def build_gpt_contract(
    packet: dict[str, Any],
    bindings: dict[str, Any],
    provenance: dict[str, Any],
) -> tuple[str, dict[str, Any], str]:
    allowed_ids = packet["gpt_contract"]["allowed_evidence_ids"]
    evidence_context = [
        {
            "evidence_id": item["public_evidence_id"],
            "document": item["display_document_name"],
            "matched_text": [target["matched_text"] for target in item["targets"]],
        }
        for item in bindings["items"]
        if item["public_evidence_id"] in allowed_ids
    ]
    instructions = (
        "You are the GPT-5.6 interpretation layer for a public procurement demonstration. "
        "Use only supplied frozen Evidence and deterministic values. Return strict JSON matching the schema. "
        "You may interpret conflicts, explain risk, propose required actions, ask the issuer a clarification "
        "question, and write an English decision brief. Do not extract source text, create Evidence IDs or bbox "
        "coordinates, calculate amounts, or generate public statistics. Use only allowed Evidence IDs and numbers."
    )
    context = {
        "case_id": packet["case_id"],
        "evidence": evidence_context,
        "deterministic_values": {
            "document_linked_reference_cost": packet["document_linked_reference_cost"],
            "market_reference": packet["market_reference"],
            "cost_coverage_warning": packet["cost_coverage_warning"],
        },
        "public_api_provenance": provenance["items"],
        "allowed_evidence_ids": allowed_ids,
        "allowed_numbers": packet["gpt_contract"]["allowed_numbers"],
    }
    return instructions, context, canonical_digest({"instructions": instructions, "context": context})


def parse_openai_decision(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("incomplete_details"):
        raise PublicDemoError("OpenAI response is incomplete")
    for output in payload.get("output") or []:
        for content in output.get("content") or []:
            if content.get("type") == "refusal":
                raise PublicDemoError("OpenAI response was refused")
            if content.get("type") == "output_text" and content.get("text"):
                try:
                    return json.loads(content["text"])
                except json.JSONDecodeError as exc:
                    raise PublicDemoError("OpenAI output is not valid JSON") from exc
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return json.loads(output_text)
    raise PublicDemoError("OpenAI response contains no structured output")


class PublicDemoState:
    def __init__(self, *, live: bool = False, timeout: float = 45.0) -> None:
        self.packet = read_json(PACKET_PATH)
        self.bindings = read_json(BINDING_PATH)
        self.provenance = read_json(PROVENANCE_PATH)
        self.source_manifest = read_json(SOURCE_MANIFEST_PATH)
        self.schema = read_json(SCHEMA_PATH)
        self.live_requested = live
        self.timeout = timeout
        self.model = os.environ.get("OPENAI_MODEL", "gpt-5.6").strip() or "gpt-5.6"
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.instructions, self.prompt_context, self.prompt_digest = build_gpt_contract(
            self.packet, self.bindings, self.provenance
        )
        self.schema_digest = sha256_file(SCHEMA_PATH)
        self.source_digest = canonical_digest(
            {
                "packet": self.packet,
                "bindings": self.bindings,
                "provenance": self.provenance,
                "source_manifest": self.source_manifest,
            }
        )
        self.lock = threading.RLock()
        self.render_lock = threading.Lock()
        self.render_cache: dict[tuple[str, int, int], bytes] = {}
        self.evidence_paths = self._resolve_evidence_paths()
        self.api_packet = self._build_api_packet()
        self.current_decision: dict[str, Any] | None = None
        self.current_mode = "ERROR"
        self.current_errors: list[str] = []
        self.refresh_decision(prefer_live=live)

    def _resolve_evidence_paths(self) -> dict[str, Path]:
        evidence_root = EVIDENCE_DIR.resolve()
        result: dict[str, Path] = {}
        for item in self.bindings["items"]:
            public_id = item["public_evidence_id"]
            path = (ROOT / item["relative_evidence_pdf_path"]).resolve()
            if evidence_root not in path.parents or not path.is_file():
                raise PublicDemoError(f"Evidence path is invalid for {public_id}")
            if sha256_file(path) != item["evidence_pdf_sha256"]:
                raise PublicDemoError(f"Evidence PDF digest mismatch for {public_id}")
            result[public_id] = path
        return result

    def _page_size(self, public_id: str, page_no: int, expected_count: int) -> dict[str, Any]:
        document = pdfium.PdfDocument(str(self.evidence_paths[public_id]))
        try:
            if len(document) != expected_count or not 1 <= page_no <= len(document):
                raise PublicDemoError(f"Evidence page metadata mismatch for {public_id}")
            page = document[page_no - 1]
            try:
                width, height = page.get_size()
            finally:
                page.close()
        finally:
            document.close()
        return {"width": float(width), "height": float(height), "page_count": expected_count}

    def _build_api_packet(self) -> dict[str, Any]:
        value = copy.deepcopy(self.packet)
        value["public_api_provenance"] = copy.deepcopy(self.provenance["items"])
        evidence = []
        for index, item in enumerate(self.bindings["items"]):
            public_id = item["public_evidence_id"]
            targets = []
            for target_index, target in enumerate(item["targets"]):
                bbox = copy.deepcopy(target["bbox"])
                targets.append(
                    {
                        "target_id": f"target_{target_index + 1}",
                        "label": target["label"],
                        "text": target["matched_text"],
                        "bbox": bbox,
                        "bbox_fragments": [bbox],
                        "global_match_count": 1,
                        "coordinate_space": item["coordinate_space"],
                        "coordinate_source": f"demo_data/evidence_binding_manifest.public.json#/items/{index}/targets/{target_index}",
                        "binding_status": item["binding_status"],
                    }
                )
            evidence.append(
                {
                    "evidence_id": public_id,
                    "document_name": item["display_document_name"],
                    "evidence_pdf_name": Path(item["relative_evidence_pdf_path"]).name,
                    "source_sha256": item["source_document_sha256"],
                    "source_document_sha256": item["source_document_sha256"],
                    "evidence_pdf_sha256": item["evidence_pdf_sha256"],
                    "page": item["page"],
                    "page_count": item["page_count"],
                    "targets": targets,
                    "jump_mode": item["jump_mode"],
                    "coordinate_space": item["coordinate_space"],
                    "coordinate_frame_id": "public_evidence_pdf_page_space",
                    "coordinate_source": "demo_data/evidence_binding_manifest.public.json",
                    "binding_origin": item["binding_origin"],
                    "binding_status": item["binding_status"],
                    "pipeline_run_id": "PUBLIC_FROZEN_EXPORT",
                    "synthetic": item["synthetic"],
                    "public_source_type": item["public_source_type"],
                    "page_size": self._page_size(public_id, int(item["page"]), int(item["page_count"])),
                }
            )
        value["evidence"] = evidence
        source_documents = []
        seen_pdf_digests: set[str] = set()
        for item in evidence:
            if item["evidence_pdf_sha256"] in seen_pdf_digests:
                continue
            seen_pdf_digests.add(item["evidence_pdf_sha256"])
            source_documents.append(
                {
                    "display_name": item["document_name"],
                    "evidence_id": item["evidence_id"],
                    "public_source_type": item["public_source_type"],
                }
            )
        value["overview"]["source_documents"] = source_documents
        value["overview"]["evidence_index"] = [
            {
                "evidence_id": item["evidence_id"],
                "display_name": item["document_name"],
                "page": item["page"],
                "target_count": len(item["targets"]),
            }
            for item in evidence
        ]
        value["static_anchor_scan"] = read_json(ROOT / "proofs" / "ANCHOR_NON_HARDCODED_PROOF.public.json") if (ROOT / "proofs" / "ANCHOR_NON_HARDCODED_PROOF.public.json").is_file() else {"status": "PENDING", "hardcoded_physical_anchor_count": 0}
        return value

    def _validate(self, decision: Any) -> dict[str, Any]:
        validated = validate_decision(decision, self.schema)
        validate_authorized_numbers(validated, self.packet["gpt_contract"]["allowed_numbers"])
        return validated

    def _matching_cache(self, path: Path) -> dict[str, Any] | None:
        try:
            cache = read_json(path)
        except (OSError, json.JSONDecodeError):
            return None
        expected = {
            "status": "VALID",
            "model": self.model,
            "source_digest": self.source_digest,
            "schema_digest": self.schema_digest,
            "prompt_digest": self.prompt_digest,
        }
        if any(cache.get(key) != value for key, value in expected.items()):
            return None
        try:
            return self._validate(cache.get("decision"))
        except PublicDemoError:
            return None

    def _call_live(self) -> tuple[dict[str, Any], str]:
        if not self.api_key:
            raise PublicDemoError("OPENAI_API_KEY is not configured")
        body = {
            "model": self.model,
            "store": False,
            "instructions": self.instructions,
            "input": json.dumps(self.prompt_context, ensure_ascii=False, separators=(",", ":")),
            "reasoning": {"effort": "low"},
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "ratin_public_procurement_decision",
                    "schema": self.schema,
                    "strict": True,
                },
            },
            "max_output_tokens": 4000,
        }
        request = Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise PublicDemoError(f"OpenAI HTTP {exc.code}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise PublicDemoError(f"OpenAI request failed: {type(exc).__name__}") from exc
        decision = self._validate(parse_openai_decision(payload))
        cache = {
            "schema": "ratin.public_gpt_cache.v1",
            "status": "VALID",
            "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": self.model,
            "returned_model": str(payload.get("model") or self.model),
            "response_id": str(payload.get("id") or ""),
            "source_digest": self.source_digest,
            "schema_digest": self.schema_digest,
            "prompt_digest": self.prompt_digest,
            "decision": decision,
        }
        atomic_write_json(RUNTIME_CACHE_PATH, cache)
        return decision, cache["returned_model"]

    def refresh_decision(self, *, prefer_live: bool) -> None:
        errors: list[str] = []
        with self.lock:
            if prefer_live:
                try:
                    decision, _returned_model = self._call_live()
                    self.current_decision = decision
                    self.current_mode = "LIVE GPT"
                    self.current_errors = []
                    return
                except PublicDemoError as exc:
                    errors.append(f"LIVE_REJECTED: {exc}")
                runtime_cache = self._matching_cache(RUNTIME_CACHE_PATH)
                if runtime_cache is not None:
                    self.current_decision = runtime_cache
                    self.current_mode = "CACHED GPT"
                    self.current_errors = errors
                    return
            frozen_cache = self._matching_cache(FROZEN_CACHE_PATH)
            if frozen_cache is not None:
                self.current_decision = frozen_cache
                self.current_mode = "CACHED GPT"
                self.current_errors = errors
                return
            self.current_decision = None
            self.current_mode = "ERROR"
            self.current_errors = errors + ["FROZEN_CACHE_REJECTED"]

    def response_payload(self) -> dict[str, Any]:
        with self.lock:
            return {
                "packet": self.api_packet,
                "decision": self.current_decision,
                "decision_mode": self.current_mode,
                "errors": list(self.current_errors),
                "gpt": {
                    "model": self.model,
                    "live_requested": self.live_requested,
                    "api_key_available": bool(self.api_key),
                    "source_digest": self.source_digest,
                    "schema_digest": self.schema_digest,
                    "prompt_digest": self.prompt_digest,
                },
            }

    def upload_contract(self) -> dict[str, Any]:
        return {
            "schema": "ratin.public_fixed_upload_contract.v1",
            "case_id": self.packet["case_id"],
            "basis_notice_id": self.source_manifest["public_notice_identifier"],
            "file_count": self.source_manifest["file_count"],
            "files": copy.deepcopy(self.source_manifest["files"]),
            "pipeline_run_ids": ["PUBLIC_FROZEN_EXPORT"],
            "canonical_file_success_count": self.source_manifest["file_count"],
            "exact_evidence_count": self.bindings["bbox_exact"],
            "fallback_count": self.bindings["fallback_jumps"],
            "ocr_used": False,
            "replay_mode": "VERIFIED_PUBLIC_FROZEN_ARTIFACTS",
        }

    def render_evidence_page(self, public_id: str, page_no: int, scale: int = 2) -> bytes:
        item = next((row for row in self.bindings["items"] if row["public_evidence_id"] == public_id), None)
        if item is None or not 1 <= page_no <= int(item["page_count"]):
            raise KeyError(public_id)
        if scale not in (1, 2, 3):
            scale = 2
        cache_key = (public_id, page_no, scale)
        with self.render_lock:
            cached = self.render_cache.get(cache_key)
            if cached is not None:
                return cached
            document = pdfium.PdfDocument(str(self.evidence_paths[public_id]))
            try:
                page = document[page_no - 1]
                try:
                    bitmap = page.render(scale=float(scale))
                    image = bitmap.to_pil()
                    output = io.BytesIO()
                    image.save(output, format="PNG", optimize=True)
                    payload = output.getvalue()
                finally:
                    page.close()
            finally:
                document.close()
            self.render_cache[cache_key] = payload
            return payload


class PublicDemoHandler(BaseHTTPRequestHandler):
    state: PublicDemoState

    def _send_bytes(self, payload: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, value: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(
            json.dumps(value, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send_bytes(INDEX_PATH.read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/demo":
            self._send_json(self.state.response_payload())
            return
        if parsed.path == "/api/upload-contract":
            self._send_json(self.state.upload_contract())
            return
        if parsed.path == "/api/health":
            payload = self.state.response_payload()
            self._send_json(
                {
                    "status": "OK" if payload["decision_mode"] != "ERROR" else "ERROR",
                    "decision_mode": payload["decision_mode"],
                    "evidence_count": self.state.bindings["total_evidence"],
                    "bbox_jump_count": self.state.bindings["bbox_exact"],
                    "fallback_count": self.state.bindings["fallback_jumps"],
                    "unverified_evidence": self.state.bindings["unverified_evidence"],
                }
            )
            return
        if parsed.path == "/api/evidence-page":
            query = parse_qs(parsed.query)
            public_id = str((query.get("evidence_id") or [""])[0])
            try:
                page_no = int((query.get("page") or ["1"])[0])
                scale = int((query.get("scale") or ["2"])[0])
                payload = self.state.render_evidence_page(public_id, page_no, scale)
            except (KeyError, ValueError):
                self._send_json({"error": "unknown evidence page"}, HTTPStatus.NOT_FOUND)
                return
            self._send_bytes(payload, "image/png")
            return
        if parsed.path.startswith("/evidence/") and parsed.path.endswith(".pdf"):
            public_id = unquote(parsed.path.rsplit("/", 1)[-1][:-4])
            path = self.state.evidence_paths.get(public_id)
            if path is None:
                self._send_json({"error": "unknown evidence PDF"}, HTTPStatus.NOT_FOUND)
                return
            self._send_bytes(path.read_bytes(), "application/pdf")
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/gpt/refresh":
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        length = min(int(self.headers.get("Content-Length") or 0), 1024 * 1024)
        if length:
            self.rfile.read(length)
        self.state.refresh_decision(prefer_live=self.state.live_requested)
        self._send_json(self.state.response_payload())

    def log_message(self, format_string: str, *args: Any) -> None:
        sys.stdout.write(
            f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] "
            + format_string % args
            + "\n"
        )
        sys.stdout.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the RATIN Build Week public evaluation demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8794)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cached", action="store_true", help="Use the frozen validated cached GPT response (default).")
    mode.add_argument("--live", action="store_true", help="Attempt a live GPT-5.6 Responses API call, then fall back safely.")
    parser.add_argument("--gpt-timeout", type=float, default=45.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = PublicDemoState(live=args.live, timeout=args.gpt_timeout)
    PublicDemoHandler.state = state
    server = ThreadingHTTPServer((args.host, args.port), PublicDemoHandler)
    print(f"RATIN public demo: http://{args.host}:{args.port}")
    print(f"Decision mode: {state.current_mode}; live requested: {state.live_requested}")
    if state.current_errors:
        print("Fallback notes: " + " | ".join(state.current_errors))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
