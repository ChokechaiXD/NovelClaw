"""test_anti_ai.py — Lock down the pattern-matching functions.

The original slop_detector had 858 LOC with no tests. After splitting it
into modules, this file locks down the behavior of `find_tier1/2/3`,
`find_mika_patterns`, and `find_adenaufal`.
"""
import pytest
from slop.anti_ai import (
    TIER1, TIER1_VARIANTS, TIER2, TIER3_PHRASES,
    ADENAUFAL_T4, MIKA_PATTERNS,
    find_tier1, find_tier2, find_tier3,
    find_mika_patterns, find_adenaufal,
)


# ── Tier 1: kill on sight ─────────────────────────────────────────

class TestFindTier1:
    """Tier 1: English words that are AI tells. Must catch inflections."""

    def test_basic_word_found(self):
        assert 'delve' in find_tier1('The author will delve into this topic.')

    def test_plural_caught(self):
        """'leverages' must be caught (auto-expanded to TIER1_VARIANTS)."""
        result = find_tier1('The system leverages many approaches.')
        assert 'leverages' in result

    def test_past_tense_caught(self):
        result = find_tier1('She utilized new methods.')
        assert 'utilized' in result

    def test_gerund_caught(self):
        result = find_tier1('They are leveraging the framework.')
        assert 'leveraging' in result

    def test_case_insensitive(self):
        """'DELVE' and 'Delve' should both be caught."""
        assert 'delve' in find_tier1('DELVE into this')
        assert 'delve' in find_tier1('Delve into this')

    def test_word_boundary_no_partial_match(self):
        """'delve' should NOT match 'delves' boundary-wise (it's in VARIANTS)
        but 'delver' (made-up) shouldn't match either."""
        result = find_tier1('The delver worked hard.')
        # 'delver' is not in TIER1_VARIANTS, so no match
        assert result == {}

    def test_empty_text(self):
        assert find_tier1('') == {}

    def test_no_tier1_returns_empty(self):
        """Clean narrative text → no Tier 1 hits."""
        text = 'ฉันเดินเข้าไปในห้องแล้วมองไปรอบๆ'
        assert find_tier1(text) == {}

    def test_returns_dict(self):
        assert isinstance(find_tier1('test'), dict)

    def test_count_aggregation(self):
        """Multiple occurrences of same word → single key with summed count."""
        text = 'delve delve delve into the topic'
        result = find_tier1(text)
        assert result.get('delve', 0) >= 3


class TestTier1Variants:
    """TIER1_VARIANTS must include inflections of every base word."""

    def test_includes_all_4_inflections(self):
        """For every base word in TIER1, we expect base + s + past + ing + ly
        in TIER1_VARIANTS. 5x expansion. Words ending in 'e' use the
        proper past/ing form (delved, delving) — not 'delveed'/'delveing'."""
        def _past(w):
            return w[:-1] + 'ed' if w.endswith('e') else w + 'ed'
        def _ing(w):
            return w[:-1] + 'ing' if w.endswith('e') else w + 'ing'
        for word in TIER1[:5]:  # spot-check 5
            for inflection in [word, word + 's', _past(word), _ing(word), word + 'ly']:
                assert inflection in TIER1_VARIANTS, \
                    f'{inflection!r} missing from TIER1_VARIANTS'

    def test_variants_is_tuple(self):
        """Was a list, now a tuple — immutability hint for callers."""
        assert isinstance(TIER1_VARIANTS, tuple)


# ── Tier 2: cluster words ─────────────────────────────────────────

class TestFindTier2:
    """Tier 2: words that are bad only in clusters (3+ per paragraph)."""

    def test_basic_word_found(self):
        assert 'robust' in find_tier2('A robust framework.')

    def test_plural_caught(self):
        # TIER2 doesn't auto-expand; only the base form is in the list
        text = 'The robust and robust framework is robust.'
        result = find_tier2(text)
        assert result.get('robust', 0) == 3

    def test_no_tier2_returns_empty(self):
        assert find_tier2('เขาเดินเข้ามาในห้อง') == {}


# ── Tier 3: filler phrases ────────────────────────────────────────

class TestFindTier3:
    """Tier 3: multi-word filler phrases (EN + TH + Mika crutches)."""

    def test_english_filler_found(self):
        result = find_tier3("It's worth noting that this is important.")
        assert "It's worth noting that" in result

    def test_thai_filler_found(self):
        result = find_tier3('อย่างไรก็ตาม เขายังคงยืนยัน')
        assert 'อย่างไรก็ตาม' in result

    def test_mika_crutch_found(self):
        result = find_tier3('เขารู้สึกว่ามันเป็นเรื่องยาก')
        assert 'รู้สึกว่า' in result

    def test_count_aggregation(self):
        text = 'น่าสังเกต น่าสังเกต น่าสังเกต'
        result = find_tier3(text)
        assert result.get('น่าสังเกต', 0) == 3

    def test_phrase_not_in_text(self):
        assert find_tier3('hello world') == {}


# ── Mika patterns ─────────────────────────────────────────────────

