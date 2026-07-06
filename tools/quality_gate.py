"""Deterministic translation quality gate — wraps scorer.py with
pipeline-level decisions (structure contract, repair notes).
Caller's single point of entry for scoring a translation attempt.

- evaluate_translation_quality() → dict (passed, score, hardFailures, repair_notes)
- evaluate_structure_contract() → source vs output structure check
- build_repair_notes() → error → actionable repair hint
"""

from __future__ import annotations

import re
from typing import Any

from scorer import PASS_THRESHOLD, report as score_report, score_chapter


def build_repair_notes(errors: list[str], mqm_errors: list | None = None) -> list[str]:
    """Map scorer errors to short, actionable repair hints.

    Uses MQM errors when available for more targeted instructions.
    Falls back to legacy string errors for backward compat.
    """
    notes: list[str] = []
    if mqm_errors:
        for e in mqm_errors:
            if hasattr(e, "to_short"):
                notes.append(_mqm_to_note(e))
    if not notes:
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
            elif error.startswith("Structure Contract"):
                notes.append("Restore missing source dialogue/system markers and keep source scene structure.")

    if not notes and errors:
        notes.append("Review the failed scorer dimensions before saving output.")
    return notes


def _mqm_to_note(e: Any) -> str:
    """Single MQM error → repair instruction."""
    notes = {
        "accuracy/omission": "Expand missing content and preserve all source events.",
        "accuracy/addition": "Remove extra content not present in source.",
        "script_leak/foreign_script": "Remove untranslated foreign-script leaks from the output.",
        "structure/missing_end_marker": "Add the required chapter end marker.",
        "style/monotonous_type": "Keep narration and dialogue structure instead of collapsing paragraphs.",
        "style/dialogue_imbalance": "Preserve dialogue lines and avoid converting speech into narration.",
        "terminology/term_mismatch": "Apply glossary and term policy replacements.",
    }
    key = f"{e.category}/{e.subcategory}"
    return notes.get(key, f"Fix {e.category}/{e.subcategory}: {e.detail[:80]}")


def _hard_failures(errors: list[str]) -> list[str]:
    advisory = ("Type Diversity", "Dialogue Ratio", "Script Purity", "LLM Judge")
    return [error for error in errors if not error.startswith(advisory)]


def evaluate_structure_contract(
    classified: list[dict[str, str]],
    source_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Check source-anchored structure that the scorer cannot infer alone."""
    if not source_profile:
        return {
            "passed": True,
            "hardFailures": [],
            "warnings": [],
            "source": {},
            "output": {},
        }

    content = [
        p for p in classified
        if p.get("text") not in ("(จบบท)", "(End)", "（終）", "(끝)")
    ]
    output_dialogue = sum(
        1 for p in content
        if p.get("type") == "dialogue" or re.search(r'["\u201c\u201d\u300c\u300d]', p.get("text", ""))
    )
    output_system = sum(
        1 for p in content
        if p.get("type") == "system" or re.search(r"(?:\u3010[^\u3011]+\u3011|\[[^\]\n]+\])", p.get("text", ""))
    )
    output_paragraphs = len(content)

    source_dialogue = int(source_profile.get("dialogueCount") or 0)
    source_system = int(source_profile.get("systemMarkerCount") or 0)
    source_paragraphs = int(source_profile.get("paragraphCount") or 0)

    hard_failures: list[str] = []
    warnings: list[str] = []

    if source_dialogue >= 1 and output_dialogue == 0:
        hard_failures.append("Structure Contract: source has dialogue but output has no dialogue paragraphs.")
    elif source_dialogue >= 4 and output_dialogue < max(1, round(source_dialogue * 0.25)):
        warnings.append(
            f"Structure Contract: dialogue count looks low ({output_dialogue}/{source_dialogue})."
        )

    if source_system >= 1 and output_system == 0:
        hard_failures.append("Structure Contract: source has system/UI markers but output has none.")
    elif source_system >= 4 and output_system < max(1, round(source_system * 0.35)):
        warnings.append(
            f"Structure Contract: system marker count looks low ({output_system}/{source_system})."
        )

    if source_paragraphs >= 8 and output_paragraphs < max(3, round(source_paragraphs * 0.35)):
        warnings.append(
            f"Structure Contract: output paragraph count is much lower ({output_paragraphs}/{source_paragraphs})."
        )

    return {
        "passed": not hard_failures,
        "hardFailures": hard_failures,
        "warnings": warnings,
        "source": {
            "paragraphCount": source_paragraphs,
            "dialogueCount": source_dialogue,
            "systemMarkerCount": source_system,
        },
        "output": {
            "paragraphCount": output_paragraphs,
            "dialogueCount": output_dialogue,
            "systemMarkerCount": output_system,
        },
    }


def evaluate_translation_quality(
    classified: list[dict[str, str]],
    source_text: str,
    target_lang: str = "th",
    threshold: float = PASS_THRESHOLD,
    source_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score a classified translation and apply the caller's threshold."""
    result = score_chapter(classified, len(source_text), target_lang, source_text)
    errors = list(getattr(result, "errors", []))
    mqm_errors = list(getattr(result, "mqm_errors", []))
    structure = evaluate_structure_contract(classified, source_profile)
    hard_failures = _hard_failures(errors) + structure["hardFailures"]
    warnings = list(getattr(result, "warnings", []))
    warnings.extend(structure["warnings"])
    metrics = dict(getattr(result, "metrics", {}) or {})
    passed = result.weighted_total >= threshold and not hard_failures
    repair_notes = build_repair_notes(hard_failures or errors, mqm_errors)
    return {
        "score": result.weighted_total,
        "passed": passed,
        "threshold": threshold,
        "report": score_report(result),
        "dimensions": {d.name: round(d.score * 100) for d in result.dimensions},
        "errors": errors,
        "mqm_errors": [{"category": e.category, "subcategory": e.subcategory,
                         "severity": e.severity, "detail": e.detail,
                         "span": e.span, "position": e.position} for e in mqm_errors],
        "hardFailures": hard_failures,
        "warnings": warnings,
        "repair_notes": repair_notes,
        "repairNotes": repair_notes,
        "lengthRatio": metrics.get("lengthRatio", metrics.get("length_ratio", 0.0)),
        "scriptLeaks": metrics.get("scriptLeaks", metrics.get("script_leaks", 0)),
        "structure": structure,
    }
