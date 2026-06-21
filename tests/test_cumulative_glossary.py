"""Tests for tools/cumulative_glossary.py — auto-discover glossary entries."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Module-level patching for constants
import tools.cumulative_glossary as cg
import tools.build_yaml as by

# ── Sample CN text with extractable entities ──────────────────────────
SAMPLE_TEXT = """全球降臨：帶著嫂嫂末世種田

第1章 测试

「王明」看着眼前的一切。
系统提示：【冰霜新星】技能已激活。
「李华」走了过来。
王明发现【空间戒指】的微光。
《冰霜之心》是一件传说中的神器。
张伟跑了过来。"""

SAMPLE_GLOSSARY = [
    {"source": "系统", "thai": "ระบบ", "lock": "reference", "priority": 2},
    {"source": "技能", "thai": "สกิล", "lock": "reference", "priority": 2},
]


@pytest.fixture
def temp_novel(tmp_path):
    """Create temporary novel with glossary directory."""
    slug = "test-glossary"
    gloss_dir = tmp_path / "novels" / slug / "glossary"
    chapters_dir = tmp_path / "novels" / slug / "chapters"
    gloss_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir.mkdir(parents=True, exist_ok=True)

    # Write initial auto.md
    auto_md = gloss_dir / "auto.md"
    auto_md.write_text(
        "# Auto Glossary — test\n\n"
        "| Source | Thai | Category | Priority | Notes |\n"
        "|--------|------|----------|----------|-------|\n"
        "| 传说明 | ตำนานย้อนยุค | ตัวละคร | 3 | existing term |\n",
        encoding="utf-8",
    )

    # Write glossary.yml (simulate build_yaml output)
    from tools.glossary import save_terms
    # Patch NOVELS_DIR
    import tools.constants as const_mod
    original_novels_dir = const_mod.NOVELS_DIR
    const_mod.NOVELS_DIR = tmp_path / "novels"

    yield slug, gloss_dir, chapters_dir

    const_mod.NOVELS_DIR = original_novels_dir


@pytest.fixture
def patch_novels_dir(tmp_path, monkeypatch):
    """Patch NOVELS_DIR in constants and build_yaml."""
    novels_dir = tmp_path / "novels"
    import tools.constants as const_mod
    monkeypatch.setattr(const_mod, "NOVELS_DIR", novels_dir)
    # Also patch in build_yaml
    import tools.build_yaml as by_mod
    monkeypatch.setattr(by_mod, "NOVELS_DIR", novels_dir)
    import tools.extract_entities as ee_mod
    import tools.cumulative_glossary as cg_mod
    return novels_dir


def test_get_candidate_entities_filters_glossary():
    """Entities already in glossary should be excluded."""
    candidates = cg.get_candidate_entities(1, SAMPLE_TEXT, SAMPLE_GLOSSARY)
    sources = [c["source"] for c in candidates]
    # "技能" and "系统" are in glossary — should not appear
    assert "技能" not in sources, "Glossary term should be filtered out"
    assert "系统" not in sources, "Glossary term should be filtered out"
    # These should be candidates
    assert "冰霜新星" in sources, "Skill name should be a candidate"
    assert "空间戒指" in sources, "Item name should be a candidate"
    assert "冰霜之心" in sources, "Game title should be a candidate"


def test_get_candidate_entities_dialogue_speakers():
    """Dialogue speakers should be extracted as character candidates."""
    candidates = cg.get_candidate_entities(1, SAMPLE_TEXT, [])
    sources = [c["source"] for c in candidates]
    assert "王明" in sources, "Character should be a candidate"
    assert "李华" in sources, "Character should be a candidate"


def test_get_candidate_entities_deduplicates():
    """Same entity should not appear twice."""
    candidates = cg.get_candidate_entities(1, SAMPLE_TEXT, [])
    sources = [c["source"] for c in candidates]
    # "王明" appears once as dialogue speaker
    assert sources.count("王明") <= 1, "Should be deduplicated"


def test_auto_md_row_format():
    """Generated rows should match auto.md table format."""
    row = cg._build_auto_md_row("测试", "ทั่วไป", 5)
    assert row.startswith("| 测试 |")
    assert "ทั่วไป" in row
    assert "ch5" in row or "auto-detect" in row


def test_process_translation_candidates_no_dup(tmp_path, monkeypatch):
    """Running twice should not add duplicates."""
    novels_dir = tmp_path / "novels"
    monkeypatch.setattr("tools.constants.NOVELS_DIR", novels_dir)
    monkeypatch.setattr("tools.cumulative_glossary._get_auto_md_path", 
        lambda slug="global-descent": novels_dir / slug / "glossary" / "auto.md")
    
    # Create slug dir
    slug = "test-slug"
    gloss_dir = novels_dir / slug / "glossary"
    gloss_dir.mkdir(parents=True)

    # Create initial auto.md
    (gloss_dir / "auto.md").write_text(
        "# Auto Glossary\n\n"
        "| Source | Thai | Category | Priority | Notes |\n"
        "|--------|------|----------|----------|-------|\n",
        encoding="utf-8",
    )

    # First run
    r1 = cg.process_translation_candidates(1, SAMPLE_TEXT, [], slug, auto_rebuild=False)
    assert r1["added"] > 0

    # Second run — should add 0 (already present)
    r2 = cg.process_translation_candidates(1, SAMPLE_TEXT, [], slug, auto_rebuild=False)
    assert r2["added"] == 0, "Should not add duplicates"


def test_category_mapping_for_game_titles():
    """Game titles should map to category 'ไอเทม'."""
    candidates = cg.get_candidate_entities(1, SAMPLE_TEXT, [])
    for c in candidates:
        if c["source"] == "冰霜之心":
            assert c["category"] == "ไอเทม", "Game title → ไอเทม"
            break
    else:
        pytest.fail("冰霜之心 not found in candidates")


def test_category_mapping_for_system_terms():
    """System bracket terms should map to category 'สกิล'."""
    candidates = cg.get_candidate_entities(1, SAMPLE_TEXT, [])
    for c in candidates:
        if c["source"] == "冰霜新星":
            assert c["category"] == "สกิล", "System term → สกิล"
            break
    else:
        pytest.fail("冰霜新星 not found in candidates")


def test_category_mapping_for_dialogue():
    """Dialogue speakers should map to category 'ตัวละคร'."""
    candidates = cg.get_candidate_entities(1, SAMPLE_TEXT, [])
    for c in candidates:
        if c["source"] == "王明":
            assert c["category"] == "ตัวละคร", "Dialogue speaker → ตัวละคร"
            break
    else:
        pytest.fail("王明 not found in candidates")
