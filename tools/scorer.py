#!/usr/bin/env python3
"""
scorer.py — Objective chapter translation quality scorer.

Scores a translated chapter JSON across 8 measurable dimensions.
No LLM calls — purely derived from the JSON structure and source comparison.
Designed to be used as a quality gate BEFORE and AFTER translation changes.

Usage:
    python tools/scorer.py chapters/0002.json --source source/0002.md
    python tools/scorer.py chapters/0002.json --source source/0002.md --verbose
    python tools/scorer.py chapters/ --source source/  (batch mode)

Score dimensions:

| # | Dimension | Weight | What it measures | Threshold |
|:-:|-----------|:------:|------------------|:---------:|
| 1 | Completeness | 20% | Output chars / source chars ratio | 0.8x–3.5x |
| 2 | CN Leak | 15% | CJK chars in narration/dialogue | 0 tolerance |
| 3 | EN Leak | 15% | English words not in allowed list | ≤ 2 allowed |
| 4 | End Marker | 10% | type=end as last block | MUST have |
| 5 | Speaker Attribution | 10% | % dialogue blocks with speaker | ≥ 20% |
| 6 | Dialogue Ratio | 10% | Dialogue blocks / total blocks | 10%–60% |
| 7 | Block Diversity | 10% | Must have narration + dialogue | ≥ 2 types |
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


# ── Config ────────────────────────────────────────────────────────────

# English words that are NOT allowed in translated output
# (gamified game terms like HP/MP/EXP are OK — tracked separately)
EN_BLACKLIST: set[str] = {
    # From validation.py EN_RETENTION_RE — words that leak from CN source
    "recruiting", "level", "disrespect", "mean", "queen",
    "erupt", "continue", "panic", "momentarily", "hollow",
    "militia", "avatar", "blacklist", "peek",
    # Additional words found in audit (70 chapters)
    "first", "kill", "plants", "zombies",
    "recruit", "loot", "skill", "quest", "boss",
    "dungeon", "party", "guild", "raid", "tank", "healer",
    "damage", "defense", "attack", "speed",
    "inventory", "equip", "item", "craft",
    "summon", "portal", "shield", "weapon", "armor",
    "pet", "mount", "crystal", "stone", "potion",
    "common", "uncommon", "rare", "epic", "legendary",
    "hybrid", "ancient", "elite", "melee", "ranged",
}

# Allowed English tokens (game UI usually kept as-is)
ALLOWED_LATIN_TOKENS: set[str] = {
    "HP", "MP", "EXP", "SSS", "SSR", "UR", "SP", "ID", "VIP",
    "S", "SS", "LR", "CD", "NPC", "PVP", "PVE",
    "LV", "LVL", "ATK", "DEF", "DMG", "BUFF", "DEBUFF",
    "AOE", "DPS", "TPS",
}

# Completeness ratio range (output / source chars)
COMPLETENESS_MIN = 0.80
COMPLETENESS_MAX = 3.50
COMPLETENESS_IDEAL_MIN = 1.00
COMPLETENESS_IDEAL_MAX = 3.00

# Dialogue ratio range
DIALOGUE_RATIO_MIN = 0.10  # 10%
DIALOGUE_RATIO_MAX = 0.60  # 60%
DIALOGUE_RATIO_IDEAL_MIN = 0.15
DIALOGUE_RATIO_IDEAL_MAX = 0.45

# Minimum blocks to be considered "translated" (not just metadata)
MIN_BLOCKS = 5

# Speaker attribution target
SPEAKER_TARGET = 0.20  # 20% of dialogue blocks should have speaker

# CJK regex
CN_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')


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
        
        # Sort: worst first
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
    blocks = data.get("blocks", [])
    output_chars = sum(len(b.get("text", "")) for b in blocks if b.get("type") != "end")
    
    if source_char_count == 0:
        return DimensionScore("Completeness", 0.20, 0.0,
                              detail="Source empty", passed=False)
    
    ratio = output_chars / source_char_count
    block_count = len(blocks)
    
    detail = f"output={output_chars} chars, source={source_char_count} chars, ratio={ratio:.2f}x, blocks={block_count}"
    
    # Penalize severely if output is tiny relative to source (truncation)
    if block_count < MIN_BLOCKS:
        return DimensionScore("Completeness", 0.20, 0.0,
                              detail=f"{detail} — TRUNCATED ({block_count} blocks)", passed=False)
    
    if ratio < COMPLETENESS_MIN:
        pct = max(0.0, ratio / COMPLETENESS_MIN)
        return DimensionScore("Completeness", 0.20, pct,
                              detail=f"{detail} — too short (< {COMPLETENESS_MIN}x)", passed=False)
    
    if ratio > COMPLETENESS_MAX:
        return DimensionScore("Completeness", 0.20, 0.3,
                              detail=f"{detail} — too long (> {COMPLETENESS_MAX}x)", passed=False)
    
    # Within range — score 1.0 if in ideal range, scaling down at edges
    if COMPLETENESS_IDEAL_MIN <= ratio <= COMPLETENESS_IDEAL_MAX:
        score = 1.0
    elif ratio < COMPLETENESS_IDEAL_MIN:
        score = 0.5 + 0.5 * (ratio - COMPLETENESS_MIN) / (COMPLETENESS_IDEAL_MIN - COMPLETENESS_MIN)
    else:
        score = 0.5 + 0.5 * (COMPLETENESS_MAX - ratio) / (COMPLETENESS_MAX - COMPLETENESS_IDEAL_MAX)
    
    return DimensionScore("Completeness", 0.20, score, detail=detail)


def _score_cn_leak(data: dict) -> DimensionScore:
    """Count CJK characters in narration/dialogue blocks. Zero tolerance."""
    blocks = data.get("blocks", [])
    total_cn = 0
    cn_blocks = []
    
    for i, b in enumerate(blocks):
        btype = b.get("type", "")
        if btype in ("narration", "dialogue"):
            chars = CN_RE.findall(b.get("text", ""))
            if chars:
                total_cn += len(chars)
                cn_blocks.append((i, btype, "".join(chars[:5])))
    
    detail_parts = [f"{total_cn} CN chars"]
    if cn_blocks:
        detail_parts.append(f"in {len(cn_blocks)} blocks")
        # Show first 3
        for i, bt, cs in cn_blocks[:3]:
            detail_parts.append(f"  [{i}]{bt}: \"{cs}\"")
    
    detail = "; ".join(detail_parts) if detail_parts else "clean"
    
    if total_cn == 0:
        return DimensionScore("CN Leak", 0.15, 1.0, detail="0 CN chars — ✅ clean")
    
    # Zero tolerance: any CN chars → proportional penalty
    # 1-3 chars: 0.3, 4-10: 0.1, 10+: 0
    if total_cn <= 3:
        score = 0.3
    elif total_cn <= 10:
        score = 0.1
    else:
        score = 0.0
    
    return DimensionScore("CN Leak", 0.15, score,
                          detail=detail, passed=total_cn == 0)


def _score_en_leak(data: dict) -> DimensionScore:
    """Count blacklisted English words. Game UI tokens (HP/MP) are OK."""
    blocks = data.get("blocks", [])
    found = []
    
    for i, b in enumerate(blocks):
        btype = b.get("type", "")
        if btype == "end":
            continue
        text = b.get("text", "")
        # Find lowercase words (after filtering out allowed tokens)
        for m in re.finditer(r'\b([a-zA-Z]{3,})\b', text):
            word = m.group(1).lower()
            if word.upper() in ALLOWED_LATIN_TOKENS:
                continue  # Allowed game UI token
            if word in EN_BLACKLIST:
                found.append((i, btype, word))
    
    # Deduplicate by word
    unique_words = set(w for _, _, w in found)
    detail_parts = [f"{len(found)} EN words ({len(unique_words)} unique)"]
    # List most common
    word_counts = Counter(w for _, _, w in found)
    for word, n in word_counts.most_common(5):
        detail_parts.append(f"  \"{word}\" ×{n}")
    
    detail = "; ".join(detail_parts)
    
    if not found:
        return DimensionScore("EN Leak", 0.15, 1.0, detail="0 EN blacklist words — ✅ clean")
    
    # Score based on count
    n = len(found)
    if n == 0:
        score = 1.0
    elif n <= 2:
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
    """Check last block is type=end with correct marker."""
    blocks = data.get("blocks", [])
    if not blocks:
        return DimensionScore("End Marker", 0.10, 0.0,
                              detail="No blocks at all", passed=False)
    
    last = blocks[-1]
    if last.get("type") != "end":
        return DimensionScore("End Marker", 0.10, 0.0,
                              detail=f"Last block type={last.get('type')}, not 'end'",
                              passed=False)
    
    text = last.get("text", "")
    # Check it contains a known end marker pattern
    has_end_pattern = bool(re.search(r'[\(（\[【][\u0e00-\u0e7fจบบทจบEnd끝終]+[\)）\]】]', text))
    
    if has_end_pattern:
        return DimensionScore("End Marker", 0.10, 1.0,
                              detail=f"✅ end marker: \"{text}\"")
    else:
        return DimensionScore("End Marker", 0.10, 0.5,
                              detail=f"type=end but text \"{text}\" doesn't match known markers",
                              passed=False)


def _score_speaker(data: dict) -> DimensionScore:
    """Check dialogue blocks have speaker attribution."""
    blocks = data.get("blocks", [])
    dialogues = [b for b in blocks if b.get("type") == "dialogue"]
    
    if not dialogues:
        return DimensionScore("Speaker", 0.10, 0.0,
                              detail="No dialogue blocks — possible truncation",
                              passed=False)
    
    with_speaker = sum(1 for b in dialogues if b.get("speaker"))
    total = len(dialogues)
    ratio = with_speaker / total if total > 0 else 0
    
    detail = f"{with_speaker}/{total} dialogues have speaker ({ratio*100:.0f}%)"
    
    if ratio >= SPEAKER_TARGET:
        return DimensionScore("Speaker", 0.10, 1.0, detail=f"✅ {detail}")
    
    # Score proportionally
    score = ratio / SPEAKER_TARGET
    return DimensionScore("Speaker", 0.10, min(score, 1.0),
                          detail=detail, passed=ratio >= SPEAKER_TARGET)


def _score_dialogue_ratio(data: dict) -> DimensionScore:
    """Dialogue should be 10-60% of total blocks."""
    blocks = data.get("blocks", [])
    non_end = [b for b in blocks if b.get("type") != "end"]
    if not non_end:
        return DimensionScore("Dialogue Ratio", 0.10, 0.0,
                              detail="Only end marker exists", passed=False)
    
    dialogue = sum(1 for b in non_end if b.get("type") == "dialogue")
    total = len(non_end)
    ratio = dialogue / total if total > 0 else 0
    
    detail = f"{dialogue}/{total} blocks = {ratio*100:.0f}% dialogue"
    
    if ratio < DIALOGUE_RATIO_MIN:
        score = ratio / DIALOGUE_RATIO_MIN * 0.5
        return DimensionScore("Dialogue Ratio", 0.10, score,
                              detail=f"{detail} — too little dialogue", passed=False)
    
    if ratio > DIALOGUE_RATIO_MAX:
        score = max(0, 1.0 - (ratio - DIALOGUE_RATIO_MAX) * 2)
        return DimensionScore("Dialogue Ratio", 0.10, score,
                              detail=f"{detail} — too much dialogue", passed=False)
    
    # In range — score higher if closer to ideal
    if DIALOGUE_RATIO_IDEAL_MIN <= ratio <= DIALOGUE_RATIO_IDEAL_MAX:
        return DimensionScore("Dialogue Ratio", 0.10, 1.0, detail=f"✅ {detail}")
    
    # In acceptable range but not ideal
    score = 0.7
    return DimensionScore("Dialogue Ratio", 0.10, score, detail=detail)


def _score_block_diversity(data: dict) -> DimensionScore:
    """Must have at least narration AND dialogue."""
    blocks = data.get("blocks", [])
    non_end = [b for b in blocks if b.get("type") != "end"]
    types = set(b.get("type") for b in non_end)
    
    has_narration = "narration" in types
    has_dialogue = "dialogue" in types
    has_system = "system" in types
    total_types = len(types)
    
    detail_parts = [f"{total_types} block types: {', '.join(sorted(types))}"]
    
    if not has_narration and not has_dialogue:
        return DimensionScore("Block Diversity", 0.10, 0.0,
                              detail="; ".join(detail_parts) + " — no narration or dialogue",
                              passed=False)
    
    if not has_dialogue:
        return DimensionScore("Block Diversity", 0.10, 0.0,
                              detail="; ".join(detail_parts) + " — no dialogue",
                              passed=False)
    
    if not has_narration:
        return DimensionScore("Block Diversity", 0.10, 0.3,
                              detail="; ".join(detail_parts) + " — no narration, only dialogue",
                              passed=False)
    
    # Base pass with bonus for variety
    base_score = 0.7
    if has_narration and has_dialogue and has_system:
        base_score = 1.0
    
    return DimensionScore("Block Diversity", 0.10, base_score,
                          detail="; ".join(detail_parts))


def _score_schema(data: dict) -> DimensionScore:
    """Check structural integrity."""
    issues = []
    
    # Title
    title = data.get("title", "")
    if not title:
        issues.append("missing title")
    elif not re.match(r'^ตอนที่ \d+', title):
        issues.append(f"bad title format: \"{title[:40]}\"")
    
    # Num
    num = data.get("num")
    if num is None:
        issues.append("missing num")
    
    # Lang
    lang = data.get("lang")
    if not lang:
        issues.append("missing lang")
    elif lang != "cn":
        issues.append(f"lang={lang} (expected cn)")
    
    # Output lang
    out_lang = data.get("output_lang")
    if not out_lang:
        issues.append("missing output_lang")
    elif out_lang != "th":
        issues.append(f"output_lang={out_lang} (expected th)")
    
    # Blocks
    if not data.get("blocks"):
        issues.append("empty blocks")
    
    detail = "; ".join(issues) if issues else "✅ all fields correct"
    score = 0.0 if issues else 1.0
    passed = len(issues) == 0
    
    return DimensionScore("Schema", 0.10, score, detail=detail, passed=passed)


# ── Main scorer ───────────────────────────────────────────────────────


def score_chapter(data: dict, source_text: str | None = None,
                  verbose: bool = False) -> ScorerResult:
    """Score one translated chapter across 8 dimensions.

    Args:
        data: Parsed chapter JSON dict
        source_text: Original CN source text (for completeness check)
        verbose: Include detail in report

    Returns:
        ScorerResult with per-dimension scores + composite
    """
    ch_num = data.get("num", 0)
    source_char_count = len(source_text) if source_text else 0
    
    # Score each dimension
    dims = [
        _score_completeness(data, source_char_count),
        _score_cn_leak(data),
        _score_en_leak(data),
        _score_end_marker(data),
        _score_speaker(data),
        _score_dialogue_ratio(data),
        _score_block_diversity(data),
        _score_schema(data),
    ]
    
    # Weighted composite
    weighted = sum(d.score * d.weight for d in dims) * 100  # scale to 0-100
    passed = weighted >= 70 and all(
        d.passed or d.weight <= 0.10  # low-weight fails OK if overall high
        for d in dims
    )
    
    # Collect errors for display
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
                # Derive source filename from JSON stem
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
    
    # Batch mode: directory
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
                    {
                        "ch": r.chapter_num,
                        "score": r.weighted_total,
                        "passed": r.passed,
                        "errors": r.errors,
                    }
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
            
            # Worst offenders by score
            print("─── Worst 5 ───")
            for r in sorted(results, key=lambda x: x.weighted_total)[:5]:
                print(f"  ch{r.chapter_num:>4d}: {r.weighted_total:.0f}/100  {'PASS' if r.passed else 'FAIL'}")
            
            print("")
            print(f"─── Dimension averages ───")
            dim_names = [d.name for d in results[0].dimensions]
            for name in dim_names:
                avg_d = sum(
                    d.score for r in results for d in r.dimensions if d.name == name
                ) / len(results)
                bar = "█" * int(avg_d * 10) + "░" * (10 - int(avg_d * 10))
                print(f"  {bar}  {name:20s}  {avg_d*100:.0f}/100")


if __name__ == "__main__":
    main()
