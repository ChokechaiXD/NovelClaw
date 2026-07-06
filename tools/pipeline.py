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
import re
import sys
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = Path(__file__).parent

sys.path.insert(0, str(_TOOLS_DIR))

from classifier import classify_and_format, estimate_type_ratios  # noqa: E402
from novel_paths import chapter_path, source_md_path  # noqa: E402
from pipeline_llm import call_llm, get_active_config as _get_active_config  # noqa: E402
from pipeline_parser import parse_output  # noqa: E402
from pipeline_save import apply_glossary_post, save_chapter, get_title as _get_title  # noqa: E402
from prompt_builder import build_prompt  # noqa: E402
from scorer import PASS_THRESHOLD  # noqa: E402
from source_cleaner import clean_source  # noqa: E402
from quality_gate import evaluate_translation_quality  # noqa: E402
from glossary_pre import build_glossary_pre_chunk  # noqa: E402
from glossary_discovery import discover_and_save  # noqa: E402
from source_profile import build_source_profile, resolve_source_lang  # noqa: E402

_GLOSSARY_DISCOVERED: set[str] = set()  # ponytail: run glossary once per slug per session

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


# ── Station 6.75: LLM Judge ────────────────────────────────────────────

_JUDGE_SYSTEM = """You are a translation quality judge. Review a Thai novel translation.
Check for:
1. Naturalness — does it read like natural Thai?
2. Consistency — are character names/pronouns consistent?
3. Clarity — is there any confusing or ambiguous phrasing?
4. Flow — does the paragraph sequence flow naturally?

Rate each 1-10. If any score < 8, provide 1-2 specific improvement suggestions.
Keep response to 3-5 lines max."""


