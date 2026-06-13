"""Tests for chapter_search.py (Phase 4 — FTS5 continuity)."""
import re
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))


# ── extract_chapter_text (both formats) ───────────────────────────
def _make_test_file(name: str, content: str) -> Path:
    """Helper: write to project tmp dir (avoids pytest tmp_path perm issues)."""
    import tempfile
    tmp_dir = Path(tempfile.gettempdir())
    path = tmp_dir / name
    path.write_text(content, encoding='utf-8')
    return path


def test_extract_old_format():
    """Old format: body BEFORE first ---, meta AFTER."""
    from chapter_search import extract_chapter_text
    path = _make_test_file('0071_test.md',
        '# Title 71\n\nBody content เฉาซิง\n\n---\n\n*Source: ch 71*\n')
    num, title, body = extract_chapter_text(path)
    assert num == 71
    assert title == 'Title 71'
    assert 'Body content' in body
    assert '*Source' not in body


def test_extract_new_format():
    """New format: header → --- → BODY → --- → meta."""
    from chapter_search import extract_chapter_text
    path = _make_test_file('0100_test.md',
        '# Title 100\n\n*Source: ch 100*\n\n---\n\nBody เฉาซิง\n\n---\n\nnote\n')
    num, title, body = extract_chapter_text(path)
    assert num == 100
    assert title == 'Title 100'
    assert 'Body' in body
    assert 'note' not in body
    assert '*Source' not in body


def test_extract_no_separator():
    """No --- line: whole file minus H1 is body."""
    from chapter_search import extract_chapter_text
    path = _make_test_file('0050_test.md',
        '# Title 50\n\nJust body content\n')
    num, title, body = extract_chapter_text(path)
    assert num == 50
    assert title == 'Title 50'
    assert 'Just body' in body


# ── extract_summary ───────────────────────────────────────────────
def test_extract_summary_short():
    from chapter_search import extract_summary
    body = 'Para 1\n\nPara 2\n\nPara 3 long enough\n\nPara 4'
    s = extract_summary(body, max_chars=100)
    assert 'Para 1' in s
    assert len(s) <= 100


def test_extract_summary_empty():
    from chapter_search import extract_summary
    assert extract_summary('', max_chars=100) == ''


# ── FTS5 search (integration — needs real DB) ─────────────────────
def test_build_index_idempotent():
    """Building index twice doesn't duplicate entries."""
    from chapter_search import build_index, get_conn
    build_index()
    n1 = get_conn().execute('SELECT COUNT(*) FROM chapter_fts').fetchone()[0]
    build_index()
    n2 = get_conn().execute('SELECT COUNT(*) FROM chapter_fts').fetchone()[0]
    assert n1 == n2
    assert n1 > 0  # We have 31 translated chapters


def test_search_finds_chinese():
    """CN names should match via FTS5."""
    from chapter_search import build_index, search
    build_index()
    results = search('เลนนิส')
    assert len(results) > 0
    # Top result should be ch 71 (introduction)
    assert any(r['chapter_num'] == 71 for r in results)


def test_search_excludes_target_chapter():
    """When searching for context, don't return the target itself."""
    from chapter_search import build_index, search
    build_index()
    results = search('เฉาซิง', limit=10, exclude_chapter=80)
    for r in results:
        assert r['chapter_num'] != 80


def test_search_handles_empty_query():
    from chapter_search import search
    assert search('') == []
    assert search('   ') == []


def test_search_handles_special_chars():
    """Query with special chars shouldn't crash."""
    from chapter_search import build_index, search
    build_index()
    # These should not raise
    results = search('【test】')
    assert isinstance(results, list)


# ── get_context (fallback path) ────────────────────────────────────
def test_get_context_fallback_when_no_source():
    """If target ch has no source file, fall back to recent ch summaries."""
    from chapter_search import build_index, get_context
    build_index()
    # Ch 9999 doesn't exist as source, should fall back
    results = get_context(9999, top_k=3)
    assert len(results) <= 3
    # All should be prior chapters
    for r in results:
        assert r['chapter_num'] < 9999


def test_get_context_excludes_target():
    from chapter_search import build_index, get_context
    build_index()
    results = get_context(50, top_k=5)
    for r in results:
        assert r['chapter_num'] < 50


# ── format_context_block ──────────────────────────────────────────
def test_format_context_block_structure():
    from chapter_search import build_index, format_context_block
    build_index()
    block = format_context_block(50, top_k=2)
    assert '## Cross-Chapter Context' in block
    assert '### Ch' in block
    assert 'FTS5' in block


def test_format_context_block_empty_when_no_chs():
    from chapter_search import format_context_block
    # ch 0 has no prior chapters
    block = format_context_block(0, top_k=3)
    assert block == ''


# ── Stats ─────────────────────────────────────────────────────────
def test_get_stats():
    from chapter_search import build_index, get_stats
    build_index()
    s = get_stats()
    assert s['indexed'] > 0
    assert s['last_indexed'] is not None
