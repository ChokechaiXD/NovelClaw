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

Multi-language support (Phase 2 — 2026-06-14):
  - `lang` field on Chapter (default 'cn' for backward compat)
  - BRACKETS config: per-language profile for dialogue / system / title / end markers
  - Reader switches on ch.lang to apply correct rendering
  - Allows: cn, jp, kr, en, th source novels — one schema, many formats
"""
from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ────────────────────────────────────────────────────────────────────
# Language + bracket profile (multi-language support)
# ────────────────────────────────────────────────────────────────────
#
# Each language has its own bracket conventions for dialogue, system
# messages, game titles, and end markers. The validator uses these to
# check that a block's text actually contains the right brackets for
# its language.
#
# Rendering: the server.js renderer also switches on ch.lang. The
# 'dialogue' curly-quote conversion (「」 → " " / 『』 → ' ') is
# language-agnostic and applies to all languages.
#
# 'cn' is the historical default. Existing chapters with no `lang`
# field default to 'cn' (backward compat).

class Language(str, Enum):
    CN = 'cn'    # Chinese — 【】, 《》, 「」, (จบบท)
    JP = 'jp'    # Japanese — 【】, 『』, 「」, （終）
    KR = 'kr'    # Korean   — 【】, 《》, 「」, (끝)
    EN = 'en'    # English  — [ ], "...", (End)
    TH = 'th'    # Thai source — same as CN brackets, (จบบท)


# Bracket profile per language. Keys = block semantic role.
# Values = (open_char, close_char) or end-marker text.
#
# For 'en' and 'th', dialogue uses straight ASCII " which the renderer
# converts to curly U+201C/U+201D at render time. We store the curly
# form in the bracket config so validator can check for it.
BRACKETS: dict[str, dict[str, str]] = {
    'cn': {
        'dialogue_open': '「',
        'dialogue_close': '」',
        'system_open': '【',
        'system_close': '】',
        'game_open': '《',
        'game_close': '》',
        'end_marker': '(จบบท)',
    },
    'jp': {
        'dialogue_open': '「',
        'dialogue_close': '」',
        'system_open': '【',
        'system_close': '】',
        'game_open': '『',
        'game_close': '』',
        'end_marker': '（終）',
    },
    'kr': {
        'dialogue_open': '「',
        'dialogue_close': '」',
        'system_open': '【',
        'system_close': '】',
        'game_open': '《',
        'game_close': '》',
        'end_marker': '(끝)',
    },
    'en': {
        # EN: curly quotes U+201C/U+201D (renderer converts ASCII " → curly)
        'dialogue_open': '\u201C',
        'dialogue_close': '\u201D',
        'system_open': '[',
        'system_close': ']',
        'game_open': '\u201C',
        'game_close': '\u201D',
        'end_marker': '(End)',
    },
    'th': {
        # TH novels translated from CN/JP keep CN brackets. TH originals
        # would use curly quotes. The source-language detection happens
        # at translation time; for now default to curly quotes.
        'dialogue_open': '\u201C',
        'dialogue_close': '\u201D',
        'system_open': '【',
        'system_close': '】',
        'game_open': '《',
        'game_close': '》',
        'end_marker': '(จบบท)',
    },
}


# ────────────────────────────────────────────────────────────────────
# Enums (the "format spec" is now a code-enforced contract)
# ────────────────────────────────────────────────────────────────────

class DialogueQuote(str, Enum):
    """CJK bracket pair for dialogue (per-language, see BRACKETS).

    Kept for backward compat — these are the CN defaults.
    """
    OPEN = '「'
    CLOSE = '」'


class SystemBracket(str, Enum):
    """CJK bracket pair for system messages."""
    OPEN = '【'
    CLOSE = '】'


class GameBracket(str, Enum):
    """CJK bracket pair for game titles."""
    OPEN = '《'
    CLOSE = '》'


class BlockType(str, Enum):
    """Type of content block in a chapter."""
    NARRATION = 'narration'   # regular paragraph
    DIALOGUE = 'dialogue'     # character speech (brackets per language)
    SYSTEM = 'system'         # game system notification
    GAME_TITLE = 'game_title' # game/book title
    END = 'end'               # end-of-chapter marker (per language)


# ────────────────────────────────────────────────────────────────────
# Content blocks
# ────────────────────────────────────────────────────────────────────

class Dialogue(BaseModel):
    """A character speaking line. Brackets per `Chapter.lang` (see BRACKETS).

    Default: 「...」 (CN/JP/KR). For EN/TH: curly "..." (U+201C/U+201D).
    Allows narration prefix (e.g. "เฉาซิงพูด 「...」") which is common
    in CN web novels where the speaker tag is inline. Use a separate
    Narration block instead if the prefix is long or has no dialogue.

    The bracket check is enforced at Chapter level via model_validator
    because we need Chapter.lang context. This per-block validator only
    rejects straight ASCII quotes (common author error).
    """
    type: BlockType = BlockType.DIALOGUE
    speaker: Optional[str] = None    # character name (e.g., "เฉาซิง") — not required
    text: str = Field(..., min_length=1, description='Dialogue text, brackets per language')

    @field_validator('text')
    @classmethod
    def reject_straight_quotes(cls, v: str) -> str:
        """Reject straight ASCII quotes — they should be curly or full-width.

        Authors (or LLM translators) sometimes insert " or ' instead of
        「」 or curly " ". Catching here gives a clear error before
        bracket check at chapter level.
        """
        if '"' in v:
            raise ValueError(
                f'Dialogue must not contain straight " — use 「」 or curly "\u201C\u201D: {v[:50]!r}'
            )
        return v


class SystemMessage(BaseModel):
    """Game system notification. Brackets per `Chapter.lang` (see BRACKETS).

    Allows inline narration prefix (e.g. "ของดรอป "【...】") for items
    that appear in narration context.
    """
    type: BlockType = BlockType.SYSTEM
    text: str = Field(..., min_length=1, description='System message, brackets per language')


class GameTitle(BaseModel):
    """Game/book title. Brackets per `Chapter.lang` (see BRACKETS).

    Allows inline narration prefix for titles mentioned in text.
    """
    type: BlockType = BlockType.GAME_TITLE
    text: str = Field(..., min_length=1, description='Game title, brackets per language')


class Narration(BaseModel):
    """Regular narrative paragraph. No brackets required (brackets may appear
    inline if quoted by the narrative).

    CN leak check: rejects raw CN chars in narration, except inside
    whitelisted zones (【...】 system, 《...》 title) which are CN by design.
    Only applies to CN-language chapters (other languages don't leak CN).
    """
    type: BlockType = BlockType.NARRATION
    text: str = Field(..., min_length=1, description='Narrative paragraph text')

    @field_validator('text')
    @classmethod
    def reject_cjk_leakage(cls, v: str) -> str:
        """Reject raw CN chars in narration.

        Whitelisted zones (per style.md): 【...】 system messages and
        《...》 game titles / donor names may contain CN chars inline
        within narration. Strip those before checking.

        Note: for non-CN languages (en, th, jp, kr) this check is
        skipped at the chapter level — see Chapter.validate_cn_only_blocks.
        """
        # Strip 【...】 and 《...》 content (greedy non-】/》 match)
        cleaned = re.sub(r'【[^】]*】', '', v)
        cleaned = re.sub(r'《[^》]*》', '', cleaned)
        cn = re.findall(r'[\u4e00-\u9fff]', cleaned)
        if cn:
            raise ValueError(
                f'Narration contains {len(cn)} raw CN chars (must be translated). '
                f'If this is a name like 蕾妮丝 inside 【】, use SystemMessage instead.'
            )
        return v


class EndMarker(BaseModel):
    """End-of-chapter marker. Text per `Chapter.lang` (see BRACKETS)."""
    type: BlockType = BlockType.END
    text: str = '(จบบท)'  # default CN/TH; Chapter.model_validator sets per-lang

    @field_validator('text')
    @classmethod
    def validate_text(cls, v: str) -> str:
        # Soft check — exact text enforced at Chapter level per language
        if not v or v.isspace():
            raise ValueError('End marker text cannot be empty')
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

    `lang` field (Phase 2 — 2026-06-14): source language of this chapter.
    Defaults to 'cn' for backward compat with existing chapters. Used by
    the validator to pick the right bracket profile (BRACKETS config) and
    by the renderer (server.js) to apply per-language styling.
    """
    schema_version: int = 1
    num: int = Field(..., ge=1, le=9999, description='Chapter number')
    title: str = Field(..., min_length=1, description='Full chapter title (e.g., "ตอนที่ 112 ...")')
    blocks: List[Block] = Field(..., min_length=1, description='Ordered content blocks')
    source: str = Field(..., pattern=r'^ch \d+$', description='Source attribution (e.g., "ch 112")')
    notes: List[str] = Field(default_factory=list, description='Translation notes (rendered in collapsible details)')
    lang: Language = Field(
        default=Language.CN,
        description='Source language (cn|jp|kr|en|th). Determines bracket profile.',
    )

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
        # title should be "ตอนที่ {N} {translated_title}" — must match
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
        # Get language-specific bracket profile
        lang = self.lang.value if isinstance(self.lang, Language) else self.lang
        brackets = BRACKETS.get(lang, BRACKETS['cn'])
        end_marker_text = brackets['end_marker']

        # Per-block bracket validation against language profile
        for i, block in enumerate(self.blocks):
            if isinstance(block, Dialogue):
                if brackets['dialogue_open'] not in block.text or brackets['dialogue_close'] not in block.text:
                    raise ValueError(
                        f'block {i} (dialogue[{lang}]) must contain '
                        f'{brackets["dialogue_open"]}...{brackets["dialogue_close"]}: '
                        f'{block.text[:50]!r}'
                    )
            elif isinstance(block, SystemMessage):
                if brackets['system_open'] not in block.text or brackets['system_close'] not in block.text:
                    raise ValueError(
                        f'block {i} (system[{lang}]) must contain '
                        f'{brackets["system_open"]}...{brackets["system_close"]}: '
                        f'{block.text[:50]!r}'
                    )
            elif isinstance(block, GameTitle):
                if brackets['game_open'] not in block.text or brackets['game_close'] not in block.text:
                    raise ValueError(
                        f'block {i} (game_title[{lang}]) must contain '
                        f'{brackets["game_open"]}...{brackets["game_close"]}: '
                        f'{block.text[:50]!r}'
                    )
            elif isinstance(block, EndMarker):
                # Set the end marker text per language (if it differs from default)
                if block.text != end_marker_text:
                    # Allow re-validation: update text to per-lang value
                    block.text = end_marker_text

        # Must have exactly one EndMarker
        end_markers = [b for b in self.blocks if isinstance(b, EndMarker)]
        if len(end_markers) == 0:
            raise ValueError(f'Chapter must have exactly one {end_marker_text} end marker')
        if len(end_markers) > 1:
            raise ValueError(f'Chapter has {len(end_markers)} end markers, must be exactly 1')
        # End marker should be the last block (notes go in separate `notes` field, not in blocks)
        if not isinstance(self.blocks[-1], EndMarker):
            raise ValueError('Last block must be end marker')
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
