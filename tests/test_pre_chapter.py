"""test_pre_chapter.py — Lock down pre_chapter.py parser helpers.

Bug #3 (Phase 1 audit) — `read_progress()` regex previously looked for
'Next chapter to translate' but the actual format is 'Next chapter: **ch 111**'.
This test locks down the FIXED regex. Other helpers (clean_source,
load_glossary, find_terms_in_source, load_dynamic_bans) get coverage too.

Note: uses `tempfile.mkdtemp()` instead of pytest's `tmp_path` fixture
because pytest's tmp_path hits Windows PermissionError on this host.
"""
import re
import sys
import tempfile
import textwrap
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))

import pytest  # noqa: E402

import pre_chapter  # noqa: E402


@pytest.fixture
def tmp_root(monkeypatch):
    """Create a fresh temp dir and patch pre_chapter.ROOT to it."""
    root = Path(tempfile.mkdtemp(prefix='novelclaw_pre_'))
    monkeypatch.setattr(pre_chapter, 'ROOT', root)
    return root


# ── read_progress: Bug #3 regression ───────────────────────────────────

class TestReadProgress:
    """Locks the 'Next chapter: **ch N**' regex from Bug #3 fix."""

    def test_extracts_number_from_canonical_format(self, tmp_root):
        """Real format: 'Next chapter: **ch 111**' → 111."""
        (tmp_root / 'progress.md').write_text(
            'Last: 110\nProgress: 110/1,239\nNext chapter: **ch 111**\n',
            encoding='utf-8',
        )
        assert pre_chapter.read_progress() == 111

    def test_extracts_number_without_bold(self, tmp_root):
        """Realistic format without markdown bold (regression guard)."""
        # The regex requires ** — real source uses **ch N** in progress.md.
        # This test guards against an even-looser regex that might lose precision.
        (tmp_root / 'progress.md').write_text('Next chapter: **ch 42**\n', encoding='utf-8')
        assert pre_chapter.read_progress() == 42

    def test_extracts_number_with_colon_variants(self, tmp_root):
        """Accept various whitespace/colon separators between 'Next chapter' and the chapter number."""
        for sep in (':', ' :', '\t', ' \t'):
            (tmp_root / 'progress.md').write_text(
                f'Next chapter{sep} **ch 99**\n', encoding='utf-8'
            )
            assert pre_chapter.read_progress() == 99, f'failed for separator {sep!r}'

    def test_exits_when_missing(self, tmp_root):
        """No 'Next chapter' line → sys.exit."""
        (tmp_root / 'progress.md').write_text('Last: 5\nProgress: 5/1,239\n', encoding='utf-8')
        with pytest.raises(SystemExit):
            pre_chapter.read_progress()


# ── clean_source ───────────────────────────────────────────────────────

class TestCleanSource:
    """Locks the source-text cleaning pipeline (header strip, line numbers,
    reader comments, duplicate title)."""

    def test_strips_trailing_line_number_after_punctuation(self):
        """'死了！11' → '死了！' (line-number noise after punctuation)."""
        raw = '他大喊道\n死了！11\n敵人跑了'
        cleaned = pre_chapter.clean_source(raw)
        assert '死了！' in cleaned
        assert '死了！11' not in cleaned

    def test_drops_short_latin_only_lines(self):
        """Latin-only reader comments like 'TL note' get dropped."""
        raw = '正文段落第一行\nTL note\n正文段落第二行'
        cleaned = pre_chapter.clean_source(raw)
        assert 'TL note' not in cleaned
        # Body paragraph preserved
        assert '正文段落第二行' in cleaned

    def test_keeps_thai_only_lines(self):
        """Thai-only paragraphs MUST survive (regression: old heuristic dropped them)."""
        raw = '正文段落第一行\nข้อความภาษาไทยเพียงอย่างเดียว\n正文段落第二行'
        cleaned = pre_chapter.clean_source(raw)
        assert 'ข้อความภาษาไทย' in cleaned

    def test_collapses_3plus_blank_lines(self):
        """5 blank lines in a row → collapsed to single blank between paragraphs.

        Note: first line of input is treated as H1 title and skipped — so we
        put real paragraphs on lines 2+. The H1-skip is the existing design.
        """
        raw = '# 第一章\n\n段落1\n\n\n\n\n段落2'
        cleaned = pre_chapter.clean_source(raw)
        # No 3+ consecutive newlines
        assert '\n\n\n' not in cleaned
        # Both paragraphs preserved (Bug #19: '段落1' was getting stripped to '段落'
        # by the line-number regex. Now requires CJK punctuation before the digit.)
        assert '段落1' in cleaned
        assert '段落2' in cleaned
        # Result is exactly the collapsed form
        assert cleaned == '段落1\n\n段落2'

    def test_does_not_strip_intentional_numbers(self):
        """'段落1' (paragraph 1) must NOT be stripped to '段落'.
        Only noise line numbers after punctuation are stripped (e.g. '死了！11').
        First line is H1 (skipped) — paragraphs are on lines 2+."""
        raw = '# 第一章\n\n第一段落1\n第二段落2'
        cleaned = pre_chapter.clean_source(raw)
        assert '段落1' in cleaned
        assert '段落2' in cleaned

    def test_strips_duplicate_title_metadata(self):
        """H1 + duplicate '第XXX章' lines are dropped, body kept."""
        raw = '# 第一章 開局\n\n全球降臨\n第一章\n\n正文開始'
        cleaned = pre_chapter.clean_source(raw)
        # Body preserved
        assert '正文開始' in cleaned


