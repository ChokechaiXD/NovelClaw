import pipeline


def test_read_source_prefers_canonical_markdown_over_legacy_json(monkeypatch, tmp_path):
    canonical = tmp_path / "0001.md"
    legacy = tmp_path / "0001.cn.json"
    canonical.write_text("canonical source body", encoding="utf-8")
    legacy.write_text('{"paragraphs": ["stale legacy body"]}', encoding="utf-8")
    monkeypatch.setattr(pipeline, "source_md_path", lambda _slug, _num: canonical)
    monkeypatch.setattr(pipeline, "chapter_path", lambda _slug, _num, _lang: legacy)

    assert pipeline.read_source(1, "test-novel") == "canonical source body"


def test_split_source_chunks_preserves_every_character_at_paragraph_boundaries():
    source = "A" * 70 + "\n\n" + "B" * 70 + "\n\n" + "C" * 30

    chunks = pipeline._split_source_chunks(source, max_chars=90)

    assert "".join(chunks) == source
    assert chunks == ["A" * 70 + "\n\n", "B" * 70 + "\n\n", "C" * 30]
    assert all(len(chunk) <= 90 for chunk in chunks)


def test_split_source_chunks_uses_sentence_boundary_for_oversized_paragraph():
    source = "甲" * 60 + "。" + "乙" * 60 + "！" + "丙" * 20

    chunks = pipeline._split_source_chunks(source, max_chars=90)

    assert "".join(chunks) == source
    assert chunks == ["甲" * 60 + "。", "乙" * 60 + "！" + "丙" * 20]


def test_source_chunk_limit_scales_with_output_budget_and_language_expansion():
    assert pipeline._source_chunk_char_limit("cn", max_tokens=2048) < pipeline._source_chunk_char_limit(
        "en", max_tokens=2048
    )
    assert pipeline._source_chunk_char_limit("cn", max_tokens=4096) > pipeline._source_chunk_char_limit(
        "cn", max_tokens=2048
    )
    assert pipeline._source_chunk_char_limit("en", max_tokens=8192) <= 6000


def test_source_chunk_limit_keeps_completion_headroom_for_cjk_to_thai():
    max_tokens = 4096

    assert pipeline._source_chunk_char_limit("cn", max_tokens) <= int(max_tokens * 0.4)
    assert pipeline._source_chunk_char_limit("jp", max_tokens) <= int(max_tokens * 0.4)
    assert pipeline._source_chunk_char_limit("cn", 512) <= int(512 * 0.4)


def test_run_one_attempt_merges_chunk_outputs_before_full_chapter_scoring(monkeypatch):
    calls = []
    scored = {}
    responses = iter(
        [
            "ย่อหน้าแปลส่วนแรก\n\n(จบบท)",
            "ย่อหน้าแปลส่วนสอง\n\n(จบบท)",
        ]
    )

    def fake_call_llm(**kwargs):
        calls.append(kwargs)
        return next(responses), "local", "model-a"

    def fake_score(classified, source, target_lang, source_profile=None):
        scored.update(
            classified=classified,
            source=source,
            target_lang=target_lang,
            source_profile=source_profile,
        )
        return {"score": 95, "passed": True, "hardFailures": []}

    monkeypatch.setattr(pipeline, "call_llm", fake_call_llm)
    monkeypatch.setattr(pipeline, "_score_and_report", fake_score)

    result = pipeline._run_one_attempt(
        prompt="STATIC\n<source_chapter>\npart one",
        chunk_prompts=[
            "STATIC\n<source_chapter>\npart one",
            "STATIC\n<source_chapter>\npart two",
        ],
        repair_instruction="",
        ch_num=7,
        target_lang="th",
        source="part one\n\npart two",
        source_profile={"paragraphCount": 2},
        attempt_cfg={"kind": "translate", "model": "model-a", "provider": "local"},
    )

    assert result["status"] == "passed"
    assert result["chunk_count"] == 2
    assert [item["text"] for item in result["classified"]] == [
        "ย่อหน้าแปลส่วนแรก",
        "ย่อหน้าแปลส่วนสอง",
        "(จบบท)",
    ]
    assert [item["text"] for item in scored["classified"]] == [
        "ย่อหน้าแปลส่วนแรก",
        "ย่อหน้าแปลส่วนสอง",
        "(จบบท)",
    ]
    assert scored["source"] == "part one\n\npart two"
    assert len(calls) == 2
    assert calls[0]["system"] == calls[1]["system"] == "STATIC"
    assert "Part 1 of 2" in calls[0]["prompt"]
    assert "Part 2 of 2" in calls[1]["prompt"]


