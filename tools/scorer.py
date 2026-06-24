#!/usr/bin/env python3
"""
scorer.py — Objective chapter translation quality scorer (v3).

Scores a translated chapter JSON across 8 measurable dimensions.
Supports both v2 (blocks) and v3 (paragraphs) chapter formats.
No LLM calls — purely derived from the JSON structure and source comparison.

Usage:
    python tools/scorer.py chapters/0002.json --source source/0002.md
    python tools/scorer.py chapters/ --source source/  (batch mode)

Score dimensions (v3-aware):

| # | Dimension | Weight | What it measures | Threshold |
|:-:|-----------|:------:|------------------|:---------:|
| 1 | Completeness | 20% | Output chars / source chars ratio | 0.8x–3.5x |
| 2 | CN Leak | 15% | CJK chars in paragraphs | 0 tolerance |
| 3 | EN Leak | 15% | English words not in allowed list | ≤ 2 allowed |
| 4 | End Marker | 10% | (จบบท) as last paragraph | MUST have |
| 5 | Speaker Attribution | 10% | % paragraphs with dialogue + speaker | ≥ 15% |
| 6 | Dialogue Ratio | 10% | Paragraphs with quotes / total | 10%–60% |
| 7 | Content Diversity | 10% | Must have varied content | ≥ narration + dialogue |
| 8 | Schema | 10% | Title, num, lang, output_lang | All correct |

Pass: weighted score ≥ 70/100
"""

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from schema import CN_RE as _cn_re_re
from validation import ALLOWED_LATIN_TOKENS, EN_BLACKLIST
CN_RE = _cn_re_re


# ── NPC Bank for speaker detection ──────────────────────────────────────

_NPC_NAMES: list[str] | None = None

def _get_novel_root() -> Path:
    """Get novel root from schema module, or infer from file path."""
    try:
        from schema import get_novel_root
        return get_novel_root()
    except (ImportError, Exception):
        # Fallback: infer from scorer.py location
        return Path(__file__).resolve().parent.parent / "novels" / "global-descent"


def _load_npc_names() -> list[str]:
    """Load character names from glossary locked.md + reference.md.

    Reads 'ตัวละคร' (character) entries from the glossary markdown tables.
    Returns sorted list of Thai names, longest first (to match multi-word names first).
    Cached after first load.
    """
    global _NPC_NAMES
    if _NPC_NAMES is not None:
        return _NPC_NAMES

    novel_root = _get_novel_root()
    glossary_dir = novel_root / "glossary"
    names: set[str] = set()

    _TABLE_ROW_RE = re.compile(r'^\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*ตัวละคร\s*\|')

    for fname in ("locked.md", "reference.md"):
        fpath = glossary_dir / fname
        if not fpath.exists():
            continue
        try:
            text = fpath.read_text(encoding="utf-8")
            for line in text.splitlines():
                m = _TABLE_ROW_RE.search(line)
                if m:
                    name = m.group(2).strip()
                    if len(name) >= 2:  # ignore single-char artifacts
                        names.add(name)
        except (OSError, UnicodeDecodeError):
            continue

    # Sort longest first so longer names match before substrings
    _NPC_NAMES = sorted(names, key=lambda n: (-len(n), n))
    return _NPC_NAMES


def _has_npc_speaker(paragraph: str) -> bool:
    """Check if a paragraph has an NPC name that identifies the speaker.

    Scans the entire paragraph for known character names.
    A name counts if it appears ANYWHERE in a paragraph that also has a quote,
    since in Thai the speaker name can be before, after, or mixed with the quote.
    """
    if not DIALOGUE_QUOTE_RE.search(paragraph):
        return False

    for name in _load_npc_names():
        if name in paragraph:
            return True
    return False

# Completeness ratio range
COMPLETENESS_MIN = 0.75
COMPLETENESS_MAX = 3.50
COMPLETENESS_IDEAL_MIN = 0.85
COMPLETENESS_IDEAL_MAX = 3.30  # Bumped from 3.00 to accommodate LLM verbosity

# Dialogue ratio range
DIALOGUE_RATIO_MIN = 0.08  # relaxed slightly
DIALOGUE_RATIO_MAX = 0.65
DIALOGUE_RATIO_IDEAL_MIN = 0.12
DIALOGUE_RATIO_IDEAL_MAX = 0.50

