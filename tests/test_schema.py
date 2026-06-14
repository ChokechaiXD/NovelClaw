"""test_schema.py — Data integrity layer (Phase 2 critical path).

Locks down the Chapter schema, BRACKETS config, helpers, and edge cases.
The schema is the contract between translator (Mika) and reader (server).
"""
import json
import sys
import shutil
import tempfile
from pathlib import Path

# Make tools/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import pytest  # noqa: E402

from schema import (  # noqa: E402
    Chapter, Narration, Dialogue, SystemMessage, GameTitle, EndMarker,
    Language, BRACKETS, DialogueQuote, SystemBracket, GameBracket, BlockType,
    load_chapter, save_chapter, chapter_path, md_to_blocks,
)


def _ch(lang='cn', dialogue='「hi」', system='【HP】', end='(จบบท)'):
    """Build a minimal valid chapter."""
    return Chapter(
        num=1, title='ตอนที่ 1 Test', source='ch 1',
        blocks=[
            {'type': 'narration', 'text': 'narrative'},
            {'type': 'dialogue', 'text': dialogue},
            {'type': 'system', 'text': system},
            {'type': 'end', 'text': end},
        ],
        lang=lang,
    )


# ── Chapter construction ─────────────────────────────────────────────

class TestChapterConstruction:
    def test_minimal_valid_cn(self):
        ch = _ch()
        assert ch.num == 1
        assert ch.lang == Language.CN
        assert len(ch.blocks) == 4

    def test_lang_default_is_cn(self):
        ch = _ch()
        assert ch.lang == Language.CN

    def test_lang_accepts_string(self):
        ch = _ch(lang='jp')
        assert ch.lang == Language.JP

    def test_lang_accepts_enum(self):
        # Use EN-appropriate brackets
        ch = Chapter(
            num=1, title='ตอนที่ 1 Test', source='ch 1',
            blocks=[
                {'type': 'narration', 'text': 'narrative'},
                {'type': 'dialogue', 'text': '\u201CHello\u201D'},
                {'type': 'system', 'text': '[HP:100]'},
                {'type': 'end', 'text': '(End)'},
            ],
            lang='en',
        )
        assert ch.lang == Language.EN

    def test_title_required(self):
        with pytest.raises(Exception):
            Chapter(num=1, source='ch 1', blocks=[
                {'type': 'narration', 'text': 'hi'},
                {'type': 'end', 'text': '(จบบท)'},
            ])

    def test_source_required_pattern(self):
        with pytest.raises(Exception):
            Chapter(num=1, title='ตอนที่ 1 X', source='bad', blocks=[
                {'type': 'narration', 'text': 'hi'},
                {'type': 'end', 'text': '(จบบท)'},
            ])

    def test_num_ge_1(self):
        with pytest.raises(Exception):
            _ch(num=0)

    def test_num_le_9999(self):
        with pytest.raises(Exception):
            _ch(num=10000)

    def test_notes_default_empty(self):
        ch = _ch()
        assert ch.notes == []


# ── Block parsing ────────────────────────────────────────────────────

class TestBlockParsing:
    def test_narration_block(self):
        ch = _ch()
        assert isinstance(ch.blocks[0], Narration)

    def test_dialogue_block(self):
        ch = _ch()
        assert isinstance(ch.blocks[1], Dialogue)

    def test_system_block(self):
        ch = _ch()
        assert isinstance(ch.blocks[2], SystemMessage)

    def test_end_block(self):
        ch = _ch()
        assert isinstance(ch.blocks[3], EndMarker)

    def test_unknown_type_rejected(self):
        with pytest.raises(Exception) as exc_info:
            Chapter(num=1, title='ตอนที่ 1 X', source='ch 1', blocks=[
                {'type': 'unknown', 'text': 'x'},
                {'type': 'end', 'text': '(จบบท)'},
            ])
        assert 'invalid type' in str(exc_info.value).lower()

    def test_block_order_preserved(self):
        ch = _ch()
        assert ch.blocks[0].type == BlockType.NARRATION
        assert ch.blocks[1].type == BlockType.DIALOGUE
        assert ch.blocks[2].type == BlockType.SYSTEM
        assert ch.blocks[3].type == BlockType.END


# ── Structure validation ─────────────────────────────────────────────

