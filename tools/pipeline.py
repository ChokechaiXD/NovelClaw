#!/usr/bin/env python3
"""
pipeline.py — NovelClaw Translation Assembly Line

สายพานการผลิต 7 สถานี:
  Station 1: รับวัตถุดิบ (read source)
  Station 2: ทำความสะอาด (clean source)
  Station 3: ประกอบคำสั่ง (build prompt)
  Station 4: ส่งผลิต (call LLM)
  Station 5: แยกชิ้นงาน (parse output)
  Station 6: ตรวจสอบ (classify + quality gate)
  Station 7: ประกอบ+แพค (format + save)

Usage (via novelclaw.py CLI):
    python novelclaw.py translate 130
    python novelclaw.py translate 130-150
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, TypedDict


class _TranslateOneResult(TypedDict, total=False):
    """Return value from translate_one()."""
    status: str  # ok, failed, dry_run
    ch: int
    paragraphs: int
    types: dict[str, float]
    path: str
    score: float
    source_chars: int
    source_preview: str
    provider: str
    model: str
    discovery: str
    judge: str
    reason: str


# ── Logging setup ────────────────────────────────────────────────────
logger = logging.getLogger("novelclaw.pipeline")
_LOGGING_CONFIGURED = False


def _ensure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return
    _LOGGING_CONFIGURED = True
    log_file = _PROJECT_ROOT / "novelclaw.log"
    try:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(str(log_file), encoding="utf-8"),
                logging.StreamHandler(),
            ],
            force=True,
        )
        logger.info("Logging initialized (file=%s)", log_file)
    except Exception:
        # Fallback: stdout-only if file write fails
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            force=True,
        )
    logger.info("Logging initialized (stdout only)")


# ── Paths ─────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = Path(__file__).parent

sys.path.insert(0, str(_TOOLS_DIR))

from classifier import classify_and_format, estimate_type_ratios  # noqa: E402
from novel_paths import chapter_path, source_md_path  # noqa: E402
from pipeline_llm import call_llm, get_active_config as _get_active_config  # noqa: E402
from pipeline_llm import FatalError  # noqa: E402
from scorer import ScorerHistory, MqmError  # noqa: E402
from pipeline_parser import parse_output  # noqa: E402
from pipeline_save import apply_glossary_post, save_chapter, get_title as _get_title  # noqa: E402
from prompt_builder import build_prompt  # noqa: E402
from scorer import PASS_THRESHOLD  # noqa: E402
from source_cleaner import clean_source  # noqa: E402
from quality_gate import evaluate_translation_quality  # noqa: E402
from glossary_pre import build_glossary_pre_chunk  # noqa: E402
from glossary_discovery import discover_and_save  # noqa: E402
from source_profile import build_source_profile, resolve_source_lang  # noqa: E402

# ── Glossary discovery persistence ────────────────────────────────────
# Previously a global set() that only lasted one session.
# Now checks glossary.json on disk — persists across sessions.

_GLOSSARY_CACHE: dict[str, bool] = {}  # slug → has_auto_discovered


def _glossary_has_been_discovered(slug: str) -> bool:
    """Check if glossary.json already contains auto-discovered terms.
    
    Cached per slug to avoid re-reading disk every chapter.
    """
    if slug in _GLOSSARY_CACHE:
        return _GLOSSARY_CACHE[slug]

    from novel_paths import glossary_json_path
    path = glossary_json_path(slug)
    if not path.exists():
        _GLOSSARY_CACHE[slug] = False
        return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        terms = data.get("terms", [])
        has_auto = any(t.get("category") == "auto_discovered" for t in terms)
        _GLOSSARY_CACHE[slug] = has_auto
        return has_auto
    except Exception:
        _GLOSSARY_CACHE[slug] = False
        return False

# ── Station 1: Source Reader ─────────────────────────────────────────


def read_source(ch_num: int, slug: str = "global-descent") -> str | None:
    """Station 1: Read source file. Supports .md and .cn.json."""
    src_json = chapter_path(slug, ch_num, "cn")

    if src_json.exists():
        data = json.loads(src_json.read_text(encoding="utf-8"))
        return "\n".join(data.get("paragraphs", []))

    src_md = source_md_path(slug, ch_num)
    if src_md.exists():
        return src_md.read_text(encoding="utf-8")

    return None


# ── Station 3: Prompt Builder ─────────────────────────────────────────


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
    """Split assembled prompt into system + user parts at the first structured marker.

    Returns (system_text or None, user_text).
    """
    split_point = prompt.find("<continuity>")
    if split_point < 0:
        split_point = prompt.find("<glossary>")
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


def _run_one_attempt(
    prompt: str,
    repair_instruction: str,
    ch_num: int,
    target_lang: str,
    source: str,
    source_profile: dict[str, Any] | None,
    attempt_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Run one LLM attempt through Stations 4-6 (call → parse → gloss → classify → score).

    Args:
        prompt: Full assembled prompt.
        repair_instruction: Quality-failure repair instruction (may be empty).
        ch_num: Chapter number (for parsing).
        target_lang: Target language code.
        source: Clean source text.
        source_profile: Source profile for scoring context.
        attempt_cfg: Attempt config with 'kind', 'model', 'provider' keys.

    Returns:
        Dict with 'status' key: 'passed', 'quality_failed', 'empty_output', or 'error'.
        Plus 'classified', 'score_result', 'provider', 'model', 'system_text',
        'user_text', and for errors: 'reason'.
    """
    system_text, user_text = _split_prompt(prompt, repair_instruction)

    try:
        response, provider_name, model_name = call_llm(
            prompt=user_text,
            system=system_text,
            model=attempt_cfg["model"],
            provider=attempt_cfg["provider"],
        )

        if not response or len(response.strip()) < 10:
            return {
                "status": "empty_output",
                "provider": provider_name,
                "model": model_name,
                "system_text": system_text,
                "user_text": user_text,
            }

        # ── Station 5: Parse ──
        paragraph_strings = parse_output(response, ch_num)
        if paragraph_strings[-1] != "(จบบท)":
            paragraph_strings.append("(จบบท)")

        # ── Station 5.5: Glossary Post-Process ──
        paragraph_strings = apply_glossary_post(paragraph_strings, target_lang)

        # ── Station 6: Classify ──
        classified = classify_and_format(paragraph_strings)

        # ── Station 6.5: Score ──
        score_result = _score_and_report(classified, source, target_lang, source_profile=source_profile)

        passed = bool(score_result.get("passed"))
        return {
            "status": "passed" if passed else "quality_failed",
            "classified": classified,
            "score_result": score_result,
            "provider": provider_name,
            "model": model_name,
            "system_text": system_text,
            "user_text": user_text,
        }
    except FatalError:
        raise  # propagate fatal errors — no point retrying
    except Exception as e:
        return {
            "status": "error",
            "reason": str(e)[:100],
            "provider": attempt_cfg["provider"],
            "model": attempt_cfg["model"],
            "system_text": system_text,
            "user_text": user_text,
        }