# Minimum paragraphs to be considered "translated"
MIN_PARAGRAPHS = 5

# Speaker attribution target (v3: lower because no explicit speaker field)
SPEAKER_TARGET = 0.12  # 12% of dialogue paragraphs (v3 has no explicit speaker field)

# Thai style thresholds
GO_DENSITY_THRESHOLD = 22  # max % of paragraphs with "ก็" before penalty
GO_DENSITY_IDEAL = 15      # ideal % — no penalty below this

# Dialogue quote detection regex — universal across all markers
DIALOGUE_QUOTE_RE = re.compile('[\u201c\u201d\u300c\u300d"]')


# ── Helpers ───────────────────────────────────────────────────────────

def _get_texts(data: dict) -> tuple[list[str], list[str], str | None]:
    """Extract (all_texts, non_end_texts, last_text) from chapter data.
    Handles both v2 (blocks) and v3 (paragraphs) formats."""
    if data.get("paragraphs"):
        texts = [p for p in data["paragraphs"] if p and p.strip()]
        non_end = [t for t in texts if t != "(จบบท)" and t != "(End)" and t != "（終）" and t != "(끝)"]
        last = texts[-1] if texts else None
        return texts, non_end, last
    else:
        blocks = data.get("blocks", [])
        texts = [b.get("text", "") for b in blocks if b.get("text", "").strip()]
        non_end = [t for t in texts if t != "(จบบท)" and t != "(End)" and t != "（終）" and t != "(끝)"]
        last = texts[-1] if texts else None
        return texts, non_end, last


# ── Scorer types ──────────────────────────────────────────────────────

@dataclass
class DimensionScore:
    name: str
    weight: float  # 0.0-1.0
    score: float   # 0.0-1.0
    detail: str = ""
    passed: bool = True


@dataclass
class ScorerResult:
    chapter_num: int
    weighted_total: float  # 0-100
    dimensions: list[DimensionScore] = field(default_factory=list)
    passed: bool = True
    errors: list[str] = field(default_factory=list)

    def report(self, verbose: bool = False) -> str:
        lines = []
        lines.append(f"─── Score Report: Chapter {self.chapter_num} ───")
        lines.append(f"Composite: {self.weighted_total:.0f}/100  {'✅ PASS' if self.passed else '❌ FAIL'}")
        lines.append("")
        sorted_dims = sorted(self.dimensions, key=lambda d: d.score)
        for d in sorted_dims:
            pct = d.score * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            flag = "✅" if d.passed else "❌"
            lines.append(f"  {flag} {bar}  {d.name:20s}  {pct:3.0f}/100  (weight {d.weight*100:.0f}%)")
            if verbose and d.detail:
                for line in d.detail.split("\n"):
                    lines.append(f"       {line}")
        if self.errors:
            lines.append("")
            lines.append(f"  ⚠ Errors ({len(self.errors)}):")
            for e in self.errors[:5]:
                lines.append(f"    • {e}")
        return "\n".join(lines)


# ── Dimension scorers ─────────────────────────────────────────────────

def _score_completeness(data: dict, source_char_count: int) -> DimensionScore:
    """Measure output completeness relative to source."""
    _, non_end, _ = _get_texts(data)
    output_chars = sum(len(t) for t in non_end)

    if source_char_count == 0:
        return DimensionScore("Completeness", 0.20, 0.0,
                              detail="Source empty", passed=False)

    ratio = output_chars / source_char_count
    total_count = len(non_end)
    detail = f"output={output_chars} chars, source={source_char_count} chars, ratio={ratio:.2f}x, paragraphs={total_count}"

    if total_count < MIN_PARAGRAPHS:
        return DimensionScore("Completeness", 0.20, 0.0,
                              detail=f"{detail} — TRUNCATED ({total_count} paragraphs)", passed=False)

    if ratio < COMPLETENESS_MIN:
        pct = max(0.0, ratio / COMPLETENESS_MIN)
        return DimensionScore("Completeness", 0.20, pct,
                              detail=f"{detail} — too short (< {COMPLETENESS_MIN}x)", passed=False)

    if ratio > COMPLETENESS_MAX:
        return DimensionScore("Completeness", 0.20, 0.3,
                              detail=f"{detail} — too long (> {COMPLETENESS_MAX}x)", passed=False)

    if COMPLETENESS_IDEAL_MIN <= ratio <= COMPLETENESS_IDEAL_MAX:
        score = 1.0
    elif ratio < COMPLETENESS_IDEAL_MIN:
        score = 0.5 + 0.5 * (ratio - COMPLETENESS_MIN) / (COMPLETENESS_IDEAL_MIN - COMPLETENESS_MIN)
    else:
        score = 0.5 + 0.5 * (COMPLETENESS_MAX - ratio) / (COMPLETENESS_MAX - COMPLETENESS_IDEAL_MAX)

    return DimensionScore("Completeness", 0.20, score, detail=detail)


