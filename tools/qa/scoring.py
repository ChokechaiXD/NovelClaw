"""tools/qa/scoring.py — Core scoring logic for translation quality.

Contains the dimension scoring functions extracted from scorer.py.
scorer.py remains as CLI wrapper importing from here.
"""

from __future__ import annotations

import re
from pathlib import Path

from .validators import ALLOWED_LATIN_TOKENS, EN_BLACKLIST, CN_RE


# ── Score dimension container ──────────────────────────────────────────

class DimensionScore:
    """Score for one quality dimension."""
    def __init__(self, name: str, weight: float, score: float,
                 detail: str = "", passed: bool | None = None):
        self.name = name
        self.weight = weight
        self.score = score
        self.detail = detail
        self.passed = passed if passed is not None else (score >= 0.5)

    def weighted(self) -> float:
        return self.score * self.weight

    def __repr__(self) -> str:
        return f"{self.name}: {self.score:.2f} (w={self.weight:.2f})"


# ── Text extraction ────────────────────────────────────────────────────

def get_texts(data: dict) -> tuple[list[str], list[str], list[str]]:
    """Extract texts from chapter data. Returns (all_texts, non_end_texts, dialogue_texts)."""
    paragraphs = data.get("paragraphs", [])
    if not paragraphs:
        blocks = data.get("blocks", [])
        texts = [b.get("text", "") for b in blocks]
    else:
        texts = paragraphs

    non_end = [t for t in texts if t not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    dialogue_texts = [t for t in non_end if re.search(r'["\u201c\u201d\u300c\u300d]', t)]
    return texts, non_end, dialogue_texts


# ── Dimension scorers ──────────────────────────────────────────────────

def score_completeness(data: dict, source_path: str | Path | None = None) -> DimensionScore:
    """Score output completeness vs source length."""
    texts, non_end, _ = get_texts(data)
    if not non_end:
        return DimensionScore("Completeness", 0.20, 0.0, detail="No content to score")

    output_chars = sum(len(t) for t in non_end)

    if source_path:
        sp = Path(source_path)
        if sp.exists():
            source_text = sp.read_text(encoding="utf-8")
            source_len = max(1, len(source_text))
            ratio = output_chars / source_len
            if 0.8 <= ratio <= 3.5:
                score = 1.0
            elif ratio < 0.8:
                score = ratio / 0.8 * 0.8
            else:
                score = max(0, 1.0 - (ratio - 3.5) / 3.0)
            detail = f"{output_chars}/{source_len} chars (ratio={ratio:.2f})"
            return DimensionScore("Completeness", 0.20, min(1.0, score), detail=detail)

    # No source — use paragraph count as proxy
    if len(non_end) >= 10:
        return DimensionScore("Completeness", 0.20, 0.8, detail=f"{len(non_end)} paragraphs (no source)")
    return DimensionScore("Completeness", 0.20, max(0.1, len(non_end) / 10),
                          detail=f"Only {len(non_end)} paragraphs (no source)")


def score_cn_leak(data: dict) -> DimensionScore:
    """Count CJK characters in paragraphs. Zero tolerance."""
    texts, non_end, _ = get_texts(data)
    total_cn = 0
    cn_items = []

    for i, t in enumerate(texts):
        if t in ("(จบบท)", "(End)", "（終）", "(끝)"):
            continue
        chars = CN_RE.findall(t)
        if chars:
            total_cn += len(chars)
            cn_items.append((i, "".join(chars[:5])))

    if total_cn == 0:
        return DimensionScore("CN Leak", 0.15, 1.0, detail="0 CN chars — ✅ clean")

    detail_parts = [f"{total_cn} CN chars"]
    if cn_items:
        detail_parts.append(f"in {len(cn_items)} paragraphs")
        for i, cs in cn_items[:3]:
            detail_parts.append(f"  [{i}]: \"{cs}\"")

    detail = "; ".join(detail_parts)
    if total_cn <= 3:
        score = 0.3
    elif total_cn <= 10:
        score = 0.1
    else:
        score = 0.0

    return DimensionScore("CN Leak", 0.15, score, detail=detail, passed=total_cn == 0)


def score_en_leak(data: dict) -> DimensionScore:
    """Count blacklisted English words."""
    texts, non_end, _ = get_texts(data)
    found = []

    for i, t in enumerate(texts):
        if t in ("(จบบท)", "(End)", "（終）", "(끝)"):
            continue
        for m in re.finditer(r'\b([a-zA-Z]{3,})\b', t):
            word = m.group(1).lower()
            if word.upper() in ALLOWED_LATIN_TOKENS:
                continue
            if word in EN_BLACKLIST:
                found.append((i, word))

    if not found:
        return DimensionScore("EN Leak", 0.15, 1.0, detail="No EN blacklist words found")

    return DimensionScore("EN Leak", 0.15, 0.0,
                          detail=f"Found {len(found)} blacklisted EN words",
                          passed=False)


# ── Composite score ────────────────────────────────────────────────────

DIMENSIONS = [score_completeness, score_cn_leak, score_en_leak]


def score_chapter(data: dict, source_path: str | Path | None = None) -> tuple[float, list[DimensionScore]]:
    """Score a chapter across all dimensions. Returns (total_score, dimension_scores)."""
    dim_scores = []
    for scorer_fn in DIMENSIONS:
        if scorer_fn == score_completeness:
            ds = score_completeness(data, source_path)
        else:
            ds = scorer_fn(data)
        dim_scores.append(ds)

    total = sum(ds.weighted() for ds in dim_scores)
    return total, dim_scores
