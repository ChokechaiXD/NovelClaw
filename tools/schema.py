"""schema.py — Chapter JSON schema (the new canonical format).

This replaces the markdown + regex parsing approach. Every chapter is a
JSON file matching this schema. The reader renders JSON directly — no
markdown parsing, no regex, no ambiguity.

Why JSON (not markdown):
  - Schema-validated: every ch has the same structure, by construction
  - Type-safe: dialogue is dialogue, system is system, narration is narration
  - Format drift impossible: 「」 not " is a schema constraint, not a convention
  - Easy to validate: dialogue[i].text uses 「」 — schema rejects straight "
  - Easy to render: app reads JSON, builds DOM directly
  - Easy to migrate: ch 1-100 from .md → .json, no data loss

The format spec is now CODE, not documentation. Style.md + format_spec.md
become schema enums and validators.

Schema versioning: v1 is the current schema. Future changes bump version.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ────────────────────────────────────────────────────────────────────
# Enums (the "format spec" is now a code-enforced contract)
# ────────────────────────────────────────────────────────────────────

class DialogueQuote(str, Enum):
    """Full-width CJK brackets for dialogue (format spec: no straight quotes)."""
    OPEN = '「'
    CLOSE = '」'


class SystemBracket(str, Enum):
    """Full-width CJK brackets for system messages."""
    OPEN = '【'
    CLOSE = '】'


class GameBracket(str, Enum):
    """Full-width CJK brackets for game titles."""
    OPEN = '《'
    CLOSE = '》'


class BlockType(str, Enum):
    """Type of content block in a chapter."""
    NARRATION = 'narration'   # regular paragraph
    DIALOGUE = 'dialogue'     # 「...」 character speech
    SYSTEM = 'system'         # 【...】 game system message
    GAME_TITLE = 'game_title' # 《...》 game/book title
    END = 'end'               # (จบบท) end marker


# ────────────────────────────────────────────────────────────────────
# Content blocks
# ────────────────────────────────────────────────────────────────────

class Dialogue(BaseModel):
    """A character speaking line. Enforced: text must be wrapped in 「」."""
    type: BlockType = BlockType.DIALOGUE
    speaker: Optional[str] = None    # character name (e.g., "เฉาซิง") — not required
    text: str = Field(..., min_length=1, description='Dialogue text, including 「」 brackets')

    @field_validator('text')
    @classmethod
    def validate_cjk_brackets(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith(DialogueQuote.OPEN) and v.endswith(DialogueQuote.CLOSE)):
            raise ValueError(
                f'Dialogue must be wrapped in 「」, got: {v[:50]!r}'
            )
        # Reject straight quotes inside dialogue
        if '"' in v or "'" in v:
            raise ValueError(f'Dialogue must not contain straight quotes: {v[:50]!r}')
        return v


class SystemMessage(BaseModel):
    """【...】 game system notification. Brackets included in text."""
    type: BlockType = BlockType.SYSTEM
    text: str = Field(..., min_length=1, description='System message, including 【】 brackets')

    @field_validator('text')
    @classmethod
    def validate_cjk_brackets(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith(SystemBracket.OPEN) and v.endswith(SystemBracket.CLOSE)):
            raise ValueError(f'System message must be wrapped in 【】, got: {v[:50]!r}')
        return v


class GameTitle(BaseModel):
    """《...》 game/book title. Brackets included in text."""
    type: BlockType = BlockType.GAME_TITLE
    text: str = Field(..., min_length=1, description='Game title, including 《》 brackets')

    @field_validator('text')
    @classmethod
    def validate_cjk_brackets(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith(GameBracket.OPEN) and v.endswith(GameBracket.CLOSE)):
            raise ValueError(f'Game title must be wrapped in 《》, got: {v[:50]!r}')
        return v


class Narration(BaseModel):
    """Regular narrative paragraph. No brackets required (brackets may appear
    inline if quoted by the narrative)."""
    type: BlockType = BlockType.NARRATION
    text: str = Field(..., min_length=1, description='Narrative paragraph text')

    @field_validator('text')
    @classmethod
    def reject_cjk_leakage(cls, v: str) -> str:
        """Reject raw CN chars in narration (no body text should be untranslated)."""
        cn = re.findall(r'[\u4e00-\u9fff]', v)
        if cn:
            raise ValueError(
                f'Narration contains {len(cn)} raw CN chars (must be translated). '
                f'If this is a name like 蕾妮丝 inside 【】, use SystemMessage instead.'
            )
        return v


class EndMarker(BaseModel):
    """(จบบท) end-of-chapter marker. Always exactly one per ch."""
    type: BlockType = BlockType.END
    text: str = '(จบบท)'

    @field_validator('text')
    @classmethod
    def validate_text(cls, v: str) -> str:
        if v != '(จบบท)':
            raise ValueError(f'End marker must be exactly "(จบบท)", got: {v!r}')
        return v


# Union for type-safe block lists (with discriminator)
Block = Union[Narration, Dialogue, SystemMessage, GameTitle, EndMarker]
BLOCK_TYPE_MAP = {
    'narration': Narration,
    'dialogue': Dialogue,
    'system': SystemMessage,
    'game_title': GameTitle,
    'end': EndMarker,
}


# ────────────────────────────────────────────────────────────────────
# Chapter (the unit of work)
# ────────────────────────────────────────────────────────────────────

class Chapter(BaseModel):
    """A single chapter. The new canonical format.

    Loaded from / saved to chapters/NNNN.json. Reader renders this directly.
    """
    schema_version: int = 1
    num: int = Field(..., ge=1, le=9999, description='Chapter number')
    title: str = Field(..., min_length=1, description='Full chapter title (e.g., "ตอนที่ 112 ...")')
    blocks: List[Block] = Field(..., min_length=1, description='Ordered content blocks')
    source: str = Field(..., pattern=r'^ch \d+$', description='Source attribution (e.g., "ch 112")')
    notes: List[str] = Field(default_factory=list, description='Translation notes (rendered in collapsible details)')

    @field_validator('blocks', mode='before')
    @classmethod
    def validate_blocks(cls, v):
        """Each block dict must be a valid Block subtype. Returns list of Block instances."""
        if not isinstance(v, list):
            raise ValueError('blocks must be a list')
        validated = []
        for i, block in enumerate(v):
            if isinstance(block, dict):
                btype = block.get('type')
                if btype not in BLOCK_TYPE_MAP:
                    raise ValueError(f'block {i} has invalid type {btype!r}; must be one of {list(BLOCK_TYPE_MAP.keys())}')
                validated.append(BLOCK_TYPE_MAP[btype](**block))
            else:
                # Already a Block instance (from model_validator chain)
                validated.append(block)
        return validated

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str, info) -> str:
        # title should be "ตอนที่ {N} {thai_title}" — must match
        m = re.match(r'^ตอนที่ (\d+) (.+)$', v.strip())
        if not m:
            raise ValueError(f'Title must be "ตอนที่ {{N}} {{title}}", got: {v!r}')
        # If num is also set, check consistency
        if 'num' in info.data:
            if int(m.group(1)) != info.data['num']:
                raise ValueError(
                    f'Title says ch {m.group(1)} but num is {info.data["num"]}'
                )
        return v.strip()

    @model_validator(mode='after')
    def validate_chapter_structure(self) -> 'Chapter':
        # Must have exactly one EndMarker
        end_markers = [b for b in self.blocks if isinstance(b, EndMarker)]
        if len(end_markers) == 0:
            raise ValueError('Chapter must have exactly one (จบบท) end marker')
        if len(end_markers) > 1:
            raise ValueError(f'Chapter has {len(end_markers)} end markers, must be exactly 1')
        # End marker should be the last block (notes go in separate `notes` field, not in blocks)
        if not isinstance(self.blocks[-1], EndMarker):
            raise ValueError('Last block must be (จบบท) end marker')
        # Must have at least one narrative/dialogue block
        content = [b for b in self.blocks if not isinstance(b, EndMarker)]
        if not content:
            raise ValueError('Chapter has no content blocks (only end marker)')
        return self


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def load_chapter(path) -> Chapter:
    """Load a ch from a .json file. Returns validated Chapter."""
    import json
    from pathlib import Path
    p = Path(path)
    data = json.loads(p.read_text(encoding='utf-8'))
    return Chapter(**data)


def save_chapter(ch: Chapter, path) -> None:
    """Save a Chapter to a .json file. Pretty-printed for git diff."""
    import json
    from pathlib import Path
    p = Path(path)
    p.write_text(
        json.dumps(ch.model_dump(), ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def chapter_path(novel_root, num: int) -> 'Path':
    """Get the canonical path for a ch: chapters/NNNN.json"""
    from pathlib import Path
    return Path(novel_root) / 'chapters' / f'{num:04d}.json'


def md_to_blocks(md_text: str) -> List[dict]:
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
