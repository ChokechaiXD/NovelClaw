"""Tests: LLM Judge JSON parsing (Phase 1 G-Eval)."""
import json


# Patch call_llm before import
import pipeline as _pmod
from pipeline import judge_translation


def _mock_call_llm(fake_response: str):
    """Return a monkeypatched call_llm that returns (fake_response, 'mock', 'mock-model')."""
    def _fake(prompt, **kwargs):
        return fake_response, "mock", "mock-model"
    return _fake


def _valid_verdict(**overrides) -> str:
    payload = {
        "dimensions": {"accuracy": 85, "fluency": 90, "terminology": 75, "coherence": 88},
        "weighted_score": 83.5,
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
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(valid_json))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is True
    assert result["score"] == 83.85
    assert result["dimensions"]["accuracy"] == 85


def test_judge_parses_json_with_fences(monkeypatch):
    """Handle markdown code fences around JSON."""
    wrapped = f"```json\n{_valid_verdict(passed=False, repair_notes=['Fix this'])}\n```"
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(wrapped))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is True
    assert result["passed"] is False
    assert "Fix this" in result["feedback"]


def test_judge_handles_partial_json(monkeypatch):
    """Missing fields must not silently pass quality control."""
    partial = json.dumps({"dimensions": {"accuracy": 75}, "weighted_score": 75.0})
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(partial))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is False
    assert result["passed"] is False
    assert result["unavailable"] is True


def test_judge_rejects_inconsistent_weighted_score(monkeypatch):
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(_valid_verdict(weighted_score=20)))

    result = judge_translation([{"type": "narration", "text": "test"}], "source")

    assert result["ok"] is False
    assert result["passed"] is False
    assert "inconsistent" in result["feedback"]


# ── Fallback parsing ────────────────────────────────────────────────


def test_judge_fallback_on_invalid_json(monkeypatch):
    """Invalid JSON is an unavailable verdict, even when it begins with FAIL."""
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm("FAIL: The translation has issues"))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is False
    assert result["passed"] is False
    assert "unavailable" in result["feedback"]


def test_judge_fallback_passes_non_fail(monkeypatch):
    """Generic plain text must never become a silent pass."""
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm("Translation looks acceptable."))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is False
    assert result["passed"] is False


def test_judge_handles_empty_response(monkeypatch):
    """Empty or garbage response should not crash."""
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(""))
    result = judge_translation([{"type": "narration", "text": "test"}], "source")
    assert result["ok"] is False
    assert result["passed"] is False


# ── Structural edge cases ───────────────────────────────────────────


def test_judge_sampled_paragraphs_field(monkeypatch):
    ok = _valid_verdict()
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(ok))
    result = judge_translation(
        [{"type": "narration", "text": f"para {i}"} for i in range(10)],
        "source",
    )
    assert result["sampledParagraphs"] >= 3  # at least beginning + end


def test_judge_sampled_paragraphs_small(monkeypatch):
    ok = _valid_verdict()
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(ok))
    result = judge_translation(
        [{"type": "narration", "text": "only one para"}],
        "source",
    )
    assert result["sampledParagraphs"] >= 1


def test_judge_removes_end_marker_from_preview(monkeypatch):
    """End marker paragraphs shouldn't appear in sampled preview."""
    ok = _valid_verdict()
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
    ok = _valid_verdict()
    monkeypatch.setattr(_pmod, "call_llm", _mock_call_llm(ok))
    result = judge_translation(
        [{"type": "dialogue", "text": '"Hello world" mixed script'},
         {"type": "narration", "text": "clean narration..."},
         {"type": "end", "text": "(จบบท)"}],
        "source",
    )
    assert result["ok"] is True


def test_judge_samples_source_beginning_middle_and_end(monkeypatch):
    captured = {}

    def fake_call(prompt, **_kwargs):
        captured["prompt"] = prompt
        return _valid_verdict(), "mock", "mock-model"

    monkeypatch.setattr(_pmod, "call_llm", fake_call)
    source = "BEGIN_MARKER" + ("a" * 800) + "MIDDLE_MARKER" + ("z" * 800) + "END_MARKER"

    result = judge_translation([{"type": "narration", "text": "translated"}], source)

    assert result["ok"] is True
    assert "BEGIN_MARKER" in captured["prompt"]
    assert "MIDDLE_MARKER" in captured["prompt"]
    assert "END_MARKER" in captured["prompt"]


