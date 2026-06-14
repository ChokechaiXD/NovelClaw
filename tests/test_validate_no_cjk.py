"""test_validate_no_cjk.py — Lock down CJK leakage detection.

The output of every translation MUST be Thai-only (PROMPT.md Section 1a).
This tool enforces that rule. These tests lock down:
  - extract_body_lines (H1 + Source footer exclusion)
  - check_chapter (body + marker detection)
  - strict mode (also flag CJK in H1)
  - 【】/《》 marker handling (allowed markers, CN inside markers is a leak)

Note: uses `tempfile.mkdtemp()` instead of pytest's `tmp_path` fixture
because pytest's tmp_path hits Windows PermissionError on this host.
"""
import re
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))

import pytest  # noqa: E402

import validate_no_cjk  # noqa: E402


@pytest.fixture
def ch_dir(monkeypatch):
    """Create a fresh temp dir and patch validate_no_cjk.CHAPTERS to it."""
    root = Path(tempfile.mkdtemp(prefix='novelclaw_cjk_'))
    chapters = root / 'chapters'
    chapters.mkdir()
    monkeypatch.setattr(validate_no_cjk, 'CHAPTERS', chapters)
    return chapters


# ── extract_body_lines ───────────────────────────────────────────────

class TestExtractBodyLines:
    """H1 + Source footer are excluded from CJK scan."""

    def test_excludes_h1_title(self):
        text = '# 第一章 開局\n\nข้อความภาษาไทย\n'
        body = validate_no_cjk.extract_body_lines(text)
        body_text = '\n'.join(body)
        assert '第一章' not in body_text
        assert 'ข้อความภาษาไทย' in body_text

    def test_excludes_source_footer_after_separator(self):
        text = (
            '# Chapter 5\n'
            '\n'
            'ข้อความภาษาไทย\n'
            '\n'
            '---\n'
            '\n'
            '*Source: ch 5 (第五章 開局)*\n'
        )
        body = validate_no_cjk.extract_body_lines(text)
        body_text = '\n'.join(body)
        assert '第五章 開局' not in body_text
        assert 'ข้อความภาษาไทย' in body_text

    def test_first_separator_wins(self):
        """Only the first '---' marks the footer; later ones stay in body."""
        text = (
            '## Heading\n'
            '\n'
            '---break---\n'
            '\n'
            'body after fake break\n'
        )
        body = validate_no_cjk.extract_body_lines(text)
        # Body should include "---break---" (not treated as separator)
        assert any('---break---' in line for line in body)


# ── check_chapter: clean files ───────────────────────────────────────

class TestCheckChapterClean:
    """Clean Thai-only files produce empty leak lists."""

    def test_pure_thai_is_clean(self, ch_dir):
        (ch_dir / '0001.md').write_text(
            '# Chapter 1\n\nข้อความภาษาไทยล้วน\n',
            encoding='utf-8',
        )
        body, marker = validate_no_cjk.check_chapter(1)
        assert body == []
        assert marker == []

    def test_returns_none_when_file_missing(self, ch_dir):
        body, marker = validate_no_cjk.check_chapter(9999)
        assert body is None
        assert marker is None


# ── check_chapter: CJK leakage detection ─────────────────────────────

class TestCheckChapterLeaks:
    """Detect CN/JP/KR characters in body and markers."""

    def test_detects_cjk_in_body(self, ch_dir):
        (ch_dir / '0001.md').write_text(
            '# Chapter 1\n\nข้อความผสม這是中文\n',
            encoding='utf-8',
        )
        body, marker = validate_no_cjk.check_chapter(1)
        assert '這' in body
        assert '是' in body
        assert '中' in body
        assert '文' in body

    def test_allows_cjk_in_source_footer(self, ch_dir):
        """*Source: ch N (CN title)* is allowed (footer excluded)."""
        (ch_dir / '0001.md').write_text(
            '# Chapter 1\n\nข้อความภาษาไทย\n\n---\n\n*Source: ch 1 (第一章)*\n',
            encoding='utf-8',
        )
        body, marker = validate_no_cjk.check_chapter(1)
        assert body == []
        assert marker == []

    def test_detects_cjk_inside_system_marker(self, ch_dir):
        """CN inside 【】 is a leak (markers allowed, content not)."""
        (ch_dir / '0001.md').write_text(
            '# Chapter 1\n\nข้อความ【系統提示】\n',
            encoding='utf-8',
        )
        body, marker = validate_no_cjk.check_chapter(1)
        # The 【...】 block is stripped from body, so body has no CN
        assert body == []
        # But CN inside 【】 is flagged in marker_issues
        assert len(marker) > 0
        assert any('系' in m or '統' in m for m in marker)

    def test_allows_cjk_inside_title_marker(self, ch_dir):
        """CN inside 《》 is allowed (game titles, donor names)."""
        (ch_dir / '0001.md').write_text(
            '# Chapter 1\n\n《全球降臨》เกม\n',
            encoding='utf-8',
        )
        body, marker = validate_no_cjk.check_chapter(1)
        assert body == []
        assert marker == []


# ── strict mode ──────────────────────────────────────────────────────

class TestStrictMode:
    """--strict also flags CJK in the H1 title line."""

    def test_strict_flags_cjk_in_h1(self, ch_dir):
        (ch_dir / '0001.md').write_text(
            '# 第一章 開局\n\nข้อความภาษาไทย\n',
            encoding='utf-8',
        )
        # Non-strict: H1 is excluded
        body_ns, _ = validate_no_cjk.check_chapter(1, strict=False)
        assert body_ns == []
        # Strict: H1 CJK is flagged
        body_s, _ = validate_no_cjk.check_chapter(1, strict=True)
        assert len(body_s) > 0
        assert '第' in body_s


# ── CJK pattern coverage ─────────────────────────────────────────────

class TestCjkPattern:
    """The CJK pattern covers CN, JP, KR ranges."""

    def test_pattern_matches_chinese(self):
        assert validate_no_cjk.CJK_PATTERN.search('中') is not None
        assert validate_no_cjk.CJK_PATTERN.search('繁體字') is not None

    def test_pattern_matches_japanese_kana(self):
        assert validate_no_cjk.CJK_PATTERN.search('ひらがな') is not None
        assert validate_no_cjk.CJK_PATTERN.search('カタカナ') is not None

    def test_pattern_matches_korean(self):
        assert validate_no_cjk.CJK_PATTERN.search('한글') is not None

    def test_pattern_does_not_match_thai(self):
        assert validate_no_cjk.CJK_PATTERN.search('ก') is None
        assert validate_no_cjk.CJK_PATTERN.search('ข้อความ') is None

    def test_pattern_does_not_match_brackets(self):
        """【 and 】 are in the CJK range but our pattern excludes them."""
        # 【 = U+3010, 】 = U+3011 (not in CJK_PATTERN ranges)
        assert validate_no_cjk.CJK_PATTERN.search('【') is None
        assert validate_no_cjk.CJK_PATTERN.search('】') is None
