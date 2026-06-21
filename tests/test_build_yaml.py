"""Tests for build_yaml.py — glossary Markdown table parser & YAML builder."""

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from build_yaml import (
    _split_table_row,
    _looks_like_separator,
    _looks_like_header,
    _parse_priority_and_notes,
    parse_markdown_terms,
    should_reject_auto_term,
    write_yaml,
)


class TestSplitTableRow:
    def test_standard_row(self):
        assert _split_table_row("| 冰 | น้ำแข็ง | ทั่วไป | 1 |") == ["冰", "น้ำแข็ง", "ทั่วไป", "1"]

    def test_no_pipe(self):
        assert _split_table_row("hello") == []

    def test_empty(self):
        assert _split_table_row("") == []

    def test_extra_whitespace(self):
        assert _split_table_row("|  A  |  B  |") == ["A", "B"]


class TestLooksLikeSeparator:
    def test_dash_only(self):
        assert _looks_like_separator(["---", "---", "---"])

    def test_not_separator(self):
        assert not _looks_like_separator(["A", "B", "C"])

    def test_with_colons(self):
        assert _looks_like_separator([":---", ":---:"])


class TestLooksLikeHeader:
    def test_source_thai(self):
        assert _looks_like_header(["Source", "Thai", "Category"])

    def test_not_header(self):
        assert not _looks_like_header(["A", "B", "C"])

    def test_case_insensitive(self):
        assert _looks_like_header(["SOURCE", "thai"])


class TestParsePriorityAndNotes:
    def test_priority_only(self):
        p, n = _parse_priority_and_notes(["2"], 1)
        assert p == 2
        assert n == ""

    def test_priority_with_notes(self):
        p, n = _parse_priority_and_notes(["2", "some notes"], 1)
        assert p == 2
        assert n == "some notes"

    def test_no_priority_cells(self):
        p, n = _parse_priority_and_notes([], 3)
        assert p == 3
        assert n == ""

    def test_non_numeric_uses_default(self):
        p, n = _parse_priority_and_notes(["locked"], 1)
        assert p == 1
        assert n == "locked"


class TestShouldRejectAutoTerm:
    def test_single_char_rejected(self):
        assert should_reject_auto_term("人", "ทั่วไป")

    def test_generic_term_rejected(self):
        assert should_reject_auto_term("之", "ทั่วไป")

    def test_known_compound_in_generic(self):
        # "冰霜" is in GENERIC_TERMS, should be rejected
        assert should_reject_auto_term("冰霜", "ทั่วไป")

    def test_novel_compound_pass(self):
        # "终极" is not in GENERIC_TERMS, passes
        assert not should_reject_auto_term("终极", "ทั่วไป")

    def test_empty_source(self):
        assert not should_reject_auto_term("", "ทั่วไป")


class TestParseMarkdownTerms:
    def test_parse_basic_table(self, tmp_path):
        md = tmp_path / "locked.md"
        md.write_text("| Source | Thai | Category | Priority | Notes |\n| --- | --- | --- | --- | --- |\n| 冰 | น้ำแข็ง | ทั่วไป | 1 | |\n| 炎 | เปลวไฟ | ทั่วไป | 2 | |\n", encoding="utf-8")
        terms = parse_markdown_terms(md, "locked", 1)
        assert len(terms) == 2
        assert terms[0]["source"] == "冰"
        assert terms[0]["lock"] == "locked"
        assert terms[1]["priority"] == 2

    def test_empty_file(self, tmp_path):
        md = tmp_path / "empty.md"
        md.write_text("", encoding="utf-8")
        assert parse_markdown_terms(md, "auto", 3) == []

    def test_nonexistent_file(self, tmp_path):
        assert parse_markdown_terms(tmp_path / "nope.md", "locked", 1) == []


class TestWriteYaml:
    def test_writes_valid_yaml(self, tmp_path):
        import build_yaml
        old_dir = build_yaml.NOVELS_DIR
        build_yaml.NOVELS_DIR = tmp_path
        slug = "test-novel"
        (tmp_path / slug / "glossary").mkdir(parents=True)
        terms = [{"source": "冰", "thai": "น้ำแข็ง", "category": "ทั่วไป", "priority": 1, "lock": "locked", "explanation": "", "notes": ""}]
        path = write_yaml(slug, terms)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "terms:" in content
        assert "น้ำแข็ง" in content
        build_yaml.NOVELS_DIR = old_dir
