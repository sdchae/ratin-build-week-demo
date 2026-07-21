from __future__ import annotations

import hashlib
from pathlib import Path

import pypdfium2 as pdfium


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolved_bbox(text_page, start: int, end: int):
    text = text_page.get_text_range()
    boxes = [text_page.get_charbox(index) for index in range(start, end) if not text[index].isspace()]
    left = min(box[0] for box in boxes)
    bottom = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    top = max(box[3] for box in boxes)
    return {"x": left, "y": bottom, "w": right - left, "h": top - bottom}


def test_all_public_evidence_is_exact(demo_state):
    manifest = demo_state.bindings
    assert manifest["total_evidence"] == 21
    assert manifest["bbox_exact"] == manifest["total_evidence"]
    assert manifest["fallback_jumps"] == 0
    assert manifest["unverified_evidence"] == 0
    assert all(item["jump_mode"] in {"BBOX_EXACT", "BBOX_EXACT_MULTI"} for item in manifest["items"])


def test_public_pdf_digests_pages_text_and_bbox(demo_state):
    for item in demo_state.bindings["items"]:
        path = ROOT / item["relative_evidence_pdf_path"]
        assert path.is_file()
        assert sha256_file(path) == item["evidence_pdf_sha256"]
        document = pdfium.PdfDocument(str(path))
        try:
            assert len(document) == item["page_count"]
            page = document[item["page"] - 1]
            try:
                width, height = page.get_size()
                text_page = page.get_textpage()
                try:
                    page_text = text_page.get_text_range()
                    for target in item["targets"]:
                        matched = target["matched_text"]
                        assert page_text.count(matched) == 1
                        start = page_text.index(matched)
                        actual = resolved_bbox(text_page, start, start + len(matched))
                        expected = target["bbox"]
                        for key in ("x", "y", "w", "h"):
                            assert abs(actual[key] - expected[key]) <= 0.05
                        assert 0 <= expected["x"] < width
                        assert 0 <= expected["y"] < height
                        assert expected["x"] + expected["w"] <= width + 0.05
                        assert expected["y"] + expected["h"] <= height + 0.05
                finally:
                    text_page.close()
            finally:
                page.close()
        finally:
            document.close()


def test_evidence_page_renders_as_png(demo_state):
    payload = demo_state.render_evidence_page("EV-012", 1, 2)
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(payload) > 1_000


def test_multi_target_binding_is_preserved(demo_state):
    item = next(row for row in demo_state.bindings["items"] if row["public_evidence_id"] == "EV-056")
    assert item["jump_mode"] == "BBOX_EXACT_MULTI"
    assert len(item["targets"]) == 6
    assert sum(int(target["matched_text"].rsplit("EA ", 1)[1]) for target in item["targets"]) == 42


def test_every_synthetic_pdf_page_has_disclosure(demo_state):
    synthetic_paths = {
        ROOT / item["relative_evidence_pdf_path"]
        for item in demo_state.bindings["items"]
        if item["synthetic"]
    }
    marker = "CONTROLLED SYNTHETIC EXHIBIT - NOT AN ACTUAL PROCUREMENT DOCUMENT"
    for path in synthetic_paths:
        document = pdfium.PdfDocument(str(path))
        try:
            for page_index in range(len(document)):
                page = document[page_index]
                try:
                    text_page = page.get_textpage()
                    try:
                        assert marker in text_page.get_text_range()
                    finally:
                        text_page.close()
                finally:
                    page.close()
        finally:
            document.close()
