from types import SimpleNamespace

import pipeline
import pipeline_save


class _FakePolicy:
    def apply_to_text(self, text):
        return SimpleNamespace(text=text.replace("HP", "พลังชีวิต"))


def test_apply_glossary_post_replaces_terms_and_keeps_end_marker(monkeypatch):
    monkeypatch.setattr("qa.term_policy.get_term_policy", lambda _lang: _FakePolicy())

    result = pipeline_save.apply_glossary_post(
        ["เฉาซิงมี HP เต็ม", "(จบบท)"],
        target_lang="th",
    )

    assert result == ["เฉาซิงมี พลังชีวิต เต็ม", "(จบบท)"]


def test_glossary_discovery_continues_after_an_earlier_auto_term(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text(
        '{"terms":[{"source":"黑龍","thai":"มังกรดำ","category":"auto_discovered"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr("novel_paths.glossary_json_path", lambda _slug: glossary_path)
    if hasattr(pipeline, "_GLOSSARY_CACHE"):
        pipeline._GLOSSARY_CACHE.clear()

    monkeypatch.setattr(
        pipeline,
        "_get_active_config",
        lambda *_args, **_kwargs: {
            "model": "translate-model",
            "provider_name": "local",
            "discovery_model": "discovery-model",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "_run_one_attempt",
        lambda **_kwargs: {
            "status": "passed",
            "system_text": "system",
            "user_text": "user",
            "classified": [{"type": "narration", "text": "ข้อความแปล"}],
            "score_result": {"score": 96, "passed": True, "hardFailures": []},
            "provider": "local",
            "model": "translate-model",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "_judge_and_auto_repair",
        lambda **kwargs: (
            kwargs["classified"],
            kwargs["score_result"],
            {"ok": True, "passed": True, "skipped": True},
        ),
    )
    calls = []

    def fake_discover(**kwargs):
        calls.append(kwargs)
        return {"discovered": 1, "saved": 1, "terms": []}

    monkeypatch.setattr(pipeline, "discover_and_save", fake_discover)

    result = pipeline._run_real_translate(
        ch_num=2,
        slug="test-novel",
        source="白狼出現。白狼咆哮。",
        source_lang="cn",
        target_lang="th",
        source_profile={},
        prompt="prompt",
        chunk_prompts=None,
        model_override=None,
        provider_override=None,
    )

    assert result["status"] == "ok"
    assert len(calls) == 1
    assert calls[0]["source_text"] == "白狼出現。白狼咆哮。"
