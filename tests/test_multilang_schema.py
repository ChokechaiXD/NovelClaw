"""test_multilang_schema.py — Multi-language schema tests for v3 paragraphs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import pytest  # noqa: E402
from schema import Chapter, Language, BRACKETS  # noqa: E402


def make_chapter(lang="cn", paragraphs=None):
    if paragraphs is None:
        paragraphs = ["content", "(จบบท)"]
    return Chapter(num=1, title="ตอนที่ 1 Test", paragraphs=paragraphs, source="ch 1", lang=lang)


class TestLanguageEnum:
    def test_languages_present(self):
        for lang in ("cn", "jp", "kr", "en", "th"):
            assert lang in BRACKETS, f"BRACKETS missing {lang}"

    def test_brackets_have_required_keys(self):
        for lang, b in BRACKETS.items():
            for key in ("dialogue_open", "dialogue_close", "system_open", "system_close",
                        "game_open", "game_close", "end_marker"):
                assert key in b, f"BRACKETS[{lang}] missing {key}"
                assert b[key], f"BRACKETS[{lang}][{key}] is empty"


class TestCNDefault:
    def test_default_lang_is_cn(self):
        ch = Chapter(num=1, title="ตอนที่ 1 Test", paragraphs=["hi", "(จบบท)"], source="ch 1")
        assert ch.lang == Language.CN


class TestJapanese:
    def test_jp_lang(self):
        ch = make_chapter("jp")
        assert ch.lang == Language.JP

    def test_jp_end_marker_auto_append(self):
        ch = Chapter(num=1, title="ตอนที่ 1 T", paragraphs=["text"], source="ch 1", lang="jp")
        assert ch.paragraphs[-1] == BRACKETS["jp"]["end_marker"] or ch.paragraphs[-1] == "（終）"


class TestKorean:
    def test_kr_lang(self):
        ch = make_chapter("kr")
        assert ch.lang == Language.KR


class TestEnglish:
    def test_en_lang(self):
        ch = make_chapter("en")
        assert ch.lang == Language.EN

    def test_en_end_marker_auto_append(self):
        ch = Chapter(num=1, title="ตอนที่ 1 T", paragraphs=["text"], source="ch 1", lang="en")
        assert ch.paragraphs[-1] in ("(End)", BRACKETS["en"]["end_marker"])


class TestThai:
    def test_th_lang(self):
        ch = make_chapter("th")
        assert ch.lang == Language.TH


class TestBackwardCompat:
    def test_no_lang_defaults_to_cn(self):
        ch = Chapter(num=1, title="ตอนที่ 1 Test", paragraphs=["hi", "(จบบท)"], source="ch 1")
        assert ch.lang == Language.CN

    def test_existing_chapters_load(self):
        """All existing translated chapters (v3 paragraphs format) should still parse."""
        import json
        chapters_dir = Path(__file__).parent.parent / "novels" / "global-descent" / "chapters"
        if not chapters_dir.exists():
            return
        ok = 0
        for p in sorted(chapters_dir.glob("0*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            try:
                Chapter(**data)
                ok += 1
            except Exception as e:
                # Skip v2 chapters with blocks (backward compat)
                if data.get("blocks"):
                    continue
                raise e
        assert ok > 0, "no v3 chapters found to test"


class TestSchemaVersion:
    def test_schema_version_3_default(self):
        ch = make_chapter()
        assert ch.schema_version == 3

    def test_end_marker_auto_append_missing(self):
        ch = Chapter(num=1, title="ตอนที่ 1 T", paragraphs=["first para", "second"], source="ch 1")
        assert ch.paragraphs[-1] == "(จบบท)"
        assert len(ch.paragraphs) == 3

    def test_end_marker_kept_if_present(self):
        ch = Chapter(num=1, title="ตอนที่ 1 T", paragraphs=["first", "(จบบท)"], source="ch 1")
        assert ch.paragraphs[-1] == "(จบบท)"
        assert len(ch.paragraphs) == 2
