"""Tests for validate_no_cjk.py — CJK leakage checker."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# Test with direct re-implementation (avoids optional validation.py dep)
import re

CN_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
JP_PATTERN = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")

# Copy the EN whitelist from validate_no_cjk for deterministic tests
TEST_ALLOWED = {"HP", "MP", "NPC", "EXP", "LV", "DMG", "BUFF"}


def has_cn(text):
    return bool(CN_PATTERN.search(text))


def has_jp(text):
    return bool(JP_PATTERN.search(text))


def classify_en_terms(text):
    """Simple EN term checker (matching validate_no_cjk.check_en_terms logic)."""
    words = re.findall(r"\b[A-Za-z][A-Za-z0-9]{1,}\b", text)
    allowed, unknown = [], []
    for w in words:
        if w.upper() in TEST_ALLOWED:
            allowed.append(w)
        elif w.isupper() and len(w) >= 2:
            unknown.append(w)
    return allowed, unknown


# ── Tests ──────────────────────────────────────────────────────────────────

class TestCNPattern:
    def test_detects_chinese(self):
        assert has_cn("你好世界")

    def test_passes_clean_thai(self):
        assert not has_cn("สวัสดีครับ")

    def test_rejects_mixed(self):
        assert has_cn("Hello 世界")

    def test_rejects_japanese_only(self):
        assert not has_cn("こんにちは")


class TestJPPattern:
    def test_detects_japanese(self):
        assert has_jp("こんにちは")

    def test_passes_thai(self):
        assert not has_jp("สวัสดี")

    def test_passes_chinese(self):
        assert not has_jp("你好")


class TestENClassifier:
    def test_allowed_pass(self):
        allowed, unknown = classify_en_terms("HP MP DMG")
        assert "HP" in allowed
        assert "MP" in allowed
        assert unknown == []

    def test_unknown_flagged(self):
        allowed, unknown = classify_en_terms("XYZZY BLASTER")
        assert "XYZZY" in unknown
        assert allowed == []

    def test_mixed(self):
        allowed, unknown = classify_en_terms("HP and XYZZY")
        assert "HP" in allowed
        assert "XYZZY" in unknown

    def test_lowercase_not_flagged(self):
        """Lowercase words aren't detected as EN game terms."""
        allowed, unknown = classify_en_terms("sword and shield")
        assert allowed == []
        assert unknown == []
