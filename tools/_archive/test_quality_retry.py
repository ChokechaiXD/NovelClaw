from quality_retry import quality_repair_decision


def test_quality_repair_decision_allows_borderline_failed_scores():
    decision = quality_repair_decision(
        {
            "score": 82,
            "passed": False,
            "repairNotes": ["Remove leaks."],
        }
    )

    assert decision["eligible"] is True
    assert decision["reason"] == "borderline_quality"
    assert decision["minScore"] == 80.0


def test_quality_repair_decision_blocks_low_scores():
    decision = quality_repair_decision(
        {
            "score": 60,
            "passed": False,
            "repairNotes": ["Expand missing content."],
        }
    )

    assert decision["eligible"] is False
    assert decision["reason"] == "score_below_repair_floor"


def test_quality_repair_decision_blocks_outputs_without_repair_notes():
    decision = quality_repair_decision({"score": 84, "passed": False})

    assert decision["eligible"] is False
    assert decision["reason"] == "no_repair_notes"

