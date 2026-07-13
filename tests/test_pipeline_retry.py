import pipeline


def test_script_leak_repair_targets_the_leaking_paragraph(monkeypatch):
    paragraphs = [
        "ย่อหน้าแรกเป็นภาษาไทยและต้องคงเดิมทุกคำ",
        "ย่อหน้าที่สองยังมี OpenBeta ซึ่งต้องถูกแก้ไข",
        "(จบบท)",
    ]
    calls = []

    def fake_call_llm(**kwargs):
        calls.append(kwargs["prompt"])
        return "ย่อหน้าที่สองถูกแก้เป็นภาษาไทยแล้ว", "fake", "repair-model"

    monkeypatch.setattr(pipeline, "call_llm", fake_call_llm)

    repaired = pipeline._repair_script_leaks(paragraphs, "th")

    assert repaired[0] == paragraphs[0]
    assert repaired[1] == "ย่อหน้าที่สองถูกแก้เป็นภาษาไทยแล้ว"
    assert repaired[2] == "(จบบท)"
    assert calls == [f"Fix script leaks in this paragraph:\n\n{paragraphs[1]}"]


def test_translate_one_retries_with_quality_repair_notes(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: "阿星醒來。")
    monkeypatch.setattr(pipeline, "build_translate_prompt", lambda **_kwargs: "SYSTEM\n<glossary>\nTranslate.")
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "primary-model",
            "provider_name": "openrouter",
            "discovery_model": "judge-model",
        },
    )

    def fake_call_llm(prompt, system=None, model=None, provider=None, **_kwargs):
        calls.append({"prompt": prompt, "system": system, "model": model, "provider": provider})
        return "เฉาซิงลืมตาขึ้น\n\n(จบบท)", "fake", model or "fake-model"

    score_results = iter(
        [
            {
                "score": 82,
                "passed": False,
                "repair_notes": [
                    "Expand missing content and preserve all source events.",
                    "Remove untranslated foreign-script leaks from the Thai output.",
                ],
                "errors": ["Completeness: too short"],
            },
            {"score": 90, "passed": True, "repair_notes": [], "errors": []},
        ]
    )

    monkeypatch.setattr(pipeline, "call_llm", fake_call_llm)
    monkeypatch.setattr(pipeline, "_score_and_report", lambda *_args, **_kwargs: next(score_results))
    monkeypatch.setattr(pipeline, "judge_translation", lambda *_args, **_kwargs: {"ok": True, "feedback": "ok"})
    monkeypatch.setattr(
        pipeline,
        "discover_and_save",
        lambda **_kwargs: {"discovered": 0, "saved": 0, "terms": []},
    )
    saved_kwargs = {}

    def fake_save_chapter(**kwargs):
        saved_kwargs.update(kwargs)
        return tmp_path / "0001.th.json"

    monkeypatch.setattr(pipeline, "save_chapter", fake_save_chapter)

    result = pipeline.translate_one(1)

    assert result["status"] == "ok"
    assert len(calls) == 2
    assert "<repair>" not in calls[0]["prompt"]
    assert "<repair>" in calls[1]["prompt"]
    assert "Expand missing content" in calls[1]["prompt"]
    assert "Remove untranslated foreign-script leaks" in calls[1]["prompt"]
    assert saved_kwargs["quality_record"]["attempts"][0]["repairEligible"] is True
    assert saved_kwargs["quality_record"]["attempts"][0]["repairReason"] == "borderline_quality"
    assert saved_kwargs["quality_record"]["score"] == 90
    assert saved_kwargs["quality_record"]["passed"] is True