# ── Station 6.6: Script Leak Auto-Correction ──────────────────────────


def _repair_script_leaks(
    paragraph_strings: list[str],
    target_lang: str,
    attempt_model: str | None = None,
    attempt_provider: str | None = None,
) -> list[str]:
    """Fix script leaks by re-translating only leaky paragraphs.

    Returns the fixed paragraph list (unchanged if no leaks found).
    """
    from qa.script_policy import detect_script_leaks

    result = detect_script_leaks(paragraph_strings, target_lang=target_lang)
    if result.ok:
        return paragraph_strings  # nothing to fix

    # Group leaks by paragraph index
    para_errors: dict[int, set[str]] = {}
    for leak in result.leaks:
        if leak.index not in para_errors:
            para_errors[leak.index] = set()
        para_errors[leak.index].add(leak.script)

    # Fix only paragraphs with leaks
    fixed = list(paragraph_strings)
    leaked_indices = sorted(para_errors.keys())
    for pi in leaked_indices:
        if pi >= len(fixed) or fixed[pi] in ("(จบบท)", "(End)", "（終）", "(끝)"):
            continue
        scripts_desc = ", ".join(sorted(para_errors[pi]))
        old_text = fixed[pi]
        # Skip very short paragraphs where auto-repair is wasteful
        if len(old_text) < 15:
            continue
        system_prompt = (
            f"You are a literary translator. Fix ONLY the {scripts_desc} script "
            f"leaks in the following {target_lang} text. Replace foreign-script "
            f"words with natural {target_lang} equivalents. "
            f"Return ONLY the fixed text, nothing else."
        )
        try:
            resp, _, _ = call_llm(
                prompt=f"Fix script leaks in this paragraph:\n\n{old_text}",
                system=system_prompt,
                model=attempt_model,
                provider=attempt_provider,
                temperature=0.1,
                max_tokens=500,
            )
            candidate = resp.strip()
            # Ensure the repair didn't trash the paragraph
            if len(candidate) >= len(old_text) * 0.5 and len(candidate) <= len(old_text) * 3:
                fixed[pi] = candidate
        except Exception:
            pass  # fall through to original text
    return fixed


