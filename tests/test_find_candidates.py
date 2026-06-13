"""test_find_candidates.py — Lock down the parser helpers.

These two functions (`split_paragraphs`, `extract_numbers`) had real bugs:
  - `split_paragraphs` previously used parts[1] which broke when source had
    no `---` (it was index-error prone on certain inputs)
  - `extract_numbers` previously didn't handle `1,000` style commas, so a
    source with "10,000" would yield "10" and "000" instead of "10000"

Both bugs are now fixed. These tests lock down the fixed behavior.
"""
import pytest
from find_candidates import split_paragraphs, extract_numbers


# ── split_paragraphs ───────────────────────────────────────────────────

class TestSplitParagraphs:
    """Source CN files have no `---`, translation TH files have 2 `---`
    separators. The function must handle both."""

    def test_source_format_no_separators(self):
        """Pure CN body — no `---`, no title line."""
        text = '第一段内容。\n\n第二段内容。\n\n第三段内容。'
        result = split_paragraphs(text)
        assert result == ['第一段内容。', '第二段内容。', '第三段内容。']

    def test_translation_format_with_separators(self):
        """TH translation: `---` separates title, body, footer."""
        text = (
            '# บทที่ 71\n'
            '\n'
            'เนื้อหาย่อหน้าแรก\n'
            '\n'
            'เนื้อหาย่อหน้าที่สอง\n'
            '\n'
            '---\n'
            '\n'
            'แหล่งที่มา: biququ.com'
        )
        result = split_paragraphs(text)
        # Footer is shortest, body is longest, so we should get the body parts
        assert 'เนื้อหาย่อหน้าแรก' in result
        assert 'เนื้อหาย่อหน้าที่สอง' in result
        assert 'แหล่งที่มา' not in ' '.join(result)  # footer dropped

    def test_strips_title_line(self):
        """A `# Title` at the start of the longest part should be removed."""
        text = '# บทที่ 5\n\nย่อหน้าเดียว'
        result = split_paragraphs(text)
        assert result == ['ย่อหน้าเดียว']

    def test_empty_paragraphs_filtered(self):
        """Blank lines and whitespace-only paragraphs should be dropped."""
        text = 'เนื้อหา\n\n   \n\nเนื้อหาสอง'
        result = split_paragraphs(text)
        assert result == ['เนื้อหา', 'เนื้อหาสอง']

    def test_single_paragraph(self):
        """Single block, no double newlines."""
        result = split_paragraphs('ข้อความเดียว')
        assert result == ['ข้อความเดียว']

    def test_three_separator_blocks_picks_longest_as_body(self):
        """When there are multiple `---` blocks, pick the LONGEST one as
        body (handles cases like title|body|footer|sources)."""
        text = (
            'Title here\n\n---\n\n'
            'Short\n\n---\n\n'
            'This is the long body that we want to extract from '
            'this multi-block file. It has lots of content.\n\n'
            'Second paragraph of the long body.\n\n'
            '---\n\n'
            'Footer'
        )
        result = split_paragraphs(text)
        joined = ' '.join(result)
        assert 'long body' in joined
        assert 'Short' not in joined
        assert 'Footer' not in joined


# ── extract_numbers ────────────────────────────────────────────────────

class TestExtractNumbers:
    """Extract 2-3 digit numbers. Must handle `1,000` style commas so that
    '10,000' yields '10000' (5+ digits intentionally excluded)."""

    def test_basic_two_digit(self):
        assert extract_numbers('他有15个苹果') == {'15'}

    def test_basic_three_digit(self):
        assert extract_numbers('有150个人') == {'150'}

    def test_multiple_numbers(self):
        assert extract_numbers('等级15，力量150，敏捷200') == {'15', '150', '200'}

    def test_excludes_one_digit(self):
        """1-digit numbers are not flagged (too noisy — "1" appears
        constantly in Chinese text)."""
        result = extract_numbers('我有1个苹果和2个橘子')
        assert '1' not in result
        assert '2' not in result

    def test_excludes_four_plus_digit(self):
        """Numbers with 4+ digits are excluded — they're almost always
        years (2026) or large amounts that the heuristic doesn't help
        with for chapter completeness checks."""
        result = extract_numbers('2026年发生了12345件事')
        # 2026 IS a 4-digit number, but the regex \b\d{2,3}\b excludes it
        assert '2026' not in result
        assert '12345' not in result

    def test_handles_thousands_separator(self):
        """The whole point of the pre-clean: '1,000' must become '1000'
        before the 2-3 digit regex runs. Without the clean, you'd get
        '1' and '000' which is wrong."""
        result = extract_numbers('他有1,000个金币')
        # 1000 is 4 digits, so it's excluded. But the commas must NOT
        # leave stray 1-digit fragments.
        assert '1' not in result
        assert '000' not in result

    def test_handles_five_digit_with_comma(self):
        """10,000 → '10000' after comma strip. Still 4+ digits → excluded."""
        result = extract_numbers('奖励10,000金币')
        assert '10' not in result
        assert '000' not in result
        assert '10000' not in result

    def test_preserves_two_three_digit_around_comma(self):
        """'12,345' → '12345' (excluded) but '1,234' → '1234' (excluded).
        What we DO want: '1,234' must not fragment into '1' and '234'."""
        result = extract_numbers('从1,234人中选出150人')
        assert '150' in result
        assert '1' not in result  # no stray 1-digit fragment

    def test_returns_set(self):
        result = extract_numbers('15 15 15')
        assert isinstance(result, set)
        assert result == {'15'}  # dedup


# ── Regression: previous bugs ──────────────────────────────────────────

class TestRegressions:
    """Specific tests that would have caught the previously-fixed bugs."""

    def test_split_no_index_error_on_empty(self):
        """Earlier version used parts[1] which could IndexError."""
        # Should not raise
        result = split_paragraphs('')
        assert result == []

    def test_split_handles_thai_dashes(self):
        """Thai `—` (em-dash) is not the same as ASCII `---`."""
        text = 'เนื้อหาแรก —\n\nเนื้อหาสอง —'
        result = split_paragraphs(text)
        assert 'เนื้อหาแรก —' in result
        assert 'เนื้อหาสอง —' in result

    def test_numbers_with_embedded_dots(self):
        """Version numbers like 3.14 — should not match."""
        result = extract_numbers('圆周率3.14')
        # 3 is 1-digit (excluded), 14 is 2-digit (included)
        # But the dot in 3.14 could confuse some regexes
        # The current \b\d{2,3}\b should still find '14' (after the dot)
        assert '14' in result
