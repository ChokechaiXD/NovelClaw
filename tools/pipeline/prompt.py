
"""prompt — Prompt builder, scorer, quality summary, and prompt splitter."""
from __future__ import annotations
import re
from typing import Any

from pipeline._shared import (
    get_logger, build_prompt, build_glossary_pre_chunk, PASS_THRESHOLD,
    evaluate_translation_quality,
)

def build_translate_prompt(
    source_text: str,
    ch_num: int,
    source_lang: str = "auto",
    target_lang: str = "th",
    slug: str = "global-descent",
    glossary_text: str = "",
    continuity_text: str = "",
    prompt_profile: str = "",
    source_profile: dict[str, Any] | None = None,
) -> str:
    """Station 3: Build prompt using prompt_builder + glossary_pre (char names)."""
    # Inject character voice map from glossary_pre
    char_context = build_glossary_pre_chunk(slug)
    if char_context:
        if glossary_text:
            glossary_text = char_context + "\n\n" + glossary_text
        else:
            glossary_text = char_context

    return build_prompt(
        source_text=source_text,
        ch_num=ch_num,
        source_lang=source_lang,
        target_lang=target_lang,
        novel_title=slug,
        glossary_text=glossary_text,
        continuity_text=continuity_text,
        profile=prompt_profile,
        source_profile=source_profile,
    )


# ── Station 6.5: Scorer ─────────────────────────────────────────────────


def _score_and_report(
    classified: list[dict[str, str]],
    source_text: str,
    target_lang: str = "th",
    threshold: float = PASS_THRESHOLD,
    source_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score translation quality. Returns result dict with pass/fail."""
    return evaluate_translation_quality(classified, source_text, target_lang, threshold, source_profile)


def _build_repair_instruction(score_result: dict[str, Any]) -> str:
    notes = score_result.get("repair_notes") or score_result.get("errors") or []
    if not notes:
        return ""
    lines = [
        "",
        "",
        "<repair>",
        "The previous translation failed the deterministic quality gate.",
        "Rewrite the full chapter and fix these issues before returning the final Thai text:",
    ]
    lines.extend(f"- {note}" for note in notes[:5])
    lines.append("</repair>")
    return "\n".join(lines)


def _quality_summary(
    score_result: dict[str, Any],
    attempts: list[dict[str, Any]],
    judge_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "passed": bool(score_result.get("passed")),
        "score": score_result.get("score", 0),
        "threshold": score_result.get("threshold", PASS_THRESHOLD),
        "hardFailures": score_result.get("hardFailures", score_result.get("errors", [])),
        "warnings": score_result.get("warnings", []),
        "repairNotes": score_result.get("repairNotes", score_result.get("repair_notes", [])),
        "lengthRatio": score_result.get("lengthRatio", 0.0),
        "scriptLeaks": score_result.get("scriptLeaks", 0),
        "structure": score_result.get("structure", {}),
        "judge": judge_result or {},
        "repairHistory": attempts,
        "attempts": attempts,
    }


# ── Prompt Splitter ────────────────────────────────────────────────────


def _split_prompt(
    prompt: str,
    repair_instruction: str = "",
) -> tuple[str | None, str]:
    """Split an assembled prompt at its earliest dynamic marker.

    Returns (system_text or None, user_text).
    """
    marker_re = re.compile(
        r"(?m)^<(?:chapter_context|glossary|continuity|source_chapter)>[ \t]*$"
    )
    split_points = [match.start() for match in marker_re.finditer(prompt)]
    split_point = min(split_points, default=-1)
    if split_point > 0 and split_point < len(prompt):
        system_text = prompt[:split_point].strip()
        user_text = prompt[split_point:].strip()
    else:
        system_text = None
        user_text = prompt
    if repair_instruction:
        user_text += repair_instruction
    return system_text, user_text


# ── Station 4-6: One Attempt Runner ────────────────────────────────────
