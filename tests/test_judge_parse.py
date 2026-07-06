"""Tests: LLM Judge JSON parsing (Phase 1 G-Eval)."""
import json
import re
from unittest.mock import ANY
from types import SimpleNamespace

import pytest

# Patch call_llm before import
import pipeline as _pmod
from pipeline import judge_translation


def _mock_call_llm(fake_response: str):
    """Return a monkeypatched call_llm that returns (fake_response, 'mock', 'mock-model')."""
    def _fake(prompt, **kwargs):
        return fake_response, "mock", "mock-model"
    return _fake


# ── JSON parsing ────────────────────────────────────────────────────


def test_judge_parses_valid_json(monkeypatch):
    valid_json = json.dumps({
        "dimensions": {"accuracy": 85, "fluency": 90, "terminology": 75, "coherence": 88},
        "weighted_score": 83.5,
        "passed": True,
        "errors": [],
        "repair_notes": [],
        "untranslated_scripts": [],
    })
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(valid_json))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is True
    assert result["score"] == 83.5
    assert result["dimensions"]["accuracy"] == 85


def test_judge_parses_json_with_fences(monkeypatch):
    """Handle markdown code fences around JSON."""
    wrapped = f"```json\n{json.dumps({'dimensions': {'accuracy': 70}, 'weighted_score': 70.0, 'passed': False, 'errors': [], 'repair_notes': ['Fix this']})}\n```"
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(wrapped))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is False
    assert "Fix this" in result["feedback"]


def test_judge_handles_partial_json(monkeypatch):
    """Missing fields should not crash — defaults apply."""
    partial = json.dumps({"dimensions": {"accuracy": 75}, "weighted_score": 75.0})
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(partial))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is True  # default
    assert result["score"] == 75.0


# ── Fallback parsing ────────────────────────────────────────────────


def test_judge_fallback_on_invalid_json(monkeypatch):
    """Invalid JSON should fall back to text-based parse."""
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm("FAIL: The translation has issues"))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is False
    assert "issues" in result["feedback"]


def test_judge_fallback_passes_non_fail(monkeypatch):
    """Plain text not starting with 'FAIL:' should pass."""
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm("Translation looks acceptable."))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is True


def test_judge_handles_empty_response(monkeypatch):
    """Empty or garbage response should not crash."""
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(""))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True  # falls back gracefully


# ── Structural edge cases ───────────────────────────────────────────


def test_judge_sampled_paragraphs_field(monkeypatch):
    ok = json.dumps({"dimensions": {}, "weighted_score": 0, "passed": True, "errors": [], "repair_notes": []})
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(ok))
    result = judge_translation(
        [{"type": "narration", "text": f"para {i}"} for i in range(10)],
        "source",
    )
    assert result["sampledParagraphs"] >= 3  # at least beginning + end


def test_judge_sampled_paragraphs_small(monkeypatch):
    ok = json.dumps({"dimensions": {}, "weighted_score": 0, "passed": True, "errors": [], "repair_notes": []})
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(ok))
    result = judge_translation(
        [{"type": "narration", "text": "only one para"}],
        "source",
    )
    assert result["sampledParagraphs"] >= 1


def test_judge_removes_end_marker_from_preview(monkeypatch):
    """End marker paragraphs shouldn't appear in sampled preview."""
    ok = json.dumps({"dimensions": {}, "weighted_score": 0, "passed": True, "errors": [], "repair_notes": []})
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(ok))
    result = judge_translation(
        [
            {"type": "narration", "text": "正文"},
            {"type": "end", "text": "(จบบท)"},
        ],
        "source",
    )
    assert result["ok"] is True


def test_judge_includes_risky_paragraphs(monkeypatch):
    """Dialogue paragraphs with mixed scripts should be sampled."""
    ok = json.dumps({"dimensions": {}, "weighted_score": 0, "passed": True, "errors": [], "repair_notes": []})
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(ok))
    result = judge_translation(
        [{"type": "dialogue", "text": '"Hello world" mixed script'},
         {"type": "narration", "text": "clean narration..."},
         {"type": "end", "text": "(จบบท)"}],
        "source",
    )
    assert result["ok"] is True
