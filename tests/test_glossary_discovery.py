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
