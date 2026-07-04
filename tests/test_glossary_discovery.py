import json

import glossary_discovery


def test_propose_translations_parses_markdown_table(monkeypatch):
    candidates = [
        {"term": "黑龍", "freq": 3, "context": "黑龍盤旋在天空"},
        {"term": "冰封", "freq": 2, "context": "冰封紀元降臨"},
    ]

    def fake_call_llm(*_args, **_kwargs):
        return (
            "\n".join(
                [
                    "| term | proposed_thai | confidence | note |",
                    "| --- | --- | --- | --- |",
                    "| 黑龍 | มังกรดำ | high | creature name |",
                    "| 冰封 | เยือกแข็ง | medium | setting term |",
                ]
            ),
            "fake",
            "fake-model",
        )

    monkeypatch.setattr("pipeline.call_llm", fake_call_llm)

    proposed = glossary_discovery.propose_translations(candidates)

    assert proposed[0]["proposed_thai"] == "มังกรดำ"
    assert proposed[0]["confidence"] == "high"
    assert proposed[1]["proposed_thai"] == "เยือกแข็ง"
    assert proposed[1]["confidence"] == "medium"


def test_save_discovered_terms_skips_low_confidence_and_noise(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text('{"terms": []}', encoding="utf-8")
    monkeypatch.setattr(glossary_discovery, "_get_glossary_path", lambda _slug: glossary_path)
    glossary_discovery._load_existing_terms.cache_clear()

    saved = glossary_discovery.save_discovered_terms(
        [
            {
                "term": "黑龍",
                "proposed_thai": "มังกรดำ",
                "confidence": "high",
                "freq": 3,
                "note": "creature name",
            },
            {
                "term": "評論",
                "proposed_thai": "ความคิดเห็น",
                "confidence": "high",
                "freq": 8,
            },
            {
                "term": "冰封",
                "proposed_thai": "เยือกแข็ง",
                "confidence": "low",
                "freq": 2,
            },
            {
                "term": "白狼",
                "proposed_thai": "?หมาป่าขาว",
                "confidence": "medium",
                "freq": 2,
            },
        ]
    )

    data = json.loads(glossary_path.read_text(encoding="utf-8"))

    assert saved == 1
    assert [term["source"] for term in data["terms"]] == ["黑龍"]


def test_save_discovered_terms_clears_glossary_caches_after_write(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text('{"terms": []}', encoding="utf-8")
    monkeypatch.setattr(glossary_discovery, "_get_glossary_path", lambda _slug: glossary_path)
    calls = {"clear": 0}
    monkeypatch.setattr(
        glossary_discovery,
        "_clear_glossary_caches",
        lambda: calls.__setitem__("clear", calls["clear"] + 1),
    )

    saved = glossary_discovery.save_discovered_terms(
        [
            {
                "term": "黑龍",
                "proposed_thai": "มังกรดำ",
                "confidence": "high",
                "freq": 3,
            },
        ]
    )

    assert saved == 1
    assert calls["clear"] == 1


def test_save_discovered_terms_does_not_clear_caches_when_nothing_saved(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text('{"terms": []}', encoding="utf-8")
    monkeypatch.setattr(glossary_discovery, "_get_glossary_path", lambda _slug: glossary_path)
    calls = {"clear": 0}
    monkeypatch.setattr(
        glossary_discovery,
        "_clear_glossary_caches",
        lambda: calls.__setitem__("clear", calls["clear"] + 1),
    )

    saved = glossary_discovery.save_discovered_terms(
        [
            {
                "term": "冰封",
                "proposed_thai": "เยือกแข็ง",
                "confidence": "low",
                "freq": 2,
            },
        ]
    )

    assert saved == 0
    assert calls["clear"] == 0
