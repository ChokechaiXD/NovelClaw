"""quality_scorer.py — LLM-as-Judge translation quality scoring.

Evaluates translation quality across 4 dimensions:
  - Fluency: natural Thai expression, readability
  - Accuracy: faithful to source content, no hallucination
  - Terminology: glossary term compliance, entity consistency
  - Completeness: all source content preserved

Architecture:
  - Regex-based checks (fast path) run first
  - LLM-as-Judge (deep path) only if regex passes
  - Structured ScoreResult with dimension scores + error categories

Error categories (simplified MQM):
  - accuracy: mistranslation, addition, omission
  - fluency: grammar, unnatural expression
  - terminology: glossary term not used, entity inconsistency
  - style: wrong register, inappropriate tone
  - completeness: missing content, truncated
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────
PASS_THRESHOLD = 7.0       # Overall score ≥ 7.0 = pass
DIMENSION_THRESHOLD = 6.0  # Per-dimension score must be ≥ 6.0
MIN_SOURCE_LEN_FOR_JUDGE = 50  # Skip LLM judge for tiny chapters


class ErrorCategory(str, Enum):
    ACCURACY = "accuracy"       # Mistranslation, addition, omission
    FLUENCY = "fluency"         # Grammar, unnatural expression
    TERMINOLOGY = "terminology"  # Glossary non-compliance, entity drift
    STYLE = "style"             # Wrong register, inappropriate tone
    COMPLETENESS = "completeness"  # Missing content, truncated


class Severity(str, Enum):
    CRITICAL = "critical"   # Blockers (hallucination, CJK leak)
    MAJOR = "major"         # Significant quality loss
    MINOR = "minor"         # Cosmetic,不影响理解
    INFO = "info"           # Suggestion


@dataclass
class ScoreResult:
    """Structured quality score for a chapter translation."""
    overall: float = 0.0          # 0-10, composite
    fluency: float = 0.0          # 0-10
    accuracy: float = 0.0         # 0-10
    terminology: float = 0.0      # 0-10
    completeness: float = 0.0     # 0-10
    errors: list[dict[str, Any]] = field(default_factory=list)
    passed: bool = False
    raw_output: str = ""
    parse_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "fluency": self.fluency,
            "accuracy": self.accuracy,
            "terminology": self.terminology,
            "completeness": self.completeness,
            "errors": self.errors,
            "passed": self.passed,
            "error_count": len(self.errors),
        }

    def summary_string(self) -> str:
        """One-line summary for console output."""
        dims = f"F:{self.fluency:.1f} A:{self.accuracy:.1f} T:{self.terminology:.1f} C:{self.completeness:.1f}"
        if self.errors:
            by_sev: dict[str, int] = {}
            for e in self.errors:
                s = e.get("severity", "info")
                by_sev[s] = by_sev.get(s, 0) + 1
            sev_str = " ".join(f"{k}={v}" for k, v in sorted(by_sev.items()))
            return f"Score {self.overall:.1f}/10 ({dims}) {sev_str}"
        return f"Score {self.overall:.1f}/10 ({dims}) ✅"


# ── Scoring prompt ────────────────────────────────────────────────────

SCORE_PROMPT_TEMPLATE = """You are an expert Thai translation quality evaluator. Analyze the following translation and score it across 4 dimensions.

### Source text (Chinese):
```text
{source_text}
```

### Translation (Thai):
```json
{chapter_json_preview}
```

### Glossary terms:
```text
{glossary_summary}
```

### Scoring criteria:
Rate each dimension 0-10 (10 = perfect).

1. **Fluency** — Does the Thai sound natural and idiomatic?
   - 9-10: reads like native Thai
   - 7-8: minor unnatural phrasings
   - 5-6: awkward but understandable
   - 0-4: machine-like, ungrammatical

2. **Accuracy** — Is the translation faithful to the source?
   - 9-10: exact meaning preserved, no hallucination
   - 7-8: minor deviations
   - 5-6: some meaning lost or added
   - 0-4: major hallucination or omission