def test_run_one_attempt_rejects_provider_truncated_chunk_before_scoring(monkeypatch):
    score_calls = []

    def fake_call_llm(**kwargs):
        kwargs["response_metadata"]["finish_reason"] = "length"
        return "ข้อความแปลที่ถูกตัดกลางประโยค", "local", "model-a"

    monkeypatch.setattr(pipeline, "call_llm", fake_call_llm)
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: score_calls.append(True),
    )

    result = pipeline._run_one_attempt(
        prompt="STATIC\n<source_chapter>\npart one",
        chunk_prompts=[
            "STATIC\n<source_chapter>\npart one",
            "STATIC\n<source_chapter>\npart two",
        ],
        repair_instruction="",
        ch_num=7,
        target_lang="th",
        source="part one\n\npart two",
        source_profile={"paragraphCount": 2},
        attempt_cfg={"kind": "translate", "model": "model-a", "provider": "local"},
    )

    assert result["status"] == "truncated_output"
    assert result["failed_chunk"] == 1
    assert result["chunk_count"] == 2
    assert score_calls == []


def test_translate_one_automatically_chunks_long_source_and_saves_one_chapter(monkeypatch, tmp_path):
    source = "first " + "a" * 70 + "\n\nsecond " + "b" * 70 + "\n\nthird " + "c" * 30
    prompt_sources = []
    saved = {}
    llm_calls = []

    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: source)
    monkeypatch.setattr(pipeline, "_source_chunk_char_limit", lambda *_args, **_kwargs: 100)
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "model-a",
            "provider_name": "local",
            "discovery_model": "judge-a",
            "max_tokens": 4096,
        },
    )

    def fake_build_prompt(**kwargs):
        prompt_sources.append(kwargs["source_text"])
        return "STATIC\n<source_chapter>\n" + kwargs["source_text"]

    def fake_call_llm(**kwargs):
        llm_calls.append(kwargs)
        part = len(llm_calls)
        return f"ข้อความแปลส่วนที่ {part}\n\n(จบบท)", "local", kwargs["model"]

    def fake_save_chapter(**kwargs):
        saved.update(kwargs)
        return tmp_path / "0001.th.json"

    monkeypatch.setattr(pipeline, "build_translate_prompt", fake_build_prompt)
    monkeypatch.setattr(pipeline, "call_llm", fake_call_llm)
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {"score": 95, "passed": True, "hardFailures": []},
    )
    monkeypatch.setattr(
        pipeline,
        "judge_translation",
        lambda *_args, **_kwargs: {"ok": True, "passed": True, "feedback": "ok"},
    )
    monkeypatch.setattr(
        pipeline,
        "discover_and_save",
        lambda **_kwargs: {"discovered": 0, "saved": 0, "terms": []},
    )
    monkeypatch.setattr(pipeline, "save_chapter", fake_save_chapter)

    result = pipeline.translate_one(1, slug="long-test", source_lang="en")

    assert result["status"] == "ok"
    assert len(prompt_sources) == len(llm_calls) == 3
    assert "".join(prompt_sources) == source
    assert [item["text"] for item in saved["classified"]] == [
        "ข้อความแปลส่วนที่ 1",
        "ข้อความแปลส่วนที่ 2",
        "ข้อความแปลส่วนที่ 3",
        "(จบบท)",
    ]


def test_translate_one_retries_provider_truncation_with_fallback_model(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: "Lin woke up.")
    monkeypatch.setattr(
        pipeline,
        "build_translate_prompt",
        lambda **_kwargs: "STATIC\n<source_chapter>\nLin woke up.",
    )
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "primary-model",
            "provider_name": "local",
            "discovery_model": "fallback-model",
            "max_tokens": 4096,
        },
    )

    def fake_call_llm(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) == 1:
            kwargs["response_metadata"]["finish_reason"] = "length"
            return "ข้อความที่ถูกตัดกลางประโยค", "local", kwargs["model"]
        kwargs["response_metadata"]["finish_reason"] = "stop"
        return "หลินลืมตาตื่นขึ้น\n\n(จบบท)", "local", kwargs["model"]

    monkeypatch.setattr(pipeline, "call_llm", fake_call_llm)
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {"score": 95, "passed": True, "hardFailures": []},
    )
    monkeypatch.setattr(
        pipeline,
        "judge_translation",
        lambda *_args, **_kwargs: {"ok": True, "passed": True, "feedback": "ok"},
    )
    monkeypatch.setattr(
        pipeline,
        "discover_and_save",
        lambda **_kwargs: {"discovered": 0, "saved": 0, "terms": []},
    )
    monkeypatch.setattr(pipeline, "save_chapter", lambda **_kwargs: tmp_path / "0001.th.json")

    result = pipeline.translate_one(1, slug="truncated-test", source_lang="en")

    assert result["status"] == "ok"
    assert calls == ["primary-model", "fallback-model"]
    assert result["quality"]["attempts"][0]["status"] == "truncated_output"
    assert result["quality"]["attempts"][0]["failedChunk"] == 1


