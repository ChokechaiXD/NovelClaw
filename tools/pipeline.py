"""pipeline.py — Thin shim for backward compatibility.

All logic moved to pipeline/ package. This file exists so existing
imports (from pipeline import translate_one, judge_translation, ...) 
continue to work without modification.
"""
from __future__ import annotations

from pipeline._shared import (
    ensure_logging,
    _TranslateOneResult,
    chapter_path, source_md_path,
    call_llm, _get_active_config, FatalError,
    ScorerHistory,
    parse_output,
    apply_glossary_post, _get_title, save_chapter,
    build_prompt,
    PASS_THRESHOLD,
    clean_source,
    evaluate_translation_quality,
    build_glossary_pre_chunk,
    discover_and_save,
    build_source_profile, resolve_source_lang, script_mix,
)
from pipeline.read_source import read_source, _source_chunk_char_limit, _split_source_chunks
from pipeline.prompt import build_translate_prompt, _score_and_report, _build_repair_instruction, _quality_summary, _split_prompt
from pipeline.attempt import _run_one_attempt
from pipeline.script_leak import _repair_script_leaks
from pipeline.judge import (
    _quantile_index, _source_section_sample, _validated_judge_payload,
    judge_translation, _judge_and_auto_repair,
)
from pipeline.orchestrate import (
    _quality_repair_decision, _try_safety_fallback,
    _attempt_record, _failed_translation_result, _needs_review_result,
    _run_real_translate, translate_one,
)

# Re-export only the public API named exports used by novelclaw.py
__all__ = [
    "translate_one",
    "judge_translation",
    "read_source",
    "clean_source",
    "build_translate_prompt",
]

if __name__ == "__main__":
    import sys
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