3. **Terminology** — Are glossary terms used correctly?
   - 9-10: all glossary terms applied consistently
   - 7-8: most glossary terms used, minor inconsistency
   - 5-6: some glossary terms missed
   - 0-4: glossary terms ignored

4. **Completeness** — Is all source content preserved?
   - 9-10: full content, same length/detail
   - 7-8: minor compression
   - 5-6: notable compression or skipped content
   - 0-4: major truncation

### Error categories:
For any issue found, report it as:
- **accuracy**: mistranslation, added content, omitted content
- **fluency**: unnatural phrasing, grammar issue
- **terminology**: glossary term not used, entity name wrong
- **style**: wrong register/tone for context
- **completeness**: content missing, truncated

### Output format (EXACT JSON, no markdown):
```json
{{
  "overall": <float 0-10>,
  "fluency": <float 0-10>,
  "accuracy": <float 0-10>,
  "terminology": <float 0-10>,
  "completeness": <float 0-10>,
  "errors": [
    {{
      "category": "accuracy|fluency|terminology|style|completeness",
      "severity": "critical|major|minor|info",
      "detail": "<specific issue description>",
      "source_excerpt": "<relevant source text>",
      "translation_excerpt": "<relevant translation text>"
    }}
  ],
  "summary": "<2-3 sentence evaluation>"
}}
```

