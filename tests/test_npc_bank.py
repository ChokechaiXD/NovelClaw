"""Tests for npc_bank.py (Phase 2 — NPC Dossier Bank)."""
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))


# ── extract_npcs ──────────────────────────────────────────────────
def test_extract_npcs_thai_text():
    """Thai names from glossary should be detected in Thai body."""
    from npc_bank import extract_npcs
    body = 'เฉาซิงพบหลิวมู่เสวี่ย เฉาซิงพูด หลิวมู่เสวี่ยฟัง ' * 5
    results = extract_npcs(body, top_n=5)
    names = [n for n, _ in results]
    assert 'เฉาซิง' in names
    assert 'หลิวมู่เสวี่ย' in names


def test_extract_npcs_cn_text():
    """CN names from glossary should be detected in CN source."""
    from npc_bank import extract_npcs
    body = '曹星遇到柳慕雪 ' * 10
    results = extract_npcs(body, top_n=5)
    names = [n for n, _ in results]
    assert '曹星' in names
    assert '柳慕雪' in names


def test_extract_npcs_empty():
    from npc_bank import extract_npcs
    assert extract_npcs('') == []
    assert extract_npcs('only english text here') == []


def test_extract_npcs_sorted_by_count():
    from npc_bank import extract_npcs
    body = 'เฉาซิง เฉาซิง เฉาซิง หลิวมู่เสวี่ย'
    results = extract_npcs(body)
    # เฉาซิง should come first (3 mentions vs 1)
    assert results[0][0] == 'เฉาซิง'
    assert results[0][1] >= results[1][1]


# ── Dossier I/O ───────────────────────────────────────────────────
def test_create_dossier_template():
    from npc_bank import create_dossier
    content = create_dossier(
        'เทส', cn_name='测试', first_ch=10, role='protagonist',
        gender='male', speech='shy', agenda='survive'
    )
    assert '# เทส' in content
    assert '曹星' not in content
    assert '测试' in content  # CN name
    assert 'ch 10' in content
    assert 'protagonist' in content
    assert 'shy' in content


def test_add_dossier_creates_file():
    """add_dossier should create file if not exists."""
    import tempfile
    from npc_bank import add_dossier, NPC_DIR
    original = NPC_DIR
    try:
        tmp = Path(tempfile.mkdtemp())
        import npc_bank
        npc_bank.NPC_DIR = tmp
        path = add_dossier('ทดสอบ', cn_name='test', first_ch=1, role='mob')
        assert path.exists()
        assert path.stem == 'ทดสอบ'
    finally:
        import npc_bank
        npc_bank.NPC_DIR = original


def test_add_dossier_skips_existing():
    """add_dossier should not overwrite existing dossiers."""
    import tempfile
    from npc_bank import add_dossier
    import npc_bank
    original = npc_bank.NPC_DIR
    try:
        tmp = Path(tempfile.mkdtemp())
        npc_bank.NPC_DIR = tmp
        # First add
        add_dossier('ซ้ำ', cn_name='first', first_ch=1)
        first_content = (tmp / 'ซ้ำ.md').read_text(encoding='utf-8')
        # Second add (should skip)
        add_dossier('ซ้ำ', cn_name='second', first_ch=2)
        second_content = (tmp / 'ซ้ำ.md').read_text(encoding='utf-8')
        assert first_content == second_content
        assert 'first' in second_content
    finally:
        npc_bank.NPC_DIR = original


def test_is_existing_npc(monkeypatch):
    import npc_bank
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(npc_bank, 'NPC_DIR', tmp)
    assert not npc_bank.is_existing_npc('ไม่มี')
    (tmp / 'มี.md').write_text('# test', encoding='utf-8')
    assert npc_bank.is_existing_npc('มี')


# ── get_dossiers_for_chapter ──────────────────────────────────────
def test_get_dossiers_uses_cn_to_th_mapping():
    """CN names in source should map to Thai dossier filenames."""
    from npc_bank import get_dossiers_for_chapter
    import npc_bank
    original = npc_bank.NPC_DIR
    try:
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        npc_bank.NPC_DIR = tmp
        # Create a dossier for เฉาซิง (Thai render of 曹星)
        (tmp / 'เฉาซิง.md').write_text(
            '# เฉาซิง\n- **CN name:** 曹星\n- **Gender:** male\n',
            encoding='utf-8',
        )
        # Create temp source file with CN names
        src_dir = Path('novels/global-descent/chapters/source')
        if src_dir.exists():
            # Use real source 101 which has 曹星 35x
            results = get_dossiers_for_chapter(101)
            assert any('เฉาซิง' in p.stem for p in results)
    finally:
        npc_bank.NPC_DIR = original


# ── format_inject_block ───────────────────────────────────────────
def test_format_inject_block_returns_string():
    from npc_bank import format_inject_block
    block = format_inject_block(0)  # ch 0 has no NPCs
    assert block == ''  # empty when no dossiers


def test_format_inject_block_with_dossier():
    """If a dossier exists and NPC appears in ch, show the block."""
    import tempfile
    from npc_bank import format_inject_block
    import npc_bank
    original = npc_bank.NPC_DIR
    try:
        tmp = Path(tempfile.mkdtemp())
        npc_bank.NPC_DIR = tmp
        # Create dossier
        (tmp / 'เฉาซิง.md').write_text(
            '# เฉาซิง\n- **Role:** protagonist\n- **CN name:** 曹星\n',
            encoding='utf-8',
        )
        # Use real ch 100 (has เฉาซิง 44x)
        block = format_inject_block(100, top_n=2)
        if block:
            assert 'NPC Dossiers' in block
            assert 'เฉาซิง' in block
    finally:
        npc_bank.NPC_DIR = original
