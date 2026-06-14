"""registry.py — Multi-novel registry (Phase 2 — 2026-06-14).

Single source of truth for which novels exist and their metadata.
Derived from `novels/<slug>/meta.md` (with optional YAML frontmatter).

The registry replaces hardcoded `novels/global-descent` paths in
tools. Future novels (CN/JP/EN/KR/TH sources, all target languages)
just need their own `meta.md` — no code changes.

Usage:
    from registry import list_novels, get_novel, novel_root, chapters_dir

    novels = list_novels()
    for n in novels:
        print(f"{n['slug']}: {n['title']} ({n['source_lang']} -> {n['target_lang']})")

    novel = get_novel('global-descent')
    ch_dir = novel['chapters_dir']

Per-novel meta.md format:
    ---
    slug: global-descent
    title: 全球降臨：帶著嫂嫂末世種田
    author: 一條小白蛇
    source_lang: cn
    target_lang: th
    source_url: https://tw.hjwzw.com/Book/Chapter/50356
    total_chapters: 1239
    status: in_progress
    ---

    # 全球降臨... (markdown body stays as documentation)

YAML frontmatter is optional. If missing, sensible defaults apply:
  - slug = directory name
  - title = slug
  - source_lang = 'cn'
  - target_lang = 'th'
  - total_chapters = 0
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


# Repo-level paths
TOOLS_DIR = Path(__file__).parent
REPO = TOOLS_DIR.parent
NOVELS_DIR = REPO / 'novels'


# ── Frontmatter parsing ─────────────────────────────────────────────

# Match YAML frontmatter: ---\n...\n---
FRONTMATTER_RE = re.compile(
    r'^---\s*\n(.*?)\n?---\s*\n?(.*)',
    re.DOTALL,
)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split meta.md into (yaml_dict, markdown_body).

    Returns ({}, text) if no frontmatter.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    yaml_block, body = m.group(1), m.group(2)
    # Minimal YAML parser (avoids PyYAML dependency for this single use).
    # Supports `key: value` (string) and `key: int` (number).
    meta = {}
    for line in yaml_block.splitlines():
        line = line.rstrip()
        if not line or line.startswith('#'):
            continue
        m2 = re.match(r'^(\w[\w_]*):\s*(.+?)\s*$', line)
        if not m2:
            continue
        key, val = m2.group(1), m2.group(2)
        # Strip surrounding quotes
        if (val.startswith('"') and val.endswith('"')) or \
           (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        # Try int
        try:
            val = int(val)
        except ValueError:
            pass
        meta[key] = val
    return meta, body


# ── Per-novel discovery ─────────────────────────────────────────────

def _read_meta(slug: str) -> dict:
    """Read meta.md for a novel, return parsed frontmatter or defaults."""
    meta_path = NOVELS_DIR / slug / 'meta.md'
    defaults = {
        'slug': slug,
        'title': slug,
        'author': '',
        'source_lang': 'cn',
        'target_lang': 'th',
        'source_url': '',
        'total_chapters': 0,
        'status': 'unknown',
    }
    if not meta_path.exists():
        return defaults
    text = meta_path.read_text(encoding='utf-8')
    parsed, _ = parse_frontmatter(text)
    return {**defaults, **parsed}


def _count_translated(slug: str) -> int:
    """Count translated chapter files (.json preferred, .md legacy).

    A chapter is "translated" if EITHER .json OR .md exists with
    the same number. .json takes precedence (new canonical).
    """
    chapters_dir = NOVELS_DIR / slug / 'chapters'
    if not chapters_dir.exists():
        return 0
    seen = set()
    for p in chapters_dir.iterdir():
        if not p.is_file():
            continue
        m = re.match(r'^(\d{4})\.(json|md)$', p.name)
        if m:
            seen.add(int(m.group(1)))
    return len(seen)


def novel_meta(slug: str) -> Optional[dict]:
    """Get full metadata for one novel.

    Returns dict with: slug, title, author, source_lang, target_lang,
    source_url, total_chapters, status, translated, root, chapters_dir,
    glossary_dir, source_dir, meta_path.

    Returns None if the slug doesn't have a meta.md (i.e. not a novel).
    """
    root = NOVELS_DIR / slug
    if not root.is_dir():
        return None
    # A novel MUST have a meta.md file — otherwise it's just a stray dir
    meta_path = root / 'meta.md'
    if not meta_path.exists():
        return None
    meta = _read_meta(slug)
    meta['root'] = root
    meta['chapters_dir'] = root / 'chapters'
    meta['glossary_dir'] = root / 'glossary'
    meta['source_dir'] = root / 'chapters' / 'source'
    meta['meta_path'] = meta_path
    meta['translated'] = _count_translated(slug)
    return meta


def list_novels() -> list[dict]:
    """Return metadata for all novels in the novels/ directory.

    Sorted by slug for stable ordering.
    """
    if not NOVELS_DIR.is_dir():
        return []
    out = []
    for entry in sorted(NOVELS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        # Skip non-novel dirs (those without meta.md)
        if not (entry / 'meta.md').exists():
            continue
        meta = novel_meta(entry.name)
        if meta is not None:
            out.append(meta)
    return out


def get_novel(slug: str) -> Optional[dict]:
    """Get one novel by slug. Returns None if not found."""
    return novel_meta(slug) if (NOVELS_DIR / slug).is_dir() else None


def get_default_novel() -> Optional[dict]:
    """Get the first novel alphabetically (for tools that take no --novel arg).

    Backward compat: tools that previously hardcoded 'global-descent' will
    fall back to this if no slug is given.
    """
    novels = list_novels()
    if not novels:
        return None
    # Prefer 'global-descent' if it exists (backward compat)
    for n in novels:
        if n['slug'] == 'global-descent':
            return n
    return novels[0]


# ── CLI for inspection ──────────────────────────────────────────────

def main():
    novels = list_novels()
    if not novels:
        print('No novels found in novels/')
        return
    print(f'=== {len(novels)} novel(s) ===\n')
    for n in novels:
        progress = f"{n['translated']}/{n['total_chapters']}" if n['total_chapters'] else f"{n['translated']}?"
        print(f"  {n['slug']}")
        print(f"    title: {n['title']}")
        print(f"    author: {n['author'] or '(unknown)'}")
        print(f"    lang: {n['source_lang']} -> {n['target_lang']}")
        print(f"    progress: {progress} ch")
        print(f"    status: {n['status']}")
        print()


if __name__ == '__main__':
    main()
