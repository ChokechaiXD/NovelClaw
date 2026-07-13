"""Tests: LLM Judge JSON parsing (Phase 1 G-Eval)."""
import json

from pipeline import judge_translation
import pipeline.judge as judge_mod


def _mock_call_llm(fake_response: str):
    """Return a monkeypatched call_llm that returns (fake_response, 'mock', 'mock-model')."""
    def _fake(prompt, **kwargs):
        return fake_response, "mock", "mock-model"
    return _fake


def _valid_verdict(**overrides) -> str:
    payload = {
        "dimensions": {"accuracy": 85, "fluency": 90, "terminology": 75, "coherence": 88},
        "weighted_score": 83.5,  # 85*0.40 + 90*0.15 + 75*0.25 + 88*0.20 = 83.85, but 83.5 reported
        # Actually let's compute: 85*0.40 + 90*0.15 + 75*0.25 + 88*0.20 = 34+13.5+18.75+17.6 = 83.85
        # So 83.5 is wrong. Use 83.85 for consistency.
        # But the old test had 83.5... The validator checks |reported - computed| <= 2.5
        # So 83.5 works because |83.85 - 83.5| = 0.35 <= 2.5
        "passed": True,
        "errors": [],
        "repair_notes": [],
        "untranslated_scripts": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


# ── JSON parsing ────────────────────────────────────────────────────


def test_judge_parses_valid_json(monkeypatch):
    valid_json = _valid_verdict()
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm(valid_json))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is True
    assert result["score"] == 83.85
    assert result["dimensions"]["accuracy"] == 85


def test_judge_parses_json_with_fences(monkeypatch):
    """Handle markdown code fences around JSON."""
    # weighted_score = 85*0.40 + 90*0.15 + 75*0.25 + 88*0.20 = 83.85
    wrapped = f"```json\n{_valid_verdict(passed=False, repair_notes=['Fix this'])}\n```"
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm(wrapped))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is False
    assert "Fix this" in result["feedback"]


def test_judge_rejects_missing_output(monkeypatch):
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm(""))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is False
    assert result["passed"] is False


def test_judge_rejects_bad_json(monkeypatch):
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm("NOT JSON { broken"))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is False


def test_judge_rejects_missing_dimensions(monkeypatch):
    missing = json.dumps({"weighted_score": 50, "passed": False, "errors": [], "repair_notes": []})
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm(missing))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is False


def test_judge_rejects_bool_score(monkeypatch):
    bad = json.dumps({
        "dimensions": {"accuracy": 85, "fluency": 90, "terminology": True, "coherence": 88},
        # valid weighted_score = 85*0.40 + 90*0.15 + 75*0.25 + 88*0.20 = 83.85, set close
        "weighted_score": 83.0, "passed": False, "errors": [], "repair_notes": [],
    })
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm(bad))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is False


def test_judge_detects_severe_error(monkeypatch):
    # weighted_score: 90*0.40 + 90*0.15 + 85*0.25 + 88*0.20 = 36+13.5+21.25+17.6 = 88.35
    severe = json.dumps({
        "dimensions": {"accuracy": 90, "fluency": 90, "terminology": 85, "coherence": 88},
        "weighted_score": 88.35, "passed": False,
        "errors": [{"type": "hallucination", "severity": "critical", "span": "", "position": 0}],
        "repair_notes": ["Remove hallucination"],
        "untranslated_scripts": [],
    })
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm(severe))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is False


def test_judge_detects_accuracy_below_threshold(monkeypatch):
    # weighted_score: 60*0.40 + 90*0.15 + 85*0.25 + 88*0.20 = 24+13.5+21.25+17.6 = 76.35
    low_accuracy = json.dumps({
        "dimensions": {"accuracy": 60, "fluency": 90, "terminology": 85, "coherence": 88},
        "weighted_score": 76.35, "passed": False,
        "errors": [{"type": "accuracy", "severity": "major", "span": "", "position": 0}],
        "repair_notes": ["Fix accuracy"],
        "untranslated_scripts": [],
    })
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm(low_accuracy))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is False
    assert result["dimensions"]["accuracy"] == 60


def test_judge_reports_errors_list(monkeypatch):
    # weighted_score: 85*0.40 + 90*0.15 + 75*0.25 + 88*0.20 = 83.85
    with_errors = json.dumps({
        "dimensions": {"accuracy": 85, "fluency": 90, "terminology": 75, "coherence": 88},
        "weighted_score": 83.85, "passed": False,
        "errors": [{"type": "terminology", "severity": "minor", "span": "HP", "position": 3}],
        "repair_notes": ["Replace 'HP' with พลังชีวิต"],
        "untranslated_scripts": [],
    })
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm(with_errors))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert isinstance(result["errors"], list)


# ── Edge cases ─────────────────────────────────────────────────────


def test_judge_handles_empty_paragraphs(monkeypatch):
    valid_json = _valid_verdict()
    monkeypatch.setattr(judge_mod, "call_llm", _mock_call_llm(valid_json))
    result = judge_translation([], "source text")
    assert result["ok"] is True or result.get("unavailable")
