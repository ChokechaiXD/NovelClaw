from source_profile import build_source_profile, detect_source_lang, resolve_source_lang, split_source_paragraphs


def test_detect_source_lang_uses_dominant_unicode_script():
    assert detect_source_lang("田中は深く息を吸い込んだ。") == "jp"
    assert detect_source_lang("김철수는 눈을 떴다.") == "kr"
    assert detect_source_lang("Lin Fan opened his eyes in the ruined city.") == "en"


def test_resolve_source_lang_prefers_explicit_value():
    lang, source = resolve_source_lang("田中は深く息を吸い込んだ。", requested_lang="jp", slug="missing-test")

    assert lang == "jp"
    assert source == "requested"


def test_source_profile_counts_structure_markers():
    profile = build_source_profile(
        "阿星睜開眼。\n\n「走吧。」\n\n【系統提示】獲得100經驗值。",
        source_lang="cn",
        target_lang="th",
        ch_num=7,
        lang_source="auto_detect",
    )

    assert profile["sourceLang"] == "cn"
    assert profile["paragraphCount"] == 3
    assert profile["dialogueCount"] == 1
    assert profile["systemMarkerCount"] == 1
    assert profile["sourceScriptMix"]["Han"] > 0
    assert profile["specialSymbolInventory"]["【"] == 1


def test_split_source_paragraphs_expands_line_based_blocks():
    paragraphs = split_source_paragraphs("line one\nline two\n\nline three\nline four")

    assert paragraphs == ["line one", "line two", "line three", "line four"]
