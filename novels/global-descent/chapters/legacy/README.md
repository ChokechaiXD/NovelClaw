# Legacy .md chapters (archived 2026-06-14)

These markdown files are no longer the source of truth. The NovelClaw
pipeline uses `.json` files (in parent directory) for all chapters.

Why archived:
- Schema-based validation (Pydantic) is much stricter
- Doctor prefers .json over .md
- Reader renders JSON directly (no marked.js parse)
- Single source of truth format

The .md files are kept here for:
- Reference: see how old ch looked
- Audit: diff against .json if needed
- Fallback: if .json missing, doctor reads .md

If you need to convert a new ch from .md, use:
  python tools/migrate_to_json.py <ch_num>
