"""Tests for tools/translation_memory.py — source→translation cache + thread safety."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from tools.translation_memory import TranslationMemory


def test_source_hash_key():
    """Same source text → same hash key."""
    tm = TranslationMemory("test")
    assert tm._source_hash_key("hello") == tm._source_hash_key("hello")


def test_source_hash_different():
    """Different source text → different hash key."""
    tm = TranslationMemory("test")
    assert tm._source_hash_key("hello") != tm._source_hash_key("world")


def test_get_source_translation_miss(tmp_path, monkeypatch):
    """Unknown source returns None."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    assert tm.get_source_translation("unknown text") is None


def test_put_and_get_source_translation(tmp_path, monkeypatch):
    """Store and retrieve chapter by source hash."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    
    chapter = {
        "num": 42,
        "title": "ตอนที่ 42",
        "blocks": [
            {"type": "narration", "text": "hello"},
            {"type": "end", "text": "(จบบท)"},
        ],
        "source": "ch 42",
        "lang": "cn",
        "output_lang": "th",
    }
    
    tm.put_source_translation("source text", chapter)
    
    cached = tm.get_source_translation("source text")
    assert cached is not None
    assert cached["num"] == 42
    assert cached["title"] == "ตอนที่ 42"
    assert len(cached["blocks"]) == 2


def test_source_translation_persistence(tmp_path, monkeypatch):
    """Source cache survives save/load round-trip."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    # Write
    tm1 = TranslationMemory("test-slug")
    tm1._path = tmp_path / ".test_tm" / "test-slug.json"
    tm1.put_source_translation("test source", {"num": 1, "title": "Ch1", "blocks": [], "source": "ch 1"})
    
    # Read fresh instance
    tm2 = TranslationMemory("test-slug")
    tm2._path = tmp_path / ".test_tm" / "test-slug.json"
    tm2._loaded = False
    cached = tm2.get_source_translation("test source")
    assert cached is not None
    assert cached["num"] == 1


def test_source_cache_miss_wrong_text(tmp_path, monkeypatch):
    """Different source text → miss."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    tm.put_source_translation("hello", {"num": 1, "title": "H", "blocks": [], "source": "h"})
    
    assert tm.get_source_translation("world") is None
    assert tm.get_source_translation("hello") is not None
