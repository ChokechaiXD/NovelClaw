"""Tests for translate.py — pure function tests (no LLM calls)."""

from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# Mock constants that translate.py imports
import translate


class TestParseTranslationOutput:
    def test_plain_text(self):
        result = translate.parse_translation_output("ข้อความแรก\n\nข้อความที่สอง", 1)
        assert "paragraphs" in result
        assert len(result["paragraphs"]) == 3  # 2 paragraphs + end marker
        assert result["paragraphs"][-1] == "(จบบท)"

    def test_with_markers(self):
        result = translate.parse_translation_output('เธอพูด "สวัสดี"\n\n【ระบบแจ้งเตือน】', 1)
        assert "สวัสดี" in result["paragraphs"][0]
        assert "【" in result["paragraphs"][1]

    def test_with_fences(self):
        result = translate.parse_translation_output('```text\nบรรยาย\n\n"พูด"\n```', 1)
        assert len(result["paragraphs"]) >= 2
        assert result["paragraphs"][0] == "บรรยาย"

    def test_empty_raises(self):
        import pytest
        with pytest.raises(ValueError):
            translate.parse_translation_output("", 1)

    def test_schema_version(self):
        result = translate.parse_translation_output("บทนำ", 5)
        assert result["schema_version"] == 3
        assert result["num"] == 5
        assert result["output_lang"] == "th"


class TestCleanSource:
    def test_strips_line_numbers(self):
        """Line numbers after punctuation are removed."""
        result = translate.clean_source("text\n你好！1\nสวัสดี")
        assert "！1" not in result
        assert "你好" in result

    def test_strips_empty_lines(self):
        result = translate.clean_source("---\n你好\n\n\nสวัสดี\n\n\n")
        assert "你好" in result
        assert "สวัสดี" in result
        # Should have at most one blank paragraph gap
        assert "\n\n\n" not in result

    def test_identity_for_clean(self):
        result = translate.clean_source("test\nสวัสดีครับ")
        assert 'สวัสดีครับ' in result


class TestSearchTerm:
    def test_search_term_basic(self, capsys):
        """search_term should not crash."""
        translate.search_term("冰")
        captured = capsys.readouterr()
        assert captured.out or True  # just check it doesn't throw