def test_translate_one_uses_discovery_model_as_fallback_after_empty_output(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: "阿星醒來。")
    monkeypatch.setattr(pipeline, "build_translate_prompt", lambda **_kwargs: "SYSTEM\n<glossary>\nTranslate.")
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "primary-model",
            "provider_name": "openrouter",
            "discovery_model": "judge-model",
        },
    )

    def fake_call_llm(prompt, system=None, model=None, provider=None, **_kwargs):
        calls.append({"model": model, "provider": provider})
        if len(calls) == 1:
            return "", "fake", model or "fake-model"
        return "เฉาซิงลืมตาขึ้น\n\nเมืองทั้งเมืองเงียบกริบ\n\n(จบบท)", "fake", model or "fake-model"

    monkeypatch.setattr(pipeline, "call_llm", fake_call_llm)
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {
            "score": 92,
            "passed": True,
            "repair_notes": [],
            "repairNotes": [],
            "errors": [],
            "hardFailures": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(pipeline, "judge_translation", lambda *_args, **_kwargs: {"ok": True, "feedback": "ok"})
    monkeypatch.setattr(
        pipeline,
        "discover_and_save",
        lambda **_kwargs: {"discovered": 0, "saved": 0, "terms": []},
    )
    monkeypatch.setattr(pipeline, "save_chapter", lambda **_kwargs: tmp_path / "0001.th.json")

    result = pipeline.translate_one(1)

    assert result["status"] == "ok"
    assert calls[0]["model"] == "primary-model"
    assert calls[1]["model"] == "judge-model"
    assert result["quality"]["attempts"][1]["kind"] == "fallback"


def test_safety_fallback_runs_after_empty_output_and_saves_with_source_lang(monkeypatch, tmp_path):
    saved_kwargs = {}

    monkeypatch.setattr(
        pipeline,
        "call_llm",
        lambda **_kwargs: (
            "เฉาซิงลืมตาขึ้น\n\nเมืองทั้งเมืองเงียบกริบ\n\n(จบบท)",
            "custom",
            "fallback-model",
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {"score": 91, "passed": True, "hardFailures": []},
    )

    def fake_save_chapter(**kwargs):
        saved_kwargs.update(kwargs)
        return tmp_path / "0001.th.json"

    monkeypatch.setattr(pipeline, "save_chapter", fake_save_chapter)

    succeeded, score, classified, model, provider, out_path = pipeline._try_safety_fallback(
        user_text="Translate.",
        system_text=None,
        ch_num=1,
        source_lang="cn",
        target_lang="th",
        source="阿星醒來。",
        source_profile={"sourceLang": "cn"},
        last_error="Empty LLM output",
        primary_provider="openrouter",
    )

    assert succeeded is True
    assert score["score"] == 91
    assert classified
    assert model == "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    assert provider == "custom"
    assert out_path == tmp_path / "0001.th.json"
    assert saved_kwargs["source_lang"] == "cn"
    assert saved_kwargs["target_lang"] == "th"
    assert saved_kwargs["quality_record"]["passed"] is True


def test_translate_one_skips_quality_repair_when_score_is_too_low(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: "阿星醒來。")
    monkeypatch.setattr(pipeline, "build_translate_prompt", lambda **_kwargs: "SYSTEM\n<glossary>\nTranslate.")
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "primary-model",
            "provider_name": "openrouter",
            "discovery_model": "judge-model",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "call_llm",
        lambda *args, **kwargs: ("เฉาซิงลืมตาขึ้น\n\n(จบบท)", "fake", kwargs.get("model") or "fake-model"),
    )
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {
            "score": 60,
            "passed": False,
            "repair_notes": ["Expand missing content and preserve all source events."],
            "repairNotes": ["Expand missing content and preserve all source events."],
            "errors": ["Completeness: too short"],
            "hardFailures": ["Completeness: too short"],
            "warnings": [],
        },
    )
    monkeypatch.setattr(pipeline, "save_chapter", lambda **_kwargs: tmp_path / "0001.th.json")

    result = pipeline.translate_one(1)

    assert result["status"] == "needs_review"
    assert "quality gate" in result["reason"]
    assert len(result["quality"]["attempts"]) == 1
    assert result["quality"]["attempts"][0]["repairEligible"] is False
    assert result["quality"]["attempts"][0]["repairReason"] == "not_eligible"


def test_translate_one_needs_review_keeps_usable_output_contract(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: "阿星醒來。")
    monkeypatch.setattr(pipeline, "build_translate_prompt", lambda **_kwargs: "SYSTEM\n<glossary>\nTranslate.")
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "primary-model",
            "provider_name": "openrouter",
            "discovery_model": "judge-model",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "call_llm",
        lambda *args, **kwargs: ("เฉาซิงลืมตาขึ้น\n\n(จบบท)", "fake", kwargs.get("model") or "fake-model"),
    )
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {"score": 60, "passed": False, "hardFailures": ["Completeness: too short"]},
    )
    monkeypatch.setattr(pipeline, "save_chapter", lambda **_kwargs: tmp_path / "0001.th.json")

    result = pipeline.translate_one(1)

    assert result["status"] == "needs_review"
    assert result["path"] == str(tmp_path / "0001.th.json")
    assert result["paragraphs"] > 0
    assert result["provider"] == "fake"
    assert result["model"] == "primary-model"


