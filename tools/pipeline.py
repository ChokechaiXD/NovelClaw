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
    status: str  # ok, needs_review, failed, dry_run
    ch: int
    paragraphs: int
    types: dict[str, float]
    path: str
    score: float
    quality: dict[str, Any]
    source_chars: int
    source_preview: str
    provider: str
    model: str
    promptProfile: str
    sourceLang: str
    sourceProfile: dict[str, Any]
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
from scorer import ScorerHistory  # noqa: E402
from pipeline_parser import parse_output  # noqa: E402
from pipeline_save import apply_glossary_post, get_title as _get_title, save_chapter  # noqa: E402,F401
from prompt_builder import build_prompt  # noqa: E402
from scorer import PASS_THRESHOLD  # noqa: E402
from source_cleaner import clean_source  # noqa: E402
from quality_gate import evaluate_translation_quality  # noqa: E402
from glossary_pre import build_glossary_pre_chunk  # noqa: E402
from glossary_discovery import discover_and_save  # noqa: E402
from source_profile import build_source_profile, resolve_source_lang, script_mix  # noqa: E402

# ── Station 1: Source Reader ─────────────────────────────────────────


def read_source(ch_num: int, slug: str = "global-descent") -> str | None:
    """Station 1: Read source file. Supports .md and .cn.json."""
    src_md = source_md_path(slug, ch_num)
    if src_md.exists():
        return src_md.read_text(encoding="utf-8")

    src_json = chapter_path(slug, ch_num, "cn")
    if src_json.exists():
        data = json.loads(src_json.read_text(encoding="utf-8"))
        return "\n".join(data.get("paragraphs", []))

    return None


# ── Station 3: Prompt Builder ─────────────────────────────────────────


def _source_chunk_char_limit(source_lang: str, max_tokens: int) -> int:
    """Estimate a safe source size for a target-language output token budget."""
    language_ratio = {
        # CJK-to-Thai can use more than two completion tokens per source char.
        "cn": 0.4,
        "zh": 0.4,
        "jp": 0.4,
        "ja": 0.4,
        "kr": 0.65,
        "ko": 0.65,
        "en": 1.4,
    }.get(source_lang.lower(), 0.6)
    return max(64, min(6000, int(max_tokens * language_ratio)))