def test_safety_fallback_translates_all_chunks_before_saving(monkeypatch, tmp_path):
    calls = []
    saved = {}

    def fake_call_llm(**kwargs):
        calls.append(kwargs)
        kwargs["response_metadata"]["finish_reason"] = "stop"
        return f"ส่วนแปลที่ {len(calls)}\n\n(จบบท)", "custom", kwargs["model"]

    monkeypatch.setattr(pipeline, "call_llm", fake_call_llm)
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {"score": 95, "passed": True, "hardFailures": []},
    )

    def fake_save_chapter(**kwargs):
        saved.update(kwargs)
        return tmp_path / "0001.th.json"

    monkeypatch.setattr(pipeline, "save_chapter", fake_save_chapter)

    succeeded, *_rest = pipeline._try_safety_fallback(
        user_text="<source_chapter>\npart two",
        system_text="STATIC",
        chunk_prompts=[
            "STATIC\n<source_chapter>\npart one",
            "STATIC\n<source_chapter>\npart two",
        ],
        ch_num=1,
        source_lang="en",
        target_lang="th",
        source="part one\n\npart two",
        source_profile={"paragraphCount": 2},
        last_error="Empty LLM output",
        primary_provider="openrouter",
    )

    assert succeeded is True
    assert len(calls) == 2
    assert [item["text"] for item in saved["classified"]] == [
        "ส่วนแปลที่ 1",
        "ส่วนแปลที่ 2",
        "(จบบท)",
    ]


def test_judge_repair_retranslates_every_chunk_before_replacing_long_chapter(monkeypatch, tmp_path):
    source = "first " + "a" * 70 + "\n\nsecond " + "b" * 70 + "\n\nthird " + "c" * 30
    calls = []
    judge_calls = []
    saved = {}

    monkeypatch.setattr(pipeline, "read_source", lambda *_args, **_kwargs: source)
    monkeypatch.setattr(pipeline, "_source_chunk_char_limit", lambda *_args, **_kwargs: 100)
    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "model-a",
            "provider_name": "local",
            "discovery_model": "judge-a",
            "max_tokens": 4096,
        },
    )
    monkeypatch.setattr(
        pipeline,
        "build_translate_prompt",
        lambda **kwargs: "STATIC\n<source_chapter>\n" + kwargs["source_text"],
    )

    def fake_call_llm(**kwargs):
        calls.append(kwargs)
        if "<judge_repair>" in kwargs["prompt"]:
            part = len(calls) - 3
            text = f"ฉบับแก้ส่วนที่ {part}"
        else:
            part = len(calls)
            text = f"ฉบับร่างส่วนที่ {part}"
        kwargs.get("response_metadata", {})["finish_reason"] = "stop"
        return text + "\n\n(จบบท)", "local", kwargs["model"]

    monkeypatch.setattr(pipeline, "call_llm", fake_call_llm)
    monkeypatch.setattr(
        pipeline,
        "_score_and_report",
        lambda *_args, **_kwargs: {"score": 90, "passed": True, "hardFailures": []},
    )
    def fake_judge(*_args, **_kwargs):
        judge_calls.append(True)
        if len(judge_calls) == 1:
            return {
                "ok": True,
                "passed": False,
                "feedback": "restore omitted event",
            }
        return {
            "ok": True,
            "passed": True,
            "feedback": "all repaired chunks verified",
        }

    monkeypatch.setattr(pipeline, "judge_translation", fake_judge)
    monkeypatch.setattr(
        pipeline,
        "discover_and_save",
        lambda **_kwargs: {"discovered": 0, "saved": 0, "terms": []},
    )

    def fake_save_chapter(**kwargs):
        saved.update(kwargs)
        return tmp_path / "0001.th.json"

    monkeypatch.setattr(pipeline, "save_chapter", fake_save_chapter)

    result = pipeline.translate_one(1, slug="judge-chunks", source_lang="en")

    assert result["status"] == "ok"
    assert len(judge_calls) == 2
    assert len(calls) == 6
    assert all("<judge_repair>" in call["prompt"] for call in calls[3:])
    assert saved["quality_record"]["judge"]["repairAccepted"] is True
    assert [item["text"] for item in saved["classified"]] == [
        "ฉบับแก้ส่วนที่ 1",
        "ฉบับแก้ส่วนที่ 2",
        "ฉบับแก้ส่วนที่ 3",
        "(จบบท)",
    ]
