"""schema.py — Chapter JSON schema (v3 paragraph format only).

No block types. All content is paragraphs with inline markers.
Chapter model is lean: just validates the paragraph array + basic fields.
"""

from __future__ import annotations

import json
import os
import re
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field, model_validator


# ── Language + bracket profile ──────────────────────────────────────────

class Language(str, Enum):
    CN = 'cn'
    JP = 'jp'
    KR = 'kr'
    EN = 'en'
    TH = 'th'


# ── Bracket profiles from reader/config/brackets.json (SSOT) ──────────

_BRACKETS_PATH = Path(__file__).resolve().parent.parent / "reader" / "config" / "brackets.json"
if _BRACKETS_PATH.exists():
    BRACKETS: dict[str, dict[str, str]] = json.loads(_BRACKETS_PATH.read_text(encoding="utf-8"))
else:
    BRACKETS = {
        'cn': {'dialogue_open': '「', 'dialogue_close': '」', 'system_open': '【', 'system_close': '】',
               'game_open': '《', 'game_close': '》', 'end_marker': '(จบบท)'},
    }


# ── Shared CN regex (SSOT — import from schema) ───────────────────────

CN_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
CN_WIDE_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
CN_INLINE_RE = re.compile(r'[\u4e00-\u9fff]{2,}')


# ── Language key normalization ─────────────────────────────────────────

def normalize_language_key(key: str) -> str:
    mapping = {
        'chinese': 'zh', 'cn': 'zh',
        'thai': 'th', 'thailand': 'th',
        'english': 'en',
        'japanese': 'jp', 'japan': 'jp',
        'korean': 'kr', 'korea': 'kr',
    }
    return mapping.get(key.lower().strip(), key)


def get_lang_config_key(key: str) -> str:
    k = key.strip().lower()
    if k in ('cn', 'zh', 'zh-cn', 'chinese'):
        return 'cn'
    return k


# ── Chapter (the unit of work — paragraphs only, no blocks) ────────────

class Chapter(BaseModel):
    """A single chapter. Paragraphs with inline markers only (no block types)."""
    schema_version: int = Field(default=3, description='Schema version — v3 (paragraphs)')
    num: int = Field(..., ge=1, le=9999, description='Chapter number')
    title: str = Field(..., min_length=1)
    paragraphs: list[str] = Field(..., min_length=1, description='Content with inline markers')
    source: str = Field(..., pattern=r'^ch \d+$')
    notes: list[str] = Field(default_factory=list)
    lang: Language = Field(default=Language.CN)
    output_lang: Language | None = Field(default=None)
    profile_lang: Language | None = Field(default=None)

    @model_validator(mode='after')
    def validate_paragraphs(self) -> 'Chapter':
        if not isinstance(self.paragraphs, list) or not self.paragraphs:
            raise ValueError('paragraphs must be a non-empty list of strings')
        if self.paragraphs[-1] not in ('(จบบท)', '(End)', '（終）', '(끝)'):
            lang = self.lang.value if isinstance(self.lang, Language) else str(self.lang)
            end = BRACKETS.get(lang, {}).get('end_marker', '(จบบท)')
            self.paragraphs.append(end)
        # Validate title matches num
        m = re.match(r'^ตอนที่ (\d+)([:：\s]+(.+))?$', self.title.strip())
        if not m:
            raise ValueError(f'Title must start with "ตอนที่ {{N}}", got: {self.title!r}')
        if int(m.group(1)) != self.num:
            raise ValueError(f'Title says ch {m.group(1)} but num is {self.num}')
        return self


# ── Path constants (from constants.py, merged) ────────────────────────

TOOLS_DIR = Path(__file__).parent
PROJECT_ROOT = TOOLS_DIR.parent
NOVELS_DIR = PROJECT_ROOT / 'novels'

_DEFAULT_SLUG = os.environ.get('NOVEL_SLUG', 'global-descent')

NOVEL_ROOT = NOVELS_DIR / _DEFAULT_SLUG
GLOSSARY_DIR = NOVEL_ROOT / 'glossary'
CHAPTERS_DIR = NOVEL_ROOT / 'chapters'
SOURCE_DIR = CHAPTERS_DIR / 'source'


def get_novel_root(slug: str | None = None, check_exists: bool = True) -> Path:
    s = slug or _DEFAULT_SLUG
    path = NOVELS_DIR / s
    if check_exists and not path.exists():
        raise FileNotFoundError(
            f"Novel '{s}' not found at {path}. "
            f"Available: {[d.name for d in NOVELS_DIR.iterdir() if d.is_dir()]}"
        )
    return path


def get_chapters_dir(slug: str | None = None) -> Path:
    return get_novel_root(slug) / 'chapters'


# ── Translation quality constants (legacy) ─────────────────────────────

LENGTH_RATIO_OK = (0.6, 3.5)
NAME_CHECKS = [
    ('曹星', 'เฉาซิง', 'โจวซิง'),
    ('柳慕雪', 'หลิวมู่เสวี่ย', 'หลิวมู่สวี่'),
    ('陈江', 'เฉินเจียง', 'เฉินเจียงก'),
    ('香江', 'ฮ่องกง', 'เซียงเจียง'),
    ('极地人', 'คนเมืองหนาว', 'ชาวโพลาร์'),
]
