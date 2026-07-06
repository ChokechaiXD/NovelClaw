import glossary_pre


def test_load_characters_uses_in_memory_cache(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text(
        '{"terms":[{"source":"曹星","thai":"เฉาซิง","category":"ตัวละคร","priority":1}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(glossary_pre, "_get_glossary_path", lambda _slug: glossary_path)
    glossary_pre.load_characters.cache_clear()

    first = glossary_pre.load_characters("test-novel")
    glossary_path.write_text(
        '{"terms":[{"source":"柳慕雪","thai":"หลิวมู่เสวี่ย","category":"ตัวละคร","priority":1}]}',
        encoding="utf-8",
    )
    cached = glossary_pre.load_characters("test-novel")
    glossary_pre.load_characters.cache_clear()
    refreshed = glossary_pre.load_characters("test-novel")

    assert [item["source"] for item in first] == ["曹星"]
    assert [item["source"] for item in cached] == ["曹星"]
    assert [item["source"] for item in refreshed] == ["柳慕雪"]




def test_character_prompt_marks_name_map_as_hard_constraint(tmp_path, monkeypatch):
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text(
        '{"terms":[{"source":"曹星","thai":"เฉาซิง","category":"ตัวละคร","priority":1}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(glossary_pre, "_get_glossary_path", lambda _slug: glossary_path)
    glossary_pre.load_characters.cache_clear()

    prompt = glossary_pre.build_character_prompt("test-novel")

    assert "HARD CONSTRAINTS" in prompt
    assert "Never substitute one character" in prompt
    assert "曹星 → เฉาซิง" in prompt