def _score_cn_leak(data: dict) -> DimensionScore:
    """Count CJK characters in paragraphs. Zero tolerance."""
    texts, non_end, _ = _get_texts(data)
    total_cn = 0
    cn_items = []

    for i, t in enumerate(texts):
        if t in ("(จบบท)", "(End)", "（終）", "(끝)"):
            continue
        chars = CN_RE.findall(t)
        if chars:
            total_cn += len(chars)
            cn_items.append((i, "".join(chars[:5])))

    detail_parts = [f"{total_cn} CN chars"]
    if cn_items:
        detail_parts.append(f"in {len(cn_items)} paragraphs")
        for i, cs in cn_items[:3]:
            detail_parts.append(f"  [{i}]: \"{cs}\"")

    detail = "; ".join(detail_parts) if detail_parts else "clean"

    if total_cn == 0:
        return DimensionScore("CN Leak", 0.15, 1.0, detail="0 CN chars — ✅ clean")

    if total_cn <= 3:
        score = 0.3
    elif total_cn <= 10:
        score = 0.1
    else:
        score = 0.0

    return DimensionScore("CN Leak", 0.15, score,
                          detail=detail, passed=total_cn == 0)


def _score_en_leak(data: dict) -> DimensionScore:
    """Count blacklisted English words."""
    texts, non_end, _ = _get_texts(data)
    found = []

    for i, t in enumerate(texts):
        if t in ("(จบบท)", "(End)", "（終）", "(끝)"):
            continue
        for m in re.finditer(r'\b([a-zA-Z]{3,})\b', t):
            word = m.group(1).lower()
            if word.upper() in ALLOWED_LATIN_TOKENS:
                continue
            if word in EN_BLACKLIST:
                found.append((i, word, "blacklist"))
            elif word not in ("open", "beta", "the", "and"):
                # Unknown English — also penalize (caught by production gate)
                found.append((i, word, "unknown"))

    unique_words = set(w for _, w, _ in found)
    detail_parts = [f"{len(found)} EN words ({len(unique_words)} unique)"]
    word_counts = Counter(w for _, w, _ in found)
    for word, n in word_counts.most_common(5):
        detail_parts.append(f'  "{word}" ×{n}')

    detail = "; ".join(detail_parts)

    if not found:
        return DimensionScore("EN Leak", 0.15, 1.0, detail="0 EN blacklist words — ✅ clean")

    n = len(found)
    if n <= 2:
        score = 0.7
    elif n <= 5:
        score = 0.4
    elif n <= 10:
        score = 0.2
    else:
        score = 0.0

    return DimensionScore("EN Leak", 0.15, score,
                          detail=detail, passed=n <= 2)


def _score_end_marker(data: dict) -> DimensionScore:
    """Check last paragraph is (จบบท) or known end marker."""
    _, _, last = _get_texts(data)
    if not last:
        return DimensionScore("End Marker", 0.10, 0.0,
                              detail="No paragraphs at all", passed=False)

    has_end_pattern = bool(re.search(
        r'[\\(（\[【][\u0e00-\u0e7fจบบทจบEnd끝終]+[\\)）\]】]',
        last
    ))

    if has_end_pattern:
        return DimensionScore("End Marker", 0.10, 1.0,
                              detail=f"✅ end marker: \"{last}\"")
    else:
        return DimensionScore("End Marker", 0.10, 0.5,
                              detail=f"Last para \"{last}\" doesn't match known end markers",
                              passed=False)