def judge_translation(
    paragraphs: list[dict[str, str]],
    source_text: str,
    model: str | None = None,
    source_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM Judge — optional quality review after scoring passes."""
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
        prompt = f"""Review this Thai novel translation using sampled beginning/middle/end/risk paragraphs:

{text_preview}

Source (first 300 chars):
{source_text[:300]}

Source structure:
- paragraphs: {structure.get('paragraphCount', '?')}
- dialogue: {structure.get('dialogueCount', '?')}
- system markers: {structure.get('systemMarkerCount', '?')}

Rate each: Naturalness / Consistency / Clarity / Flow / Completeness
If any score < 8, start with FAIL: and give 1-2 specific repair suggestions.
Otherwise start with PASS: and keep feedback brief."""

        response, provider, model_name = call_llm(
            prompt=prompt, system=_JUDGE_SYSTEM,
            model=model, temperature=0.1, max_tokens=500,
        )
        feedback = response.strip()
        return {
            "ok": True,
            "passed": not feedback.upper().startswith("FAIL:"),
            "feedback": feedback,
            "model": model_name,
            "sampledParagraphs": len(sample_indexes),
        }
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
        # Attempt one targeted repair guided by Judge feedback
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
                    # Repair worked — use the improved translation
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
) -> dict[str, Any]:
    """Run the full 7-station assembly line for one chapter.

    Returns:
        {"status": "ok", "ch": num, "paragraphs": N, "types": {...}, "path": "..."}
        or {"status": "failed", "ch": num, "reason": "..."}
    """
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
            source,
            source_lang=source_lang,
            target_lang=target_lang,
            ch_num=ch_num,
            lang_source=source_lang_source,
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
            source_text=source,
            ch_num=ch_num,
            source_lang=source_lang,
            target_lang=target_lang,
            slug=slug,
            prompt_profile=prompt_profile,
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
        else:
            # ── Retry policy: translate once, repair once on quality fail,
            #    fallback to discovery model only on provider/empty failures. ──
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
            for attempt_cfg in attempt_plan:
                if attempt_cfg["kind"] == "repair" and not allow_repair:
                    continue
                try:
                    # ── Station 4: Call LLM ──
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

                    response, provider_name, model_name = call_llm(
                        prompt=user_text,
                        system=system_text,
                        model=attempt_cfg["model"],
                        provider=attempt_cfg["provider"],
                    )

                    if not response or len(response.strip()) < 10:
                        last_error = "Empty LLM output"
                        attempts.append({
                            "kind": attempt_cfg["kind"],
                            "model": attempt_cfg["model"],
                            "provider": provider_name,
                            "status": "empty_output",
                        })
                        allow_repair = False
                        continue

                    # ── Station 5: Parse ──
                    paragraph_strings = parse_output(response, ch_num)
                    if paragraph_strings[-1] != "(จบบท)":
                        paragraph_strings.append("(จบบท)")

                    # ── Station 5.5: Glossary Post-Process ──
                    paragraph_strings = apply_glossary_post(paragraph_strings, target_lang)

                    # ── Station 6: Classify ──
                    classified = classify_and_format(paragraph_strings)

                    # ── Station 6.5: Scorer ──
                    score_result = _score_and_report(classified, source, target_lang, source_profile=source_profile)
                    attempts.append({
                        "kind": attempt_cfg["kind"],
                        "model": model_name,
                        "provider": provider_name,
                        "status": "passed" if score_result["passed"] else "quality_failed",
                        "score": score_result.get("score", 0),
                        "hardFailures": score_result.get("hardFailures", score_result.get("errors", [])),
                        "structure": score_result.get("structure", {}),
                    })

                    if score_result["passed"]:
                        translation_ready = True
                        break  # success!

                    last_error = f"scorer: {score_result['score']}/100 < {PASS_THRESHOLD}"
                    # ponytail: inline quality_repair_decision (was quality_retry.py)
                    _scr = float(score_result.get("score") or 0.0)
                    _notes = [str(n) for n in (score_result.get("repairNotes") or score_result.get("repair_notes") or []) if str(n).strip()]
                    _eligible = (not score_result.get("passed")) and bool(_notes) and (_scr >= 80.0)
                    repair_decision = {"eligible": _eligible, "reason": "borderline_quality" if _eligible else "not_eligible", "score": _scr}
                    attempts[-1]["repairEligible"] = repair_decision["eligible"]
                    attempts[-1]["repairReason"] = repair_decision["reason"]
                    repair_instruction = (
                        _build_repair_instruction(score_result)
                        if repair_decision["eligible"] else ""
                    )

                    if attempt_cfg["kind"] == "translate" and repair_instruction:
                        continue  # one targeted repair retry

                    return {
                        "status": "needs_review", "ch": ch_num,
                        "reason": f"quality gate failed after retry: {last_error}",
                        "score": score_result.get("score", 0),
                        "quality": _quality_summary(score_result, attempts),
                        "sourceLang": source_lang,
                        "sourceProfile": source_profile,
                    }

                except Exception as e:
                    last_error = str(e)[:100]
                    attempts.append({
                        "kind": attempt_cfg["kind"],
                        "model": attempt_cfg["model"],
                        "provider": attempt_cfg["provider"],
                        "status": "error",
                        "reason": last_error,
                    })
                    allow_repair = False
                    if attempt_cfg["kind"] != "fallback":
                        continue
                    return {"status": "failed", "ch": ch_num, "reason": str(e)[:300]}

            if not translation_ready:
                # ── Safety filter auto-fallback ──
                # If OpenRouter moderation truncated output (empty/short), retry once
                # via 9Router with a less-censored OpenRouter model.
                if "empty_or_short_content" in last_error and primary_provider == "openrouter":
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
                            if score_result["passed"]:
                                path = save_chapter(ch_num, classified, score_result, source_lang, target_lang, source, source_profile)
                                return {
                                    "status": "ok",
                                    "ch": ch_num,
                                    "path": path,
                                    "score": score_result.get("score", 0),
                                    "quality": score_result,
                                    "model": fallback_model,
                                    "provider": prov_retry,
                                    "attempts": attempts,
                                    "sourceLang": source_lang,
                                    "targetLang": target_lang,
                                    "sourceProfile": source_profile,
                                }
                    except Exception:
                        pass  # fallback failed, proceed to normal failure

                return {
                    "status": "failed",
                    "ch": ch_num,
                    "reason": last_error,
                    "quality": {"attempts": attempts, "repairHistory": attempts},
                    "sourceLang": source_lang,
                    "sourceProfile": source_profile,
                }

            # ── Station 6.75: LLM Judge + Auto Repair ──
            judge_model = model_override or cfg.get("discovery_model") or primary_model
            classified, score_result, judge_result = _judge_and_auto_repair(
                classified=classified,
                source=source,
                score_result=score_result,
                source_profile=source_profile,
                judge_model=judge_model,
                primary_model=primary_model,
                primary_provider=primary_provider,
                system_text=system_text,
                user_text=user_text,
                ch_num=ch_num,
                target_lang=target_lang,
                attempts=attempts,
            )

            # ── Station 6.8: Auto Glossary Discovery ──
            # ponytail: run once per session via module-level set
            if source and _GLOSSARY_DISCOVERED.add(slug) is None:
                cfg = _get_active_config()
                discovery_result = discover_and_save(
                    source_text=source,
                    slug=slug,
                    source_lang=source_lang,
                    discovery_model=model_override or cfg.get("discovery_model"),
                )
            else:
                discovery_result = {"discovered": 0, "saved": 0, "terms": []}

        quality_record = _quality_summary(score_result, attempts if not mock else [], judge_result)
        final_status = "needs_review" if quality_record.get("passed") is False else "ok"
        out_path = save_chapter(
            classified=classified,
            ch_num=ch_num,
            slug=slug,
            source_text=source,
            source_lang=source_lang,
            target_lang=target_lang,
            provider_name=provider_name,
            model_name=model_name,
            prompt_profile=prompt_profile,
            quality_record=quality_record,
            source_profile=source_profile,
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
            "discovery": f"{discovery_result['discovered']} found, {discovery_result['saved']} saved" if discovery_result['discovered'] > 0 else "none",
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
    print(json.dumps(result, ensure_ascii=False, indent=2))
