from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import server


@pytest.fixture(scope="session")
def demo_state():
    return server.PublicDemoState(live=False)

