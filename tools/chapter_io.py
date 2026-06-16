"""chapter_io.py — Chapter file I/O helpers.

Load, save, path resolution, and markdown-to-JSON migration for Chapter
objects. Imports the Chapter model and BLOCK_TYPE_MAP from schema.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Tuple

from tools.schema import BLOCK_TYPE_MAP, Chapter


def load_chapter(path) -> Chapter:
    """Load a ch from a .json file. Returns validated Chapter."""
    p = Path(path)
    data = json.loads(p.read_text(encoding='utf-8'))
    return Chapter(**data)


def save_chapter(ch: Chapter, path) -> None:
    """Save a Chapter to a .json file. Pretty-printed for git diff."""
    p = Path(path)
    p.write_text(
        json.dumps(ch.model_dump(), ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def chapter_path(novel_root, num: int) -> Path:
    """Get the canonical path for a ch: chapters/NNNN.json"""
    return Path(novel_root) / 'chapters' / f'{num:04d}.json'


def md_to_blocks(md_text: str) -> Tuple[List[dict], List[str]]:
    """Migrate a legacy .md file to JSON blocks (best-effort, lossy for
    complex formatting).

    Used for one-time migration of ch 1-100 from .md to .json.
    """
    # Strip meta footer
    parts = re.split(r'\n---\n', md_text, maxsplit=1)
    body = parts[0].strip()
    meta = parts[1].strip() if len(parts) > 1 else ''

    blocks = []
    for line in body.split('\n'):
        line = line.rstrip()
        if not line:
            continue
        # Title
        if line.startswith('# '):
            continue  # title handled separately
        # End marker
        if line.strip() == '(จบบท)':
            blocks.append({'type': 'end', 'text': '(จบบท)'})
            continue
        # System message
        if line.startswith('【') and line.endswith('】'):
            blocks.append({'type': 'system', 'text': line})
            continue
        # Dialogue
        if line.startswith('「') and line.endswith('」'):
            blocks.append({'type': 'dialogue', 'text': line})
            continue
        # Game title (inline) — keep as narration
        # Otherwise narration
        blocks.append({'type': 'narration', 'text': line})

    # Extract notes from meta
    notes = []
    if meta:
        for line in meta.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                notes.append(line[2:])
    return blocks, notes
