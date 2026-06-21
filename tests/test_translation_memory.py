"""Tests for tools/translation_memory.py — block-level translation cache."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.translation_memory import (
    TranslationMemory,
    _bigrams,
    _block_hash,
    jaccard_similarity,
    length_ratio_ok,
)


def test_bigrams():
    """Character bigrams generated correctly."""
    bg = _bigrams("hello")
    assert "he" in bg
    assert "el" in bg


def test_bigrams_short_text():
    """Very short text produces empty bigram set."""
    bg = _bigrams("a")
    assert len(bg) == 0


def test_bigrams_thai():
    """Thai text bigrams work."""
    bg = _bigrams("สวัสดี")
    assert len(bg) >= 3


def test_block_hash_deterministic():
    """Same text → same hash."""
    assert _block_hash("สวัสดี") == _block_hash("สวัสดี")


def test_block_hash_different():
    """Different text → different hash."""
    assert _block_hash("สวัสดี") != _block_hash("ลาก่อน")


def test_jaccard_similarity_identical():
    """Identical texts → Jaccard 1.0."""
    assert jaccard_similarity("สวัสดีครับ", "สวัสดีครับ") == 1.0


def test_jaccard_similarity_no_overlap():
    """Completely different texts → Jaccard 0.0."""
    assert jaccard_similarity("ABC", "XYZ") == 0.0


def test_jaccard_similarity_partial():
    """Similar texts → Jaccard between 0 and 1."""
    sim = jaccard_similarity("เฉาซิงเดินเข้ามา", "เฉาซิงเดินออกไป")
    assert 0.3 < sim < 0.99, f"Expected ~0.5-0.8, got {sim}"


def test_jaccard_similarity_empty():
    """Empty text → Jaccard 0.0."""
    assert jaccard_similarity("", "test") == 0.0


def test_length_ratio_ok():
    assert length_ratio_ok("test", "test") is True
    assert length_ratio_ok("a", "a" * 100) is False  # too different


def test_translation_memory_exact_match(tmp_path, monkeypatch):
    """Exact match returns found with 'exact' method."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    tm.clear()
    
    # Add a block
    tm.add("สวัสดีครับ", "dialogue", 1)
    tm.save()
    
    # Lookup
    found, translation, method = tm.lookup("สวัสดีครับ")
    assert found is True
    assert method == "exact"


def test_translation_memory_fuzzy_with_latin(tmp_path, monkeypatch):
    """Similar Latin text triggers fuzzy match.
    
    Uses Latin text to avoid Thai grapheme cluster issues with bigrams.
    """
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    tm.clear()
    
    tm.add("The quick brown fox jumps over the lazy dog", "narration", 1)
    tm.save()
    
    # Very similar (only 's' added — 1 char difference)
    found, _, method = tm.lookup("The quick brown fox jumps over the lazy dogs")
    assert found is True, "Should fuzzy match"
    assert method == "fuzzy"


def test_translation_memory_miss(tmp_path, monkeypatch):
    """Very different text returns not found."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    tm.clear()
    
    tm.add("เฉาซิงเดินเข้ามา", "narration", 1)
    tm.save()
    
    found, translation, method = tm.lookup("ลมพัดผ่านไปอย่างแผ่วเบา")
    assert found is False
    assert method == "miss"


def test_translation_memory_add_duplicate(tmp_path, monkeypatch):
    """Adding same block twice increments count."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    tm.clear()
    
    assert tm.add("Hello", "narration", 1) is True  # new
    assert tm.add("Hello", "narration", 2) is False  # duplicate
    assert tm._exact_cache[_block_hash("Hello")]["count"] == 2


def test_translation_memory_batch(tmp_path, monkeypatch):
    """Batch add returns correct count."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    tm.clear()
    
    blocks = [
        {"text": "Hello world", "type": "narration"},
        {"text": "How are you", "type": "dialogue"},
        {"text": "(จบบท)", "type": "end"},  # should be skipped
    ]
    added = tm.add_batch(blocks, 42)
    assert added == 2  # end block skipped


def test_translation_memory_stats(tmp_path, monkeypatch):
    """Stats returns correct counts."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    tm.clear()
    
    assert tm.stats()["blocks"] == 0
    
    tm.add("Block A", "narration", 1)
    tm.add("Block B", "dialogue", 1)
    
    s = tm.stats()
    assert s["blocks"] == 2


def test_translation_memory_persistence(tmp_path, monkeypatch):
    """Save + load round-trip preserves data."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    tm.clear()
    
    tm.add("Persist me", "narration", 1)
    tm.save()
    
    # New instance — should load from disk
    tm2 = TranslationMemory("test-slug")
    tm2._path = tmp_path / ".test_tm" / "test-slug.json"
    tm2._loaded = False
    found, _, method = tm2.lookup("Persist me")
    assert found is True


def test_clean_block_strips_quotes():
    """Clean block strips outer quotation marks."""
    from tools.translation_memory import _clean_block
    assert _clean_block('"Hello"') == "Hello"
    assert _clean_block('"สวัสดี"') == "สวัสดี"
    assert _clean_block("「ทดสอบ」") == "ทดสอบ"


def test_translation_memory_end_blocks_skipped(tmp_path, monkeypatch):
    """End marker blocks should not be cached."""
    monkeypatch.setattr("tools.translation_memory.TM_DIR_NAME", ".test_tm")
    
    tm = TranslationMemory("test-slug")
    tm._path = tmp_path / ".test_tm" / "test-slug.json"
    tm.clear()
    
    assert tm.add("(จบบท)", "end", 1) is False
    assert tm.add("(จบ)", "end", 1) is False
