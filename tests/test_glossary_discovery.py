import json
import time
from concurrent.futures import ThreadPoolExecutor

import glossary_discovery
import glossary_pre


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

    monkeypatch.setattr("pipeline_llm.call_llm", fake_call_llm)

    proposed = glossary_discovery.propose_translations(candidates)

    assert proposed[0]["proposed_thai"] == "มังกรดำ"
    assert proposed[0]["confidence"] == "high"
    assert proposed[1]["proposed_thai"] == "เยือกแข็ง"
    assert proposed[1]["confidence"] == "medium"


def test_propose_translations_uses_language_specific_prompt(monkeypatch):
    prompts = []

    def fake_call_llm(*_args, **kwargs):
        prompts.append(kwargs["prompt"])
        return "Moon Blade | ดาบจันทรา | high | skill", "fake", "fake-model"

    monkeypatch.setattr("pipeline_llm.call_llm", fake_call_llm)
    candidate = [{"term": "Moon Blade", "freq": 2, "context": "Moon Blade flashed"}]

    glossary_discovery.propose_translations([dict(candidate[0])], source_lang="jp")
    glossary_discovery.propose_translations([dict(candidate[0])], source_lang="en")

    assert "Japanese→Thai" in prompts[0]
    assert "Chinese→Thai" not in prompts[0]
    assert "English→Thai" in prompts[1]
    assert "Chinese→Thai" not in prompts[1]


def test_extract_unknown_english_terms_includes_repeated_named_phrases(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text('{"terms": []}', encoding="utf-8")
    monkeypatch.setattr(glossary_discovery, "_get_glossary_path", lambda _slug: glossary_path)
    glossary_discovery._load_existing_terms.cache_clear()

    candidates = glossary_discovery.extract_unknown_terms(
        "Black Dragon landed. The Black Dragon roared. "
        "Mana Core pulsed. The mana core cracked.",
        slug="test-novel",
        source_lang="en",
    )

    terms = {item["term"].casefold() for item in candidates}
    assert "black dragon" in terms
    assert "mana core" in terms


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


def test_save_discovered_terms_preserves_top_level_metadata(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text(
        json.dumps(
            {
                "version": 4,
                "sourceLanguage": "jp",
                "review": {"owner": "editor"},
                "terms": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(glossary_discovery, "_get_glossary_path", lambda _slug: glossary_path)

    saved = glossary_discovery.save_discovered_terms(
        [{"term": "黒龍", "proposed_thai": "มังกรดำ", "confidence": "high", "freq": 3}],
        slug="test-novel",
    )

    data = json.loads(glossary_path.read_text(encoding="utf-8"))
    assert saved == 1
    assert data["version"] == 4
    assert data["sourceLanguage"] == "jp"
    assert data["review"] == {"owner": "editor"}


def test_save_discovered_terms_bootstraps_a_new_novel_glossary(tmp_path, monkeypatch):
    glossary_path = tmp_path / "new-novel" / "glossary" / "glossary.json"
    monkeypatch.setattr(glossary_discovery, "_get_glossary_path", lambda _slug: glossary_path)

    saved = glossary_discovery.save_discovered_terms(
        [{"term": "Moon Blade", "proposed_thai": "ดาบจันทรา", "confidence": "high", "freq": 3}],
        slug="new-novel",
    )

    data = json.loads(glossary_path.read_text(encoding="utf-8"))
    assert saved == 1
    assert data["terms"][0]["source"] == "Moon Blade"
    assert data["terms"][0]["verified"] is False


def test_save_discovered_terms_does_not_replace_malformed_glossary(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    original = '{"terms": ['
    glossary_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(glossary_discovery, "_get_glossary_path", lambda _slug: glossary_path)

    saved = glossary_discovery.save_discovered_terms(
        [{"term": "黒龍", "proposed_thai": "มังกรดำ", "confidence": "high", "freq": 3}],
        slug="test-novel",
    )

    assert saved == 0
    assert glossary_path.read_text(encoding="utf-8") == original


def test_parallel_saves_merge_without_lost_updates(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text('{"version": 1, "terms": []}', encoding="utf-8")
    monkeypatch.setattr(glossary_discovery, "_get_glossary_path", lambda _slug: glossary_path)
    glossary_discovery._load_existing_terms.cache_clear()

    real_atomic_write = glossary_discovery.atomic_write_json

    def delayed_atomic_write(*args, **kwargs):
        time.sleep(0.015)
        return real_atomic_write(*args, **kwargs)

    monkeypatch.setattr(glossary_discovery, "atomic_write_json", delayed_atomic_write)
    discovered = [
        {
            "term": f"Term{index}",
            "proposed_thai": f"คำ{index}",
            "confidence": "high",
            "freq": 2,
        }
        for index in range(8)
    ]

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda candidate: glossary_discovery.save_discovered_terms(
                    [candidate], slug="test-novel"
                ),
                discovered,
            )
        )

    data = json.loads(glossary_path.read_text(encoding="utf-8"))
    assert {term["source"] for term in data["terms"]} == {
        candidate["term"] for candidate in discovered
    }
    assert data["version"] == 1


def test_replaced_glossary_lock_is_not_removed_by_previous_owner(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    lock_path = tmp_path / ".glossary.json.lock"
    glossary_path.write_text('{"terms": []}', encoding="utf-8")

    real_close = glossary_discovery.os.close

    def close_then_replace(fd):
        real_close(fd)
        lock_path.unlink()
        lock_path.write_text("replacement-owner\n", encoding="ascii")

    monkeypatch.setattr(glossary_discovery.os, "close", close_then_replace)
    with glossary_discovery._glossary_write_lock(glossary_path):
        original_token = lock_path.read_text(encoding="ascii").splitlines()[0]

    assert original_token != "replacement-owner"
    assert lock_path.read_text(encoding="ascii").splitlines()[0] == "replacement-owner"


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


def test_clear_glossary_caches_includes_character_and_term_maps(monkeypatch):
    cleared = []

    class CacheProbe:
        def __init__(self, name):
            self.name = name

        def cache_clear(self):
            cleared.append(self.name)

    monkeypatch.setattr(glossary_pre, "load_characters", CacheProbe("characters"))
    monkeypatch.setattr(glossary_pre, "load_known_terms", CacheProbe("terms"))

    glossary_discovery._clear_glossary_caches()

    assert cleared == ["characters", "terms"]


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