def test_translate_one_repairs_repeated_borderline_quality_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: "阿星醒來。")
    monkeypatch.setattr(pipeline, "build_translate_prompt", lambda **_kwargs: "SYSTEM\n<glossary>\nTranslate.")
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "primary-model",
            "provider_name": "openrouter",
            "discovery_model": "judge-model",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "call_llm",
        lambda *args, **kwargs: ("เฉาซิงลืมตาขึ้น\n\n(จบบท)", "fake", kwargs.get("model") or "fake-model"),
    )
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {
            "score": 82,
            "passed": False,
            "repair_notes": ["Remove untranslated foreign-script leaks from the Thai output."],
            "repairNotes": ["Remove untranslated foreign-script leaks from the Thai output."],
            "errors": ["Script Purity: leak"],
            "hardFailures": ["Script Purity: leak"],
            "warnings": [],
        },
    )
    monkeypatch.setattr(pipeline, "save_chapter", lambda **_kwargs: tmp_path / "0001.th.json")

    result = pipeline.translate_one(1)

    assert result["status"] == "needs_review"
    assert len(result["quality"]["attempts"]) == 2
    assert result["quality"]["attempts"][0]["repairEligible"] is True
    assert result["quality"]["attempts"][1]["status"] == "quality_failed"


def test_translate_one_auto_detects_source_lang_for_profile(monkeypatch, tmp_path):
    prompt_kwargs = {}
    saved_kwargs = {}

    monkeypatch.setattr(
        pipeline,
        "read_source",
        lambda *_args, **_kwargs: "Lin Fan opened his eyes.\n\n\"Let's go.\"",
    )

    def fake_build_prompt(**kwargs):
        prompt_kwargs.update(kwargs)
        return "prompt"

    def fake_save_chapter(**kwargs):
        saved_kwargs.update(kwargs)
        return tmp_path / "0001.th.json"

    monkeypatch.setattr(pipeline, "build_translate_prompt", fake_build_prompt)
    monkeypatch.setattr(pipeline, "save_chapter", fake_save_chapter)

    result = pipeline.translate_one(1, slug="missing-test", mock=True)

    assert result["status"] == "ok"
    assert prompt_kwargs["source_lang"] == "en"
    assert prompt_kwargs["source_profile"]["sourceLang"] == "en"
    assert saved_kwargs["source_lang"] == "en"
    assert saved_kwargs["source_profile"]["dialogueCount"] == 1


def test_translate_one_judge_auto_repair_saves_chapter_after_successful_fix(monkeypatch, tmp_path):
    """When Judge flags an issue but auto-repair rebuilds it to passing quality, save as ok."""
    saved_kwargs = {}

    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: "阿星醒來。\n\n「走吧。」")
    monkeypatch.setattr(pipeline, "build_translate_prompt", lambda **_kwargs: "SYSTEM\n<glossary>\nTranslate.")
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "primary-model",
            "provider_name": "openrouter",
            "discovery_model": "judge-model",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "call_llm",
        lambda *args, **kwargs: ('"ไปกันเถอะ"\n\nเฉาซิงลืมตาขึ้น\n\n(จบบท)', "fake", kwargs.get("model") or "fake-model"),
    )
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {
            "score": 92,
            "passed": True,
            "repair_notes": [],
            "repairNotes": [],
            "errors": [],
            "hardFailures": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        pipeline,
        "judge_translation",
        lambda *_args, **_kwargs: {"ok": True, "passed": False, "feedback": "FAIL: tone drift"},
    )
    monkeypatch.setattr(
        pipeline,
        "discover_and_save",
        lambda **_kwargs: {"discovered": 0, "saved": 0, "terms": []},
    )

    def fake_save_chapter(**kwargs):
        saved_kwargs.update(kwargs)
        return tmp_path / "0001.th.json"

    monkeypatch.setattr(pipeline, "save_chapter", fake_save_chapter)

    result = pipeline.translate_one(1)

    assert result["status"] == "ok"
    assert saved_kwargs["quality_record"]["judge"]["repaired"] is True
    assert any(a["kind"] == "judge_repair" for a in saved_kwargs["quality_record"]["attempts"])



def test_translate_one_tolerates_empty_judge_feedback(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: "阿星醒來。")
    monkeypatch.setattr(pipeline, "build_translate_prompt", lambda **_kwargs: "SYSTEM\n<glossary>\nTranslate.")
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "primary-model",
            "provider_name": "openrouter",
            "discovery_model": "judge-model",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "call_llm",
        lambda *args, **kwargs: ("เฉาซิงลืมตาขึ้น\n\n(จบบท)", "fake", kwargs.get("model") or "fake-model"),
    )
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {"score": 92, "passed": True, "hardFailures": []},
    )
    monkeypatch.setattr(pipeline, "judge_translation", lambda *_args, **_kwargs: {"ok": True, "feedback": None})
    monkeypatch.setattr(pipeline, "discover_and_save", lambda **_kwargs: {"discovered": 0, "saved": 0, "terms": []})
    monkeypatch.setattr(pipeline, "save_chapter", lambda **_kwargs: tmp_path / "0001.th.json")

    result = pipeline.translate_one(1)

    assert result["status"] == "ok"
    assert result["judge"] == ""
