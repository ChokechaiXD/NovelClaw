"""Translation profile helper tests."""

import translate as translate_tool
from schema import Chapter


def test_profile_lang_prefers_target_then_source_then_cn():
    assert translate_tool.get_profile_lang("zh", "th") == "th"
    assert translate_tool.get_profile_lang("zh", "en") == "en"
    assert translate_tool.get_profile_lang("xx", "unknown") == "cn"
    assert translate_tool.get_profile_lang("ja", "unknown", profile_lang="en") == "en"


def test_validate_quality_gates_uses_target_end_marker():
    ch = Chapter(
        num=1,
        title="ตอนที่ 1 Test",
        source="ch 1",
        blocks=[
            {"type": "narration", "text": "เล่าเรื่อง"},
            {"type": "dialogue", "text": "“Hello”"},
            {"type": "end", "text": "(End)"},
        ],
        lang="cn",
        output_lang="en",
    )

    ok, messages = translate_tool.validate_quality_gates(
        ch, "source text", source_lang="zh", target_lang="en"
    )

    assert ok
    assert all("last block" not in message for message in messages)


def test_validate_quality_gates_rejects_wrong_target_end_marker():
    ch = Chapter(
        num=1,
        title="ตอนที่ 1 Test",
        source="ch 1",
        blocks=[
            {"type": "narration", "text": "เล่าเรื่อง"},
            {"type": "dialogue", "text": "“Hello”"},
            {"type": "end", "text": "(End)"},
        ],
        lang="cn",
        output_lang="en",
    )
    ch.blocks[-1].text = "(จบบท)"

    ok, messages = translate_tool.validate_quality_gates(
        ch, "source text", source_lang="zh", target_lang="en"
    )

    assert not ok
    assert any("last block must be en end marker" in message for message in messages)