def test_judge_covers_quarter_section_in_long_chapter_with_bounded_prompt(monkeypatch):
    captured = {}

    def fake_call(prompt, **_kwargs):
        captured["prompt"] = prompt
        return _valid_verdict(), "mock", "mock-model"

    monkeypatch.setattr(_pmod, "call_llm", fake_call)
    source = ("a" * 500) + "SOURCE_QUARTER_EVENT" + ("b" * 1480)
    paragraphs = [
        {
            "type": "narration",
            "text": "เหตุการณ์เฉพาะช่วงหนึ่งในสี่" if index == 25 else f"ข้อความช่วงที่ {index}",
        }
        for index in range(100)
    ]

    result = judge_translation(paragraphs, source)

    assert result["ok"] is True
    assert "SOURCE_QUARTER_EVENT" in captured["prompt"]
    assert "เหตุการณ์เฉพาะช่วงหนึ่งในสี่" in captured["prompt"]
    assert "[25%]" in captured["prompt"]
    assert len(captured["prompt"]) < 6000


def test_judge_exception_marks_verdict_unavailable(monkeypatch):
    def fail_call(*_args, **_kwargs):
        raise RuntimeError("provider timeout")

    monkeypatch.setattr(_pmod, "call_llm", fail_call)
    result = judge_translation([{"type": "narration", "text": "translated"}], "source")

    assert result["ok"] is False
    assert result["passed"] is False
    assert "provider timeout" in result["feedback"]


def test_unavailable_judge_marks_chapter_for_review_without_rewriting(monkeypatch):
    classified = [{"type": "narration", "text": "kept translation"}]
    monkeypatch.setattr(
        _pmod,
        "judge_translation",
        lambda *_args, **_kwargs: {
            "ok": False,
            "passed": False,
            "unavailable": True,
            "feedback": "LLM Judge unavailable: invalid JSON",
        },
    )

    output, score, judge = _pmod._judge_and_auto_repair(
        classified=classified,
        source="source",
        score_result={"score": 90, "passed": True, "hardFailures": []},
        source_profile={},
        judge_model="judge",
        primary_model="primary",
        primary_provider="mock",
        system_text="system",
        user_text="prompt",
        ch_num=1,
        target_lang="th",
        attempts=[],
    )

    assert output == classified
    assert score["passed"] is False
    assert any("Judge unavailable" in item for item in score["hardFailures"])
    assert judge["unavailable"] is True


def test_repair_that_fails_second_judge_keeps_original_translation(monkeypatch):
    original = [{"type": "narration", "text": "original translation"}]
    verdicts = iter([
        {"ok": True, "passed": False, "feedback": "missing event"},
        {"ok": True, "passed": False, "feedback": "event still missing"},
    ])
    monkeypatch.setattr(_pmod, "judge_translation", lambda *_args, **_kwargs: next(verdicts))
    monkeypatch.setattr(
        _pmod,
        "call_llm",
        lambda **_kwargs: ("repaired candidate text\n\n(จบบท)", "mock", "primary"),
    )
    monkeypatch.setattr(
        _pmod,
        "_score_and_report",
        lambda *_args, **_kwargs: {"score": 92, "passed": True, "hardFailures": []},
    )
    attempts = []

    output, score, judge = _pmod._judge_and_auto_repair(
        classified=original,
        source="source",
        score_result={"score": 90, "passed": True, "hardFailures": []},
        source_profile={},
        judge_model="judge",
        primary_model="primary",
        primary_provider="mock",
        system_text="system",
        user_text="prompt",
        ch_num=1,
        target_lang="th",
        attempts=attempts,
    )

    assert output == original
    assert score["passed"] is False
    assert judge["repairAccepted"] is False
    assert judge["repairJudge"]["feedback"] == "event still missing"
    assert "original output retained" in judge["feedback"]
    assert attempts[-1]["status"] == "judge_failed"