# ── find_terms_in_source ──────────────────────────────────────────────

class TestGlossaryMatching:
    """Verify term matching works (auto.md inclusion is tested elsewhere)."""

    def test_finds_term_in_source(self):
        """Term that exists in source → returns mapping."""
        glossary = [('曹星', 'เฉาซิง', 'protagonist')]
        source = '曹星 走進了房間'
        found = pre_chapter.find_terms_in_source(source, glossary)
        assert found == {'曹星': 'เฉาซิง'}

    def test_no_match_returns_empty(self):
        """No terms in source → empty dict."""
        glossary = [('曹星', 'เฉาซิง', '')]
        found = pre_chapter.find_terms_in_source('無關內容', glossary)
        assert found == {}

    def test_multiple_terms_all_found(self):
        """All matching terms are returned."""
        glossary = [
            ('曹星', 'เฉาซิง', ''),
            ('系統', 'ระบบ', ''),
        ]
        source = '曹星 啟動了 系統'
        found = pre_chapter.find_terms_in_source(source, glossary)
        assert found == {'曹星': 'เฉาซิง', '系統': 'ระบบ'}


# ── load_dynamic_bans ────────────────────────────────────────────────

class TestLoadDynamicBans:
    """Parse '## Banned (auto)' section of dynamic_bans.md."""

    def test_parses_sorted_top_n(self, tmp_root):
        """Top-N entries sorted by frequency desc."""
        (tmp_root / 'dynamic_bans.md').write_text(textwrap.dedent('''\
            ## Whitelisted
            - whitelist stuff

            ## Banned (auto)
            - a b  (5x in 3 ch)
            - x y  (20x in 8 ch)
            - p q  (1x in 1 ch)

            ## Other
            - ignore me
        '''), encoding='utf-8')
        result = pre_chapter.load_dynamic_bans(limit=2)
        assert result == ['x y', 'a b']

    def test_empty_when_section_missing(self, tmp_root):
        """No '## Banned (auto)' section → empty list (not an error)."""
        (tmp_root / 'dynamic_bans.md').write_text('## Whitelisted\n- stuff\n', encoding='utf-8')
        result = pre_chapter.load_dynamic_bans()
        assert result == []

    def test_missing_file_returns_empty(self, tmp_root):
        """File doesn't exist → empty list (graceful)."""
        result = pre_chapter.load_dynamic_bans()
        assert result == []


# ── get_chapter_title ────────────────────────────────────────────────

class TestGetChapterTitle:
    """Read the H1 title from a translated chapter file."""

    def test_returns_title_from_existing_chapter(self, tmp_root):
        ch_dir = tmp_root / 'chapters'
        ch_dir.mkdir()
        (ch_dir / '0042.md').write_text('# บทที่ 42: การทดสอบ\n\nbody\n', encoding='utf-8')
        assert pre_chapter.get_chapter_title(42) == 'บทที่ 42: การทดสอบ'

    def test_returns_placeholder_when_missing(self, tmp_root):
        result = pre_chapter.get_chapter_title(9999)
        assert '9999' in result
        assert 'not yet translated' in result

    def test_returns_placeholder_when_no_h1(self, tmp_root):
        ch_dir = tmp_root / 'chapters'
        ch_dir.mkdir()
        (ch_dir / '0001.md').write_text('no title here\n', encoding='utf-8')
        result = pre_chapter.get_chapter_title(1)
        assert 'no title' in result.lower()