# ── Station 6.75: LLM Judge ────────────────────────────────────────────

_JUDGE_SYSTEM = """You are a literary translation quality evaluator (G-Eval protocol).
Assess the translation on 4 dimensions, each 0-100. For each dimension, reason
step-by-step before assigning a score, then output structured JSON.

SCORING RUBRIC:
1. **Accuracy** (weight 0.40): All events, entities, and actions preserved
   from source. No omission, addition, or hallucination.
2. **Fluency** (weight 0.15): Natural target-language grammar and phrasing.
   Reads like native writing.
3. **Terminology** (weight 0.25): Glossary terms and proper nouns used
   correctly and consistently.
4. **Coherence** (weight 0.20): Logical flow between paragraphs. Dialogue
   and narration transitions feel natural.

For each dimension:
- Reason: 1-2 sentences explaining your reasoning.
- Score: 0-100 integer.
- If score < 70, list specific error(s).

OUTPUT FORMAT — ONLY valid JSON, no other text:
{
  "dimensions": {"accuracy": 85, "fluency": 90, "terminology": 75, "coherence": 88},
  "weighted_score": 83.5,
  "passed": true,
  "errors": [
    {"type": "terminology/leak", "severity": "minor", "span": "untranslated term 'HP'", "position": 3}
  ],
  "repair_notes": ["Replace 'HP' with Thai equivalent 'พลังชีวิต'."],
  "untranslated_scripts": []
}"""


