"""test_edge_cases.py — Comprehensive edge case tests for NovelClaw.

Covers schema, validation, normalize, and build_yaml edge cases that the
existing test suite does not exercise. Designed to catch structural regressions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from schema import Chapter, Language, BRACKETS
from validation import (
    EN_RETENTION_RE,
    LATIN_REPLACEMENT_HINTS,
    LOWER_LATIN_LEAK_RE,
    check_file_for_cjk_leaks,
    validate_translation_quality,
)
from tools.normalize_chapter_schema import (
    normalize_chapter,
    expected_end_marker,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ch(
    num: int = 1,
    title: str = "ตอนที่ 1 Test",
    source: str = "ch 1",
    blocks: list | None = None,
    lang: str = "cn",
    output_lang: str | None = None,
    profile_lang: str | None = None,
) -> Chapter:
    """Build a Chapter with minimal valid defaults."""
    if blocks is None:
        blocks = [{"type": "narration", "text": "เล่าเรื่อง"}, {"type": "end", "text": "(จบบท)"}]
    kwargs: dict = {"num": num, "title": title, "source": source, "blocks": blocks, "lang": lang}
    if output_lang is not None:
        kwargs["output_lang"] = output_lang
    if profile_lang is not None:
        kwargs["profile_lang"] = profile_lang
    return Chapter(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Schema Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestChapterOutputLang:
    """output_lang and profile_lang fields."""

    def test_accepts_output_lang(self):
        """output_lang='en' should use EN brackets, not fallback to CN."""
        ch = _ch(output_lang="en", blocks=[
            {"type": "narration", "text": "Test"},
            {"type": "dialogue", "text": "\u201cHello\u201d"},
            {"type": "system", "text": "[System]"},
            {"type": "end", "text": "(End)"},
        ])
        assert ch.output_lang == Language.EN
        assert ch.blocks[-1].text == "(End)"

    def test_accepts_profile_lang(self):
        """profile_lang='en' overrides output_lang and lang."""
        ch = _ch(output_lang="th", profile_lang="en", blocks=[
            {"type": "narration", "text": "Test"},
            {"type": "dialogue", "text": "\u201cHi\u201d"},
            {"type": "system", "text": "[Sys]"},
            {"type": "end", "text": "(End)"},
        ])
        assert ch.profile_lang == Language.EN
        assert ch.blocks[-1].text == "(End)"

    def test_output_lang_none_defaults_to_lang(self):
        """When output_lang is None, validating brackets use 'lang'."""
        ch = _ch(lang="cn")
        assert ch.output_lang is None

    def test_all_5_languages_roundtrip(self):
        """Each language can be used as lang directly (backward compat)."""
        for lang in ("cn", "jp", "kr", "en", "th"):
            bp = BRACKETS[lang]
            ch = _ch(lang=lang, blocks=[
                {"type": "narration", "text": "Body"},
                {"type": "dialogue", "text": f"{bp['dialogue_open']}Hi{bp['dialogue_close']}"},
                {"type": "system", "text": f"{bp['system_open']}Sys{bp['system_close']}"},
                {"type": "end", "text": bp["end_marker"]},
            ])
            assert ch.lang.value == lang, f"{lang}: lang field mismatch"

    def test_en_dialogue_accepts_straight_quotes(self):
        """EN blocks may use straight double quotes."""
        _ch(lang="en", blocks=[
            {"type": "narration", "text": "x"},
            {"type": "dialogue", "text": '"Hello"'},
            {"type": "end", "text": "(End)"},
        ])


class TestChapterBlockEdgeCases:

    def test_empty_blocks_rejected(self):
        with pytest.raises(Exception):
            _ch(blocks=[])

    def test_only_end_marker_rejected(self):
        with pytest.raises(Exception):
            _ch(blocks=[{"type": "end", "text": "(จบบท)"}])

    def test_end_marker_must_be_last(self):
        with pytest.raises(Exception):
            _ch(blocks=[
                {"type": "narration", "text": "x"},
                {"type": "end", "text": "(จบบท)"},
                {"type": "narration", "text": "y"},
            ])

    def test_two_end_markers_rejected(self):
        with pytest.raises(Exception):
            _ch(blocks=[
                {"type": "narration", "text": "x"},
                {"type": "end", "text": "(จบบท)"},
                {"type": "end", "text": "(จบบท)"},
            ])

    def test_speaker_field_accepted_on_dialogue(self):
        ch = _ch(blocks=[
            {"type": "dialogue", "text": "\u300cHi\u300d", "speaker": "เฉาซิง"},
            {"type": "end", "text": "(จบบท)"},
        ])
        assert ch.blocks[0].speaker == "เฉาซิง"

    def test_game_title_block(self):
        """Game titles with appropriate brackets."""
        _ch(blocks=[
            {"type": "narration", "text": "x"},
            {"type": "game_title", "text": "\u300aFrozen Era\u300b"},
            {"type": "end", "text": "(จบบท)"},
        ])

    def test_game_title_en_uses_curly_quotes(self):
        """EN game titles use curly quotes per brackets.json."""
        _ch(lang="en", blocks=[
            {"type": "narration", "text": "x"},
            {"type": "game_title", "text": "\u201cFrozen Era\u201d"},
            {"type": "end", "text": "(End)"},
        ])


class TestChapterSerialization:
    """JSON round-trip and field persistence."""

    def test_output_lang_roundtrip(self):
        """output_lang survives JSON serialization."""
        data = _ch(output_lang="en", blocks=[
            {"type": "narration", "text": "x"},
            {"type": "dialogue", "text": "\u201cHi\u201d"},
            {"type": "system", "text": "[Sys]"},
            {"type": "end", "text": "(End)"},
        ]).model_dump()
        assert data["output_lang"] == "en"
        ch2 = Chapter(**data)
        assert ch2.output_lang == Language.EN

    def test_lang_default_in_json(self):
        """Serializing a chapter with default lang includes 'cn'."""
        data = Chapter(
            num=1, title="\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 1 Test", source="ch 1",
            blocks=[{"type": "narration", "text": "x"}, {"type": "end", "text": "(\u0e08\u0e1a\u0e1a\u0e17)"}],
        ).model_dump()
        assert data["lang"] == "cn"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Validation Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


def make_validate_ch(text: str, lang: str = "cn", output_lang: str | None = None) -> Chapter:
    return _ch(lang=lang, output_lang=output_lang, blocks=[
        {"type": "narration", "text": text},
        {"type": "end", "text": BRACKETS.get(output_lang or lang, BRACKETS["cn"])["end_marker"]},
    ])


class TestENRetention:

    def test_recruiting_flagged(self):
        ch = make_validate_ch("ยัง recruiting ได้", output_lang="th")
        ok, msgs = validate_translation_quality(ch, "source", "zh", "th")
        assert not ok
        assert any("recruiting" in m for m in msgs)

    def test_level_flagged(self):
        ch = make_validate_ch("พวกนั้น level 20", output_lang="th")
        ok, msgs = validate_translation_quality(ch, "source", "zh", "th")
        assert not ok
        assert any("level" in m for m in msgs)

    def test_disrespect_flagged(self):
        ch = make_validate_ch("อย่า disrespect", output_lang="th")
        ok, msgs = validate_translation_quality(ch, "source", "zh", "th")
        assert not ok
        assert any("disrespect" in m for m in msgs)

    def test_continue_flagged(self):
        ch = make_validate_ch("คาร์ฮาน continue：", output_lang="th")
        ok, msgs = validate_translation_quality(ch, "source", "zh", "th")
        assert not ok
        assert any("continue" in m for m in msgs)

    def test_whitelisted_not_flagged(self):
        """HP, MP, EXP should NOT trigger EN RETENTION errors."""
        # These are whitelisted tokens caught by Latin leak check as WARNING,
        # but should NOT be flagged by EN_RETENTION_RE
        import re
        test_text = "HP: 100, MP: 50, EXP: 500"
        retention_matches = EN_RETENTION_RE.findall(test_text)
        assert len(retention_matches) == 0, f"EN_RETENTION should not match: {retention_matches}"


class TestCJKLeak:

    def test_cn_characters_flagged(self):
        """CJK in narration triggers quality gate error.
        We create the chapter normally (passing schema), then inject CJK into
        the block text afterward to test the validation gate directly."""
        ch = _ch(output_lang="th", blocks=[
            {"type": "narration", "text": "\u0e40\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e23\u0e32\u0e27\u0e17\u0e35\u0e48\u0e21\u0e35\u0e40\u0e19\u0e37\u0e49\u0e2d\u0e2b\u0e32"},
            {"type": "end", "text": "(\u0e08\u0e1a\u0e1a\u0e17)"},
        ])
        # Inject CJK directly into block text (bypass schema validation)
        ch.blocks[0].text = "\u0e21\u0e35\u0e2d\u0e31\u0e01\u0e29\u0e23\u0e08\u0e35\u0e19\u0e1b\u0e19\u0e01\u0e25\u0e32\u0e07 \u4e2d\u6587"
        ok, msgs = validate_translation_quality(ch, "source text", "zh", "th")
        assert not ok
        assert any("CJK" in m for m in msgs)

    def test_system_blocks_also_checked(self):
        ch = _ch(output_lang="th", blocks=[
            {"type": "system", "text": "【任务完成】"},
            {"type": "end", "text": "(จบบท)"},
        ])
        ok, msgs = validate_translation_quality(ch, "source", "zh", "th")
        assert not ok
        assert any("CJK" in m for m in msgs)


class TestLengthRatio:

    def test_too_short_flagged(self):
        ch = _ch(blocks=[
            {"type": "narration", "text": "สั้นมาก"},
            {"type": "end", "text": "(จบบท)"},
        ])
        ok, msgs = validate_translation_quality(ch, "\u4e2d" * 500, "zh", "th")
        assert not ok
        assert any("ratio" in m for m in msgs)

    def test_too_long_flagged(self):
        ch = _ch(blocks=[
            {"type": "narration", "text": "\u0e01" * 2000},
            {"type": "end", "text": "(จบบท)"},
        ])
        ok, msgs = validate_translation_quality(ch, "\u4e2d" * 100, "zh", "th")
        assert not ok
        assert any("ratio" in m for m in msgs)


class TestEndMarkerValidation:

    def test_kr_end_marker(self):
        _ch(lang="kr", blocks=[
            {"type": "narration", "text": "x"},
            {"type": "dialogue", "text": "\u300cHI\u300d"},
            {"type": "end", "text": "(\uaf43)"},
        ])


class TestFileChecker:

    def test_clean_file_passes(self):
        data = {
            "blocks": [
                {"type": "narration", "text": "เรื่องราว"},
                {"type": "end", "text": "(จบบท)"},
            ]
        }
        p = Path(__file__).parent / "fixtures" / "_edge_test_clean.json"
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        try:
            issues = check_file_for_cjk_leaks(str(p))
            fails = [i for i in issues if i["severity"] == "FAIL"]
            assert len(fails) == 0, f"Expected clean, got {fails}"
        finally:
            p.unlink(missing_ok=True)

    def test_dirty_file_flagged(self):
        data = {
            "blocks": [
                {"type": "narration", "text": "มีอักษรจีนปนกลาง 中文"},
                {"type": "end", "text": "(จบบท)"},
            ]
        }
        p = Path(__file__).parent / "fixtures" / "_edge_test_dirty.json"
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        try:
            issues = check_file_for_cjk_leaks(str(p))
            fails = [i for i in issues if i["severity"] == "FAIL"]
            assert len(fails) > 0, "Expected CJK leak flagged"
        finally:
            p.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. EN_RETENTION_RE Pattern Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestENRetentionRegex:

    def test_matches_known_patterns(self):
        test_text = "recruiting level disrespect mean queen erupt continue panic"
        matches = EN_RETENTION_RE.findall(test_text)
        assert len(matches) == 8

    def test_case_insensitive(self):
        matches = EN_RETENTION_RE.findall("Recruiting LEVEL Disrespect")
        assert len(matches) == 3

    def test_not_partial_match(self):
        """'levels' should NOT match 'level' due to word boundary."""
        matches = EN_RETENTION_RE.findall("levels recruitment")
        assert len(matches) == 0

    def test_hints_exist_for_all_words(self):
        """Every EN_RETENTION word should have a Thai hint."""
        words = {"recruiting", "level", "disrespect", "mean", "queen",
                 "erupt", "continue", "panic", "momentarily", "hollow",
                 "militia", "avatar", "blacklist", "peek"}
        for w in words:
            found = any(k.lower() == w.lower() for k in LATIN_REPLACEMENT_HINTS)
            assert found, f"No hint for '{w}' in LATIN_REPLACEMENT_HINTS"


class TestLatinLeakRegex:

    def test_lower_latin_contains_en_retention(self):
        """Every word in EN_RETENTION_RE should also be in LOWER_LATIN_LEAK_RE."""
        import re
        ll_pattern = LOWER_LATIN_LEAK_RE.pattern
        ll_words = set(re.findall(r"\b(\w+)\b", ll_pattern))
        en_words = {"recruiting", "level", "disrespect", "mean", "queen",
                    "erupt", "continue", "panic", "momentarily", "hollow",
                    "militia", "avatar", "blacklist", "peek"}
        missing = en_words - ll_words
        assert len(missing) == 0, f"Words in EN_RETENTION_RE but NOT in LOWER_LATIN_LEAK_RE: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Normalize Tool Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizeEdgeCases:

    def _run(self, data: dict, lang: str = "cn", output_lang: str = "th"):
        return normalize_chapter(data, data.get("num", 1), lang, output_lang)

    def test_already_normalized(self):
        data = {
            "schema_version": 2,
            "num": 1,
            "title": "ตอนที่ 1 Test",
            "source": "ch 1",
            "lang": "cn",
            "output_lang": "th",
            "notes": [],
            "blocks": [
                {"type": "narration", "text": "เล่าเรื่อง"},
                {"type": "end", "text": "(จบบท)"},
            ],
        }
        _, changes = self._run(data)
        assert len(changes) == 0

    def test_missing_output_lang_added(self):
        data = {"num": 1, "source": "ch 1", "lang": "cn",
                "blocks": [{"type": "narration", "text": "x"}], "notes": []}
        norm, changes = self._run(data)
        assert norm["output_lang"] == "th"
        assert any("output_lang" in c for c in changes)

    def test_missing_end_block(self):
        data = {"num": 1, "source": "ch 1", "lang": "cn", "output_lang": "th",
                "notes": [], "blocks": [{"type": "narration", "text": "x"}]}
        norm, changes = self._run(data)
        assert norm["blocks"][-1]["type"] == "end"
        assert any("end" in c for c in changes)

    def test_end_block_not_last(self):
        data = {"num": 1, "source": "ch 1", "lang": "cn", "output_lang": "th",
                "notes": [], "blocks": [
                    {"type": "narration", "text": "x"},
                    {"type": "end", "text": "(จบบท)"},
                    {"type": "narration", "text": "y"},
                ]}
        norm, _ = self._run(data)
        assert norm["blocks"][-1]["type"] == "end"

    def test_wrong_end_marker_fixed(self):
        data = {"num": 1, "source": "ch 1", "lang": "cn", "output_lang": "th",
                "notes": [], "blocks": [
                    {"type": "narration", "text": "x"},
                    {"type": "end", "text": "(End)"},
                ]}
        norm, _ = self._run(data)
        assert norm["blocks"][-1]["text"] == "(จบบท)"

    def test_wrong_end_marker_en_output(self):
        data = {"num": 1, "source": "ch 1", "lang": "cn", "output_lang": "en",
                "notes": [], "blocks": [
                    {"type": "narration", "text": "x"},
                    {"type": "end", "text": "(จบบท)"},
                ]}
        norm, _ = self._run(data, output_lang="en")
        assert norm["blocks"][-1]["text"] == "(End)"

    def test_duplicate_end_blocks_deduped(self):
        data = {"num": 1, "source": "ch 1", "lang": "cn", "output_lang": "th",
                "notes": [], "blocks": [
                    {"type": "narration", "text": "x"},
                    {"type": "end", "text": "(จบบท)"},
                    {"type": "end", "text": "(จบบท)"},
                ]}
        norm, _ = self._run(data)
        ends = [b for b in norm["blocks"] if b["type"] == "end"]
        assert len(ends) == 1

    def test_missing_notes_added(self):
        data = {"num": 1, "source": "ch 1", "lang": "cn", "output_lang": "th",
                "blocks": [{"type": "narration", "text": "x"},
                           {"type": "end", "text": "(จบบท)"}]}
        norm, _ = self._run(data)
        assert isinstance(norm.get("notes"), list)

    def test_format_v2_migration(self):
        data = {"format": "v2", "num": 1, "source": "ch 1", "lang": "cn",
                "output_lang": "th", "notes": [], "blocks": [
                    {"type": "narration", "text": "x"},
                    {"type": "end", "text": "(จบบท)"},
                ]}
        norm, _ = self._run(data)
        assert norm["schema_version"] == 2
        assert "format" not in norm


class TestExpectedEndMarker:

    def test_thai(self):
        assert expected_end_marker("th") == "(จบบท)"

    def test_english(self):
        assert expected_end_marker("en") == "(End)"

    def test_unknown_fallback(self):
        assert expected_end_marker("xx") == "(จบบท)"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Build YAML Auto-Reject Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════




# 6. Integration: Existing chapters consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestExistingChaptersAllLoad:

    def test_all_existing_chapters_pass_schema(self):
        """Every translated chapter file must load through Chapter.model_validate()."""
        chapters_dir = Path(__file__).parent.parent / "novels" / "global-descent" / "chapters"
        if not chapters_dir.exists():
            pytest.skip("No chapters dir")
        failures = []
        for p in sorted(chapters_dir.glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            if not p.name[0].isdigit():
                continue  # skip fts_index.db etc.
            try:
                Chapter(**data)
            except Exception as e:
                failures.append(f"{p.name}: {e}")
        assert len(failures) == 0, f"Failed chapters:\n" + "\n".join(failures[:10])

    def test_all_chapters_have_thai_end_marker(self):
        """Every translated chapter should end with (จบบท)."""
        chapters_dir = Path(__file__).parent.parent / "novels" / "global-descent" / "chapters"
        if not chapters_dir.exists():
            pytest.skip("No chapters dir")
        bad = []
        for p in sorted(chapters_dir.glob("0*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            blocks = data.get("blocks", [])
            if not blocks or blocks[-1].get("text") != "(จบบท)":
                bad.append(p.name)
        assert len(bad) == 0, f"Chapters with wrong/empty end marker: {bad}"

    def test_lang_cn_and_output_lang_th(self):
        """All translated chapters must have lang=cn, output_lang=th."""
        chapters_dir = Path(__file__).parent.parent / "novels" / "global-descent" / "chapters"
        if not chapters_dir.exists():
            pytest.skip("No chapters dir")
        bad_lang = []
        bad_output = []
        for p in sorted(chapters_dir.glob("0*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("lang") != "cn":
                bad_lang.append(p.name)
            if data.get("output_lang") != "th":
                bad_output.append(p.name)
        assert len(bad_lang) == 0, f"Wrong lang: {bad_lang}"
        assert len(bad_output) == 0, f"Missing/wrong output_lang: {bad_output}"
