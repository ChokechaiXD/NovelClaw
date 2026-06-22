"""Tests for tools/chapter_io.py — chapter file I/O."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tools.translate import chapter_path, load_chapter, save_chapter, md_to_blocks
from tools.schema import Chapter


SAMPLE_CHAPTER = Chapter(
    num=1,
    title="ตอนที่ 1 Testing",
    blocks=[
        {"type": "narration", "text": "This is a test chapter."},
        {"type": "end", "text": "(จบบท)"},
    ],
    source="ch 1",
    lang="cn",
)


def test_save_and_load_chapter(tmp_path):
    """Save a chapter to JSON, then load it back."""
    path = tmp_path / "0001.json"
    save_chapter(SAMPLE_CHAPTER, path)
    
    assert path.exists()
    loaded = load_chapter(path)
    assert loaded.num == 1
    assert loaded.title == "ตอนที่ 1 Testing"
    assert len(loaded.blocks) == 2


def test_save_chapter_pretty_printed(tmp_path):
    """Saved JSON is pretty-printed with indent=2."""
    path = tmp_path / "0001.json"
    save_chapter(SAMPLE_CHAPTER, path)
    
    content = path.read_text(encoding="utf-8")
    assert '"indent":' not in content  # shouldn't have raw indent
    assert "  " in content  # has indentation


def test_save_chapter_ensure_ascii_false(tmp_path):
    """Thai text is not escaped."""
    path = tmp_path / "thai.json"
    save_chapter(SAMPLE_CHAPTER, path)
    
    content = path.read_text(encoding="utf-8")
    assert "ตอนที่" in content
    assert "(จบบท)" in content


def test_load_chapter_validates_schema(tmp_path):
    """Loading validates chapter via Pydantic."""
    data = {
        "num": 5,
        "title": "ตอนที่ 5 Testing",
        "blocks": [
            {"type": "narration", "text": "Chapter text"},
            {"type": "end", "text": "(จบบท)"},
        ],
        "source": "ch 5",
    }
    path = tmp_path / "0005.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    
    ch = load_chapter(path)
    assert ch.num == 5
    assert ch.title == "ตอนที่ 5 Testing"


def test_load_chapter_invalid_data(tmp_path):
    """Invalid data raises Pydantic validation error."""
    data = {
        "num": "not_a_number",  # wrong type
        "title": "",
        "blocks": [],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    
    with pytest.raises(Exception):
        load_chapter(path)


def test_chapter_path():
    """chapter_path returns chapters/NNNN.json."""
    path = chapter_path("/novels/test", 42)
    assert path.name == "0042.json"
    assert "chapters" in str(path)


def test_md_to_blocks_empty():
    """Empty markdown produces no blocks."""
    blocks, meta = md_to_blocks("")
    assert blocks == []


def test_md_to_blocks_basic():
    """Basic markdown parses into blocks."""
    md = "This is a test.\n\n---\nmeta: data"
    blocks, meta = md_to_blocks(md)
    assert len(blocks) >= 1
    assert "This is a test" in blocks[0].get("text", blocks[0].get("content", ""))


def test_md_to_blocks_no_meta():
    """Markdown without '---' separator still parses."""
    md = "Just some text without a meta footer."
    blocks, meta = md_to_blocks(md)
    assert len(blocks) >= 1