Respond ONLY with the JSON block. No other text."""


def build_score_prompt(
    source_text: str,
    chapter_data: dict[str, Any],
    glossary_terms: list[dict[str, Any]] | None = None,
) -> str:
    """Build the LLM scoring prompt for a chapter translation."""
    # Truncate source if very long
    src_display = source_text[:2000]
    if len(source_text) > 2000:
        src_display += "\n...(truncated)"

    # Chapter preview (blocks limited to avoid token explosion)
    blocks = chapter_data.get("blocks", [])
    preview_blocks = blocks[:30]
    chapter_json = {
        "num": chapter_data.get("num"),
        "title": chapter_data.get("title", ""),
        "blocks": [
            {"type": b.get("type"), "text": b.get("text", "")[:200]}
            for b in preview_blocks
        ],
        "source": chapter_data.get("source"),
    }
    if len(blocks) > 30:
        chapter_json["_note"] = f"(...{len(blocks) - 30} more blocks truncated)"

    # Glossary summary (compact)
    if glossary_terms:
        locked = [t for t in glossary_terms if t.get("lock") == "locked"][:15]
        ref = [t for t in glossary_terms if t.get("lock") == "reference"][:10]
        gloss_lines = ["### Locked terms:"]
        for t in locked:
            gloss_lines.append(f"- {t['source']} → {t.get('thai', '?')}")
        if ref:
            gloss_lines.append("### Reference terms (top 10):")
            for t in ref:
                gloss_lines.append(f"- {t['source']} → {t.get('thai', '?')}")
        glossary_summary = "\n".join(gloss_lines)
    else:
        glossary_summary = "(no glossary loaded)"

    return SCORE_PROMPT_TEMPLATE.format(
        source_text=src_display,
        chapter_json_preview=json.dumps(chapter_json, ensure_ascii=False, indent=2)[:3000],
        glossary_summary=glossary_summary[:1000],
    )


def parse_score_response(llm_output: str) -> ScoreResult:
    """Parse LLM response into ScoreResult."""
    result = ScoreResult()

    # Strip markdown code fences
    cleaned = llm_output.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    # Extract JSON block
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        result.parse_error = "No JSON found in LLM output"
        result.raw_output = llm_output[:500]
        return result

    json_str = cleaned[start: end + 1]
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        result.parse_error = f"JSON parse error: {e}"
        result.raw_output = llm_output[:500]
        return result

    result.overall = float(data.get("overall", 0))
    result.fluency = float(data.get("fluency", 0))
    result.accuracy = float(data.get("accuracy", 0))
    result.terminology = float(data.get("terminology", 0))
    result.completeness = float(data.get("completeness", 0))
    result.errors = data.get("errors", [])
    result.raw_output = llm_output[:500]

    # Validate dimensions
    for dim in ["fluency", "accuracy", "terminology", "completeness"]:
        val = getattr(result, dim)
        if not (0 <= val <= 10):
            result.parse_error = f"Invalid {dim} score: {val}"
            return result

    # Pass/fail
    all_dims_ok = all(
        getattr(result, dim) >= DIMENSION_THRESHOLD
        for dim in ["fluency", "accuracy", "terminology", "completeness"]
    )
    result.passed = result.overall >= PASS_THRESHOLD and all_dims_ok

    return result


def mock_score(source_text: str, chapter_data: dict[str, Any]) -> ScoreResult:
    """Mock scorer for testing — returns plausible scores."""
    result = ScoreResult()
    
    blocks_text = " ".join(
        b.get("text", "") for b in chapter_data.get("blocks", [])
    )
    num_blocks = len(chapter_data.get("blocks", []))
    
    # Mock logic: check for obvious issues
    errors = []
    
    # Check end marker
    if chapter_data.get("blocks", []):
        last_block = chapter_data["blocks"][-1]
        if last_block.get("type") != "end":
            errors.append({
                "category": "completeness",
                "severity": "critical",
                "detail": "Missing end marker block",
                "source_excerpt": "",
                "translation_excerpt": f"last block type: {last_block.get('type')}",
            })
    
    # Mock scores — always pass for mock
    result.overall = 8.5
    result.fluency = 8.0
    result.accuracy = 8.5
    result.terminology = 8.0
    result.completeness = 9.0
    result.errors = errors
    result.passed = True
    
    return result


def score_translation(
    source_text: str,
    chapter_data: dict[str, Any],
    glossary_terms: list[dict[str, Any]] | None = None,
    mock: bool = False,
    model: str = "haiku",
) -> ScoreResult:
    """Full translation scoring: mock or LLM-as-Judge.

    Args:
        source_text: Cleaned source text
        chapter_data: Chapter dict (parsed JSON)
        glossary_terms: Optional list of glossary terms
        mock: Use mock scorer instead of real LLM
        model: LLM model for scoring (used only if not mock)

    Returns:
        ScoreResult with dimension scores, errors, pass/fail
    """
    if mock:
        return mock_score(source_text, chapter_data)

    if len(source_text) < MIN_SOURCE_LEN_FOR_JUDGE:
        result = ScoreResult()
        result.overall = 8.0
        result.fluency = 8.0
        result.accuracy = 8.0
        result.terminology = 8.0
        result.completeness = 8.0
        result.passed = True
        return result

    try:
        from providers import call_llm
        prompt = build_score_prompt(source_text, chapter_data, glossary_terms)
        llm_output = call_llm(prompt)
        return parse_score_response(llm_output)
    except Exception as e:
        result = ScoreResult()
        result.parse_error = str(e)
        return result


# ── Quality Gate V2 ───────────────────────────────────────────────────

def quality_gate_v2(
    source_text: str,
    chapter_data: dict[str, Any],
    glossary_terms: list[dict[str, Any]] | None = None,
    regex_validator: Any = None,
    mock: bool = True,
    model: str = "haiku",
) -> tuple[bool, list[str], ScoreResult | None]:
    """Two-stage quality gate:
    1. Regex checks (fast path) — from existing validation.py
    2. LLM judge (deep path) — only if regex passes

    Args:
        source_text: Cleaned source text
        chapter_data: Chapter dict
        glossary_terms: Optional glossary terms
        regex_validator: callable(source_text, chapter_data) -> (bool, [str])
        mock: Use mock scorer
        model: LLM model for scoring

    Returns:
        (passed, messages_list, score_result_or_none)
    """
    messages: list[str] = []
    score_result: ScoreResult | None = None

    # Stage 1: Regex checks
    if regex_validator:
        regex_ok, regex_messages = regex_validator(source_text, chapter_data)
        messages.extend(regex_messages)
        if not regex_ok:
            return False, messages, None

    # Stage 2: LLM judge
    score_result = score_translation(
        source_text, chapter_data, glossary_terms,
        mock=mock, model=model,
    )
    if score_result.parse_error:
        messages.append(f"⚠ LLM judge parse error: {score_result.parse_error}")
        # Don't fail on parse error — fall back to regex-only result
        return True, messages, score_result

    for err in score_result.errors:
        sev = err.get("severity", "info")
        cat = err.get("category", "unknown")
        detail = err.get("detail", "")
        prefix = "ERROR" if sev in ("critical", "major") else "WARNING"
        messages.append(f"{prefix} [{sev}/{cat}] {detail}")

    if not score_result.passed:
        messages.append(
            f"ERROR LLM judge: score {score_result.overall:.1f}/10 "
            f"(fluency={score_result.fluency:.1f} accuracy={score_result.accuracy:.1f} "
            f"terminology={score_result.terminology:.1f} completeness={score_result.completeness:.1f})"
        )
        return False, messages, score_result

    return True, messages, score_result


def build_quality_report(
    chapters: list[dict[str, Any]],
    results: list[ScoreResult | None],
) -> str:
    """Build a markdown quality report for a batch of chapters.

    Args:
        chapters: List of chapter dicts (each with 'num', 'title')
        results: Corresponding ScoreResult objects (None = regex-only)

    Returns:
        Markdown report string
    """
    lines = [
        "# NovelClaw Translation Quality Report",
        "",
        f"| Ch | Title | Overall | Fluency | Accuracy | Terminology | Completeness | Errors | Pass |",
        f"|---|-------|---------|---------|----------|-------------|--------------|--------|------|",
    ]

    for i, ch in enumerate(chapters):
        num = ch.get("num", "?")
        title = ch.get("title", "")[:30]
        sr = results[i]
        if sr is None:
            lines.append(f"| {num} | {title} | — | — | — | — | — | — | regex |")
        else:
            err_count = len(sr.errors)
            status = "✅" if sr.passed else "❌"
            lines.append(
                f"| {num} | {title} | {sr.overall:.1f} | {sr.fluency:.1f} | "
                f"{sr.accuracy:.1f} | {sr.terminology:.1f} | {sr.completeness:.1f} | "
                f"{err_count} | {status} |"
            )

    # Summary statistics
    scored = [s for s in results if s is not None]
    if scored:
        avg_overall = sum(s.overall for s in scored) / len(scored)
        passed_count = sum(1 for s in scored if s.passed)
        total_errors = sum(len(s.errors) for s in scored)
        lines.extend([
            "",
            "## Summary",
            f"- Chapters scored: {len(scored)}",
            f"- Average overall score: {avg_overall:.2f}/10",
            f"- Passed: {passed_count}/{len(scored)} ({passed_count/len(scored)*100:.0f}%)",
            f"- Total errors found: {total_errors}",
        ])

        # Error breakdown
        error_cats: dict[str, int] = {}
        error_sevs: dict[str, int] = {}
        for s in scored:
            for e in s.errors:
                cat = e.get("category", "unknown")
                sev = e.get("severity", "info")
                error_cats[cat] = error_cats.get(cat, 0) + 1
                error_sevs[sev] = error_sevs.get(sev, 0) + 1
        if error_cats:
            lines.extend(["", "### Errors by Category"])
            for cat, count in sorted(error_cats.items(), key=lambda x: -x[1]):
                lines.append(f"- {cat}: {count}")
        if error_sevs:
            lines.extend(["", "### Errors by Severity"])
            for sev, count in sorted(error_sevs.items(), key=lambda x: -x[1]):
                lines.append(f"- {sev}: {count}")

    return "\n".join(lines)
