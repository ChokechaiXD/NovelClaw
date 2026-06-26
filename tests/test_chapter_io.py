"""Tests for tools/chapter_io.py — chapter file I/O."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure tools/ is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from translate import chapter_path, load_chapter, save_chapter
from schema import Chapter


SAMPLE_CHAPTER = Chapter(
    num=1,
    title="ตอนที่ 1 Testing",
    paragraphs=["This is a test chapter.", "(จบบท)"],
    source="ch 1",
    lang="cn",
)


def test_save_and_load_chapter(tmp_path):
    """Save a chapter to JSON, then load it back."""
    path = tmp_path / "0001.json"
    save_chapter(SAMPLE_CHAPTER, path)

    assert path.exists()
    ch = load_chapter(path)
    assert ch.num == 1
    assert ch.paragraphs == ["This is a test chapter.", "(จบบท)"]


def test_loaded_chapter_valid():
    ch = load_chapter(Path(__file__).parent.parent / "novels" / "global-descent" / "chapters" / "0001.th.json")
    assert isinstance(ch, Chapter)
    assert ch.num == 1
