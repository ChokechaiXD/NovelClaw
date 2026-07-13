"""judge — LLM Judge quality evaluation and auto-repair orchestration."""
from __future__ import annotations
import json
import re
from typing import Any

from pipeline._shared import (
    get_logger, call_llm, _get_active_config, source_md_path,
    classify_and_format, apply_glossary_post, parse_output,
    PASS_THRESHOLD,
)
from pipeline.prompt import _score_and_report, _quality_summary, _build_repair_instruction
from pipeline.read_source import read_source
from pipeline.attempt import _run_one_attempt

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
  "repair_notes": ["Replace 'HP' with Thai equivalent '\\u0e1e\\u0e25\\u0e31\\u0e07\\u0e0a\\u0e35\\u0e27\\u0e34\\u0e15'."],
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

