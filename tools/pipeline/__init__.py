"""pipeline — Translation pipeline package."""
from __future__ import annotations

from ._shared import (
    ensure_logging, _TranslateOneResult,
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
    _PROJECT_ROOT,  # backward compat for tests
)
from .read_source import read_source
from .prompt import (
    build_translate_prompt,
    _build_repair_instruction,  # backward compat
    _quality_summary,           # backward compat
    _split_prompt,              # backward compat
)
from .judge import judge_translation
from .orchestrate import (
    translate_one, _run_real_translate,
    _quality_repair_decision,   # backward compat
    _failed_translation_result, # backward compat
    _needs_review_result,       # backward compat
)

__all__ = [
    "translate_one",
    "judge_translation",
    "read_source",
    "clean_source",
    "build_translate_prompt",
    "ensure_logging",
]
