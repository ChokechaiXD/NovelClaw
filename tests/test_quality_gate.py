from types import SimpleNamespace

import quality_gate
from quality_gate import evaluate_translation_quality


def test_quality_gate_applies_caller_threshold(monkeypatch):
    fake_result = SimpleNamespace(
        weighted_total=90.0,
        dimensions=[SimpleNamespace(name="Completeness", score=0.9)],
        errors=[],
    )

    monkeypatch.setattr(quality_gate, "score_chapter", lambda *_args, **_kwargs: fake_result)
    monkeypatch.setattr(quality_gate, "score_report", lambda _result: "report")

    result = evaluate_translation_quality([], "source", threshold=95.0)

    assert result["score"] == 90.0
    assert result["threshold"] == 95.0
    assert result["passed"] is False


def test_quality_gate_returns_repair_notes_for_failed_translation():
    classified = [{"type": "narration", "text": "ยังแปลไม่ครบ"}]

    result = evaluate_translation_quality(classified, "原" * 2000)

    assert result["passed"] is False
    assert result["errors"]
    assert result["repair_notes"]