class TestStructure:
    def test_missing_end_marker_rejected(self):
        with pytest.raises(Exception):
            Chapter(num=1, title='ตอนที่ 1 X', source='ch 1', blocks=[
                {'type': 'narration', 'text': 'hi'},
            ])

    def test_two_end_markers_rejected(self):
        with pytest.raises(Exception):
            Chapter(num=1, title='ตอนที่ 1 X', source='ch 1', blocks=[
                {'type': 'narration', 'text': 'hi'},
                {'type': 'end', 'text': '(จบบท)'},
                {'type': 'end', 'text': '(จบบท)'},
            ])

    def test_end_must_be_last(self):
        with pytest.raises(Exception):
            Chapter(num=1, title='ตอนที่ 1 X', source='ch 1', blocks=[
                {'type': 'end', 'text': '(จบบท)'},
                {'type': 'narration', 'text': 'hi'},
            ])

    def test_only_end_marker_rejected(self):
        with pytest.raises(Exception):
            Chapter(num=1, title='ตอนที่ 1 X', source='ch 1', blocks=[
                {'type': 'end', 'text': '(จบบท)'},
            ])


# ── Title validation ─────────────────────────────────────────────────

class TestTitle:
    def test_title_must_match_pattern(self):
        with pytest.raises(Exception):
            Chapter(num=1, title='No prefix here', source='ch 1', blocks=[
                {'type': 'narration', 'text': 'hi'},
                {'type': 'end', 'text': '(จบบท)'},
            ])

    def test_title_num_must_match_chapter_num(self):
        with pytest.raises(Exception) as exc_info:
            Chapter(num=1, title='ตอนที่ 5 Wrong', source='ch 1', blocks=[
                {'type': 'narration', 'text': 'hi'},
                {'type': 'end', 'text': '(จบบท)'},
            ])
        assert 'Title says ch 5 but num is 1' in str(exc_info.value)


# ── Helpers ──────────────────────────────────────────────────────────

class TestHelpers:
    def test_chapter_path_format(self):
        p = chapter_path('/tmp/novel', 5)
        assert p.name == '0005.json'
        assert 'chapters' in p.parts

    def test_save_load_roundtrip(self):
        d = Path(tempfile.mkdtemp(prefix="schema_test_"))
        try:
            path = d / "test.json"
            ch = _ch()
            save_chapter(ch, path)
            loaded = load_chapter(path)
            assert loaded.num == ch.num
            assert loaded.title == ch.title
            assert len(loaded.blocks) == len(ch.blocks)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_save_pretty_printed(self):
        """Output is indented (2 spaces) for git diff."""
        d = Path(tempfile.mkdtemp(prefix="schema_test_"))
        try:
            path = d / "test.json"
            save_chapter(_ch(), path)
            text = path.read_text(encoding='utf-8')
            assert '\n  "num"' in text  # 2-space indent
            assert text.endswith('\n')  # trailing newline
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_save_preserves_unicode(self):
        d = Path(tempfile.mkdtemp(prefix="schema_test_"))
        try:
            path = d / "test.json"
            ch = _ch()
            save_chapter(ch, path)
            text = path.read_text(encoding='utf-8')
            assert 'ตอนที่' in text  # not escaped to \uXXXX
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ── md_to_blocks migration helper ────────────────────────────────────

class TestMdToBlocks:
    def test_basic_migration(self):
        md = """# ตอนที่ 1 Test

นี่คือการเล่าเรื่อง

「สวัสดี」

【HP: 100】

(จบบท)
"""
        blocks, notes = md_to_blocks(md)
        assert len(blocks) > 0
        assert any(b['type'] == 'dialogue' for b in blocks)
        assert any(b['type'] == 'system' for b in blocks)
        # last block should be end
        assert blocks[-1]['type'] == 'end'
        assert blocks[-1]['text'] == '(จบบท)'

    def test_strips_h1_title(self):
        md = "# ตอนที่ 1 X\n\nbody text\n\n(จบบท)\n"
        blocks, _ = md_to_blocks(md)
        # No block should contain "# ตอนที่"
        for b in blocks:
            assert not b['text'].startswith('# ')

    def test_extracts_notes(self):
        md = """# ตอนที่ 1 X

body

(จบบท)

---

- note 1
- note 2
"""
        blocks, notes = md_to_blocks(md)
        assert 'note 1' in notes
        assert 'note 2' in notes
