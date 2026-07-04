"""Quality repair retry policy for the translation pipeline."""

from __future__ import annotations

from typing import Any

from scorer import PASS_THRESHOLD

REPAIR_MIN_SCORE = 80.0


def _repair_notes(score_result: dict[str, Any]) -> list[str]:
    notes = score_result.get("repairNotes") or score_result.get("repair_notes") or []
    return [str(note) for note in notes if str(note).strip()]


def quality_repair_decision(
    score_result: dict[str, Any],
    threshold: float = PASS_THRESHOLD,
    min_score: float = REPAIR_MIN_SCORE,
) -> dict[str, Any]:
    """Return whether a failed translation should get one repair retry.

    The retry is intentionally reserved for near-miss or high-score hard-fail
    outputs. Very low scores usually indicate missing content or structural
    collapse, so retrying them immediately tends to waste provider quota.
    """
    score = float(score_result.get("score") or 0.0)
    notes = _repair_notes(score_result)

    if score_result.get("passed") is True:
        return {"eligible": False, "reason": "already_passed", "score": score}
    if not notes:
        return {"eligible": False, "reason": "no_repair_notes", "score": score}
    if score < min_score:
        return {
            "eligible": False,
            "reason": "score_below_repair_floor",
            "score": score,
            "minScore": min_score,
        }

    return {
        "eligible": True,
        "reason": "borderline_quality",
        "score": score,
        "minScore": min_score,
        "threshold": float(score_result.get("threshold") or threshold),
        "repairNotes": notes,
    }