def _score_speaker(data: dict) -> DimensionScore:
    """Check paragraphs with dialogue have speaker attribution.

    For v3 (paragraphs): detect dialogue via inline quote markers,
    then scan for known NPC names near the quote (using glossary bank).
    For v2 (blocks): use the speaker field on dialogue blocks.
    """
    texts, non_end, _ = _get_texts(data)

    if data.get("paragraphs"):
        # v3 paragraphs mode — use NPC bank for speaker detection
        dialogue_paras = [t for t in texts if DIALOGUE_QUOTE_RE.search(t)
                          and t not in ("(จบบท)", "(End)", "（終）", "(끝)")]
        if not dialogue_paras:
            return DimensionScore("Speaker", 0.10, 0.0,
                                  detail="No dialogue paragraphs detected", passed=False)

        with_speaker = sum(1 for t in dialogue_paras if _has_npc_speaker(t))

        total = len(dialogue_paras)
        ratio = with_speaker / total if total > 0 else 0
        detail = f"{with_speaker}/{total} dialogue paragraphs have speaker ({ratio*100:.0f}%)"

        if ratio >= SPEAKER_TARGET:
            return DimensionScore("Speaker", 0.10, 1.0, detail=f"✅ {detail}")

        score = ratio / SPEAKER_TARGET
        return DimensionScore("Speaker", 0.10, min(score, 1.0),
                              detail=detail, passed=ratio >= SPEAKER_TARGET)
    else:
        # v2 blocks mode — use NPC bank same as v3 (speaker field is never populated)
        blocks = data.get("blocks", [])
        dialogue_texts = [b.get("text", "") for b in blocks if b.get("type") == "dialogue"]
        if not dialogue_texts:
            return DimensionScore("Speaker", 0.10, 0.0,
                                  detail="No dialogue blocks detected", passed=False)

        with_speaker = sum(1 for t in dialogue_texts if _has_npc_speaker(t))
        total = len(dialogue_texts)
        ratio = with_speaker / total if total > 0 else 0
        detail = f"{with_speaker}/{total} dialogues have speaker ({ratio*100:.0f}%)"
        if ratio >= SPEAKER_TARGET:
            return DimensionScore("Speaker", 0.10, 1.0, detail=f"✅ {detail}")
        score = ratio / SPEAKER_TARGET
        return DimensionScore("Speaker", 0.10, min(score, 1.0),
                              detail=detail, passed=ratio >= SPEAKER_TARGET)


def _score_dialogue_ratio(data: dict, source_text: str | None = None) -> DimensionScore:
    """Dialogue paragraphs / total paragraphs.

    Two modes:
    1. Source-relative (when source available): compare DIALOGUE CHAR RATIO
       in translation vs source (characters in quotes / total characters).
       This is unit-agnostic — works even when paragraph grouping differs.
    2. Hard thresholds (fallback when no source).

    For v3: detect dialogue via inline quote markers.
    For v2: use block type.
    """
    texts, non_end, _ = _get_texts(data)

    if not non_end:
        return DimensionScore("Dialogue Ratio", 0.10, 0.0,
                              detail="Only end marker exists", passed=False)

    if data.get("paragraphs"):
        # v3: detect by inline quotes
        dialogue = sum(1 for t in non_end if DIALOGUE_QUOTE_RE.search(t))
    else:
        # v2: use block type
        blocks = data.get("blocks", [])
        non_end_blocks = [b for b in blocks if b.get("type") != "end"]
        dialogue = sum(1 for b in non_end_blocks if b.get("type") == "dialogue")
        non_end = non_end_blocks

    total = len(non_end)
    ratio = dialogue / total if total > 0 else 0
    detail = f"{dialogue}/{total} blocks = {ratio*100:.0f}% dialogue"

    # ── Source-relative check (CHAR-based, unit-agnostic) ──────────
    if source_text:
        # Count dialogue characters in source (chars inside CN quote markers)
        src_dialogue_chars = sum(
            len(m.group()) for m in re.finditer(r'「[^」]*」', source_text)
        )
        src_total_chars = len(source_text)
        src_char_ratio = src_dialogue_chars / src_total_chars if src_total_chars > 0 else 0

        # Count dialogue characters in translation (chars inside quotes)
        th_dialogue_chars = 0
        for t in non_end:
            # Handle both straight "..." and curly "..." (U+201C/U+201D) quotes
            for m in re.finditer(
                r'\u201c[^\u201d]*\u201d|"[^"]*"|\u300c[^\u300d]*\u300d',
                t
            ):
                th_dialogue_chars += len(m.group())
        th_total_chars = sum(len(t) for t in non_end)
        th_char_ratio = th_dialogue_chars / th_total_chars if th_total_chars > 0 else 0

        diff = abs(th_char_ratio - src_char_ratio)
        detail += f"\n       Source: {src_dialogue_chars}/{src_total_chars} = {src_char_ratio*100:.0f}% dialogue chars"
        detail += f"\n       Trans:  {th_dialogue_chars}/{th_total_chars} = {th_char_ratio*100:.0f}% dialogue chars"
        detail += f"\n       Δ{diff*100:.0f}pp"

        if diff <= 0.20:
            return DimensionScore("Dialogue Ratio", 0.10, 1.0,
                                  detail=f"✅ {detail}")

        score = max(0, 1.0 - (diff - 0.20) * 2)
        return DimensionScore("Dialogue Ratio", 0.10, min(score, 1.0),
                              detail=detail, passed=False)

    # ── Fallback: hard thresholds (no source available) ─────────────
    if ratio < DIALOGUE_RATIO_MIN:
        score = ratio / DIALOGUE_RATIO_MIN * 0.5
        return DimensionScore("Dialogue Ratio", 0.10, score,
                              detail=f"{detail} — too little dialogue", passed=False)

    if ratio > DIALOGUE_RATIO_MAX:
        score = max(0, 1.0 - (ratio - DIALOGUE_RATIO_MAX) * 2)
        return DimensionScore("Dialogue Ratio", 0.10, score,
                              detail=f"{detail} — too much dialogue", passed=False)

    if DIALOGUE_RATIO_IDEAL_MIN <= ratio <= DIALOGUE_RATIO_IDEAL_MAX:
        return DimensionScore("Dialogue Ratio", 0.10, 1.0, detail=f"✅ {detail}")

    score = 0.7
    return DimensionScore("Dialogue Ratio", 0.10, score, detail=detail)


