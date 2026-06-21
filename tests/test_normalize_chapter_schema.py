"""Tests for normalize_chapter_schema.py — JSON chapter normalizer."""

from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# Mock brackets.json to avoid file dependency
import normalize_chapter_schema as ncs


class TestExpectedEndMarker:
    def test_default_thai(self):
        """When brackets.json unavailable, returns '(จบบท)'."""
        old = ncs._brackets_data
        ncs._brackets_data = {}
        try:
            assert ncs.expected_end_marker("th") == "(จบบท)"
        finally:
            ncs._brackets_data = old

    def test_configurable(self):
        old = ncs._brackets_data
        ncs._brackets_data = {"th": {"end_marker": "(จบตอน)"}}
        try:
            assert ncs.expected_end_marker("th") == "(จบตอน)"
        finally:
            ncs._brackets_data = old


class TestNormalizeChapter:
    def test_basic_normalization(self):
        data = {
            "format": "v2",
            "num": 1,
            "title": "test",
            "output_lang": "th",
            "blocks": [{"type": "dialogue", "text": "hello"}]
        }
        out, changes = ncs.normalize_chapter(data, 1, "cn", "th")
        assert out["schema_version"] == 2
        assert "format" not in out
        assert out["lang"] == "cn"
        assert out["source"] == "ch 1"
        assert len(changes) >= 3

    def test_title_clean(self):
        """Title that doesn't start with 'ตอนที่' gets prefixed."""
        data = {"num": 5, "title": "สวัสดี", "output_lang": "th", "blocks": []}
        out, _ = ncs.normalize_chapter(data, 5, "cn", "th")
        assert "ตอนที่ 5: สวัสดี" in out["title"]

    def test_title_with_existing_prefix(self):
        data = {"num": 5, "title": "ตอนที่ 5 สวัสดี", "output_lang": "th", "blocks": []}
        out, _ = ncs.normalize_chapter(data, 5, "cn", "th")
        assert out["title"] == "ตอนที่ 5 สวัสดี"

    def test_missing_blocks(self):
        data = {"num": 1, "output_lang": "th"}
        out, _ = ncs.normalize_chapter(data, 1, "cn", "th")
        # normalize_chapter creates blocks[], then appends end marker
        assert len(out["blocks"]) == 1
        assert out["blocks"][0]["type"] == "end"

    def test_dialogue_speaker_added(self):
        data = {"num": 1, "output_lang": "th",
                "blocks": [{"type": "dialogue", "text": "hi"}]}
        out, changes = ncs.normalize_chapter(data, 1, "cn", "th")
        assert out["blocks"][0]["speaker"] is None
        assert any("speaker" in c for c in changes)

    def test_end_marker_appended(self):
        data = {"num": 1, "output_lang": "th", "blocks": []}
        out, _ = ncs.normalize_chapter(data, 1, "cn", "th")
        assert out["blocks"][-1]["type"] == "end"

    def test_end_marker_corrected(self):
        data = {"num": 1, "output_lang": "th",
                "blocks": [{"type": "end", "text": "(wrong)"}]}
        out, changes = ncs.normalize_chapter(data, 1, "cn", "th")
        end = [b for b in out["blocks"] if b["type"] == "end"]
        assert end[0]["text"] == "(จบบท)"
