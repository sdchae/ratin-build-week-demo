from __future__ import annotations

import copy

import pytest

import server


def test_cached_decision_uses_only_allowed_numbers(demo_state):
    cache = server.read_json(server.FROZEN_CACHE_PATH)
    server.validate_authorized_numbers(cache["decision"], demo_state.packet["gpt_contract"]["allowed_numbers"])


def test_unauthorized_number_is_rejected(demo_state):
    cache = server.read_json(server.FROZEN_CACHE_PATH)
    modified = copy.deepcopy(cache["decision"])
    modified["risk_interpretation"] += " Unverified quantity 999999 requires review."
    with pytest.raises(server.PublicDemoError, match="unauthorized number"):
        server.validate_authorized_numbers(modified, demo_state.packet["gpt_contract"]["allowed_numbers"])