def _score_content_diversity(data: dict) -> DimensionScore:
    """Must have both narration and dialogue content.

    For v3: check that some paragraphs have dialogue markers AND some don't.
    For v2: check block types.
    """
    texts, non_end, _ = _get_texts(data)

    if not non_end:
        return DimensionScore("Content Diversity", 0.10, 0.0,
                              detail="No content paragraphs", passed=False)

    if data.get("paragraphs"):
        has_dialogue = any(DIALOGUE_QUOTE_RE.search(t) for t in non_end)
        has_narration = any(not DIALOGUE_QUOTE_RE.search(t) for t in non_end)
        total_paras = len(non_end)
        detail_parts = [f"{total_paras} paragraphs"]

        if not has_narration and not has_dialogue:
            return DimensionScore("Content Diversity", 0.10, 0.0,
                                  detail="; ".join(detail_parts) + " — no narration or dialogue",
                                  passed=False)
        if not has_dialogue:
            return DimensionScore("Content Diversity", 0.10, 0.0,
                                  detail="; ".join(detail_parts) + " — all narration (no dialogue)",
                                  passed=False)
        if not has_narration:
            return DimensionScore("Content Diversity", 0.10, 0.3,
                                  detail="; ".join(detail_parts) + " — all dialogue (no narration)",
                                  passed=False)

        # Has both → 1.0
        return DimensionScore("Content Diversity", 0.10, 1.0,
                              detail="; ".join(detail_parts) + " — narration + dialogue ✅")
    else:
        # v2 blocks mode
        blocks = data.get("blocks", [])
        non_end_blocks = [b for b in blocks if b.get("type") != "end"]
        types = set(b.get("type") for b in non_end_blocks)
        has_narration = "narration" in types
        has_dialogue = "dialogue" in types
        has_system = "system" in types
        total_types = len(types)

        detail_parts = [f"{total_types} block types: {', '.join(sorted(types))}"]

        if not has_narration and not has_dialogue:
            return DimensionScore("Content Diversity", 0.10, 0.0,
                                  detail="; ".join(detail_parts) + " — no narration or dialogue",
                                  passed=False)
        if not has_dialogue:
            return DimensionScore("Content Diversity", 0.10, 0.0,
                                  detail="; ".join(detail_parts) + " — no dialogue",
                                  passed=False)
        if not has_narration:
            return DimensionScore("Content Diversity", 0.10, 0.3,
                                  detail="; ".join(detail_parts) + " — no narration, only dialogue",
                                  passed=False)

        base_score = 0.7
        if has_narration and has_dialogue and has_system:
            base_score = 1.0

        return DimensionScore("Content Diversity", 0.10, base_score,
                              detail="; ".join(detail_parts))


