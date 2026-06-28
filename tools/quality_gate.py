"""Deterministic translation quality gate used by the local pipeline."""

from __future__ import annotations

from typing import Any

from scorer import PASS_THRESHOLD, report as score_report, score_chapter


def build_repair_notes(errors: list[str]) -> list[str]:
    """Map scorer errors to short, actionable repair hints."""
    notes: list[str] = []
    for error in errors:
        if error.startswith("Completeness"):
            notes.append("Expand missing content and preserve all source events.")
        elif error.startswith("Script Purity"):
            notes.append("Remove untranslated foreign-script leaks from the Thai output.")
        elif error.startswith("End Marker"):
            notes.append("Add the required chapter end marker.")
        elif error.startswith("Type Diversity"):
            notes.append("Keep narration and dialogue structure instead of collapsing paragraphs.")
        elif error.startswith("Dialogue Ratio"):
            notes.append("Preserve dialogue lines and avoid converting speech into narration.")
        elif error.startswith("Term Compliance"):
            notes.append("Apply glossary and term policy replacements.")

    if not notes and errors:
        notes.append("Review the failed scorer dimensions before saving output.")
    return notes


def evaluate_translation_quality(
    classified: list[dict[str, str]],
    source_text: str,
    target_lang: str = "th",
    threshold: float = PASS_THRESHOLD,
) -> dict[str, Any]:
    """Score a classified translation and apply the caller's threshold."""
    result = score_chapter(classified, len(source_text), target_lang)
    passed = result.weighted_total >= threshold
    return {
        "score": result.weighted_total,
        "passed": passed,
        "threshold": threshold,
        "report": score_report(result),
        "dimensions": {d.name: round(d.score * 100) for d in result.dimensions},
        "errors": result.errors,
        "repair_notes": build_repair_notes(result.errors),
    }
