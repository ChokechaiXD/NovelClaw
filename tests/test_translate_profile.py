"""Translation profile helper tests."""

import translate as translate_tool
from schema import Chapter


def test_profile_lang_prefers_target_then_source_then_cn():
    assert translate_tool.get_profile_lang("zh", "th") == "th"
    assert translate_tool.get_profile_lang("zh", "en") == "en"
    assert translate_tool.get_profile_lang("xx", "unknown") == "cn"
    assert translate_tool.get_profile_lang("ja", "unknown", profile_lang="en") == "en"


def test_bracket_profile_returns_correct_brackets():
    bp = translate_tool.get_bracket_profile("zh", "th")
    assert bp["dialogue_open"] == "“"
    assert bp["end_marker"] == "(จบบท)"
