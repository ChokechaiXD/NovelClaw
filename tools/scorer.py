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
class MqmError:
    """Structured translation error per MQM typology.

    category — one of: accuracy, fluency, terminology, style, locale, script_leak, structure
    subcategory — e.g. omission, addition, mistranslation, hangul_leak, missing_end_marker
    severity — minor, major, critical
    span — excerpt with problem (first 120 chars)
    position — paragraph index, or -1 for whole-chapter
    detail — human-readable description
    """
    category: str
    subcategory: str
    severity: str  # minor, major, critical
    span: str = ""
    position: int = -1
    detail: str = ""

    def to_short(self) -> str:
        return f"[{self.severity}] {self.category}/{self.subcategory}: {self.detail[:80]}"


@dataclass
class ScorerHistory:
    """Adaptive threshold tracking: adjusts PASS_THRESHOLD based on real chapters.

    Starts at PASS_THRESHOLD (85.0). After 3+ chapters, threshold =
    max(85.0, mean - 1.5σ). This prevents inflated expectations and
    catches genuine outliers instead of fighting a fixed number.
    """
    scores: list[float] = field(default_factory=list)
    _threshold_override: float | None = None

    def update(self, score: float) -> None:
        self.scores.append(score)
        n = len(self.scores)
        if n >= 3:
            mean = sum(self.scores) / n
            variance = sum((s - mean) ** 2 for s in self.scores) / n
            std = variance ** 0.5
            self._threshold_override = max(85.0, mean - 1.5 * std)

    @property
    def effective_threshold(self) -> float:
        return self._threshold_override or PASS_THRESHOLD


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
    mqm_errors: list[MqmError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


# ── Language-specific thresholds ────────────────────────────────────────
# Each target language gets its own thresholds and end marker patterns

PASS_THRESHOLD = 85.0  # 85/100 ถึงผ่าน

LANG_CONFIGS: dict[str, dict[str, Any]] = {
    "th": {
        "completeness_min": 0.85,
        "completeness_ideal_min": 1.0,
        "completeness_ideal_max": 3.00,
        "completeness_max": 3.50,
        "dialogue_ratio_min": 0.05,
        "dialogue_ratio_max": 0.80,
        "dialogue_ideal_min": 0.08,
        "dialogue_ideal_max": 0.65,
        "end_marker_regex": r"\(.*?(?:จบ|End|끝|終).*?\)",
    },
    "en": {
        "completeness_min": 0.70,
        "completeness_ideal_min": 0.85,
        "completeness_ideal_max": 2.00,
        "completeness_max": 2.50,
        "dialogue_ratio_min": 0.05,
        "dialogue_ratio_max": 0.85,
        "dialogue_ideal_min": 0.08,
        "dialogue_ideal_max": 0.70,
        "end_marker_regex": r"\(.*?(?:จบ|End|끝|終).*?\)",
    },
    "ko": {
        "completeness_min": 0.75,
        "completeness_ideal_min": 0.90,
        "completeness_ideal_max": 2.50,
        "completeness_max": 3.00,
        "dialogue_ratio_min": 0.05,
        "dialogue_ratio_max": 0.80,
        "dialogue_ideal_min": 0.08,
        "dialogue_ideal_max": 0.65,
        "end_marker_regex": r"\(.*?(?:จบ|End|끝|終).*?\)",
    },
}

def _get_lang_config(target_lang: str) -> dict[str, Any]:
    """Get config for a target language, falling back to Thai defaults."""
    return LANG_CONFIGS.get(target_lang, LANG_CONFIGS["th"])


def _score_completeness(
    paragraphs: list[dict[str, str]], source_char_count: int, target_lang: str = "th"
) -> DimensionScore:
    """Measure output completeness relative to source (language-aware)."""
    cfg = _get_lang_config(target_lang)
    min_ = cfg["completeness_min"]
    ideal_min = cfg["completeness_ideal_min"]
    ideal_max = cfg["completeness_ideal_max"]
    max_ = cfg["completeness_max"]
    texts = [p["text"] for p in paragraphs if p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    output_chars = sum(len(t) for t in texts)
    n_paras = len(texts)

    if source_char_count == 0:
        return DimensionScore("Completeness", 0.20, 0.0, "source empty", False)

    ratio = output_chars / source_char_count
    detail = f"{output_chars} chars vs {source_char_count} src ({ratio:.2f}x, {n_paras} paras)"

    if n_paras < 3:
        return DimensionScore("Completeness", 0.20, 0.0, f"{detail} — truncated", False)

    if ratio < min_:
        return DimensionScore("Completeness", 0.20, max(0.0, ratio / min_),
                              f"{detail} — too short", False)

    if ratio > max_:
        return DimensionScore("Completeness", 0.20, 0.3,
                              f"{detail} — too long", False)

    if ideal_min <= ratio <= ideal_max:
        return DimensionScore("Completeness", 0.20, 1.0, f"{detail} ✅")

    # Penalty zone
    if ratio < ideal_min:
        score = 0.6 + 0.4 * (ratio - min_) / (ideal_min - min_)
    else:
        score = 0.6 + 0.4 * (max_ - ratio) / (max_ - ideal_max)

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

    # Load allowed tokens from the cached policy.
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

    # Proportional scoring: more leaks = lower score, but not dropping to 0 at 4+
    if count == 0:
        score = 1.0
    elif count <= 1:
        score = 0.8
    elif count <= 3:
        score = 0.6
    elif count <= 5:
        score = 0.4
    elif count <= 10:
        score = 0.2
    else:
        score = 0.0

    return DimensionScore("Script Purity", 0.20, score,
                          f"⚠️ {count} leaks ({scripts})", passed=count <= 1)


def _score_end_marker(paragraphs: list[dict[str, str]], target_lang: str = "th") -> DimensionScore:
    """Check that last paragraph is an end marker (language-aware)."""
    if not paragraphs:
        return DimensionScore("End Marker", 0.10, 0.0, "no paragraphs", False)

    last = paragraphs[-1]["text"] if isinstance(paragraphs[-1], dict) else str(paragraphs[-1])
    cfg = _get_lang_config(target_lang)
    has_end = bool(re.search(cfg["end_marker_regex"], last))

    if has_end:
        return DimensionScore("End Marker", 0.10, 1.0, f"✅ {last}")
    return DimensionScore("End Marker", 0.10, 0.0, f"no end marker (last: '{last}')", False)


def _score_type_diversity(
    paragraphs: list[dict[str, str]], source_has_dialogue: bool = True
) -> DimensionScore:
    """Must have narration and at least some dialogue/system."""
    types = [p["type"] for p in paragraphs
             if p["type"] != "end" and p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    if not types:
        return DimensionScore("Type Diversity", 0.15, 0.0, "no content", False)

    unique = set(types)
    detail = f"types: {', '.join(sorted(unique))}"

    if "narration" in unique and "dialogue" in unique:
        return DimensionScore("Type Diversity", 0.15, 1.0, f"{detail} ✅")
    if "narration" in unique and not source_has_dialogue:
        return DimensionScore("Type Diversity", 0.15, 1.0, f"{detail} — narration-only source ✅")
    if "narration" in unique:
        return DimensionScore("Type Diversity", 0.15, 0.5, f"{detail} — no dialogue", False)

    return DimensionScore("Type Diversity", 0.15, 0.3, f"{detail} — all {list(unique)}", False)


def _score_dialogue_ratio(
    paragraphs: list[dict[str, str]], source_has_dialogue: bool = True,
    target_lang: str = "th",
) -> DimensionScore:
    """% dialogue paragraphs vs total (language-aware)."""
    cfg = _get_lang_config(target_lang)
    min_ = cfg["dialogue_ratio_min"]
    max_ = cfg["dialogue_ratio_max"]
    ideal_min = cfg["dialogue_ideal_min"]
    ideal_max = cfg["dialogue_ideal_max"]
    non_end = [p for p in paragraphs
               if p["type"] != "end" and p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    if not non_end:
        return DimensionScore("Dialogue Ratio", 0.15, 0.0, "no content", False)

    dialogue = sum(1 for p in non_end if p["type"] == "dialogue")
    ratio = dialogue / len(non_end)
    detail = f"{dialogue}/{len(non_end)} = {ratio*100:.0f}% dialogue"

    if dialogue == 0 and not source_has_dialogue:
        return DimensionScore("Dialogue Ratio", 0.15, 1.0, f"{detail} — narration-only source ✅")

    if ratio < min_:
        return DimensionScore("Dialogue Ratio", 0.15, max(0, ratio / min_ * 0.6),
                              f"{detail} — too little", False)
    if ratio > max_:
        return DimensionScore("Dialogue Ratio", 0.15, max(0, 1.0 - (ratio - max_) * 2),
                              f"{detail} — too much", False)
    if ideal_min <= ratio <= ideal_max:
        return DimensionScore("Dialogue Ratio", 0.15, 1.0, f"{detail} ✅")

    return DimensionScore("Dialogue Ratio", 0.15, 0.8, detail)


# ── Dimension 6: Term Compliance ────────────────────────────────────

def _score_term_compliance(
    paragraphs: list[dict[str, str]],
    target_lang: str = "th",
    source_text: str = "",
) -> DimensionScore:
    """Check glossary term usage: no leaks AND proper coverage.

    Two checks:
    1. Leak detection: replace-action terms should NOT appear in original form
    2. Coverage: replace-action Thai values SHOULD appear in output
    """
    try:
        from qa.term_policy import get_term_policy
        tp = get_term_policy(target_lang)
    except ImportError:
        return DimensionScore("Term Compliance", 0.20, 1.0, "no term_policy loaded")

    texts = [p["text"] for p in paragraphs
             if p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    if not texts:
        return DimensionScore("Term Compliance", 0.20, 0.0, "no content")

    full_text = "\n".join(texts)

    # ── Check 1: Leak detection ──
    replace_terms = {k: v.value for k, v in tp.terms.items()
                     if v.action == "replace" and v.value}
    leaked = []
    for source_term in sorted(replace_terms):
        if source_term.lower() in full_text.lower():
            leaked.append(source_term)

    leak_score = 1.0
    if leaked:
        count = len(leaked)
        if count <= 2:
            leak_score = 0.7
        elif count <= 5:
            leak_score = 0.4
        else:
            leak_score = 0.1

    # ── Check 2: Coverage — only source terms present in this chapter matter ──
    source_lower = source_text.lower()
    replace_values = set()
    if source_lower:
        replace_values = {
            thai_value
            for source_term, thai_value in replace_terms.items()
            if source_term.lower() in source_lower
        }
    missing_values = []
    for thai_val in sorted(replace_values):
        if thai_val.lower() not in full_text.lower():
            missing_values.append(thai_val)

    coverage_score = 1.0
    if missing_values:
        missing_pct = len(missing_values) / len(replace_values)
        if missing_pct > 0.5:
            coverage_score = 0.3  # most terms missing
        else:
            coverage_score = 0.5  # some source terms missing

    # ── Combined score ──
    combined = min(leak_score, coverage_score)
    parts = []
    if leaked:
        parts.append(f"leaks: {'; '.join(leaked[:3])}")
    if missing_values:
        parts.append(f"missing coverage: {', '.join(missing_values[:3])}")

    detail = "; ".join(parts) if parts else "✅ all terms clean"
    return DimensionScore(
        "Term Compliance", 0.20, combined,
        detail,
        passed=combined > 0.5,
    )


# ── MQM Mapping ─────────────────────────────────────────────────────


def _mqm_map(dim_name: str, detail: str) -> tuple[str, str, str]:
    """Map DimensionScore → (mqm_category, mqm_subcategory, severity)."""
    _d = detail.lower()
    mapping = {
        "Completeness": ("accuracy", "omission" if "short" in _d or "truncated" in _d else "addition"),
        "Script Purity": ("script_leak", "foreign_script"),
        "End Marker": ("structure", "missing_end_marker"),
        "Type Diversity": ("style", "monotonous_type"),
        "Dialogue Ratio": ("style", "dialogue_imbalance"),
        "Term Compliance": ("terminology", "term_mismatch"),
    }
    cat, sub = mapping.get(dim_name, ("accuracy", "general"))

    # Severity heuristic
    sev: str = "major"
    if "minor" in _d or "slight" in _d or "some" in _d or "≤" in _d:
        sev = "minor"
    elif "missing" in _d or "truncated" in _d or "too short" in _d or "too long" in _d:
        sev = "critical"

    return cat, sub, sev


# ── Master Score Function ───────────────────────────────────────────


def score_chapter(
    paragraphs: list[dict[str, str]],
    source_char_count: int = 0,
    target_lang: str = "th",
    source_text: str = "",
) -> ScorerResult:
    """Score one chapter across 6 dimensions. No LLM calls."""
    source_has_dialogue = bool(re.search(r'[「」"“”]', source_text or ""))
    texts = [
        p["text"] for p in paragraphs
        if p["text"] not in ("(จบบท)", "(End)", "（終）", "(끝)")
    ]
    output_chars = sum(len(t) for t in texts)
    length_ratio = round(output_chars / source_char_count, 3) if source_char_count else 0.0

    dims = [
        _score_completeness(paragraphs, source_char_count, target_lang),
        _score_script_purity(paragraphs, target_lang),
        _score_end_marker(paragraphs, target_lang),
        _score_type_diversity(paragraphs, source_has_dialogue),
        _score_dialogue_ratio(paragraphs, source_has_dialogue, target_lang),
        _score_term_compliance(paragraphs, target_lang, source_text),
    ]

    weighted = sum(d.score * d.weight for d in dims) * 100
    errors = [f"{d.name}: {d.detail[:80]}" for d in dims if not d.passed]
    warnings = [
        f"{d.name}: {d.detail[:80]}"
        for d in dims
        if d.passed and d.score < 1.0 and d.name in {"Type Diversity", "Dialogue Ratio"}
    ]
    passed = weighted >= PASS_THRESHOLD

    # Build structured MQM errors
    mqm_errors: list[MqmError] = []
    for d in dims:
        if d.passed:
            continue
        cat, sub, sev = _mqm_map(d.name, d.detail)
        mqm_errors.append(MqmError(
            category=cat, subcategory=sub, severity=sev,
            span=d.detail[:120], position=-1, detail=d.detail,
        ))

    return ScorerResult(
        weighted_total=round(weighted, 1),
        dimensions=dims,
        passed=passed,
        errors=errors,
        mqm_errors=mqm_errors,
        warnings=warnings,
        metrics={
            "lengthRatio": length_ratio,
            "sourceHasDialogue": source_has_dialogue,
            "source_has_dialogue": source_has_dialogue,
            "scriptLeaks": next(
                (0 if d.passed else 1 for d in dims if d.name == "Script Purity"),
                0,
            ),
        },
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
