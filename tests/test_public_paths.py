from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_manifest_paths_are_relative_and_public(demo_state):
    for item in demo_state.bindings["items"]:
        path = Path(item["relative_evidence_pdf_path"])
        assert not path.is_absolute()
        assert path.parts[0] == "evidence"
        assert ".." not in path.parts


def test_public_audit_is_clean():
    audit = json.loads((ROOT / "proofs" / "PUBLIC_EXPORT_AUDIT.json").read_text(encoding="utf-8"))
    assert audit["status"] == "PASS"
    for key in (
        "secret_findings",
        "absolute_path_findings",
        "private_run_path_findings",
        "personal_data_findings",
        "unapproved_third_party_asset_findings",
    ):
        assert audit[key] == 0


def test_no_private_source_extensions_or_large_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", ".venv", ".runtime", "tmp"} for part in path.parts):
            continue
        assert path.suffix.lower() not in {".hwp", ".hwpx"}
        assert path.stat().st_size < 100 * 1024 * 1024

