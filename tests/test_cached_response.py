from __future__ import annotations

import server


def test_cached_mode_is_default_and_valid(demo_state):
    assert demo_state.current_mode == "CACHED GPT"
    assert demo_state.current_decision is not None
    assert demo_state.current_errors == []


def test_frozen_cache_digests_match(demo_state):
    cache = server.read_json(server.FROZEN_CACHE_PATH)
    assert cache["status"] == "VALID"
    assert cache["model"] == "gpt-5.6"
    assert cache["source_digest"] == demo_state.source_digest
    assert cache["schema_digest"] == demo_state.schema_digest
    assert cache["prompt_digest"] == demo_state.prompt_digest
    assert server.validate_decision(cache["decision"], demo_state.schema) == cache["decision"]


def test_live_cache_path_is_not_the_frozen_repository_file():
    assert server.RUNTIME_CACHE_PATH.parent.name == ".runtime"
    assert server.RUNTIME_CACHE_PATH != server.FROZEN_CACHE_PATH

