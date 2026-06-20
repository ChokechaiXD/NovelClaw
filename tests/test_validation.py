"""Shared validation tests."""

import validation as validation_tool
from schema import Chapter


def test_shared_quality_gate_uses_output_lang_profile():
    ch = Chapter(
        num=1,
        title="ตอนที่ 1 Test",
        source="ch 1",
        lang="cn",
        output_lang="en",
        blocks=[
            {"type": "narration", "text": "Story"},
            {"type": "dialogue", "text": "“Hello”"},
            {"type": "end", "text": "(End)"},
        ],
    )

    ok, messages = validation_tool.validate_translation_quality(ch, "source text", "zh", "en")

    assert ok
    assert all("last block" not in message for message in messages)


def test_shared_quality_gate_rejects_wrong_output_lang_end_marker():
    ch = Chapter(
        num=1,
        title="ตอนที่ 1 Test",
        source="ch 1",
        lang="cn",
        output_lang="en",
        blocks=[
            {"type": "narration", "text": "Story"},
            {"type": "dialogue", "text": "“Hello”"},
            {"type": "end", "text": "(จบบท)"},
        ],
    )
    ch.blocks[-1].text = "(จบบท)"

    ok, messages = validation_tool.validate_translation_quality(ch, "source text", "zh", "en")

    assert not ok
    assert any("last block must be en end marker" in message for message in messages)


def test_shared_file_checker_reuses_profile_aware_rules():
    issues = validation_tool.check_file_for_cjk_leaks("tests/fixtures/0001-en.json")

    assert not any(issue["severity"] == "FAIL" for issue in issues)
