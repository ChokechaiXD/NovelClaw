"""Canonical Python path helpers for NovelClaw data files."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOVELS_DIR = PROJECT_ROOT / "novels"
SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def pad(num: int | str) -> str:
    return str(num).zfill(4)


def assert_valid_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        raise ValueError("Invalid slug format")


def novel_dir(slug: str) -> Path:
    assert_valid_slug(slug)
    return NOVELS_DIR / slug


def chapter_dir(slug: str) -> Path:
    return novel_dir(slug) / "chapters"


def chapter_path(slug: str, num: int | str, lang: str) -> Path:
    return chapter_dir(slug) / f"{pad(num)}.{lang}.json"


def source_md_path(slug: str, num: int | str) -> Path:
    return chapter_dir(slug) / "source" / f"{pad(num)}.md"


def novel_json_path(slug: str) -> Path:
    return novel_dir(slug) / "novel.json"


def chapters_index_path(slug: str) -> Path:
    return novel_dir(slug) / "chapters.json"


def glossary_json_path(slug: str) -> Path:
    return novel_dir(slug) / "glossary" / "glossary.json"

