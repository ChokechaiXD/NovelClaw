"""registry/contracts.py — Centralized schema and model definitions.

Re-exports from canonical sources (contracts.py, schema.py).
Single import point for all schema consumers.
"""

# ── Chapter schema ────────────────────────────────────────────────────

# Canonical Pydantic model (SSOT)
from contracts import ChapterV2, ChapterPipeline, ChapterTitle  # noqa: F401

# JSON schema path
from pathlib import Path as _Path
CHAPTER_SCHEMA_PATH = _Path(__file__).resolve().parent.parent / "schema" / "chapter.schema.json"

# Language definitions
from schema import Language, BRACKETS  # noqa: F401


def load_chapter_schema() -> dict:
    """Load the canonical chapter JSON schema."""
    import json
    return json.loads(CHAPTER_SCHEMA_PATH.read_text(encoding="utf-8"))
