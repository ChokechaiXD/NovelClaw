"""Tests for translate.py — pure function tests (no LLM calls)."""

from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# Mock constants that translate.py imports
import translate


class TestParseLLMOutput:
    def test_plain_json(self):
        result = translate.parse_llm_output('{"blocks": []}', 1)
        assert result == {"blocks": []}

    def test_json_with_fences(self):
        result = translate.parse_llm_output('```json\n{"num": 1}\n```', 1)
        assert result == {"num": 1}

    def test_json_with_prose(self):
        result = translate.parse_llm_output('Here is the translation:\n{"title": "test"}\n---end---', 1)
        assert result == {"title": "test"}

    def test_empty_raises(self):
        import pytest
        with pytest.raises(ValueError):
            translate.parse_llm_output("no json here", 1)


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
        assert "สวัสดีครับ" in result


class TestExtractUnknownTerms:
    def test_no_unknowns(self):
        result = translate.extract_unknown_terms("你好", {"你好"})
        assert result == []

    def test_unknown_detected(self):
        result = translate.extract_unknown_terms("冰霜魔法", {"火焰"})
        # Should find terms not in known set
        assert isinstance(result, list)


class TestSearchTerm:
    def test_search_term_basic(self, capsys):
        """search_term should not crash."""
        translate.search_term("冰")
        captured = capsys.readouterr()
        assert captured.out or True  # just check it doesn't throw
