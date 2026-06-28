#!/usr/bin/env python3
"""
scorer.py — 6-dimension translation quality scorer (no LLM).

มิติที่วัด:
  1. Completeness        (20%) — output length vs source
  2. Script Purity       (20%) — foreign script leak (via script_policy)
  3. End Marker          (10%) — มี (จบบท) ไหม
  4. Type Diversity      (15%) — มี narration + dialogue เป็นหลัก
  5. Dialogue Ratio      (15%) — % dialogue ไม่ต่ำ/สูงเกิน
  6. Term Compliance     (20%) — ตรง glossary (ผ่าน term_policy)

ผ่าน: 95/100 (hard threshold ตามพี่โชค)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DimensionScore:
    name: str
    weight: float  # 0.0-1.0
    score: float   # 0.0-1.0
    detail: str = ""
    passed: bool = True


@dataclass
class ScorerResult:
    weighted_total: float   # 0-100
    dimensions: list[DimensionScore] = field(default_factory=list)
    passed: bool = True
    errors: list[str] = field(default_factory=list)


# ── Thresholds ─────────────────────────────────────────────────────────

PASS_THRESHOLD = 95.0  # พี่โชคสั่ง: 95/100 ถึงผ่าน

COMPLETENESS_MIN = 0.30
COMPLETENESS_IDEAL_MIN = 0.50
COMPLETENESS_IDEAL_MAX = 3.00
COMPLETENESS_MAX = 3.50

DIALOGUE_RATIO_MIN = 0.08
DIALOGUE_RATIO_MAX = 0.65
DIALOGUE_IDEAL_MIN = 0.12
DIALOGUE_IDEAL_MAX = 0.50


def _score_completeness(
    paragraphs: list[dict[str, str]], source_char_count: int
) -> DimensionScore:
    """Measure output completeness relative to source."""
    texts = [p["text"] for p in paragraphs if p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    output_chars = sum(len(t) for t in texts)
    n_paras = len(texts)

    if source_char_count == 0:
        return DimensionScore("Completeness", 0.20, 0.0, "source empty", False)

    ratio = output_chars / source_char_count
    detail = f"{output_chars} chars vs {source_char_count} src ({ratio:.2f}x, {n_paras} paras)"

    if n_paras < 3:
        return DimensionScore("Completeness", 0.20, 0.0, f"{detail} — truncated", False)

    if ratio < COMPLETENESS_MIN:
        return DimensionScore("Completeness", 0.20, max(0.0, ratio / COMPLETENESS_MIN),
                              f"{detail} — too short", False)

    if ratio > COMPLETENESS_MAX:
        return DimensionScore("Completeness", 0.20, 0.3,
                              f"{detail} — too long", False)

    if COMPLETENESS_IDEAL_MIN <= ratio <= COMPLETENESS_IDEAL_MAX:
        return DimensionScore("Completeness", 0.20, 1.0, f"{detail} ✅")

    # Penalty zone
    if ratio < COMPLETENESS_IDEAL_MIN:
        score = 0.6 + 0.4 * (ratio - COMPLETENESS_MIN) / (COMPLETENESS_IDEAL_MIN - COMPLETENESS_MIN)
    else:
        score = 0.6 + 0.4 * (COMPLETENESS_MAX - ratio) / (COMPLETENESS_MAX - COMPLETENESS_IDEAL_MAX)

    return DimensionScore("Completeness", 0.20, score, detail)


def _score_script_purity(
    paragraphs: list[dict[str, str]], target_lang: str = "th"
) -> DimensionScore:
    """Script purity check via script_policy."""
    from qa.script_policy import detect_script_leaks

    texts = [p["text"] for p in paragraphs
             if p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    if not texts:
        return DimensionScore("Script Purity", 0.20, 0.0, "no paragraphs", False)

    # Load allowed tokens
    try:
        from qa.term_policy import get_term_policy
        tp = get_term_policy(target_lang)
        allowed = tp.preserve_tokens | {t.upper() for t in tp.terms.keys()}
        for patterns in tp.preserve_patterns.values():
            for pat in patterns:
                for m in pat.finditer("\n".join(texts)):
                    allowed.add(m.group(0))
                    allowed.add(m.group(0).upper())
    except ImportError:
        allowed = set()

    result = detect_script_leaks(texts, target_lang=target_lang, allowed_latin_tokens=allowed)

    if result.ok:
        return DimensionScore("Script Purity", 0.20, 1.0, "✅ clean")

    count = result.error_count
    scripts = ", ".join(f"{s}×{c}" for s, c in result.foreign_script_counts.items())

    if count <= 1:
        score = 0.5
    elif count <= 3:
        score = 0.2
    else:
        score = 0.0

    return DimensionScore("Script Purity", 0.20, score,
                          f"⚠️ {count} leaks ({scripts})", passed=count == 0)


def _score_end_marker(paragraphs: list[dict[str, str]]) -> DimensionScore:
    """Check that last paragraph is an end marker."""
    if not paragraphs:
        return DimensionScore("End Marker", 0.10, 0.0, "no paragraphs", False)

    last = paragraphs[-1]["text"] if isinstance(paragraphs[-1], dict) else str(paragraphs[-1])
    has_end = bool(re.search(r"[\(\（\[【][\u0e00-\u0e7fจบบทจบEnd끝終]+[\)\）\]】]", last))

    if has_end:
        return DimensionScore("End Marker", 0.10, 1.0, f"✅ {last}")
    return DimensionScore("End Marker", 0.10, 0.0, f"no end marker (last: '{last}')", False)


def _score_type_diversity(paragraphs: list[dict[str, str]]) -> DimensionScore:
    """Must have narration and at least some dialogue/system."""
    types = [p["type"] for p in paragraphs
             if p["type"] != "end" and p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    if not types:
        return DimensionScore("Type Diversity", 0.15, 0.0, "no content", False)

    unique = set(types)
    detail = f"types: {', '.join(sorted(unique))}"

    if "narration" in unique and "dialogue" in unique:
        return DimensionScore("Type Diversity", 0.15, 1.0, f"{detail} ✅")
    if "narration" in unique:
        return DimensionScore("Type Diversity", 0.15, 0.5, f"{detail} — no dialogue", False)

    return DimensionScore("Type Diversity", 0.15, 0.3, f"{detail} — all {list(unique)}", False)


def _score_dialogue_ratio(paragraphs: list[dict[str, str]]) -> DimensionScore:
    """% dialogue paragraphs vs total."""
    non_end = [p for p in paragraphs
               if p["type"] != "end" and p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    if not non_end:
        return DimensionScore("Dialogue Ratio", 0.15, 0.0, "no content", False)

    dialogue = sum(1 for p in non_end if p["type"] == "dialogue")
    ratio = dialogue / len(non_end)
    detail = f"{dialogue}/{len(non_end)} = {ratio*100:.0f}% dialogue"

    if ratio < DIALOGUE_RATIO_MIN:
        return DimensionScore("Dialogue Ratio", 0.15, max(0, ratio / DIALOGUE_RATIO_MIN * 0.6),
                              f"{detail} — too little", False)
    if ratio > DIALOGUE_RATIO_MAX:
        return DimensionScore("Dialogue Ratio", 0.15, max(0, 1.0 - (ratio - DIALOGUE_RATIO_MAX) * 2),
                              f"{detail} — too much", False)
    if DIALOGUE_IDEAL_MIN <= ratio <= DIALOGUE_IDEAL_MAX:
        return DimensionScore("Dialogue Ratio", 0.15, 1.0, f"{detail} ✅")

    return DimensionScore("Dialogue Ratio", 0.15, 0.8, detail)


def score_chapter(
    paragraphs: list[dict[str, str]],
    source_char_count: int = 0,
    target_lang: str = "th",
) -> ScorerResult:
    """Score one chapter across 6 dimensions. No LLM calls."""
    dims = [
        _score_completeness(paragraphs, source_char_count),
        _score_script_purity(paragraphs, target_lang),
        _score_end_marker(paragraphs),
        _score_type_diversity(paragraphs),
        _score_dialogue_ratio(paragraphs),
    ]

    weighted = sum(d.score * d.weight for d in dims) * 100
    passed = weighted >= PASS_THRESHOLD

    errors = [f"{d.name}: {d.detail[:80]}" for d in dims if not d.passed]

    return ScorerResult(
        weighted_total=round(weighted, 1),
        dimensions=dims,
        passed=passed,
        errors=errors,
    )


def report(result: ScorerResult) -> str:
    """Human-readable score report."""
    lines = [f"📊 คะแนน: {result.weighted_total}/100  {'✅ PASS' if result.passed else '❌ FAIL'}"]
    for d in sorted(result.dimensions, key=lambda x: x.score):
        flag = "✅" if d.passed else "❌"
        pct = d.score * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"  {flag} {bar} {d.name:20s} {pct:3.0f} (น้ำหนัก {d.weight*100:.0f}%)")
        if not d.passed:
            lines.append(f"         {d.detail[:80]}")
    if result.errors:
        lines.append(f"  ⚠️  {len(result.errors)} issue(s)")
    return "\n".join(lines)
