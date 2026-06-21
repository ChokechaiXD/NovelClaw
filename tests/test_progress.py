"""Tests for tools/progress.py — chapter translation progress tracking."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# Module-level patching for PROGRESS_DIR
import tools.progress as progress_mod


@pytest.fixture(autouse=True)
def temp_progress_dir(monkeypatch):
    """Use a temp directory for progress files to avoid side effects."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(progress_mod, "PROGRESS_DIR", Path(tmp))
        yield


def test_init_progress():
    state = progress_mod.init_progress([1, 2, 3], "test-slug")
    assert str(1) in state
    assert state["1"]["status"] == "pending"
    assert state["2"]["status"] == "pending"
    assert state["3"]["status"] == "pending"


def test_init_progress_preserves_existing():
    path = progress_mod._get_path("test-slug")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"5": {"status": "done", "retries": 0, "updated": None}}))
    
    state = progress_mod.init_progress([1, 5], "test-slug")
    assert state["5"]["status"] == "done"  # preserved
    assert state["1"]["status"] == "pending"  # new


def test_mark_running():
    state = progress_mod.init_progress([1], "test-slug")
    progress_mod.mark_running(1, "test-slug", state)
    assert state["1"]["status"] == "running"


def test_mark_done():
    state = progress_mod.init_progress([1], "test-slug")
    progress_mod.mark_done(1, "test-slug", state)
    assert state["1"]["status"] == "done"


def test_mark_failed():
    state = progress_mod.init_progress([1], "test-slug")
    progress_mod.mark_failed(1, "test-slug", state)
    assert state["1"]["status"] == "failed"


def test_get_pending():
    state = {
        "1": {"status": "pending"},
        "2": {"status": "done"},
        "3": {"status": "failed"},
        "4": {"status": "running"},
    }
    pending = progress_mod.get_pending(state)
    assert "1" in pending
    assert "3" in pending  # failed is also pending
    assert "2" not in pending
    assert "4" not in pending


def test_get_summary():
    state = {
        "1": {"status": "done"},
        "2": {"status": "done"},
        "3": {"status": "failed"},
        "4": {"status": "running"},
        "5": {"status": "pending"},
    }
    summary = progress_mod.get_summary(state)
    assert summary["done"] == 2
    assert summary["failed"] == 1
    assert summary["running"] == 1
    assert summary["pending"] == 1


def test_clear_progress():
    progress_mod.init_progress([1, 2, 3], "test-slug")
    assert progress_mod._get_path("test-slug").exists()
    progress_mod.clear_progress("test-slug")
    assert not progress_mod._get_path("test-slug").exists()


def test_persistence():
    """Verify save + load round-trip."""
    state = progress_mod.init_progress([1], "test-slug")
    progress_mod.mark_done(1, "test-slug", state)
    
    loaded = progress_mod.load_progress("test-slug")
    assert loaded["1"]["status"] == "done"
