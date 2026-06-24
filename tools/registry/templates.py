"""registry/templates.py — Centralized prompt templates, repair rules, and report formats.

Re-exports from canonical sources.
Single import point for all template consumers.
"""

# ── Translate prompts ────────────────────────────────────────────────
from glossary import format_tm_prompt  # noqa: F401

# ── Repair rules ─────────────────────────────────────────────────────
from orchestrator.repair import repair_chapter  # noqa: F401

# ── Report formatting ────────────────────────────────────────────────
from orchestrator.report import novel_report  # noqa: F401

# ── Glossary terms ───────────────────────────────────────────────────
from glossary import load_terms, load_style_rules, validate_translation  # noqa: F401