def _split_source_chunks(source_text: str, max_chars: int) -> list[str]:
    """Split source without losing characters, preferring paragraph boundaries."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if len(source_text) <= max_chars:
        return [source_text]

    chunks: list[str] = []
    cursor = 0
    while len(source_text) - cursor > max_chars:
        window = source_text[cursor:cursor + max_chars]
        minimum_break = max_chars // 2
        paragraph_break = window.rfind("\n\n", minimum_break)
        if paragraph_break >= 0:
            cut = paragraph_break + 2
        else:
            sentence_break = max(
                (window.rfind(mark, minimum_break) for mark in ".!?。！？…"),
                default=-1,
            )
            cut = sentence_break + 1 if sentence_break >= 0 else max_chars
        chunks.append(source_text[cursor:cursor + cut])
        cursor += cut
    if cursor < len(source_text):
        chunks.append(source_text[cursor:])
    return chunks


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


def _run_one_attempt(
    prompt: str,
    repair_instruction: str,
    ch_num: int,
    target_lang: str,
    source: str,
    source_profile: dict[str, Any] | None,
    attempt_cfg: dict[str, Any],
    chunk_prompts: list[str] | None = None,
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
        Dict with 'status' key: 'passed', 'quality_failed', 'empty_output',
        'truncated_output', or 'error'.
        Plus 'classified', 'score_result', 'provider', 'model', 'system_text',
        'user_text', and for errors: 'reason'.
    """
    prompts = chunk_prompts or [prompt]
    chunk_count = len(prompts)
    system_text: str | None = None
    user_text = ""
    try:
        paragraph_strings: list[str] = []
        provider_name = attempt_cfg["provider"]
        model_name = attempt_cfg["model"]

        for chunk_index, chunk_prompt in enumerate(prompts, start=1):
            system_text, user_text = _split_prompt(chunk_prompt, repair_instruction)
            if chunk_count > 1:
                chunk_instruction = (
                    "<chunk_context>\n"
                    f"Part {chunk_index} of {chunk_count}. Translate only this consecutive "
                    "source part. Preserve paragraph order and all content. Do not add a "
                    "chapter title or an end-of-chapter marker.\n"
                    "</chunk_context>\n\n"
                )
                user_text = chunk_instruction + user_text

            response_metadata: dict[str, Any] = {}
            response, provider_name, model_name = call_llm(
                prompt=user_text,
                system=system_text,
                model=attempt_cfg["model"],
                provider=attempt_cfg["provider"],
                response_metadata=response_metadata,
            )

            if response_metadata.get("finish_reason") in {
                "length", "max_tokens", "max_output_tokens",
            }:
                return {
                    "status": "truncated_output",
                    "reason": "provider stopped at the output token limit",
                    "provider": provider_name,
                    "model": model_name,
                    "system_text": system_text,
                    "user_text": user_text,
                    "chunk_count": chunk_count,
                    "failed_chunk": chunk_index,
                }

            if not response or len(response.strip()) < 10:
                return {
                    "status": "empty_output",
                    "provider": provider_name,
                    "model": model_name,
                    "system_text": system_text,
                    "user_text": user_text,
                    "chunk_count": chunk_count,
                    "failed_chunk": chunk_index,
                }

            # ── Station 5: Parse ──
            parsed_chunk = parse_output(response, ch_num)
            paragraph_strings.extend(
                paragraph for paragraph in parsed_chunk
                if paragraph not in {"(จบบท)", "(End)", "（終）", "(끝)"}
            )

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
            "chunk_count": chunk_count,
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
            "chunk_count": chunk_count,
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
        if leak.paragraph_index not in para_errors:
            para_errors[leak.paragraph_index] = set()
        para_errors[leak.paragraph_index].add(leak.script)

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
Assess the translation on 4 dimensions, each 0-100, and return a concise structured verdict.

SCORING RUBRIC:
1. **Accuracy** (weight 0.40): All events, entities, and actions preserved
   from source. No omission, addition, or hallucination.
2. **Fluency** (weight 0.15): Natural target-language grammar and phrasing.
   Reads like native writing.
3. **Terminology** (weight 0.25): Glossary terms and proper nouns used
   correctly and consistently.
4. **Coherence** (weight 0.20): Logical flow between paragraphs. Dialogue
   and narration transitions feel natural.

Pass only when weighted_score is at least 80, accuracy is at least 75, and there
are no major or critical errors. List concrete repair notes for every failure.

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

_JUDGE_DIMENSION_WEIGHTS = {
    "accuracy": 0.40,
    "fluency": 0.15,
    "terminology": 0.25,
    "coherence": 0.20,
}


_JUDGE_SECTION_QUANTILES = (0.0, 0.25, 0.5, 0.75, 1.0)


def _quantile_index(length: int, quantile: float) -> int:
    """Return a stable index for a normalized chapter position."""

    return round(max(0, length - 1) * quantile)


def _source_section_sample(source_text: str, section_chars: int = 190) -> str:
    """Sample five aligned chapter sections with a constant-size Judge budget."""

    text = str(source_text or "").strip()
    if len(text) <= section_chars * len(_JUDGE_SECTION_QUANTILES):
        return text

    samples: list[str] = []
    half_window = section_chars // 2
    for quantile in _JUDGE_SECTION_QUANTILES:
        center = _quantile_index(len(text), quantile)
        start = min(max(0, center - half_window), len(text) - section_chars)
        label = f"{round(quantile * 100)}%"
        samples.append(f"[{label}] {text[start:start + section_chars]}")
    return "\n".join(samples)


