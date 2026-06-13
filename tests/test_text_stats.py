"""test_text_stats.py — Lock down tokenization + n-gram analysis."""
import pytest
from slop.text_stats import (
    tokenize_th, split_sentences_th, split_paragraphs, get_ngrams,
)


class TestTokenizeTh:
    """TH text → word-ish tokens for n-gram analysis."""

    def test_basic_thai(self):
        """Thai text has no spaces → no internal split. The whole text
        becomes 1 token (tokenization isn't word-segmentation)."""
        result = tokenize_th('ฉันเดินเข้ามาในห้อง')
        assert result == ['ฉันเดินเข้ามาในห้อง']

    def test_thai_with_spaces_splits(self):
        """If spaces are present, they ARE split on."""
        result = tokenize_th('ฉัน เดิน เข้ามา ใน ห้อง')
        assert 'ฉัน' in result
        assert 'เดิน' in result
        assert 'เข้ามา' in result

    def test_keeps_thai_punctuation(self):
        """TH punctuation . ? ! is preserved per the regex."""
        result = tokenize_th('เขาพูดว่า สวัสดี. แล้วเดินออกไป')
        # "สวัสดี." should remain as a token
        assert any('สวัสดี' in t for t in result)

    def test_strips_zero_width_chars(self):
        """U+200B-U+200F and U+FEFF are zero-width and shouldn't appear
        in tokens. (These often sneak in from copy-paste.)"""
        result = tokenize_th('ฉัน\u200bเดิน\u200cเข้า\ufeffมา')
        # Tokens should not contain the zero-width chars themselves
        for tok in result:
            assert '\u200b' not in tok
            assert '\u200c' not in tok
            assert '\ufeff' not in tok

    def test_strips_markdown_sigils(self):
        """# * _ ~ ` > | should become spaces."""
        result = tokenize_th('# **หัวข้อ** ~~ลบ~~ `code`')
        for tok in result:
            assert tok[0] not in '#*_~`>|'

    def test_normalizes_newlines(self):
        """\\n and \\r both become space."""
        result = tokenize_th('เขาเดิน\nเข้ามา\rในห้อง')
        # No tokens with embedded newlines
        for tok in result:
            assert '\n' not in tok
            assert '\r' not in tok

    def test_strips_punctuation(self):
        """Non-Thai punctuation should be removed."""
        result = tokenize_th('"สวัสดี," เขาพูด.')
        # No double quotes, no commas in tokens
        for tok in result:
            assert '"' not in tok
            assert ',' not in tok

    def test_keeps_thai_punctuation(self):
        """TH punctuation . ? ! is preserved per the regex."""
        result = tokenize_th('เขาพูดว่า สวัสดี. แล้วเดินออกไป')
        # "สวัสดี." should remain
        assert any('สวัสดี' in t for t in result)

    def test_filters_single_char_tokens(self):
        """Tokens of length ≤1 are dropped (too noisy for n-grams)."""
        result = tokenize_th('ก ข ค ฉ')
        # All single chars — should be empty
        assert result == []

    def test_empty_text(self):
        assert tokenize_th('') == []

    def test_returns_list(self):
        assert isinstance(tokenize_th('ทดสอบ'), list)


class TestSplitSentencesTh:
    """Split TH text on sentence boundaries."""

    def test_basic_split(self):
        text = 'เขาเดินเข้ามา. แล้วนั่งลง. และพูดคุย.'
        result = split_sentences_th(text)
        assert len(result) == 3
        assert 'เขาเดินเข้ามา' in result[0]

    def test_strips_brackets_before_split(self):
        """【system messages】 shouldn't be treated as sentences."""
        text = 'เขาพูด【ระบบแจ้งเตือน】แล้วเดินออกไป.'
        result = split_sentences_th(text)
        # The 【】 content is stripped, leaving one continuous text
        # which gets split by periods
        for s in result:
            assert '【' not in s
            assert '】' not in s

    def test_filters_short_sentences(self):
        """Sentences shorter than 5 chars are dropped."""
        text = 'สวย. เขาเดินเข้ามาในห้อง.'
        result = split_sentences_th(text)
        # 'สวย.' is 4 chars (incl period after strip) — dropped
        # The longer one stays
        assert all(len(s) > 5 for s in result)

    def test_handles_thai_punctuation(self):
        """。 is a TH sentence-ending punctuation."""
        text = 'เขาพูด。 แล้วเดินออกไป。'
        result = split_sentences_th(text)
        assert len(result) == 2

    def test_empty_text(self):
        assert split_sentences_th('') == []


