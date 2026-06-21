"""Tests for tools/extract_entities.py — entity extraction and placeholder pipeline."""

from __future__ import annotations

from tools.extract_entities import (
    PLACEHOLDER_RE,
    entity_extraction_pipeline,
    entity_to_placeholder,
    extract_entities,
    extract_from_brackets,
    restore_entities_from_map,
    verify_no_leaked_entities,
)

# ── Sample CN novel text with known entities ──────────────────────────
SAMPLE_TEXT = """全球降臨：帶著嫂嫂末世種田

第1章 测试

「王明」看着眼前的一切，心中充满了震惊。
系统提示：【冰霜新星】技能已激活。
「李华」走了过来，说道：「这个世界已经完全变了。」

王明打开了系统面板，发现【空间戒指】正在发出微弱的光芒。
《冰霜之心》是一件传说中的神器。
李华站在【传送阵】上，准备前往新的区域。

张伟从远处跑来，气喘吁吁地说：「不好了！前面的【魔兽森林】出现了大批怪物！」
王明冷静地打开【宠物界面】，召唤出了小白。
小白是一只巨大的【冰霜巨狼】。"""


def test_extract_game_titles():
    """Extract 《》 bracketed terms — these are proper nouns."""
    entities = extract_from_brackets(SAMPLE_TEXT)
    game_titles = [e["source"] for e in entities if e["bracket_type"] == "game_title"]
    assert "冰霜之心" in game_titles, "Should extract game/bracket titles"


def test_extract_system_terms():
    """Extract 【】 bracketed terms — skill/item/notification names."""
    entities = extract_from_brackets(SAMPLE_TEXT)
    system_terms = [e["source"] for e in entities if e["bracket_type"] == "system"]
    assert "冰霜新星" in system_terms, "Should extract system bracket terms"
    assert "空间戒指" in system_terms
    assert "传送阵" in system_terms
    assert "魔兽森林" in system_terms
    assert "宠物界面" in system_terms
    assert "冰霜巨狼" in system_terms


def test_placeholder_deterministic():
    """Same entity → same placeholder."""
    p1 = entity_to_placeholder("冰霜新星")
    p2 = entity_to_placeholder("冰霜新星")
    assert p1 == p2
    assert p1.startswith("__ENT_")
    assert p1.endswith("__")
    assert len(p1) == 16  # __ENT_XXXXXXXX__


def test_different_entities_different_placeholders():
    """Different entities → different placeholders."""
    p1 = entity_to_placeholder("冰霜新星")
    p2 = entity_to_placeholder("空间戒指")
    assert p1 != p2


def test_extract_entities_pipeline():
    """Full pipeline extracts entities and creates placeholder map."""
    result = entity_extraction_pipeline(1, SAMPLE_TEXT)
    assert result["count"] > 0
    assert result["chapter"] == 1
    # Should have some system/game entities
    sources = [e["source"] for e in result["entities"]]
    assert "冰霜新星" in sources


def test_placehold_and_restore():
    """Replace entities with placeholders, then restore."""
    result = entity_extraction_pipeline(1, SAMPLE_TEXT, min_freq=1)
    assert result["placeheld_text"] != SAMPLE_TEXT, "Text should be modified"
    assert "__ENT_" in result["placeheld_text"], "Should contain placeholders"

    # Reconstruct what a mock LLM would produce (placeholders in text)
    mock_llm_output = result["placeheld_text"][:100]
    restored = restore_entities_from_map(mock_llm_output, result["placeholder_map"])
    assert restored is not None


def test_verify_no_leaked_entities():
    """After restore, no original entity text should leak."""
    result = entity_extraction_pipeline(1, SAMPLE_TEXT, min_freq=1)
    # After full restore, all placeholders should be resolved
    restored = restore_entities_from_map(result["placeheld_text"], result["placeholder_map"])
    # Count remaining placeholders
    remaining = PLACEHOLDER_RE.findall(restored)
    assert len(remaining) == 0, f"Placeholders remain after restore: {remaining}"


def test_generic_terms_filtered():
    """Generic/common CN words should not be extracted as entities."""
    text = "他知道这个系统功能可以提升能力等级"
    entities = extract_entities(text, min_freq=1)
    sources = [e["source"] for e in entities]
    # These are generic words
    assert "知道" not in sources, "知道 is generic, should not be entity"
    assert "系统" not in sources, "系统 is generic, should not be entity"
    assert "功能" not in sources, "功能 is generic, should not be entity"
    assert "能力" not in sources, "能力 is generic, should not be entity"


def test_placeholder_regex():
    """PLACEHOLDER_RE matches entity placeholders."""
    assert PLACEHOLDER_RE.match("__ENT_a1b2c3d4__")
    assert not PLACEHOLDER_RE.match("__ENT_abc__")  # too short
    assert not PLACEHOLDER_RE.match("some text")


def test_entity_pipeline_with_glossary():
    """Glossary entities are marked correctly."""
    glossary = [{"source": "冰霜新星", "thai": "น้ำแข็ง nova", "lock": "reference", "priority": 2}]
    entities = extract_entities(SAMPLE_TEXT, glossary, min_freq=1)
    frost_nova = [e for e in entities if e["source"] == "冰霜新星"]
    assert frost_nova
    assert frost_nova[0]["in_glossary"] is True
    assert frost_nova[0]["thai"] == "น้ำแข็ง nova"