def _validated_judge_payload(raw: str) -> dict[str, Any]:
    """Validate the model contract; malformed verdicts must never become silent passes."""

    value = str(raw or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        value = value.rsplit("```", 1)[0].strip()
    if not value:
        raise ValueError("empty Judge response")
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Judge response must be a JSON object")

    dimensions_raw = parsed.get("dimensions")
    if not isinstance(dimensions_raw, dict):
        raise ValueError("Judge dimensions are missing")
    dimensions: dict[str, float] = {}
    for name in _JUDGE_DIMENSION_WEIGHTS:
        score_raw = dimensions_raw.get(name)
        if isinstance(score_raw, bool):
            raise ValueError(f"Judge dimension {name} is invalid")
        try:
            score = float(score_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Judge dimension {name} is missing or invalid") from exc
        if score != score or not 0 <= score <= 100:
            raise ValueError(f"Judge dimension {name} is outside 0-100")
        dimensions[name] = score

    if not isinstance(parsed.get("passed"), bool):
        raise ValueError("Judge passed flag is missing or invalid")
    errors = parsed.get("errors")
    repair_notes = parsed.get("repair_notes")
    if not isinstance(errors, list) or not all(isinstance(item, dict) for item in errors):
        raise ValueError("Judge errors must be a list of objects")
    if not isinstance(repair_notes, list) or not all(isinstance(item, str) for item in repair_notes):
        raise ValueError("Judge repair_notes must be a list of strings")

    weighted_score = round(sum(dimensions[name] * weight for name, weight in _JUDGE_DIMENSION_WEIGHTS.items()), 2)
    reported_score_raw = parsed.get("weighted_score")
    if isinstance(reported_score_raw, bool):
        raise ValueError("Judge weighted_score is invalid")
    try:
        reported_score = float(reported_score_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Judge weighted_score is missing or invalid") from exc
    if reported_score != reported_score or not 0 <= reported_score <= 100:
        raise ValueError("Judge weighted_score is outside 0-100")
    if abs(reported_score - weighted_score) > 2.5:
        raise ValueError("Judge weighted_score is inconsistent with its dimensions")
    severe_error = any(
        str(item.get("severity") or "").strip().lower() in {"major", "critical", "blocking"}
        for item in errors
    )
    passed = bool(
        parsed["passed"]
        and weighted_score >= 80
        and dimensions["accuracy"] >= 75
        and not severe_error
    )
    return {
        "dimensions": dimensions,
        "weighted_score": weighted_score,
        "passed": passed,
        "errors": errors,
        "repair_notes": repair_notes,
    }


def judge_translation(
    paragraphs: list[dict[str, str]],
    source_text: str,
    model: str | None = None,
    source_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """G-Eval quality judge via LLM. Returns structured JSON with dimensions + errors."""
    try:
        content = [p for p in paragraphs if p.get("type") != "end"]
        # Five section-aligned samples cover long/chunked chapters without growing
        # the Judge prompt with chapter length. Risk samples remain separately capped.
        sample_indexes = {
            _quantile_index(len(content), quantile)
            for quantile in _JUDGE_SECTION_QUANTILES
        } if content else set()
        risky_indexes = [
            i for i, p in enumerate(content)
            if p.get("type") in {"dialogue", "system"} or re.search(r"[A-Za-z\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", p.get("text", ""))
        ][:4]
        sample_indexes.update(risky_indexes)
        sampled_indexes = sorted(i for i in sample_indexes if 0 <= i < len(content))
        text_preview = "\n".join(
            f"[{i + 1}:{content[i].get('type', 'narration')}] {content[i].get('text', '')[:180]}"
            for i in sampled_indexes
        )
        structure = source_profile or {}
        source_sample = _source_section_sample(source_text)
        prompt = f"""Review this literary translation using the G-Eval rubric.

Sample paragraphs (section-aligned at 0% / 25% / 50% / 75% / 100%, plus risk):
{text_preview}

Source sample (section-aligned at 0% / 25% / 50% / 75% / 100%):
{source_sample}

Source structure:
- paragraphs: {structure.get('paragraphCount', '?')}
- dialogue: {structure.get('dialogueCount', '?')}
- system markers: {structure.get('systemMarkerCount', '?')}

Respond with ONLY valid JSON matching the specified format."""

        response, provider, model_name = call_llm(
            prompt=prompt, system=_JUDGE_SYSTEM,
            model=model, temperature=0.1, max_tokens=800,
        )
        parsed = _validated_judge_payload(response)
        dims = parsed["dimensions"]
        weighted = parsed["weighted_score"]
        errors = parsed["errors"]
        passed = parsed["passed"]
        repair_notes = parsed["repair_notes"]
        return {
            "ok": True,
            "passed": passed,
            "score": weighted,
            "dimensions": dims,
            "errors": errors,
            "repair_notes": repair_notes,
            "feedback": repair_notes[0] if repair_notes else ("ok" if passed else "needs review"),
            "model": model_name,
            "sampledParagraphs": len(sampled_indexes),
        }
    except Exception as e:
        return {
            "ok": False,
            "passed": False,
            "unavailable": True,
            "feedback": f"LLM Judge unavailable: {e}"[:240],
        }


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
    chunk_prompts: list[str] | None = None,
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

    if not judge_result.get("ok"):
        judge_feedback = str(judge_result.get("feedback") or "LLM Judge unavailable")[:240]
        score_result = {
            **score_result,
            "passed": False,
            "hardFailures": [
                *score_result.get("hardFailures", []),
                judge_feedback,
            ],
            "repairNotes": [
                *score_result.get("repairNotes", score_result.get("repair_notes", [])),
                "Review this chapter manually because the quality Judge did not return a valid verdict.",
            ],
        }
    elif judge_result.get("passed") is False:
        judge_feedback = str(judge_result.get("feedback", ""))[:400]
        initial_judge = dict(judge_result)
        judge_repair_instruction = (
            "\n\n<judge_repair>\nAn LLM quality reviewer suggested improvements."
            " Rewrite the full chapter addressing these points before returning:\n"
            + judge_feedback + "\n</judge_repair>"
        )
        judge_repaired = False
        repair_status = "quality_failed"
        repair_failure = "Auto-repair did not pass the deterministic quality gate; original output retained."
        repair_score = 0
        try:
            if chunk_prompts:
                repair_result = _run_one_attempt(
                    prompt=chunk_prompts[0],
                    chunk_prompts=chunk_prompts,
                    repair_instruction=judge_repair_instruction,
                    ch_num=ch_num,
                    target_lang=target_lang,
                    source=source,
                    source_profile=source_profile,
                    attempt_cfg={
                        "kind": "judge_repair",
                        "model": primary_model,
                        "provider": primary_provider,
                    },
                )
                classified2 = repair_result.get("classified", [])
                score2 = repair_result.get("score_result", {})
            else:
                resp2, _, _ = call_llm(
                    prompt=user_text + judge_repair_instruction,
                    system=system_text,
                    model=primary_model,
                    provider=primary_provider,
                )
                paras2 = parse_output(resp2, ch_num) if resp2 and len(resp2.strip()) >= 10 else []
                if paras2 and paras2[-1] != "(จบบท)":
                    paras2.append("(จบบท)")
                paras2 = apply_glossary_post(paras2, target_lang)
                classified2 = classify_and_format(paras2) if paras2 else []
                score2 = (
                    _score_and_report(classified2, source, target_lang, source_profile=source_profile)
                    if classified2 else {}
                )

            if isinstance(score2, dict) and score2.get("passed"):
                repair_score = score2.get("score", 0)
                repair_judge = judge_translation(
                    classified2,
                    source,
                    judge_model,
                    source_profile=source_profile,
                )
                repair_judge_passed = bool(
                    repair_judge.get("ok") and repair_judge.get("passed") is True
                )
                if repair_judge_passed:
                    classified = classified2
                    score_result = score2
                    judge_repaired = True
                    repair_status = "passed"
                    judge_result = {
                        **repair_judge,
                        "initialVerdict": initial_judge,
                        "repairJudge": dict(repair_judge),
                        "repairAttempted": True,
                        "repairAccepted": True,
                        "repaired": True,
                        "scoreAfterRepair": repair_score,
                    }
                else:
                    repair_status = (
                        "judge_unavailable" if not repair_judge.get("ok") else "judge_failed"
                    )
                    repair_judge_feedback = str(
                        repair_judge.get("feedback") or "repaired output did not pass the LLM Judge"
                    )[:240]
                    repair_failure = (
                        "Auto-repair rejected; original output retained. "
                        f"Repair Judge: {repair_judge_feedback}. "
                        f"Initial Judge: {judge_feedback or 'quality risk detected'}."
                    )[:500]
                    judge_result = {
                        **repair_judge,
                        "initialVerdict": initial_judge,
                        "repairJudge": dict(repair_judge),
                        "repairAttempted": True,
                        "repairAccepted": False,
                        "repaired": False,
                        "candidateScoreAfterRepair": repair_score,
                        "feedback": repair_failure,
                    }
            else:
                repair_score = score2.get("score", 0) if isinstance(score2, dict) else 0
                repair_failure = (
                    "Auto-repair rejected by the deterministic quality gate; original output retained. "
                    f"Candidate score: {repair_score}. Initial Judge: "
                    f"{judge_feedback or 'quality risk detected'}."
                )[:500]
                judge_result = {
                    **initial_judge,
                    "repairAttempted": True,
                    "repairAccepted": False,
                    "repaired": False,
                    "candidateScoreAfterRepair": repair_score,
                    "feedback": repair_failure,
                }
        except Exception as exc:
            repair_status = "error"
            repair_failure = (
                "Auto-repair failed before validation; original output retained. "
                f"{exc}"
            )[:500]
            judge_result = {
                **initial_judge,
                "repairAttempted": True,
                "repairAccepted": False,
                "repaired": False,
                "feedback": repair_failure,
            }

        attempts.append({
            "kind": "judge_repair",
            "model": primary_model,
            "provider": primary_provider,
            "status": repair_status,
            "score": repair_score,
            **({"reason": repair_failure[:240]} if not judge_repaired else {}),
            **({"chunkCount": len(chunk_prompts)} if chunk_prompts else {}),
        })

        if not judge_repaired:
            score_result = {
                **score_result,
                "passed": False,
                "hardFailures": [
                    *score_result.get("hardFailures", []),
                    repair_failure,
                ],
                "repairNotes": [
                    *score_result.get("repairNotes", score_result.get("repair_notes", [])),
                    (judge_feedback or repair_failure)[:240],
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
    source_lang: str,
    target_lang: str,
    source: str,
    source_profile: dict[str, Any] | None,
    last_error: str,
    primary_provider: str,
    chunk_prompts: list[str] | None = None,
    slug: str = "global-descent",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], str, str, str]:
    """Attempt OpenRouter safety filter auto-fallback to 9Router.

    Returns (succeeded, score_result, classified, fallback_model, fallback_provider, path)
    or (False, ...) if fallback fails.
    """
    if primary_provider != "openrouter" or "empty" not in last_error.lower():
        return (False, {}, [], "", "", "")

    fallback_model = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    try:
        if chunk_prompts:
            fallback_result = _run_one_attempt(
                prompt=chunk_prompts[0],
                chunk_prompts=chunk_prompts,
                repair_instruction="",
                ch_num=ch_num,
                target_lang=target_lang,
                source=source,
                source_profile=source_profile,
                attempt_cfg={
                    "kind": "safety_fallback",
                    "model": fallback_model,
                    "provider": "custom",
                },
            )
            classified = fallback_result.get("classified", [])
            score_result = fallback_result.get("score_result", {})
            prov_retry = fallback_result.get("provider", "custom")
        else:
            response_retry, prov_retry, _ = call_llm(
                prompt=user_text,
                system=system_text,
                model=fallback_model,
                provider="custom",
            )
            paras = parse_output(response_retry, ch_num) if response_retry and len(response_retry.strip()) >= 5 else []
            if paras and paras[-1] != "(จบบท)":
                paras.append("(จบบท)")
            paras = apply_glossary_post(paras, target_lang)
            classified = classify_and_format(paras) if paras else []
            score_result = (
                _score_and_report(classified, source, target_lang, source_profile=source_profile)
                if classified else {}
            )

        if score_result.get("passed"):
            out_path = save_chapter(
                classified=classified, ch_num=ch_num, slug=slug, source_text=source,
                source_lang=source_lang, target_lang=target_lang, source_profile=source_profile,
                quality_record=score_result,
            )
            return (True, score_result, classified, fallback_model, prov_retry, out_path)
    except Exception:
        pass
    return (False, {}, [], "", "", "")


def _attempt_record(
    attempt_cfg: dict[str, Any],
    result: dict[str, Any],
    status: str,
    score_result: dict[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    record = {
        "kind": attempt_cfg["kind"],
        "model": result.get("model", ""),
        "provider": result.get("provider", ""),
        "status": status,
    }
    if score_result is not None:
        record.update({
            "score": score_result.get("score", 0),
            "hardFailures": score_result.get("hardFailures", score_result.get("errors", [])),
            "structure": score_result.get("structure", {}),
        })
    if reason is not None:
        record["reason"] = reason
    if result.get("chunk_count"):
        record["chunkCount"] = result["chunk_count"]
    if result.get("failed_chunk"):
        record["failedChunk"] = result["failed_chunk"]
    return record


def _failed_translation_result(
    *,
    ch_num: int,
    reason: str,
    attempts: list[dict[str, Any]],
    source_lang: str,
    source_profile: dict[str, Any],
    quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "failed", "ch": ch_num, "reason": reason,
        "classified": [], "score_result": {}, "judge_result": {},
        "attempts": attempts, "provider_name": "", "model_name": "",
        "discovery_result": {}, "source_lang": source_lang,
        "source_profile": source_profile,
        **({"quality": quality} if quality is not None else {}),
    }


def _needs_review_result(
    *,
    ch_num: int,
    reason: str,
    classified: list[dict[str, str]],
    score_result: dict[str, Any],
    judge_result: dict[str, Any],
    attempts: list[dict[str, Any]],
    provider_name: str,
    model_name: str,
    source_lang: str,
    source_profile: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "needs_review", "ch": ch_num,
        "reason": reason,
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
    chunk_prompts: list[str] | None,
    model_override: str | None,
    provider_override: str | None,
    runtime_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the real (non-mock) translation loop: retry → judge → glossary.

    Returns a dict with keys:
      status: "ok" | "needs_review" | "failed"
      plus classified, score_result, judge_result, attempts, provider_name,
      model_name, discovery_result, source_lang, source_profile, reason, score
    """
    cfg = runtime_cfg or _get_active_config(provider_override)
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
            chunk_prompts=chunk_prompts,
        )

        system_text = result["system_text"]
        user_text = result["user_text"]

        if result["status"] == "passed":
            classified = result["classified"]
            score_result = result["score_result"]
            provider_name = result["provider"]
            model_name = result["model"]
            attempts.append(_attempt_record(attempt_cfg, result, "passed", score_result))
            translation_ready = True
            break

        if result["status"] == "empty_output":
            last_error = "Empty LLM output"
            attempts.append(_attempt_record(attempt_cfg, result, "empty_output"))
            allow_repair = False
            continue

        if result["status"] == "truncated_output":
            last_error = (
                f"LLM output truncated at chunk {result.get('failed_chunk', '?')}"
                f"/{result.get('chunk_count', '?')}"
            )
            attempts.append(_attempt_record(
                attempt_cfg, result, "truncated_output", reason=last_error,
            ))
            allow_repair = False
            continue

        if result["status"] == "error":
            last_error = result.get("reason", "unknown")
            attempts.append(_attempt_record(attempt_cfg, result, "error", reason=last_error))
            allow_repair = False
            if attempt_cfg["kind"] != "fallback":
                continue
            return _failed_translation_result(
                ch_num=ch_num, reason=last_error[:300], attempts=attempts,
                source_lang=source_lang, source_profile=source_profile,
            )

        # quality_failed
        classified = result["classified"]
        score_result = result["score_result"]
        provider_name = result["provider"]
        model_name = result["model"]
        last_error = f"scorer: {score_result.get('score', 0)}/100 < {PASS_THRESHOLD}"
        attempts.append(_attempt_record(attempt_cfg, result, "quality_failed", score_result))

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

        return _needs_review_result(
            ch_num=ch_num,
            reason=f"quality gate failed after retry: {last_error}",
            classified=classified,
            score_result=score_result,
            judge_result=judge_result,
            attempts=attempts,
            provider_name=provider_name,
            model_name=model_name,
            source_lang=source_lang,
            source_profile=source_profile,
        )

    if not translation_ready:
        succeeded, fb_score, fb_classified, fb_model, fb_prov, out_path = _try_safety_fallback(
            user_text=user_text, system_text=system_text,
            ch_num=ch_num, source_lang=source_lang, target_lang=target_lang,
            source=source, source_profile=source_profile,
            last_error=last_error, primary_provider=primary_provider,
            chunk_prompts=chunk_prompts,
            slug=slug,
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
        return _failed_translation_result(
            ch_num=ch_num, reason=last_error, attempts=attempts,
            source_lang=source_lang, source_profile=source_profile,
            quality={"attempts": attempts, "repairHistory": attempts},
        )

    # ── Station 6.75: LLM Judge + Auto Repair ──
    judge_model = model_override or cfg.get("discovery_model") or primary_model
    classified, score_result, judge_result = _judge_and_auto_repair(
        classified=classified, source=source,
        score_result=score_result, source_profile=source_profile,
        judge_model=judge_model, primary_model=primary_model,
        primary_provider=primary_provider,
        system_text=system_text, user_text=user_text,
        ch_num=ch_num, target_lang=target_lang, attempts=attempts,
        chunk_prompts=chunk_prompts,
    )

    # ── Station 6.8: Auto Glossary Discovery ──
    if source:
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
        source = clean_source(raw)
        if not source:
            return {"status": "failed", "ch": ch_num, "reason": "empty_after_clean"}
        # Reuse one Unicode scan for language detection and the structure contract.
        source_script_mix = script_mix(source)
        source_lang, source_lang_source = resolve_source_lang(
            raw, source_lang, slug, script_counts=source_script_mix,
        )
        source_profile = build_source_profile(
            source, source_lang=source_lang, target_lang=target_lang,
            ch_num=ch_num, lang_source=source_lang_source,
            script_counts=source_script_mix,
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
        runtime_cfg = None if mock else _get_active_config(provider_override)
        max_tokens = int((runtime_cfg or {}).get("max_tokens") or 4096)
        source_chunks = _split_source_chunks(
            source,
            max_chars=_source_chunk_char_limit(source_lang, max_tokens),
        ) if not mock else [source]
        chunk_prompts: list[str] = []
        for source_chunk in source_chunks:
            chunk_profile = source_profile
            if len(source_chunks) > 1:
                chunk_profile = build_source_profile(
                    source_chunk,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    ch_num=ch_num,
                    lang_source=source_lang_source,
                    script_counts=script_mix(source_chunk),
                )
            chunk_prompts.append(build_translate_prompt(
                source_text=source_chunk, ch_num=ch_num,
                source_lang=source_lang, target_lang=target_lang,
                slug=slug, prompt_profile=prompt_profile,
                source_profile=chunk_profile,
            ))
        prompt = chunk_prompts[0]

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
                chunk_prompts=chunk_prompts if len(chunk_prompts) > 1 else None,
                model_override=model_override, provider_override=provider_override,
                runtime_cfg=runtime_cfg,
            )

            if r["status"] == "failed":
                return {
                    "status": "failed",
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
        review_reason = r.get("reason", "") if not mock and final_status == "needs_review" else ""
        if not review_reason and final_status == "needs_review" and isinstance(judge_result, dict):
            review_reason = str(judge_result.get("feedback") or "")[:240]
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
            "reason": review_reason or ("LLM judge flagged quality risk" if final_status == "needs_review" else ""),
            "paragraphs": len(classified),
            "types": estimate_type_ratios(classified),
            "path": str(out_path),
            "provider": provider_name,
            "model": model_name,
            "promptProfile": prompt_profile or "faithful_default",
            "sourceLang": source_lang,
            "sourceProfile": source_profile,
            "score": score_result.get("score", 0) if isinstance(score_result, dict) else 0,
            "quality": quality_record,
            "judge": (
                str(judge_result.get("feedback") or ("" if judge_result.get("ok") else "judge_error"))[:200]
                if isinstance(judge_result, dict) else "judge_error"
            ),
            "discovery": f"{discovery_result.get('discovered', 0)} found, {discovery_result.get('saved', 0)} saved" if isinstance(discovery_result, dict) and discovery_result.get('discovered', 0) > 0 else "none",
        }

    except Exception as e:
        logger.exception("translate_one failed for ch %s", ch_num)
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
