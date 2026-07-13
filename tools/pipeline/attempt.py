
"""attempt — Single LLM attempt runner (Stations 4-6)."""
from __future__ import annotations
from typing import Any

from pipeline._shared import (
    get_logger, call_llm, FatalError, parse_output, apply_glossary_post,
    classify_and_format, PASS_THRESHOLD,
)
from pipeline.prompt import _score_and_report, _split_prompt


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

