from prompt_builder import PROMPT_PROFILES, build_prompt


def test_prompt_default_has_no_quality_rule_contradictions():
    prompt = build_prompt(
        source_text="阿星睜開眼時，城市已經變成廢墟。",
        ch_num=1,
        source_lang="cn",
        target_lang="th",
        novel_title="global-descent",
    )

    assert "Output length must be >=85% of source" in prompt
    assert "Output length must be ≥70% of source" not in prompt
    assert "Match source paragraph count exactly" not in prompt
    assert "Preserve source paragraph structure" in prompt


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