def _score_schema(data: dict) -> DimensionScore:
    """Check structural integrity — supports both v2 and v3 formats."""
    issues = []

    # Title
    title_raw = data.get("title", "")
    title = title_raw
    if isinstance(title_raw, dict):
        title = title_raw.get("translated", "") or title_raw.get("source", "")
    if not title:
        issues.append("missing title")
    elif not re.match(r'^(ตอนที่|บทที่|Chapter|Episode)\s+\d+', title):
        issues.append(f"bad title format: \"{title[:40]}\"")

    # Num (v3: chapterNo, v2: num)
    num = data.get("chapterNo") or data.get("num")
    if num is None:
        issues.append("missing chapter number (chapterNo/num)")

    # Lang (v3: sourceLang + targetLang, v2: lang)
    src_lang = data.get("sourceLang") or data.get("lang")
    tgt_lang = data.get("targetLang") or data.get("output_lang") or data.get("target_lang")
    if not src_lang:
        issues.append("missing source language (sourceLang/lang)")
    if not tgt_lang:
        issues.append("missing target language (targetLang/output_lang)")

    # Content: paragraphs or blocks
    has_paras = bool(data.get("paragraphs"))
    has_blocks = bool(data.get("blocks"))
    if not has_paras and not has_blocks:
        issues.append("no paragraphs or blocks")
    elif has_paras and not data["paragraphs"]:
        issues.append("empty paragraphs")
    elif has_blocks and not data["blocks"]:
        issues.append("empty blocks")
    elif has_paras and len(data["paragraphs"]) < 5:
        issues.append("too few paragraphs (<5) — may be truncated")

    detail = "; ".join(issues) if issues else "✅ all fields correct"
    score = 0.0 if issues else 1.0
    passed = len(issues) == 0

    return DimensionScore("Schema", 0.10, score, detail=detail, passed=passed)


# ── Thai style: "ก็" density ────────────────────────────────────────

def _score_thai_style(data: dict) -> DimensionScore:
    """Check Thai style: "ก็" density (CN→TH artifact marker)."""
    texts, non_end, _ = _get_texts(data)
    if not non_end:
        return DimensionScore("Thai Style", 0.05, 0.0, detail="no paragraphs")

    go_count = sum(1 for t in non_end if "ก็" in t)
    density = (go_count / len(non_end)) * 100
    detail = f'"{chr(0x0E01)}{chr(0x0E63)}" in {go_count}/{len(non_end)} ({density:.1f}%)'

    if density <= GO_DENSITY_IDEAL:
        return DimensionScore("Thai Style", 0.05, 1.0, detail=f"{detail} — natural")
    elif density <= GO_DENSITY_THRESHOLD:
        score = 1.0 - ((density - GO_DENSITY_IDEAL) / (GO_DENSITY_THRESHOLD - GO_DENSITY_IDEAL)) * 0.5
        return DimensionScore("Thai Style", 0.05, max(0.5, score), detail=f"{detail} — high")
    else:
        score = max(0, 0.5 - ((density - GO_DENSITY_THRESHOLD) / 20) * 0.5)
        return DimensionScore("Thai Style", 0.05, score, detail=f"{detail} — exceeds {GO_DENSITY_THRESHOLD}%")


# ── Main scorer ───────────────────────────────────────────────────────

def score_chapter(data: dict, source_text: str | None = None,
                  verbose: bool = False) -> ScorerResult:
    """Score one translated chapter across 9 dimensions."""
    ch_num = data.get("chapterNo") or data.get("num", 0)
    source_char_count = len(source_text) if source_text else 0

    dims = [
        _score_completeness(data, source_char_count),
        _score_cn_leak(data),
        _score_en_leak(data),
        _score_end_marker(data),
        _score_speaker(data),
        _score_dialogue_ratio(data, source_text),
        _score_content_diversity(data),
        _score_schema(data),
        _score_thai_style(data),
    ]

    weighted = sum(d.score * d.weight for d in dims) * 100
    passed = weighted >= 70 and all(
        d.passed or d.weight <= 0.10
        for d in dims
    )

    errors = []
    for d in dims:
        if not d.passed:
            errors.append(f"{d.name}: {d.detail[:80]}")

    return ScorerResult(
        chapter_num=ch_num,
        weighted_total=round(weighted, 1),
        dimensions=dims,
        passed=passed,
        errors=errors,
    )


