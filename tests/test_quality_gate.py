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


def test_quality_gate_returns_structured_quality_fields():
    classified = [
        {"type": "narration", "text": "เฉาซิงเดินไปข้างหน้า"},
        {"type": "end", "text": "(จบบท)"},
    ]

    result = evaluate_translation_quality(classified, "原" * 2000)

    assert "hardFailures" in result
    assert "warnings" in result
    assert "repairNotes" in result
    assert "lengthRatio" in result
    assert "scriptLeaks" in result


def test_quality_gate_hard_fails_and_counts_foreign_script_leaks():
    classified = [
        {"type": "narration", "text": "ข้อความนี้ยังมี Open Beta ปะปนอยู่"},
        {"type": "end", "text": "(จบบท)"},
    ]

    result = evaluate_translation_quality(classified, "原" * 40)

    assert result["passed"] is False
    assert result["scriptLeaks"] == 2
    assert any(error.startswith("Script Purity") for error in result["hardFailures"])


def test_quality_gate_fails_missing_source_structure(monkeypatch):
    fake_result = SimpleNamespace(
        weighted_total=95.0,
        dimensions=[SimpleNamespace(name="Completeness", score=1.0)],
        errors=[],
        warnings=[],
        metrics={"lengthRatio": 1.0, "scriptLeaks": 0},
    )

    monkeypatch.setattr(quality_gate, "score_chapter", lambda *_args, **_kwargs: fake_result)
    monkeypatch.setattr(quality_gate, "score_report", lambda _result: "report")

    result = evaluate_translation_quality(
        [{"type": "narration", "text": "เฉาซิงเดินไปข้างหน้าอย่างเงียบงัน"}],
        "source",
        source_profile={"paragraphCount": 3, "dialogueCount": 1, "systemMarkerCount": 1},
    )

    assert result["passed"] is False
    assert any("Structure Contract" in error for error in result["hardFailures"])
    assert result["structure"]["output"]["dialogueCount"] == 0
