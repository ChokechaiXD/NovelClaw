"""test_glossary_gate.py — Pre-translate guard (Tier 2 critical path).

Locks down the behavior of:
  - extract_cn_terms() — finds 2-4 char CN sequences
  - STOPWORDS filter — excludes common Chinese particles
  - load_glossary_source_set() — loads all CN source terms
  - load_dynamic_bans() — loads banned terms
  - scan_chapter() — full gate logic
  - format_report() — pretty-print report

The gate catches new CN terms BEFORE translation, preventing the leak
that cn_checker (post-translate) would otherwise find.

Note: uses `tempfile.mkdtemp()` instead of pytest's `tmp_path` fixture
because pytest's tmp_path hits Windows PermissionError on this host.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Make tools/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import pytest  # noqa: E402

import glossary_gate as gg  # noqa: E402


@pytest.fixture
def tmp_src():
    """Provide a fresh source/ dir as Path (cleaned up after test)."""
    d = Path(tempfile.mkdtemp(prefix="gate_test_"))
    src = d / "source"
    src.mkdir()
    yield src
    shutil.rmtree(d, ignore_errors=True)


class TestExtractCNTerms:
    """Extracts 2-4 char CJK sequences as term candidates (with overlap)."""

    def test_basic_extraction(self):
        text = '曹星走路到目的地'
        terms = gg.extract_cn_terms(text)
        # "曹星" (2-char) should appear
        assert '曹星' in terms
        assert terms['曹星'] == 1

    def test_count_occurrences(self):
        text = '曹星和曹星一起，曹星笑'
        terms = gg.extract_cn_terms(text)
        # 曹星 appears 3 times
        assert terms['曹星'] == 3

    def test_min_len_filter(self):
        text = '曹星走路'
        terms = gg.extract_cn_terms(text, min_len=3)
        # 2-char terms excluded
        assert '曹星' not in terms
        assert '曹星走' in terms  # 3-char term still there

    def test_max_len_filter(self):
        text = '這是一個很長的詞語結構'
        terms = gg.extract_cn_terms(text, max_len=2)
        # 3+ char terms excluded (e.g. 這是一, 一個很, 個很長)
        assert '這是一' not in terms
        assert '一個很' not in terms
        # 2-char terms included
        assert '這是' in terms
        assert '一個' in terms  # 2 chars at position 2-3

    def test_empty_text(self):
        assert gg.extract_cn_terms('') == {}

    def test_no_cjk_text(self):
        text = 'hello world 123'
        assert gg.extract_cn_terms(text) == {}

    def test_substring_in_glossary_too(self):
        """If a longer term is in glossary, its substrings may also be 'known'."""
        text = '冰封城很大 冰封城很高'  # 冰封城 appears 2x
        terms = gg.extract_cn_terms(text)
        # Both 冰封城 and 封城 are frequent
        assert terms['冰封城'] == 2
        assert terms['封城'] == 2  # substring of frequent term


class TestStopwords:
    """Common Chinese particles are filtered out."""

    def test_conjunctions_excluded(self):
        for word in ('然後', '不過', '果然', '所以', '但是'):
            assert word in gg.STOPWORDS, f'{word} should be in stopwords'

    def test_verbs_excluded(self):
        for word in ('點頭', '看著', '說道', '笑道', '問道'):
            assert word in gg.STOPWORDS, f'{word} should be in stopwords'

    def test_site_nav_excluded(self):
        for word in ('首頁', '上一章', '下一章', '字體', '加入書籤'):
            assert word in gg.STOPWORDS, f'{word} should be in stopwords'

    def test_real_names_not_excluded(self):
        for word in ('曹星', '蕾妮丝', '冰封城', '野豬戰士'):
            assert word not in gg.STOPWORDS, f'{word} is a real term, should NOT be in stopwords'


class TestLoadGlossarySourceSet:
    """Loads all CN source terms from glossary.yml."""

    def test_returns_set(self):
        src_set = gg.load_glossary_source_set()
        assert isinstance(src_set, set)

    def test_contains_known_terms(self):
        src_set = gg.load_glossary_source_set()
        # 曹星 should be in glossary (it's the main character)
        assert '曹星' in src_set


class TestLoadDynamicBans:
    """Loads banned CN terms from dynamic_bans.md."""

    def test_returns_set(self):
        bans = gg.load_dynamic_bans()
        assert isinstance(bans, set)

    def test_no_error_if_missing(self, monkeypatch):
        """If dynamic_bans.md doesn't exist, return empty set."""
        # Patch the path to a non-existent file
        d = Path(tempfile.mkdtemp(prefix="gate_dynban_"))
        try:
            monkeypatch.setattr(gg, 'DYNAMIC_BANS_FILE', d / 'missing.md')
            assert gg.load_dynamic_bans() == set()
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestScanChapter:
    """Full gate logic — known / banned / new terms."""

    def test_source_not_found(self, monkeypatch, tmp_src):
        monkeypatch.setattr(gg, 'SOURCE_DIR', tmp_src)
        result = gg.scan_chapter(999)
        assert 'error' in result
        assert result['num'] == 999

    def test_clean_chapter_passes(self, monkeypatch, tmp_src):
        """All CN terms in source are in glossary → gate passed."""
        src = tmp_src / '0001.md'
        src.write_text('曹星和蕾妮丝一起去打猎', encoding='utf-8')
        monkeypatch.setattr(gg, 'SOURCE_DIR', tmp_src)
        result = gg.scan_chapter(1)
        assert result['gate_passed'] is True
        assert len(result['terms_new']) == 0

    def test_new_term_fails(self, monkeypatch, tmp_src):
        """A term not in glossary → gate fails."""
        src = tmp_src / '0001.md'
        # 冰封城 appears 3x, not in stopwords, not in glossary
        src.write_text('冰封城很大，冰封城有城墙，冰封城很冷', encoding='utf-8')
        monkeypatch.setattr(gg, 'SOURCE_DIR', tmp_src)
        # Patch the STOPWORDS to be empty so 冰封城 is detected
        monkeypatch.setattr(gg, 'STOPWORDS', frozenset())
        # Patch glossary to be empty
        monkeypatch.setattr(gg, 'load_glossary_source_set', lambda: set())
        result = gg.scan_chapter(1)
        assert result['gate_passed'] is False
        assert any(t == '冰封城' for t, _ in result['terms_new'])

    def test_banned_term_not_counted_as_new(self, monkeypatch, tmp_src):
        src = tmp_src / '0001.md'
        src.write_text('领主是领主，领主来了', encoding='utf-8')
        monkeypatch.setattr(gg, 'SOURCE_DIR', tmp_src)
        monkeypatch.setattr(gg, 'STOPWORDS', frozenset())
        monkeypatch.setattr(gg, 'load_dynamic_bans', lambda: {'领主'})
        monkeypatch.setattr(gg, 'load_glossary_source_set', lambda: set())
        result = gg.scan_chapter(1)
        assert '领主' not in [t for t, _ in result['terms_new']]
        assert '领主' in [t for t, _ in result['terms_banned']]

    def test_min_occurrences_filter(self, monkeypatch, tmp_src):
        """Terms appearing only once are excluded at min_occurrences=2."""
        src = tmp_src / '0001.md'
        src.write_text('冰封城在北方 仅仅一次', encoding='utf-8')
        monkeypatch.setattr(gg, 'SOURCE_DIR', tmp_src)
        monkeypatch.setattr(gg, 'STOPWORDS', frozenset())
        monkeypatch.setattr(gg, 'load_glossary_source_set', lambda: set())
        result = gg.scan_chapter(1, min_occurrences=2)
        # 冰封城 appears once, filtered out
        assert all(t != '冰封城' for t, _ in result['terms_new'])

    def test_stopwords_excluded(self, monkeypatch, tmp_src):
        """Common words in STOPWORDS are excluded from the gate."""
        src = tmp_src / '0001.md'
        src.write_text('然後他不過然後說道', encoding='utf-8')
        monkeypatch.setattr(gg, 'SOURCE_DIR', tmp_src)
        monkeypatch.setattr(gg, 'load_glossary_source_set', lambda: set())
        result = gg.scan_chapter(1)
        # All should be filtered out as stopwords
        new_terms = [t for t, _ in result['terms_new']]
        assert '然後' not in new_terms
        assert '不過' not in new_terms
        assert '說道' not in new_terms


class TestFormatReport:
    """Pretty-print the gate result."""

    def test_error_format(self):
        result = {'error': 'Source not found', 'num': 99}
        report = gg.format_report(result)
        assert 'Source not found' in report

    def test_passed_report(self, monkeypatch, tmp_src):
        src = tmp_src / '0001.md'
        src.write_text('曹星和蕾妮丝', encoding='utf-8')
        monkeypatch.setattr(gg, 'SOURCE_DIR', tmp_src)
        result = gg.scan_chapter(1)
        report = gg.format_report(result)
        assert 'GATE PASSED' in report

    def test_failed_report_shows_new_terms(self, monkeypatch, tmp_src):
        src = tmp_src / '0001.md'
        src.write_text('冰封城很大 冰封城很高 冰封城很美', encoding='utf-8')
        monkeypatch.setattr(gg, 'SOURCE_DIR', tmp_src)
        monkeypatch.setattr(gg, 'STOPWORDS', frozenset())
        monkeypatch.setattr(gg, 'load_glossary_source_set', lambda: set())
        result = gg.scan_chapter(1)
        report = gg.format_report(result, suggest=True)
        assert 'GATE FAILED' in report
        assert '冰封城' in report
        assert 'NEEDS TRANSLATION' in report  # from suggest
