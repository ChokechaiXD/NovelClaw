import pipeline


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
                "score": 60,
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
    monkeypatch.setattr(pipeline, "save_chapter", lambda **_kwargs: tmp_path / "0001.th.json")

    result = pipeline.translate_one(1)

    assert result["status"] == "ok"
    assert len(calls) == 2
    assert "<repair>" not in calls[0]["prompt"]
    assert "<repair>" in calls[1]["prompt"]
    assert "Expand missing content" in calls[1]["prompt"]
    assert "Remove untranslated foreign-script leaks" in calls[1]["prompt"]