def judge_translation(
    paragraphs: list[dict[str, str]],
    source_text: str,
    model: str | None = None,
    source_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """G-Eval quality judge via LLM. Returns structured JSON with dimensions + errors."""
    try:
        content = [p for p in paragraphs if p.get("type") != "end"]
        sample_indexes = {0, 1, 2}
        if content:
            mid = len(content) // 2
            sample_indexes.update({max(0, mid - 1), mid, min(len(content) - 1, mid + 1)})
            sample_indexes.update({max(0, len(content) - 3), max(0, len(content) - 2), len(content) - 1})
        risky_indexes = [
            i for i, p in enumerate(content)
            if p.get("type") in {"dialogue", "system"} or re.search(r"[A-Za-z\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", p.get("text", ""))
        ][:4]
        sample_indexes.update(risky_indexes)
        text_preview = "\n".join(
            f"[{i + 1}:{content[i].get('type', 'narration')}] {content[i].get('text', '')[:180]}"
            for i in sorted(i for i in sample_indexes if 0 <= i < len(content))
        )
        structure = source_profile or {}
        prompt = f"""Review this translation using G-Eval protocol with chain-of-thought.

Sample paragraphs (beginning / middle / end / risk):
{text_preview}

Source sample (first 300 chars):
{source_text[:300]}

Source structure:
- paragraphs: {structure.get('paragraphCount', '?')}
- dialogue: {structure.get('dialogueCount', '?')}
- system markers: {structure.get('systemMarkerCount', '?')}

For each of the 4 rubric dimensions, reason 1-2 sentences then assign 0-100.
Respond with ONLY valid JSON matching the specified format."""

        response, provider, model_name = call_llm(
            prompt=prompt, system=_JUDGE_SYSTEM,
            model=model, temperature=0.1, max_tokens=800,
        )
        raw = response.strip()
        # Parse JSON from response (handle possible markdown fences)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        parsed = json.loads(raw)
        dims: dict[str, int] = parsed.get("dimensions", {})
        weighted = parsed.get("weighted_score", 0)
        errors: list[dict[str, Any]] = parsed.get("errors", [])
        passed = parsed.get("passed", True)
        repair_notes: list[str] = parsed.get("repair_notes", [])
        return {
            "ok": True,
            "passed": passed,
            "score": weighted,
            "dimensions": dims,
            "errors": errors,
            "repair_notes": repair_notes,
            "feedback": repair_notes[0] if repair_notes else ("ok" if passed else "needs review"),
            "model": model_name,
            "sampledParagraphs": len(sample_indexes),
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Fallback: try plain text parse for non-JSON responses
        try:
            raw_local = response if isinstance(response, str) else str(response)
            passed_local = not raw_local.upper().startswith("FAIL:")
            return {
                "ok": True,
                "passed": passed_local,
                "score": 0,
                "dimensions": {},
                "errors": [],
                "repair_notes": [],
                "feedback": raw_local[:200],
                "model": model_name,
                "sampledParagraphs": 0,
            }
        except Exception:
            return {"ok": False, "passed": True, "feedback": f"parse error: {e}"[:200]}
    except Exception as e:
        return {"ok": False, "passed": True, "feedback": str(e)[:200]}


# ── Station 6.75: LLM Judge + Auto Repair Orchestration ──────────────


def _judge_and_auto_repair(
    classified: list[dict[str, str]],
    source: str,
    score_result: dict[str, Any],
    source_profile: dict[str, Any] | None,
    judge_model: str | None,
    primary_model: str,
    primary_provider: str,
    system_text: str | None,
    user_text: str,
    ch_num: int,
    target_lang: str,
    attempts: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    """Station 6.75: Run LLM Judge if score warrants, attempt auto-repair on failure.

    Mutates attempts (appends judged_repair attempt) in-place.
    Returns (classified, score_result, judge_result) — may be updated after repair.
    """
    # Ponytail: skip Judge for high-scoring chapters (>=95) — saves ~70% of Judge calls
    score_val = score_result.get("score", 0)
    if 85.0 <= score_val < 95.0:
        judge_result = judge_translation(
            classified,
            source,
            judge_model,
            source_profile=source_profile,
        )
    else:
        judge_result = {"ok": True, "passed": True, "skipped": True}

    if judge_result.get("ok") and judge_result.get("passed") is False:
        judge_feedback = str(judge_result.get("feedback", ""))[:400]
        judge_repair_instruction = (
            "\n\n<judge_repair>\nAn LLM quality reviewer suggested improvements."
            " Rewrite the full chapter addressing these points before returning:\n"
            + judge_feedback + "\n</judge_repair>"
        )
        judge_repaired = False
        try:
            resp2, _, _ = call_llm(
                prompt=user_text + judge_repair_instruction,
                system=system_text,
                model=primary_model,
                provider=primary_provider,
            )
            if resp2 and len(resp2.strip()) >= 10:
                paras2 = parse_output(resp2, ch_num)
                if paras2[-1] != "(จบบท)":
                    paras2.append("(จบบท)")
                paras2 = apply_glossary_post(paras2, target_lang)
                classified2 = classify_and_format(paras2)
                score2 = _score_and_report(classified2, source, target_lang, source_profile=source_profile)
                if score2["passed"]:
                    classified = classified2
                    score_result = score2
                    judge_repaired = True
                    judge_result["repaired"] = True
                    judge_result["scoreAfterRepair"] = score2.get("score", 0)
                    attempts.append({
                        "kind": "judge_repair",
                        "model": primary_model,
                        "provider": primary_provider,
                        "status": "passed",
                        "score": score2.get("score", 0),
                    })
        except Exception:
            pass

        if not judge_repaired:
            score_result = {
                **score_result,
                "passed": False,
                "hardFailures": [
                    *score_result.get("hardFailures", []),
                    "LLM Judge: repair attempted but still flagged.",
                ],
                "repairNotes": [
                    *score_result.get("repairNotes", score_result.get("repair_notes", [])),
                    judge_feedback[:240],
                ],
            }

    return classified, score_result, judge_result


# ── Retry quality decision ─────────────────────────────────────────────


def _quality_repair_decision(score_result: dict[str, Any]) -> dict[str, Any]:
    """Determine if a quality-failed chapter is eligible for auto-repair retry."""
    _scr = float(score_result.get("score") or 0.0)
    _notes = [str(n) for n in (score_result.get("repairNotes") or score_result.get("repair_notes") or []) if str(n).strip()]
    _eligible = (not score_result.get("passed")) and bool(_notes) and (_scr >= 80.0)
    return {"eligible": _eligible, "reason": "borderline_quality" if _eligible else "not_eligible", "score": _scr}


# ── Safety Fallback ────────────────────────────────────────────────────


def _try_safety_fallback(
    user_text: str,
    system_text: str | None,
    ch_num: int,
    target_lang: str,
    source: str,
    source_profile: dict[str, Any] | None,
    last_error: str,
    primary_provider: str,
) -> tuple[bool, dict[str, Any], list[dict[str, str]], str, str, str]:
    """Attempt OpenRouter safety filter auto-fallback to 9Router.

    Returns (succeeded, score_result, classified, fallback_model, fallback_provider, path)
    or (False, ...) if fallback fails.
    """
    if "empty_or_short_content" not in last_error or primary_provider != "openrouter":
        return (False, {}, [], "", "", "")

    fallback_model = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    try:
        response_retry, prov_retry, _ = call_llm(
            prompt=user_text,
            system=system_text,
            model=fallback_model,
            provider="custom",
        )
        if response_retry and len(response_retry.strip()) >= 50:
            paras = parse_output(response_retry, ch_num)
            if paras[-1] != "(จบบท)":
                paras.append("(จบบท)")
            paras = apply_glossary_post(paras, target_lang)
            classified = classify_and_format(paras)
            score_result = _score_and_report(classified, source, target_lang, source_profile=source_profile)
            if score_result.get("passed"):
                out_path = save_chapter(ch_num, classified, score_result, source_lang, target_lang, source, source_profile)
                return (True, score_result, classified, fallback_model, prov_retry, out_path)
    except Exception:
        pass
    return (False, {}, [], "", "", "")


# ── Real Translation Orchestration ──────────────────────────────────────


def _run_real_translate(
    *,
    ch_num: int,
    slug: str,
    source: str,
    source_lang: str,
    target_lang: str,
    source_profile: dict[str, Any],
    prompt: str,
    model_override: str | None,
    provider_override: str | None,
) -> dict[str, Any]:
    """Run the real (non-mock) translation loop: retry → judge → glossary.

    Returns a dict with keys:
      status: "ok" | "needs_review" | "failed"
      plus classified, score_result, judge_result, attempts, provider_name,
      model_name, discovery_result, source_lang, source_profile, reason, score
    """
    cfg = _get_active_config(provider_override)
    primary_model = model_override or cfg["model"]
    discovery_model = cfg.get("discovery_model") or primary_model
    primary_provider = cfg["provider_name"]

    attempts: list[dict[str, Any]] = []
    last_error = "unknown"
    repair_instruction = ""
    judge_result: dict[str, Any] = {"ok": False, "passed": True, "feedback": "", "model": "", "sampledParagraphs": 0}
    attempt_plan = [
        {"kind": "translate", "model": primary_model, "provider": primary_provider},
        {"kind": "repair", "model": primary_model, "provider": primary_provider},
        {"kind": "fallback", "model": discovery_model, "provider": primary_provider},
    ]
    allow_repair = True
    translation_ready = False
    classified: list[dict[str, str]] = []
    score_result: dict[str, Any] = {}
    provider_name = ""
    model_name = ""
    system_text: str | None = None
    user_text = ""

    for attempt_cfg in attempt_plan:
        if attempt_cfg["kind"] == "repair" and not allow_repair:
            continue

        result = _run_one_attempt(
            prompt=prompt,
            repair_instruction=repair_instruction,
            ch_num=ch_num,
            target_lang=target_lang,
            source=source,
            source_profile=source_profile,
            attempt_cfg=attempt_cfg,
        )

        system_text = result["system_text"]
        user_text = result["user_text"]

        if result["status"] == "passed":
            classified = result["classified"]
            score_result = result["score_result"]
            provider_name = result["provider"]
            model_name = result["model"]
            attempts.append({
                "kind": attempt_cfg["kind"],
                "model": model_name,
                "provider": provider_name,
                "status": "passed",
                "score": score_result.get("score", 0),
                "hardFailures": score_result.get("hardFailures", score_result.get("errors", [])),
                "structure": score_result.get("structure", {}),
            })
            translation_ready = True
            break

        if result["status"] == "empty_output":
            last_error = "Empty LLM output"
            attempts.append({
                "kind": attempt_cfg["kind"],
                "model": result["model"],
                "provider": result["provider"],
                "status": "empty_output",
            })
            allow_repair = False
            continue

        if result["status"] == "error":
            last_error = result.get("reason", "unknown")
            attempts.append({
                "kind": attempt_cfg["kind"],
                "model": result["model"],
                "provider": result["provider"],
                "status": "error",
                "reason": last_error,
            })
            allow_repair = False
            if attempt_cfg["kind"] != "fallback":
                continue
            return {
                "status": "failed", "ch": ch_num, "reason": last_error[:300],
                "classified": [], "score_result": {}, "judge_result": {},
                "attempts": attempts, "provider_name": "", "model_name": "",
                "discovery_result": {}, "source_lang": source_lang,
                "source_profile": source_profile,
            }

        # quality_failed
        classified = result["classified"]
        score_result = result["score_result"]
        provider_name = result["provider"]
        model_name = result["model"]
        last_error = f"scorer: {score_result.get('score', 0)}/100 < {PASS_THRESHOLD}"
        attempts.append({
            "kind": attempt_cfg["kind"],
            "model": model_name,
            "provider": provider_name,
            "status": "quality_failed",
            "score": score_result.get("score", 0),
            "hardFailures": score_result.get("hardFailures", score_result.get("errors", [])),
            "structure": score_result.get("structure", {}),
        })

        repair_decision = _quality_repair_decision(score_result)
        attempts[-1]["repairEligible"] = repair_decision["eligible"]
        attempts[-1]["repairReason"] = repair_decision["reason"]
        repair_instruction = _build_repair_instruction(score_result) if repair_decision["eligible"] else ""

        # ── Station 6.6: Script Leak Auto-Correction ──
        # Fix only leaky paragraphs instead of retrying the whole chapter
        _leak_fixed = False
        _hard = score_result.get("hardFailures") or score_result.get("errors") or []
        _only_script_leaks = all(
            e.startswith("Script Purity") or "leak" in e.lower()
            for e in _hard
        ) and any(
            e.startswith("Script Purity") or "leak" in e.lower()
            for e in _hard
        )
        if _only_script_leaks and score_result.get("hardFailures"):
            from classifier import classify_and_format
            _para_strings = [p["text"] for p in classified] if classified else []
            _repaired = _repair_script_leaks(
                _para_strings, target_lang,
                attempt_model=model_name, attempt_provider=provider_name,
            )
            if _repaired != _para_strings:
                _reclassified = classify_and_format(_repaired)
                _new_score = _score_and_report(
                    _reclassified, source, target_lang, source_profile=source_profile
                )
                if _new_score.get("passed"):
                    classified = _reclassified
                    score_result = _new_score
                    _leak_fixed = True
                    attempts[-1]["status"] = "leak_repaired"
                    attempts[-1]["score"] = _new_score.get("score", 0)
                    translation_ready = True
                    break

        if _leak_fixed:
            continue

        if attempt_cfg["kind"] == "translate" and repair_instruction:
            continue

        return {
            "status": "needs_review", "ch": ch_num,
            "reason": f"quality gate failed after retry: {last_error}",
            "score": score_result.get("score", 0),
            "classified": classified,
            "score_result": score_result,
            "judge_result": judge_result,
            "attempts": attempts,
            "provider_name": provider_name,
            "model_name": model_name,
            "discovery_result": {},
            "quality": _quality_summary(score_result, attempts),
            "source_lang": source_lang,
            "source_profile": source_profile,
        }

    if not translation_ready:
        succeeded, fb_score, fb_classified, fb_model, fb_prov, out_path = _try_safety_fallback(
            user_text=user_text, system_text=system_text,
            ch_num=ch_num, target_lang=target_lang,
            source=source, source_profile=source_profile,
            last_error=last_error, primary_provider=primary_provider,
        )
        if succeeded:
            return {
                "status": "ok", "ch": ch_num, "path": out_path,
                "score": fb_score.get("score", 0),
                "classified": fb_classified,
                "score_result": fb_score,
                "judge_result": judge_result,
                "attempts": attempts,
                "provider_name": fb_prov,
                "model_name": fb_model,
                "discovery_result": {},
                "source_lang": source_lang,
                "source_profile": source_profile,
                "quality": fb_score,
            }
        return {
            "status": "failed", "ch": ch_num, "reason": last_error,
            "classified": [], "score_result": {}, "judge_result": {},
            "attempts": attempts, "provider_name": "", "model_name": "",
            "discovery_result": {}, "source_lang": source_lang,
            "source_profile": source_profile,
            "quality": {"attempts": attempts, "repairHistory": attempts},
        }

    # ── Station 6.75: LLM Judge + Auto Repair ──
    judge_model = model_override or cfg.get("discovery_model") or primary_model
    classified, score_result, judge_result = _judge_and_auto_repair(
        classified=classified, source=source,
        score_result=score_result, source_profile=source_profile,
        judge_model=judge_model, primary_model=primary_model,
        primary_provider=primary_provider,
        system_text=system_text, user_text=user_text,
        ch_num=ch_num, target_lang=target_lang, attempts=attempts,
    )

    # ── Station 6.8: Auto Glossary Discovery ──
    if source and not _glossary_has_been_discovered(slug):
        cfg = _get_active_config()
        discovery_result = discover_and_save(
            source_text=source, slug=slug, source_lang=source_lang,
            discovery_model=model_override or cfg.get("discovery_model"),
        )
    else:
        discovery_result = {"discovered": 0, "saved": 0, "terms": []}

    return {
        "status": "ok", "ch": ch_num,
        "classified": classified,
        "score_result": score_result,
        "judge_result": judge_result,
        "attempts": attempts,
        "provider_name": provider_name,
        "model_name": model_name,
        "discovery_result": discovery_result,
        "source_lang": source_lang,
        "source_profile": source_profile,
    }


# ── MASTER PIPELINE ───────────────────────────────────────────────────


def translate_one(
    ch_num: int,
    slug: str = "global-descent",
    source_lang: str = "auto",
    target_lang: str = "th",
    model_override: str | None = None,
    provider_override: str | None = None,
    prompt_profile: str = "",
    dry_run: bool = False,
    mock: bool = False,
    scorer_history: ScorerHistory | None = None,
) -> dict[str, Any]:
    """Run the full 7-station assembly line for one chapter.

    Returns:
        {"status": "ok", "ch": num, "paragraphs": N, "types": {...}, "path": "..."}
        or {"status": "failed", "ch": num, "reason": "..."}
    """
    _ensure_logging()
    try:
        # ── Station 1-2: Read + Clean ──
        raw = read_source(ch_num, slug)
        if raw is None:
            return {"status": "failed", "ch": ch_num, "reason": "source_not_found"}
        source_lang, source_lang_source = resolve_source_lang(raw, source_lang, slug)
        source = clean_source(raw)
        if not source:
            return {"status": "failed", "ch": ch_num, "reason": "empty_after_clean"}
        source_profile = build_source_profile(
            source, source_lang=source_lang, target_lang=target_lang,
            ch_num=ch_num, lang_source=source_lang_source,
        )

        if dry_run:
            return {
                "status": "dry_run", "ch": ch_num,
                "source_preview": source[:300],
                "source_chars": len(source),
                "sourceLang": source_lang,
                "sourceProfile": source_profile,
            }

        # ── Station 3: Build Prompt ──
        prompt = build_translate_prompt(
            source_text=source, ch_num=ch_num,
            source_lang=source_lang, target_lang=target_lang,
            slug=slug, prompt_profile=prompt_profile,
            source_profile=source_profile,
        )

        if mock:
            paragraph_strings = [
                f"[MOCK] ch {ch_num} — แปลด้วย {source_lang}→{target_lang}",
                "(จบบท)",
            ]
            provider_name = "mock"
            model_name = "mock"
            classified = classify_and_format(paragraph_strings)
            score_result = {"score": 100, "passed": True, "report": "(mock)", "dimensions": {}}
            judge_result = {"ok": True, "feedback": "(mock)"}
            discovery_result = {"discovered": 0, "saved": 0, "terms": []}
            attempts: list[dict[str, Any]] = []
        else:
            r = _run_real_translate(
                ch_num=ch_num, slug=slug,
                source=source, source_lang=source_lang,
                target_lang=target_lang, source_profile=source_profile,
                prompt=prompt,
                model_override=model_override, provider_override=provider_override,
            )

            if r["status"] in ("failed", "needs_review"):
                return {
                    "status": r["status"],
                    "ch": ch_num,
                    "reason": r.get("reason", ""),
                    "score": r.get("score", 0),
                    "quality": r.get("quality", r.get("score_result", {})),
                    "path": r.get("path", ""),
                    "sourceLang": r.get("source_lang", source_lang),
                    "sourceProfile": r.get("source_profile", source_profile),
                }

            classified = r["classified"]
            score_result = r["score_result"]
            judge_result = r["judge_result"]
            provider_name = r["provider_name"]
            model_name = r["model_name"]
            discovery_result = r["discovery_result"]
            attempts = r["attempts"]

        # Track score for adaptive threshold (Phase 3)
        if scorer_history is not None and "score" in score_result:
            scorer_history.update(score_result["score"])

        quality_record = _quality_summary(score_result, attempts if not mock else [], judge_result)
        final_status = "needs_review" if quality_record.get("passed") is False else "ok"
        out_path = save_chapter(
            classified=classified, ch_num=ch_num, slug=slug,
            source_text=source, source_lang=source_lang, target_lang=target_lang,
            provider_name=provider_name, model_name=model_name,
            prompt_profile=prompt_profile,
            quality_record=quality_record, source_profile=source_profile,
        )

        return {
            "status": final_status,
            "ch": ch_num,
            "reason": "LLM judge flagged quality risk" if final_status == "needs_review" else "",
            "paragraphs": len(classified),
            "types": estimate_type_ratios(classified),
            "path": str(out_path),
            "provider": provider_name,
            "model": model_name,
            "promptProfile": prompt_profile or "faithful_default",
            "sourceLang": source_lang,
            "sourceProfile": source_profile,
            "score": score_result["score"],
            "quality": quality_record,
            "judge": judge_result["feedback"][:200] if judge_result.get("ok") else "judge_error",
            "discovery": f"{discovery_result['discovered']} found, {discovery_result['saved']} saved" if discovery_result.get('discovered', 0) > 0 else "none",
        }

    except Exception as e:
        return {"status": "failed", "ch": ch_num, "reason": str(e)[:300]}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    import argparse

    ap = argparse.ArgumentParser(description="Test pipeline")
    ap.add_argument("ch", type=int, help="Chapter number")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--from", dest="source_lang", default="auto")
    ap.add_argument("--slug", default="global-descent")
    args = ap.parse_args()

    result = translate_one(
        ch_num=args.ch,
        slug=args.slug,
        source_lang=args.source_lang,
        dry_run=args.dry_run,
        mock=args.mock,
    )
