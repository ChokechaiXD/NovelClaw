"""orchestrate — Master translation orchestrator: retry, judge, glossary discovery, translate_one."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from pipeline._shared import (
    get_logger, _TranslateOneResult, call_llm, FatalError,
    _get_active_config, build_source_profile, resolve_source_lang,
    script_mix, parse_output, apply_glossary_post, save_chapter,
    _get_title, classify_and_format, PASS_THRESHOLD, clean_source,
    discover_and_save, build_glossary_pre_chunk, ScorerHistory,
    ensure_logging,
)
from pipeline.prompt import (
    build_translate_prompt, _build_repair_instruction,
    _quality_summary, _score_and_report,
)
from pipeline.judge import _judge_and_auto_repair
from pipeline.script_leak import _repair_script_leaks
from pipeline.read_source import (
    read_source, _source_chunk_char_limit, _split_source_chunks,
)
from pipeline.attempt import _run_one_attempt
from pipeline._shared import estimate_type_ratios

log = get_logger("orchestrate")


# ── Station 6.5 Helper: Quality Repair Decision ────────────────────────


def _quality_repair_decision(score_result: dict[str, Any]) -> dict[str, Any]:
    """Determine if a quality-failed chapter is eligible for auto-repair retry."""
    _scr = float(score_result.get("score") or 0.0)
    _notes = [str(n) for n in (score_result.get("repairNotes") or score_result.get("repair_notes") or [])]
    _repair_eligible = _scr >= 20.0 and len(_notes) > 0
    return {
        "eligible": _repair_eligible,
        "reason": (
            f"score={_scr:.1f} >= 20 with {len(_notes)} repair notes"
            if _repair_eligible else
            f"score={_scr:.1f} < 20 or no repair notes"
        ),
    }


# ── Station 6.75: Safety Fallback ──────────────────────────────────────


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
    """Attempt OpenRouter as a safety fallback when the primary translation engine fails.

    Returns (succeeded, score_result, classified, model_name, provider_name, out_path).
    """
    cfg = _get_active_config()
    fallback_provider = ""
    fallback_model = ""
    router_cfg: dict[str, Any] = {}
    for provider_name in ["openrouter"]:
        provider_cfg = cfg.get("providers", {}).get(provider_name)
        all_models = provider_cfg.get("models", []) if provider_cfg else []
        if all_models:
            fallback_model = all_models[0]
            fallback_provider = provider_name
            router_cfg = {
                "model": fallback_model,
                "provider": fallback_provider,
                "kind": "fallback",
            }
            break
    if not fallback_model:
        log.warning("No safety fallback configured")
        return (
            False, {"score": 0, "passed": False}, [],
            "", "", "",
        )
    fallback_prompt = chunk_prompts[0] if chunk_prompts else (
        system_text + "\n\n" + user_text if system_text else user_text
    )
    try:
        result = _run_one_attempt(
            prompt=fallback_prompt,
            repair_instruction="",
            ch_num=ch_num,
            target_lang=target_lang,
            source=source,
            source_profile=source_profile,
            attempt_cfg=router_cfg,
            chunk_prompts=chunk_prompts,
        )
        if result["status"] == "passed":
            out_path = save_chapter(
                classified=result["classified"],
                ch_num=ch_num,
                slug=slug,
                source_text=source,
                source_lang=source_lang,
                target_lang=target_lang,
                provider_name=fallback_provider,
                model_name=fallback_model,
                prompt_profile="fallback",
                quality_record=_quality_summary(
                    result["score_result"],
                    [{"kind": "fallback", "model": fallback_model, "provider": fallback_provider}],
                ),
                source_profile=source_profile,
            )
            return (
                True,
                result["score_result"],
                result["classified"],
                fallback_model,
                fallback_provider,
                str(out_path),
            )
    except Exception:
        log.exception("Safety fallback failed")
    return (
        False, {"score": 0, "passed": False}, [],
        "", "", "",
    )


# ── Attempt Record Builder ─────────────────────────────────────────────


def _attempt_record(
    attempt_cfg: dict[str, Any],
    result: dict[str, Any],
    status: str,
    score_result: dict[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build a record dict for a single attempt."""
    record: dict[str, Any] = {
        "kind": attempt_cfg["kind"],
        "model": result.get("model", ""),
        "provider": result.get("provider", ""),
        "status": status,
    }
    if score_result is not None:
        record["score"] = score_result.get("score", 0)
        record["quality_detail"] = score_result.get("dimensions", {})
    if reason:
        record["reason"] = reason
    return record


