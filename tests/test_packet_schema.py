from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_packet_is_fixed_and_engine_free(demo_state):
    packet = demo_state.packet
    assert packet["schema"] == "ratin.build_week_public_packet.v1"
    assert packet["overview"]["document_count"] == demo_state.source_manifest["file_count"]
    assert len(packet["overview"]["format_counts"]) == 3
    assert packet["public_export"]["proprietary_engine_included"] is False
    assert "evidence" not in packet


def test_runtime_packet_reads_public_bindings(demo_state):
    packet = demo_state.api_packet
    assert len(packet["evidence"]) == demo_state.bindings["total_evidence"]
    assert all(item["pipeline_run_id"] == "PUBLIC_FROZEN_EXPORT" for item in packet["evidence"])
    assert all(item["binding_origin"] == "public_exact_text_binder" for item in packet["evidence"])
    assert len(packet["overview"]["source_documents"]) == demo_state.source_manifest["file_count"]
    assert any(item["evidence_id"] == "EV-065" for item in packet["overview"]["source_documents"])
    assert len(packet["overview"]["evidence_index"]) == demo_state.bindings["total_evidence"]
    assert {item["evidence_id"] for item in packet["overview"]["evidence_index"]} == {
        item["public_evidence_id"] for item in demo_state.bindings["items"]
    }


def test_ui_uses_manifest_driven_multi_file_drop():
    html = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    assert "Upload or drop attachments" in html
    assert 'uploadDropZone.addEventListener("drop"' in html
    assert "event.dataTransfer?.files" in html
    assert "evidence_binding_manifest.public.json" not in html


def test_internal_engine_names_are_not_exposed():
    html = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    server_text = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
    for internal_name in ("SDRI", "CDSA", "EDN", "VSN", "WSN"):
        assert internal_name not in html
        assert internal_name not in server_text
