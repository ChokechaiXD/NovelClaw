"""test_edge_cases.py — Edge case tests for v3 paragraphs format.

All tests use the v3 paragraphs-only Chapter schema.
No block types, no BlockType enum, no block-level validators.
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
    check_en_terms,
    check_file_for_cjk_leaks,
    expected_end_marker,
    validate_translation_quality,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _ch(
    num: int = 1,
    title: str = "ตอนที่ 1 Test",
    source: str = "ch 1",
    paragraphs: list | None = None,
    lang: str = "cn",
    output_lang: str | None = None,
    profile_lang: str | None = None,
) -> Chapter:
    """Build a Chapter with minimal valid defaults (v3 paragraphs)."""
    if paragraphs is None:
        paragraphs = ["เล่าเรื่อง", "(จบบท)"]
    kwargs: dict = {"num": num, "title": title, "source": source, "paragraphs": paragraphs, "lang": lang}
    if output_lang is not None:
        kwargs["output_lang"] = output_lang
    if profile_lang is not None:
        kwargs["profile_lang"] = profile_lang
    return Chapter(**kwargs)


# ═══════════════════════════════════════════════════════════════════════
# 1. Schema Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestChapterOutputLang:
    """output_lang and profile_lang fields with paragraphs."""

    def test_accepts_output_lang(self):
        ch = _ch(output_lang="en")
        assert ch.output_lang == Language.EN

    def test_accepts_profile_lang(self):
        ch = _ch(output_lang="th", profile_lang="en")
        assert ch.profile_lang == Language.EN

    def test_output_lang_none_defaults_to_lang(self):
        ch = _ch(lang="cn")
        assert ch.lang == Language.CN


class TestChapterSerialization:
    """JSON serialization/deserialization roundtrips."""

    def test_paragraphs_roundtrip(self):
        paragraphs = ["เนื้อเรื่องตอนแรก", "「สวัสดี」", "(จบบท)"]
        ch = _ch(paragraphs=paragraphs)
        data = ch.model_dump()
        assert data["paragraphs"] == paragraphs
        assert "blocks" not in data

    def test_output_lang_roundtrip(self):
        ch = _ch(output_lang="en")
        data = ch.model_dump()
        loaded = Chapter(**data)
        assert loaded.output_lang == Language.EN

    def test_lang_default_in_json(self):
        ch = Chapter(num=1, title="ตอนที่ 1 T", paragraphs=["text", "(จบบท)"], source="ch 1")
        data = ch.model_dump()
        assert "lang" in data
        assert data["lang"] == "cn"


class TestChapterBlockEdgeCases:
    """Edge cases around content types — all use paragraphs now."""

    def test_content_markers_in_paragraphs(self):
        """Dialogue markers, system markers all live inline in paragraphs."""
        p = _ch(paragraphs=["เฉาซิงพูด 「สวัสดี」", "【ระบบ】ได้รับไอเท็ม", "(จบบท)"])
        assert "「สวัสดี」" in p.paragraphs[0]
        assert "【ระบบ】" in p.paragraphs[1]

    def test_no_block_types_present(self):
        """v3 Chapter has no 'blocks' field in JSON output."""
        ch = _ch()
        data = ch.model_dump()
        assert "blocks" not in data

    def test_paragraphs_is_list_of_strings(self):
        ch = _ch()
        for p in ch.paragraphs:
            assert isinstance(p, str), f"Expected str, got {type(p)}: {p!r}"


class TestEndMarkerValidation:
    """End marker auto-append and validation."""

    def test_auto_appends_jp_marker(self):
        ch = Chapter(num=1, title="ตอนที่ 1 T", paragraphs=["text"], source="ch 1", lang="jp")
        assert ch.paragraphs[-1] == BRACKETS["jp"]["end_marker"]

    def test_auto_appends_kr_marker(self):
        ch = Chapter(num=1, title="ตอนที่ 1 T", paragraphs=["text"], source="ch 1", lang="kr")
        assert ch.paragraphs[-1] == BRACKETS["kr"]["end_marker"]

    def test_keeps_existing_marker(self):
        ch = _ch(paragraphs=["content", "(จบบท)"])
        assert ch.paragraphs[-1] == "(จบบท)"
        assert len(ch.paragraphs) == 2


class TestExistingChaptersAllLoad:
    """All existing v3 paragraphs chapters load without error."""

    def test_all_chapters_load_as_paragraphs(self):
        chapters_dir = Path(__file__).parent.parent / "novels" / "global-descent" / "chapters"
        if not chapters_dir.exists():
            pytest.skip("No chapters dir")
        ok = 0
        for p in sorted(chapters_dir.glob("0*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            if not data.get("paragraphs"):
                continue  # skip v2 chapters
            Chapter(**data)  # raises if invalid
            ok += 1
        assert ok > 0, "no v3 chapters found to test"


# ═══════════════════════════════════════════════════════════════════════
# 2. EN Retention / Leak Detection
# ═══════════════════════════════════════════════════════════════════════


class TestENRetention:
    """EN retention patterns parsed from the CN source."""

    def test_recruiting_flagged(self):
        assert EN_RETENTION_RE.search("recruiting")
        assert not EN_RETENTION_RE.search("รับสมัคร")

    def test_level_flagged(self):
        assert EN_RETENTION_RE.search("level 50")
        assert not EN_RETENTION_RE.search("ระดับ 50")

    def test_disrespect_flagged(self):
        assert EN_RETENTION_RE.search("disrespect")
        assert not EN_RETENTION_RE.search("ไม่เคารพ")

    def test_continue_flagged(self):
        assert EN_RETENTION_RE.search("continue")
        assert not EN_RETENTION_RE.search("ต่อไป")


class TestENLeakInParagraphs:
    """EN leak detection in v3 paragraphs format."""

    def test_latin_token_hint_provides_fix(self):
        assert "รับสมัคร" == LATIN_REPLACEMENT_HINTS.get("recruiting", "")
        assert "ระดับ" == LATIN_REPLACEMENT_HINTS.get("level", "")
        assert "บัญชีดำ" == LATIN_REPLACEMENT_HINTS.get("blacklist", "")

    def test_check_en_terms_whitelisted(self):
        whitelisted, _, _ = check_en_terms("HP: 100, MP: 50")
        assert "HP" in whitelisted or "MP" in whitelisted

    def test_lowercase_en_caught_by_leak_re(self):
        assert LOWER_LATIN_LEAK_RE.search("got level 50")
        assert not LOWER_LATIN_LEAK_RE.search("ได้ระดับ 50")


# ═══════════════════════════════════════════════════════════════════════
# 3. CJK Leak Detection
# ═══════════════════════════════════════════════════════════════════════


class TestCJKLeak:
    """CJK leak detection in paragraphs."""

    def test_cn_characters_flagged(self):
        ok, msgs = validate_translation_quality(
            _ch(paragraphs=["เนื้อเรื่อง 中文ปน", "(จบบท)"]),
            "source text",
        )
        assert not ok
        assert any("CJK" in m or "paragraph" in m for m in msgs)

    def test_no_false_positive_thai(self):
        ok, msgs = validate_translation_quality(
            _ch(paragraphs=["เนื้อเรื่องภาษาไทยธรรมดา", "(จบบท)"]),
            "source text",
        )
        assert ok


class TestCJKLeakInParagraphs:
    """CJK leaks in paragraph texts are caught by validation."""

    def test_cn_in_narration_paragraph(self):
        ok, msgs = validate_translation_quality(
            _ch(paragraphs=["เฉาซิงไปที่ 森林", "(จบบท)"]),
            "source text",
        )
        assert not ok
        assert any("CJK" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════
# 4. Completeness / Length Ratio
# ═══════════════════════════════════════════════════════════════════════


class TestLengthRatio:
    """Translation length ratio checks."""

    def test_too_short_flagged(self):
        """Very short output compared to long source."""
        ok, msgs = validate_translation_quality(
            _ch(paragraphs=["สั้น", "(จบบท)"]),
            "ยาวมาก" * 200,
        )
        assert not ok
        assert any("incomplete" in m.lower() for m in msgs)

    def test_too_long_flagged(self):
        """Very long output compared to short source."""
        ok, msgs = validate_translation_quality(
            _ch(paragraphs=["ยาวมาก" * 500, "(จบบท)"]),
            "สั้น",
        )
        assert not ok
        assert any("suspiciously long" in m.lower() for m in msgs)

    def test_good_length_passes(self):
        ok, msgs = validate_translation_quality(
            _ch(paragraphs=["เนื้อเรื่องปกติความยาวพอเหมาะและสมดุลดี", "(จบบท)"]),
            "source text for ratio test",
        )
        assert ok


# ═══════════════════════════════════════════════════════════════════════
# 5. Paragraph validation in quality gates
# ═══════════════════════════════════════════════════════════════════════


class TestParagraphValidation:
    """Quality gate validation on paragraph-level content."""

    def test_narration_with_system_marker_passes(self):
        """【】 in paragraph content is fine — no block types to check."""
        ok, msgs = validate_translation_quality(
            _ch(paragraphs=["เฉาซิงเห็น 【ข้อความระบบ】 ปรากฏ", "(จบบท)"]),
            "source text",
        )
        assert ok

    def test_dialogue_with_cjk_fails(self):
        """CJK chars in any paragraph should still be caught."""
        ok, msgs = validate_translation_quality(
            _ch(paragraphs=["「สวัสดี」 有中文", "(จบบท)"]),
            "source text",
        )
        assert not ok
        assert any("CJK" in m for m in msgs)

    def test_source_artifact_in_paragraph(self):
        """Source artifacts like 求订阅 should be caught."""
        ok, msgs = validate_translation_quality(
            _ch(paragraphs=["เนื้อเรื่องปกติ", "求订阅", "(จบบท)"]),
            "source text",
        )
        assert not ok
        assert any("artifact" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════
# 6. Bracket and end-marker helpers
# ═══════════════════════════════════════════════════════════════════════


class TestBracketHelpers:
    """Bracket profile and expected end-marker lookups."""

    def test_expected_end_marker_thai(self):
        assert expected_end_marker("th") == "(จบบท)"

    def test_expected_end_marker_english(self):
        assert expected_end_marker("en") == "(End)"

    def test_expected_end_marker_jp(self):
        assert expected_end_marker("jp") == "（終）"

    def test_expected_end_marker_kr(self):
        assert expected_end_marker("kr") == "(끝)"

    def test_expected_end_marker_fallback(self):
        assert expected_end_marker("unknown") == "(จบบท)"
