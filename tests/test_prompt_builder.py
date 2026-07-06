from prompt_builder import PROMPT_PROFILES, build_prompt
from source_profile import build_source_profile


def test_prompt_default_has_no_quality_rule_contradictions():
    profile = build_source_profile(
        "阿星睜開眼時，城市已經變成廢墟。\n\n「走吧。」",
        source_lang="cn",
        target_lang="th",
        ch_num=1,
        lang_source="test",
    )
    prompt = build_prompt(
        source_text="阿星睜開眼時，城市已經變成廢墟。",
        ch_num=1,
        source_lang="cn",
        target_lang="th",
        novel_title="global-descent",
        source_profile=profile,
    )

    assert "Output length must be >=85% of source" in prompt
    assert "Output length must be ≥70% of source" not in prompt
    assert "Match source paragraph count exactly" not in prompt
    assert "Match source paragraph count — CRITICAL" not in prompt
    assert "Source-anchored structure" in prompt
    assert "<structure_contract>" in prompt
    assert "dialogue paragraphs: 1" in prompt


def test_prompt_profiles_are_explicit_presets():
    assert {"faithful_default", "flowing_thai", "strict_literal"} <= set(PROMPT_PROFILES)

    prompt = build_prompt(
        source_text="「走吧。」",
        ch_num=2,
        source_lang="cn",
        target_lang="th",
        profile="strict_literal",
    )

    assert "<prompt_profile>" in prompt
    assert "strict_literal" in prompt



def test_prompt_preserves_dialogue_line_structure():
    prompt = build_prompt(
        source_text='张三: 「一」\n李四: 「二」',
        ch_num=3,
        source_lang="cn",
        target_lang="th",
        novel_title="global-descent",
    )

    assert "Do not combine multiple source dialogue lines" in prompt
    assert 'Chat/forum lines with `Name: "..."` must remain separate paragraphs' in prompt
    assert "No JSON, XML, markdown fences" in prompt
