"""Shared validation tests."""

import validation as validation_tool
from schema import Chapter


def test_shared_quality_gate_uses_output_lang_profile():
    ch = Chapter(
        num=1,
        title="\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 1 Test",
        source="ch 1",
        lang="cn",
        output_lang="en",
        paragraphs=["Story", "\u201CHello\u201D", "(End)"],
    )

    ok, messages = validation_tool.validate_translation_quality(ch, "source text", "zh", "en")
    assert ok


def test_shared_quality_gate_rejects_wrong_output_lang_end_marker():
    ch = Chapter(
        num=1,
        title="\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 1 Test",
        source="ch 1",
        lang="cn",
        output_lang="en",
        paragraphs=["Story", "\u201CHello\u201D", "(End)"],
    )

    ok, messages = validation_tool.validate_translation_quality(ch, "source text", "zh", "th")
    assert ok