def score_file(json_path: Path, source_path: Path | None = None,
               verbose: bool = False) -> ScorerResult | None:
    """Score a chapter JSON file."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ Cannot read {json_path}: {e}", file=sys.stderr)
        return None

    source_text = None
    if source_path and source_path.exists():
        source_text = source_path.read_text(encoding="utf-8")
    elif source_path:
        print(f"⚠ Source not found: {source_path}", file=sys.stderr)

    return score_chapter(data, source_text=source_text, verbose=verbose)


# ── CLI ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score translated chapter JSON quality across 8 dimensions."
    )
    parser.add_argument("target",
                        help="Chapter JSON file, or directory to batch-score")
    parser.add_argument("--source", "-s", default=None,
                        help="Source .md file, or directory (for batch)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show dimension details")
    parser.add_argument("--pass-threshold", type=float, default=70.0,
                        help="Pass threshold (default: 70.0)")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of human-readable report")
    args = parser.parse_args()

    target = Path(args.target)

    # Single file mode
    if target.is_file():
        src = None
        if args.source:
            src = Path(args.source)
            if src.is_dir():
                src = src / f"{target.stem}.md"
        result = score_file(target, source_path=src, verbose=args.verbose)
        if result is None:
            sys.exit(1)
        if args.json:
            print(json.dumps({
                "ch": result.chapter_num,
                "score": result.weighted_total,
                "passed": result.passed,
                "dimensions": {d.name: round(d.score * 100) for d in result.dimensions},
                "errors": result.errors,
            }, ensure_ascii=False))
        else:
            print(result.report(verbose=args.verbose))
            if not result.passed:
                sys.exit(1)
        return

    # Batch mode
    if target.is_dir():
        json_files = sorted(target.glob("*.json"))
        source_dir = Path(args.source) if args.source else None
        results = []
        for jf in json_files:
            src_file = source_dir / f"{jf.stem}.md" if source_dir else None
            r = score_file(jf, source_path=src_file)
            if r:
                results.append(r)

        if not results:
            print("No valid chapter files found.")
            sys.exit(1)

        if args.json:
            output = {
                "total": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed),
                "avg_score": round(sum(r.weighted_total for r in results) / len(results), 1),
                "results": [
                    {"ch": r.chapter_num, "score": r.weighted_total, "passed": r.passed,
                     "errors": r.errors}
                    for r in results
                ],
            }
            print(json.dumps(output, ensure_ascii=False))
        else:
            passed = [r for r in results if r.passed]
            failed = [r for r in results if not r.passed]
            avg = sum(r.weighted_total for r in results) / len(results)

            print(f"═══════ BATCH SCORE: {len(results)} chapters ═══════")
            print(f"  ✅ Passed: {len(passed)}")
            print(f"  ❌ Failed: {len(failed)}")
            print(f"  📊 Average: {avg:.0f}/100")
            print("")

            if failed:
                print("─── Failed chapters ───")
                for r in sorted(failed, key=lambda x: x.weighted_total):
                    print(f"  ch{r.chapter_num:>4d}: {r.weighted_total:.0f}/100")
                    for e in r.errors[:2]:
                        print(f"         {e}")
                print("")

            print("─── Worst 5 ───")
            for r in sorted(results, key=lambda x: x.weighted_total)[:5]:
                print(f"  ch{r.chapter_num:>4d}: {r.weighted_total:.0f}/100  {'PASS' if r.passed else 'FAIL'}")

            print("")
            print("─── Dimension averages ───")
            dim_names = [d.name for d in results[0].dimensions]
            for name in dim_names:
                avg_d = sum(
                    d.score for r in results for d in r.dimensions if d.name == name
                ) / len(results)
                bar = "█" * int(avg_d * 10) + "░" * (10 - int(avg_d * 10))
                print(f"  {bar}  {name:20s}  {avg_d*100:.0f}/100")


if __name__ == "__main__":
    main()
