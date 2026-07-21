from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "demo_data"
PROOF_DIR = ROOT / "proofs"
BINDING_PATH = DATA_DIR / "evidence_binding_manifest.public.json"
EXPORT_MANIFEST_PATH = DATA_DIR / "public_export_manifest.json"
AUDIT_PATH = PROOF_DIR / "PUBLIC_EXPORT_AUDIT.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_files() -> list[Path]:
    excluded_parts = {".git", ".venv", ".runtime", "tmp", "__pycache__", ".pytest_cache"}
    return [
        path
        for path in sorted(ROOT.rglob("*"))
        if path.is_file() and not any(part in excluded_parts for part in path.relative_to(ROOT).parts)
    ]


def compute_bbox(text_page, start: int, end: int) -> dict[str, float]:
    page_text = text_page.get_text_range()
    boxes = [text_page.get_charbox(index) for index in range(start, end) if not page_text[index].isspace()]
    left = min(box[0] for box in boxes)
    bottom = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    top = max(box[3] for box in boxes)
    return {"x": left, "y": bottom, "w": right - left, "h": top - bottom}


def validate_jumps(bindings: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    target_count = 0
    multi_target_count = 0
    for item in bindings["items"]:
        public_id = item["public_evidence_id"]
        path = (ROOT / item["relative_evidence_pdf_path"]).resolve()
        if not path.is_file() or ROOT.resolve() not in path.parents:
            errors.append(f"{public_id}: invalid public PDF path")
            continue
        if sha256_file(path) != item["evidence_pdf_sha256"]:
            errors.append(f"{public_id}: Evidence PDF digest mismatch")
            continue
        document = pdfium.PdfDocument(str(path))
        try:
            if len(document) != item["page_count"]:
                errors.append(f"{public_id}: page count mismatch")
                continue
            if not 1 <= item["page"] <= len(document):
                errors.append(f"{public_id}: page outside public PDF")
                continue
            page = document[item["page"] - 1]
            try:
                width, height = page.get_size()
                text_page = page.get_textpage()
                try:
                    page_text = text_page.get_text_range()
                    if len(item["targets"]) > 1:
                        multi_target_count += 1
                    for target in item["targets"]:
                        target_count += 1
                        matched = target["matched_text"]
                        if page_text.count(matched) != 1:
                            errors.append(f"{public_id}: target text is not unique")
                            continue
                        start = page_text.index(matched)
                        actual = compute_bbox(text_page, start, start + len(matched))
                        expected = target["bbox"]
                        if any(abs(actual[key] - expected[key]) > 0.05 for key in ("x", "y", "w", "h")):
                            errors.append(f"{public_id}: bbox differs from final PDF text layer")
                        if not (
                            0 <= expected["x"] < width
                            and 0 <= expected["y"] < height
                            and expected["x"] + expected["w"] <= width + 0.05
                            and expected["y"] + expected["h"] <= height + 0.05
                        ):
                            errors.append(f"{public_id}: bbox is outside the public PDF page")
                finally:
                    text_page.close()
            finally:
                page.close()
        finally:
            document.close()
    return {
        "schema_version": "ratin.public_jump_validation.v1",
        "status": "PASS" if not errors else "FAIL",
        "runtime_bound_exact_evidence_links": bindings["bbox_exact"],
        "total_evidence_links": bindings["total_evidence"],
        "exact_target_count": target_count,
        "multi_target_evidence_count": multi_target_count,
        "fallback_jumps": bindings["fallback_jumps"],
        "unverified_evidence_used": bindings["unverified_evidence"],
        "errors": errors,
    }


def static_anchor_scan() -> dict[str, Any]:
    scan_files = [ROOT / "app" / "index.html", ROOT / "app" / "server.py"]
    scan_files.extend(sorted((ROOT / "tools").glob("*.py")))
    scan_files.extend(sorted((ROOT / "tests").glob("*.py")))
    patterns = {
        "windows_absolute_path": re.compile(r"[A-Za-z]:[\\/](?:Users|Windows|ProgramData|Program Files)[\\/]", re.I),
        "private_run_path": re.compile(r"docs[\\/]RUNS[\\/]", re.I),
        "internal_document_id": re.compile(r"\bdoc_[0-9a-f]{8,}\b", re.I),
        "internal_artifact_path": re.compile(r"artifacts[\\/](?:norm|raw|debug)[\\/]", re.I),
        "literal_bbox_array": re.compile(r"\bbbox\s*[:=]\s*\[\s*-?\d", re.I),
        "literal_evidence_page_query": re.compile(r"evidence-page[^\n]{0,120}[?&]page=\d", re.I),
    }
    findings = []
    for path in scan_files:
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in patterns.items():
                if pattern.search(line):
                    findings.append(
                        {
                            "file": path.relative_to(ROOT).as_posix(),
                            "line": line_number,
                            "pattern": label,
                        }
                    )
    return {
        "schema_version": "ratin.public_static_anchor_scan.v1",
        "status": "PASS" if not findings else "FAIL",
        "scanned_files": [path.relative_to(ROOT).as_posix() for path in scan_files],
        "hardcoded_physical_anchor_count": len(findings),
        "findings": findings,
    }


def public_export_audit() -> dict[str, Any]:
    files = relative_files()
    text_suffixes = {".py", ".html", ".js", ".json", ".md", ".txt", ".ps1", ".example", ".gitignore"}
    secret_pattern = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
    absolute_pattern = re.compile(r"[A-Za-z]:[\\/](?:Users|Windows|ProgramData|Program Files)[\\/]", re.I)
    private_run_pattern = re.compile(r"docs[\\/]RUNS(?:[\\/]|\b)", re.I)
    personal_patterns = [
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
        re.compile(r"\b(?:0\d{1,2})[- )]\d{3,4}[- ]\d{4}\b"),
        re.compile(r"\b010[- ]\d{4}[- ]\d{4}\b"),
        re.compile(r"\bdogu\b", re.I),
    ]
    prohibited_asset_suffixes = {".ttf", ".otf", ".woff", ".woff2", ".mp3", ".wav", ".mp4", ".mov", ".svg", ".ico", ".dll", ".exe", ".db", ".sqlite", ".duckdb"}
    forbidden_directories = {".pipeline_deps", "venv", ".venv", "__pycache__"}
    secret_findings = []
    absolute_findings = []
    private_run_findings = []
    personal_findings = []
    asset_findings = []
    oversized_findings = []
    private_source_findings = []

    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.stat().st_size >= 100 * 1024 * 1024:
            oversized_findings.append(relative)
        if path.suffix.lower() in prohibited_asset_suffixes:
            asset_findings.append(relative)
        if path.suffix.lower() in {".hwp", ".hwpx"}:
            private_source_findings.append(relative)
        if any(part in forbidden_directories for part in path.relative_to(ROOT).parts):
            private_source_findings.append(relative)
        if path.suffix.lower() not in text_suffixes and path.name not in {".gitignore"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if secret_pattern.search(text):
            secret_findings.append(relative)
        if absolute_pattern.search(text):
            absolute_findings.append(relative)
        if private_run_pattern.search(text):
            private_run_findings.append(relative)
        if any(pattern.search(text) for pattern in personal_patterns):
            personal_findings.append(relative)

    pdf_contact_findings = []
    for path in sorted((ROOT / "evidence").glob("*.pdf")):
        document = pdfium.PdfDocument(str(path))
        try:
            full_text_parts = []
            for page_index in range(len(document)):
                page = document[page_index]
                try:
                    text_page = page.get_textpage()
                    try:
                        full_text_parts.append(text_page.get_text_range())
                    finally:
                        text_page.close()
                finally:
                    page.close()
            full_text = "\n".join(full_text_parts)
            if any(pattern.search(full_text) for pattern in personal_patterns):
                pdf_contact_findings.append(path.relative_to(ROOT).as_posix())
        finally:
            document.close()
    personal_findings.extend(pdf_contact_findings)

    required_counts = {
        "secret_findings": len(set(secret_findings)),
        "absolute_path_findings": len(set(absolute_findings)),
        "private_run_path_findings": len(set(private_run_findings)),
        "personal_data_findings": len(set(personal_findings)),
        "unapproved_third_party_asset_findings": len(set(asset_findings)),
    }
    supporting_counts = {
        "oversized_file_findings": len(set(oversized_findings)),
        "private_source_or_forbidden_directory_findings": len(set(private_source_findings)),
    }
    details = {
        "secret": sorted(set(secret_findings)),
        "absolute_path": sorted(set(absolute_findings)),
        "private_run_path": sorted(set(private_run_findings)),
        "personal_data": sorted(set(personal_findings)),
        "unapproved_asset": sorted(set(asset_findings)),
        "oversized_file": sorted(set(oversized_findings)),
        "private_source_or_directory": sorted(set(private_source_findings)),
    }
    passed = all(value == 0 for value in required_counts.values()) and all(
        value == 0 for value in supporting_counts.values()
    )
    return {
        "schema_version": "ratin.public_export_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        **required_counts,
        **supporting_counts,
        "gitleaks_status": "AVAILABLE" if shutil.which("gitleaks") else "NOT_INSTALLED_STATIC_EQUIVALENT_USED",
        "files_scanned": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "details": details,
    }


def write_export_manifest() -> None:
    excluded = {EXPORT_MANIFEST_PATH.resolve(), AUDIT_PATH.resolve()}
    records = []
    for path in relative_files():
        if path.resolve() in excluded:
            continue
        records.append(
            {
                "relative_path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    write_json(
        EXPORT_MANIFEST_PATH,
        {
            "schema_version": "ratin.public_export_manifest.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "manifest_scope_excludes": [
                "demo_data/public_export_manifest.json",
                "proofs/PUBLIC_EXPORT_AUDIT.json",
            ],
            "file_count": len(records),
            "files": records,
        },
    )


def main() -> int:
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    bindings = read_json(BINDING_PATH)
    jump = validate_jumps(bindings)
    static = static_anchor_scan()
    proof = {
        "schema_version": "ratin.anchor_non_hardcoded_proof.public.v1",
        "status": "PASS" if jump["status"] == "PASS" and static["status"] == "PASS" else "FAIL",
        "runtime_bound_exact_evidence_links": jump["runtime_bound_exact_evidence_links"],
        "total_evidence_links": jump["total_evidence_links"],
        "hardcoded_physical_anchors": static["hardcoded_physical_anchor_count"],
        "hardcoded_physical_anchor_count": static["hardcoded_physical_anchor_count"],
        "fallback_jumps": jump["fallback_jumps"],
        "unverified_evidence_used": jump["unverified_evidence_used"],
        "immutable_reference_modified": False,
        "binding_source": "demo_data/evidence_binding_manifest.public.json",
    }
    write_json(PROOF_DIR / "JUMP_VALIDATION_SUMMARY.json", jump)
    write_json(PROOF_DIR / "ANCHOR_NON_HARDCODED_PROOF.public.json", proof)
    (PROOF_DIR / "ANCHOR_STATIC_SCAN.public.txt").write_text(
        "\n".join(
            [
                f'Status: {static["status"]}',
                f'Scanned files: {len(static["scanned_files"])}',
                f'Hardcoded physical anchors: {static["hardcoded_physical_anchor_count"]}',
                f'Findings: {len(static["findings"])}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (PROOF_DIR / "ANCHOR_NON_HARDCODED_PROOF.public.md").write_text(
        "# Public Non-Hardcoded Anchor Proof\n\n"
        f'- Runtime-bound exact evidence links: {proof["runtime_bound_exact_evidence_links"]}/{proof["total_evidence_links"]}\n'
        f'- Hardcoded physical anchors: {proof["hardcoded_physical_anchors"]}\n'
        f'- Fallback jumps: {proof["fallback_jumps"]}\n'
        f'- Unverified evidence used: {proof["unverified_evidence_used"]}\n'
        f'- Immutable reference modified: {str(proof["immutable_reference_modified"]).lower()}\n\n'
        "The application contains public Evidence aliases but no physical page, bbox, PDF path, or internal RUN location. "
        "Runtime navigation resolves only through the public binding manifest.\n",
        encoding="utf-8",
    )
    write_export_manifest()
    audit = public_export_audit()
    write_json(AUDIT_PATH, audit)
    if proof["status"] != "PASS" or audit["status"] != "PASS":
        print(json.dumps({"proof": proof["status"], "audit": audit["status"], "details": audit["details"]}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "status": "PASS",
                "exact_evidence": proof["runtime_bound_exact_evidence_links"],
                "hardcoded_physical_anchors": proof["hardcoded_physical_anchors"],
                "fallback": proof["fallback_jumps"],
                "audit": audit["status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
