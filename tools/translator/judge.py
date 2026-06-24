"""Translator judge — quality evaluator using a separate model.

Uses deterministic QA first (no LLM cost), then LLM judge for
deeper quality assessment. Always uses a different/cheaper model
than the translator to avoid self-confirmation bias.

Usage:
    from translator.judge import judge_chapter, JudgeConfig, JudgeResult

    result = judge_chapter(
        paragraphs=chapter_data["paragraphs"],
        source_text=source_text,
        config=JudgeConfig(profile="judge"),
    )
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from translator.router import new_session, route


@dataclass
class JudgeConfig:
    """Configuration for the judge evaluator."""
    profile: str = "judge"
    min_deterministic_score: float = 0.5  # Fail-fast: skip LLM if deterministic < this
    system_prompt: str = (
        "You are a translation quality evaluator. "
        "Assess the Thai translation of a Chinese novel chapter. "
        "Rate 0-100 based on: accuracy, fluency, terminology consistency, completeness. "
        "Respond with JSON only: {\"score\": N, \"issues\": [\"...\"]}"
    )


@dataclass
class JudgeResult:
    """Result of a quality judgment."""
    ok: bool = False
    score: int | None = None
    mqm: dict = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    error: str | None = None
    deterministic_passed: bool = False
    llm_used: bool = False
    elapsed_ms: int = 0


# ── Deterministic checks (no LLM cost) ───────────────────────────────

def _deterministic_check(paragraphs: list[str], source_text: str | None = None) -> JudgeResult:
    """Run deterministic checks first. Returns pass/fail + issues.

    Checks:
      - Paragraph count reasonable
      - End marker present
      - No empty paragraphs
      - No CJK leak (basic)
      - Length ratio reasonable (if source provided)
    """
    issues = []
    score = 100

    if not paragraphs:
        return JudgeResult(ok=False, score=0, issues=["No paragraphs"], error="empty")

    # 1. End marker
    last = paragraphs[-1].strip()
    if last not in ("(จบบท)", "(End)", "（終）", "(끝)"):
        issues.append(f"Missing end marker: '{last[:20]}'")
        score -= 15

    # 2. Empty paragraphs
    empty_count = sum(1 for p in paragraphs if not p.strip())
    if empty_count > 0:
        issues.append(f"{empty_count} empty paragraphs")
        score -= 5 * empty_count

    # 3. Basic CJK leak check
    cjk = re.compile(r"[\u4e00-\u9fff]")
    cjk_count = sum(len(cjk.findall(p)) for p in paragraphs)
    if cjk_count > 0:
        issues.append(f"{cjk_count} CJK chars found")
        score -= min(30, cjk_count * 2)

    # 4. Length ratio (if source provided)
    if source_text:
        target_text = "".join(p for p in paragraphs if p not in ("(จบบท)", "(End)", "（終）", "(끝)"))
        ratio = len(target_text) / max(1, len(source_text))
        if ratio < 0.5:
            issues.append(f"Too short: ratio={ratio:.2f}")
            score -= 20
        elif ratio > 6.0:
            issues.append(f"Very long: ratio={ratio:.2f}")
            score -= 10

    score = max(0, min(100, score))
    return JudgeResult(
        ok=score >= 50,
        score=score,
        issues=issues,
        deterministic_passed=True,
    )


# ── LLM Judge ─────────────────────────────────────────────────────────

def _llm_judge(paragraphs: list[str], config: JudgeConfig) -> JudgeResult:
    """Run LLM-based quality evaluation using judge profile.

    Note: This is a placeholder that returns a pass-through result.
    Full implementation requires working judge profile with LLM calls.
    """
    session = new_session(profile=config.profile)

    # Build prompt
    text = "\n".join(p for p in paragraphs[:30] if p != "(จบบท)")
    prompt = f"Rate this Thai translation (0-100)\n\n{text[:2000]}"

    result = route(session, prompt, system=config.system_prompt)
    if not result.ok:
        return JudgeResult(
            ok=False,
            error=f"LLM judge failed: {result.error}",
            deterministic_passed=False,
            llm_used=True,
        )

    return JudgeResult(
        ok=True,
        score=None,  # score from LLM judge — not parsed in deterministic-only mode
        llm_used=True,
        deterministic_passed=True,
    )


# ── Public API ────────────────────────────────────────────────────────

def judge_chapter(
    paragraphs: list[str],
    source_text: str | None = None,
    config: JudgeConfig | None = None,
    skip_llm: bool = False,
) -> JudgeResult:
    """Evaluate chapter translation quality.

    Two-stage evaluation:
      1. Deterministic QA (always runs, zero cost)
      2. LLM judge (only if deterministic passes AND skip_llm=False)

    Args:
        paragraphs: Translated chapter paragraphs
        source_text: Original source text (optional, for length check)
        config: Judge configuration
        skip_llm: Skip LLM judge (deterministic only)

    Returns:
        JudgeResult with score, issues, and evaluation metadata.
    """
    if config is None:
        config = JudgeConfig()

    start = time.time()

    # Stage 1: Deterministic QA
    det_result = _deterministic_check(paragraphs, source_text)

    # If deterministic fails badly, skip LLM judge
    if not det_result.ok and (det_result.score or 0) < config.min_deterministic_score * 100:
        det_result.elapsed_ms = int((time.time() - start) * 1000)
        return det_result

    # Stage 2: LLM judge (optional)
    if skip_llm:
        det_result.elapsed_ms = int((time.time() - start) * 1000)
        return det_result

    llm_result = _llm_judge(paragraphs, config)
    elapsed_ms = int((time.time() - start) * 1000)

    # Merge: use LLM score if available, else deterministic
    return JudgeResult(
        ok=det_result.ok,
        score=llm_result.score if llm_result.llm_used else det_result.score,
        issues=det_result.issues + llm_result.issues,
        deterministic_passed=det_result.deterministic_passed,
        llm_used=llm_result.llm_used,
        elapsed_ms=elapsed_ms,
    )
