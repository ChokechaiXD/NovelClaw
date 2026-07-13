"""Pipeline package shared types, logging, paths, and sibling imports.
Shared module so each pipeline/* module can access these without circular imports.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, TypedDict


# ── Result type ────────────────────────────────────────────────────────

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


# ── Paths ─────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = Path(__file__).parent

sys.path.insert(0, str(_TOOLS_DIR))


# ── Imports from sibling tools/ modules ───────────────────────────────

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


# ── Logging setup ────────────────────────────────────────────────────

_logger: logging.Logger | None = None


def ensure_logging() -> None:
    global _logger
    if _logger is not None:
        return
    _logger = logging.getLogger("novelclaw.pipeline")
    _logger.setLevel(logging.DEBUG)
    log_file = _PROJECT_ROOT / "novelclaw.log"
    try:
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(str(log_file), maxBytes=10*1024*1024, backupCount=3, encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        _logger.addHandler(handler)
    except Exception:
        pass  # stdout fallback
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    _logger.addHandler(console)
    _logger.info("Logging initialized")
    logging.getLogger("pipeline_llm").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> logging.Logger:
    ensure_logging()
    if name:
        return logging.getLogger(f"novelclaw.pipeline.{name}")
    assert _logger is not None
    return _logger

