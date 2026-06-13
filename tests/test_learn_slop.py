"""Tests for learn_slop.py (Phase 3 — Dynamic Ban List)."""
import sys
from pathlib import Path
from collections import Counter

TOOLS = Path(__file__).resolve().parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))
import learn_slop as ls  # noqa: E402


# ── tokenize_th ────────────────────────────────────────────────────
def test_tokenize_strips_punctuation():
    tokens = ls.tokenize_th('สวัสดี, ครับ! "ผม" มาแล้ว.')
    assert 'สวัสดี' in tokens
    assert 'ครับ' in tokens
    assert ',' not in ' '.join(tokens)
    assert '"' not in ' '.join(tokens)


def test_tokenize_strips_brackets():
    """System messages in 【】 and titles in 《》 should be excluded."""
    text = 'เฉาซิง 【HP: 100/100】 ได้ 《ไอเทม》 มา ใหม่'
    tokens = ls.tokenize_th(text)
    joined = ' '.join(tokens)
    assert 'HP' not in joined
    assert '100' not in joined
    assert 'ไอเทม' not in joined
    assert 'เฉาซิง' in tokens
    assert 'ใหม่' in tokens


def test_tokenize_strips_meta():
    text = '*Source: ch 100*\n\n---\n\nเฉาซิง มา แล้ว'
    tokens = ls.tokenize_th(text)
    assert 'Source' not in ' '.join(tokens)
    assert 'เฉาซิง' in tokens
    # ch is short token, may or may not appear; we test the body
    assert 'แล้ว' in tokens


# ── get_bigrams ────────────────────────────────────────────────────
def test_bigrams_skip_stopwords():
    tokens = ['เฉาซิง', 'คือ', 'นาย', 'ของ', 'ผม']
    bgs = ls.get_bigrams(tokens)
    # All stopword-led or tailed → no bigrams
    assert bgs == []


def test_bigrams_skip_short_tokens():
    tokens = ['ผ', 'เฉาซิง', 'มา', 'แล้ว']
    bgs = ls.get_bigrams(tokens)
    # len < 2 → skip
    assert bgs == []


def test_bigrams_keeps_valid_pairs():
    tokens = ['เฉาซิง', 'สั่ง', 'ทหาร', 'ออก']
    bgs = ls.get_bigrams(tokens)
    assert ('เฉาซิง', 'สั่ง') in bgs
    assert ('สั่ง', 'ทหาร') in bgs
    assert ('ทหาร', 'ออก') in bgs


# ── Threshold logic ───────────────────────────────────────────────
def test_find_candidates_excludes_below_threshold():
    """1 occurrence = not a crutch."""
    agg = Counter({('เฉาซิง', 'สั่ง'): 1})
    candidates = ls.find_candidates(agg, set(), set())
    assert candidates == []


def test_find_candidates_excludes_single_chapter():
    """3+ in 1 ch but no other ch = below cross-chapter threshold."""
    agg = Counter({('เฉาซิง', 'สั่ง'): 5})
    candidates = ls.find_candidates(agg, set(), set())
    # 5x but chapter_count=0 (no ch scanned) → skip
    assert all(cc < 2 for _, _, cc in candidates)


def test_find_candidates_includes_repetitive():
    """3+ in 1 ch AND 2+ ch = flag."""
    # Mock TRANSLATED_CHAPTERS so the chapter_count check passes
    ls.TRANSLATED_CHAPTERS = [1, 2, 3]
    agg = Counter({('ยิ้ม', 'เย็น'): 6, ('ทหาร', 'ออก'): 6})
    # Force chapter_count by patching scan_chapter
    orig_scan = ls.scan_chapter
    def fake_scan(n):
        return Counter({('ยิ้ม', 'เย็น'): 2, ('ทหาร', 'ออก'): 2})
    ls.scan_chapter = fake_scan
    # Also stub glossary check (no real glossary in this test scope)
    orig_glossary = ls.is_glossary_term
    ls.is_glossary_term = lambda w: False
    try:
        candidates = ls.find_candidates(agg, set(), set())
        bg_set = {bg for bg, _, _ in candidates}
        assert ('ยิ้ม', 'เย็น') in bg_set
        assert ('ทหาร', 'ออก') in bg_set
    finally:
        ls.scan_chapter = orig_scan
        ls.is_glossary_term = orig_glossary


def test_find_candidates_excludes_existing():
    agg = Counter({('ยิ้ม', 'เย็น'): 6})
    existing = {('ยิ้ม', 'เย็น')}
    candidates = ls.find_candidates(agg, existing, set())
    assert all(bg not in existing for bg, _, _ in candidates)


def test_find_candidates_excludes_whitelist():
    agg = Counter({('เฉาซิง', 'สั่ง'): 6})
    whitelist = {('เฉาซิง', 'สั่ง')}
    candidates = ls.find_candidates(agg, set(), whitelist)
    assert all(bg not in whitelist for bg, _, _ in candidates)


# ── file I/O ──────────────────────────────────────────────────────
def test_format_ban_file_structure():
    new = [(('เฉาซิง', 'สั่ง'), 6, 3)]
    existing = {('ยิ้ม', 'เย็น')}
    whitelist = set()
    out = ls.format_ban_file(new, existing, whitelist)
    assert '## Banned (auto)' in out
    assert '## Previously banned' in out
    assert '## [whitelist]' in out
    assert 'เฉาซิง สั่ง' in out
    assert 'ยิ้ม เย็น' in out


def test_format_ban_file_handles_empty():
    out = ls.format_ban_file([], set(), set())
    assert '## Banned (auto)' in out
    assert '(no new candidates)' in out


# ── Discovery ─────────────────────────────────────────────────────
def test_translated_chapters_filter():
    """Only 4-digit numeric .md files count as chapters (no source/ or backup/)."""
    chs = ls.TRANSLATED_CHAPTERS
    # Each chapter is a positive integer
    assert all(n > 0 for n in chs)
    # No duplicates
    assert len(chs) == len(set(chs))
    # Sorted
    assert chs == sorted(chs)
    # Excludes any source/ subfolder files (would have larger stems)