class TestFindMikaPatterns:
    """Mika-specific regex patterns: subject echo, emotion lumps, etc."""

    def test_subject_echo_caoxin(self):
        """3+ consecutive sentences starting with เฉาซิง → flag.
        Each line must end with \\n for the pattern to match 3+ times."""
        text = 'เฉาซิงเดินเข้ามา\nเฉาซิงมองไปรอบๆ\nเฉาซิงถอนหายใจ\n'
        results = find_mika_patterns(text)
        assert any('เฉาซิง' in desc for desc, _ in results)

    def test_subject_echo_two_sentences_not_flagged(self):
        """Only 2 consecutive = no echo (need 3+)."""
        text = 'เฉาซิงเดินเข้ามา\nเฉาซิงมองไปรอบๆ\nคนอื่นพูดอะไรบางอย่าง'
        results = find_mika_patterns(text)
        # No 3-streak, so no subject echo
        subject_echo_hits = [r for r in results if 'Subject echo' in r[0]]
        assert subject_echo_hits == []

    def test_weak_perception_verb_flagged(self):
        text = 'เขารู้สึกว่ามันแปลกๆ'
        results = find_mika_patterns(text)
        assert any('Weak perception' in desc for desc, _ in results)

    def test_em_dash_placeholder_pattern(self):
        """3+ em dashes in one paragraph → missing data flag."""
        text = 'แล้วเขาก็ — และ — ยัง — ไม่พูด'
        results = find_mika_patterns(text)
        assert any('em dash' in desc.lower() for desc, _ in results)

    def test_clean_text_no_patterns(self):
        text = 'เขาเดินเข้ามาในห้อง มองไปรอบๆ แล้วนั่งลง'
        results = find_mika_patterns(text)
        assert results == []

    def test_returns_list_of_tuples(self):
        results = find_mika_patterns('รู้สึกว่า')
        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], tuple)
            assert len(results[0]) == 2
            desc, snippet = results[0]
            assert isinstance(desc, str)
            assert isinstance(snippet, str)


# ── Adenaufal T4 structural patterns ──────────────────────────────

class TestFindAdenaufal:
    """Adenaufal's 16 sub-tiers (4.5-4.16). Some are EN-only, some TH."""

    def test_ing_skip_for_thai(self):
        """4.5 -ing pattern is marked 'EN only — TH skip' for TH translations.
        Pure TH text shouldn't trigger."""
        # Pure TH text — no -ing words
        text = 'เขาเดินเข้ามาในห้อง'
        results = find_adenaufal(text)
        # No -ing in this text, so empty
        assert results == []

    def test_copula_avoidance_caught_in_english(self):
        """T4.7: 'isn't just X, it's Y' pattern."""
        text = "It isn't just a tool, it's a movement."
        results = find_adenaufal(text)
        assert any('copula avoidance' in desc for desc, _ in results)

    def test_negative_parallelism_caught(self):
        """T4.11: 'not just X, but Y'."""
        text = "This is not just a book, but a manifesto."
        results = find_adenaufal(text)
        assert any('negative parallelism' in desc for desc, _ in results)

    def test_despite_challenges_caught(self):
        """T4.9: 'Despite challenges' framing."""
        text = "Despite the challenges they faced, they succeeded."
        results = find_adenaufal(text)
        assert any('Despite challenges' in desc for desc, _ in results)

    def test_clean_text_no_adenaufal(self):
        text = 'ฉันเดินเข้ามาในห้องแล้วมองไปรอบๆ'
        results = find_adenaufal(text)
        assert results == []


# ── Structural integrity ──────────────────────────────────────────

class TestPatternListSanity:
    """The lists themselves should be sane — non-empty, no typos."""

    def test_tier1_non_empty(self):
        assert len(TIER1) >= 20, f'TIER1 has only {len(TIER1)} words (expected ≥20)'

    def test_tier2_non_empty(self):
        assert len(TIER2) >= 10, f'TIER2 has only {len(TIER2)} words (expected ≥10)'

    def test_tier3_has_thai_phrases(self):
        """TIER3 must include TH translation crutches (not just EN)."""
        thai_phrases = [p for p in TIER3_PHRASES if any('\u0e00' <= c <= '\u0e7f' for c in p)]
        assert len(thai_phrases) >= 10, f'TIER3 has only {len(thai_phrases)} TH phrases'

    def test_mika_patterns_non_empty(self):
        assert len(MIKA_PATTERNS) >= 5, f'MIKA_PATTERNS has only {len(MIKA_PATTERNS)} patterns'

    def test_adenaufal_t4_non_empty(self):
        assert len(ADENAUFAL_T4) >= 4, f'ADENAUFAL_T4 has only {len(ADENAUFAL_T4)} patterns'

    def test_adenaufal_pattern_format(self):
        """Each entry must be (regex_str, description) or
        (regex_str, description, skip_flag)."""
        for entry in ADENAUFAL_T4:
            assert len(entry) in (2, 3), f'Bad ADENAUFAL_T4 entry: {entry}'
            assert isinstance(entry[0], str)  # regex
            assert isinstance(entry[1], str)  # description