class TestSplitParagraphs:
    """Split on double-newline."""

    def test_basic(self):
        text = 'ย่อหน้าแรก\n\nย่อหน้าที่สอง\n\nย่อหน้าที่สาม'
        result = split_paragraphs(text)
        assert result == ['ย่อหน้าแรก', 'ย่อหน้าที่สอง', 'ย่อหน้าที่สาม']

    def test_strips_whitespace(self):
        text = '  เนื้อหา  \n\n  เนื้อหาสอง  '
        result = split_paragraphs(text)
        assert result == ['เนื้อหา', 'เนื้อหาสอง']

    def test_filters_empty_paragraphs(self):
        text = 'เนื้อหา\n\n\n\nเนื้อหาสอง'
        result = split_paragraphs(text)
        # Multiple blank lines should not create empty paragraphs
        assert result == ['เนื้อหา', 'เนื้อหาสอง']

    def test_single_paragraph(self):
        result = split_paragraphs('ข้อความเดียว')
        assert result == ['ข้อความเดียว']

    def test_empty_text(self):
        assert split_paragraphs('') == []


class TestGetNgrams:
    """N-gram analysis: 3-7 word sequences."""

    def test_basic_ngram(self):
        tokens = ['ฉัน', 'เดิน', 'เข้า', 'มา', 'ใน', 'ห้อง']
        ngrams = get_ngrams(tokens, n_min=3, n_max=3)
        assert ('ฉัน เดิน เข้า') in ngrams
        assert ('เดิน เข้า มา') in ngrams

    def test_ngram_range(self):
        """n_min=3, n_max=5 should generate 3, 4, 5-grams."""
        tokens = ['a', 'b', 'c', 'd', 'e']
        ngrams = get_ngrams(tokens, n_min=3, n_max=5)
        # 3-grams: 3 of them (a b c, b c d, c d e)
        # 4-grams: 2 of them
        # 5-grams: 1 of them
        # Total: 6 unique
        assert len(ngrams) == 6

    def test_thai_filter(self):
        """N-grams containing TH chars should be kept."""
        tokens = ['สวัสดี', 'ทุกคน', 'ฉัน', 'มา', 'แล้ว']
        ngrams = get_ngrams(tokens, n_min=3, n_max=3)
        assert ('สวัสดี ทุกคน ฉัน') in ngrams

    def test_word_count_filter(self):
        """N-grams with only 1 word + 2 punct should be filtered out."""
        # If an n-gram is "word,.," that's 1 word + 2 punct → filter
        tokens = ['hello', ',', '.', 'world']
        ngrams = get_ngrams(tokens, n_min=3, n_max=3)
        # "hello , ." — 1 word + 2 punct → filtered
        assert ('hello , .') not in ngrams

    def test_returns_counter(self):
        from collections import Counter
        tokens = ['a', 'b', 'c']
        ngrams = get_ngrams(tokens, n_min=3, n_max=3)
        assert isinstance(ngrams, Counter)

    def test_too_few_tokens(self):
        """If tokens < n_max, no n-grams possible."""
        tokens = ['a', 'b']
        ngrams = get_ngrams(tokens, n_min=3, n_max=5)
        assert ngrams == {}

    def test_default_ngram_range(self):
        """Default n_min=3, n_max=7."""
        tokens = [str(i) for i in range(10)]
        ngrams = get_ngrams(tokens)
        # 3+4+5+6+7 = 26 unique n-grams (10 tokens max)
        assert len(ngrams) == sum(10 - n + 1 for n in range(3, 8))