# ── Result Builders ────────────────────────────────────────────────────


def _failed_translation_result(
    *,
    ch_num: int,
    reason: str,
    attempts: list[dict[str, Any]],
    source_lang: str,
    source_profile: dict[str, Any],
    quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a 'failed' result from `_run_real_translate`."""
    return {
        "status": "failed",
        "ch": ch_num,
        "reason": reason,
        "classified": [],
        "score_result": {},
        "judge_result": {},
        "attempts": attempts,
        "provider_name": "",
        "model_name": "",
        "discovery_result": {},
        "source_lang": source_lang,
        "source_profile": source_profile,
        "quality": quality or {},
        "score": 0,
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
    """Build a 'needs_review' result from `_run_real_translate`."""
    return {
        "status": "needs_review",
        "ch": ch_num,
        "reason": reason,
        "classified": classified,
        "score_result": score_result,
        "judge_result": judge_result,
        "attempts": attempts,
        "provider_name": provider_name,
        "model_name": model_name,
        "discovery_result": {},
        "source_lang": source_lang,
        "source_profile": source_profile,
    }


# ── Station 6.6: Script Leak Auto-Correction ────────────────────────────


def _try_auto_correct_script_leaks(
    classified: list[dict[str, str]],
    score_result: dict[str, Any],
    source: str,
    target_lang: str,
    source_profile: dict[str, Any],
    model_name: str,
    provider_name: str,
) -> tuple[list[dict[str, str]], dict[str, Any], bool, float]:
    """If quality failure is only script leaks, attempt targeted auto-correction.

    Returns (classified, score_result, leak_fixed, new_score).
    """
    _hard = score_result.get("hardFailures") or score_result.get("errors") or []
    if not _hard:
        return classified, score_result, False, 0.0

    _only_script_leaks = all(
        e.startswith("Script Purity") or "leak" in e.lower()
        for e in _hard
    )
    if not _only_script_leaks:
        return classified, score_result, False, 0.0

    from classifier import classify_and_format

    _para_strings = [p["text"] for p in classified] if classified else []
    _repaired = _repair_script_leaks(
        _para_strings, target_lang,
        attempt_model=model_name, attempt_provider=provider_name,
    )
    if _repaired == _para_strings:
        return classified, score_result, False, 0.0

    _reclassified = classify_and_format(_repaired)
    _new_score = _score_and_report(
        _reclassified, source, target_lang, source_profile=source_profile,
    )
    if _new_score.get("passed"):
        return _reclassified, _new_score, True, _new_score.get("score", 0.0)

    return classified, score_result, False, 0.0


# ── Station 4-7: Real (non-mock) Translate Loop ────────────────────────


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
        _classified, _score, _leak_fixed, _new_score = _try_auto_correct_script_leaks(
            classified=classified, score_result=score_result,
            source=source, target_lang=target_lang,
            source_profile=source_profile,
            model_name=model_name, provider_name=provider_name,
        )
        if _leak_fixed:
            classified = _classified
            score_result = _score
            attempts[-1]["status"] = "leak_repaired"
            attempts[-1]["score"] = _new_score
            translation_ready = True
            break

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


# ── MASTER PIPELINE ────────────────────────────────────────────────────


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
    ensure_logging()
    try:
        # ── Station 1-2: Read + Clean ──
        raw = read_source(ch_num, slug)
        if raw is None:
            return {"status": "failed", "ch": ch_num, "reason": "source_not_found"}
        source = clean_source(raw)
        if not source:
            return {"status": "failed", "ch": ch_num, "reason": "empty_after_clean"}
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

        # Track score for adaptive threshold
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
            "discovery": (
                f"{discovery_result.get('discovered', 0)} found, "
                f"{discovery_result.get('saved', 0)} saved"
                if isinstance(discovery_result, dict) and discovery_result.get('discovered', 0) > 0
                else "none"
            ),
        }

    except Exception as e:
        log.exception("translate_one failed for ch %s", ch_num)
        return {"status": "failed", "ch": ch_num, "reason": str(e)[:300]}
