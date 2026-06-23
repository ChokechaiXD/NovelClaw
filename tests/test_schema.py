"""test_schema.py — Chapter schema tests for v3 paragraphs format."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import pytest  # noqa: E402
from schema import Chapter, Language  # noqa: E402


def _ch(num=1, title="\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 1 Test", paragraphs=None,
         source='ch 1', lang='cn'):
    """Build a minimal valid chapter."""
    if paragraphs is None:
        paragraphs = ['\u0e40\u0e19\u0e37\u0e49\u0e2d\u0e40\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e15\u0e2d\u0e19\u0e19\u0e35\u0e49',
                      '(\u0e08\u0e1a\u0e1a\u0e17)']
    return Chapter(num=num, title=title, paragraphs=paragraphs, source=source, lang=lang)


class TestChapterMinimal:
    def test_minimal_chapter(self):
        ch = _ch()
        assert ch.num == 1
        assert ch.title == '\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 1 Test'
        assert len(ch.paragraphs) >= 2
        assert ch.paragraphs[-1] == '(\u0e08\u0e1a\u0e1a\u0e17)'  # (จบบท)
        assert ch.source == 'ch 1'
        assert ch.lang == Language.CN

    def test_view(self):
        ch = _ch()
        assert ch.model_dump() is not None

    def test_lang_thai(self):
        ch = _ch(lang='th')
        assert ch.lang == 'th'


class TestChapterValidation:
    def test_title_required(self):
        with pytest.raises(Exception):
            Chapter(num=1, title='Bad Title', paragraphs=['text', '(จบบท)'], source='ch 1')

    def test_title_with_colon(self):
        ch = Chapter(num=1, title='\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 1: \u0e40\u0e23\u0e34\u0e48\u0e21\u0e15\u0e49\u0e19',
                     paragraphs=['\u0e40\u0e19\u0e37\u0e49\u0e2d', '(\u0e08\u0e1a\u0e1a\u0e17)'], source='ch 1')
        assert ch.num == 1

    def test_source_required_pattern(self):
        with pytest.raises(Exception):
            Chapter(num=1, title='\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 1 X', source='bad source',
                    paragraphs=['text', '(\u0e08\u0e1a\u0e1a\u0e17)'])

    def test_num_ge_1(self):
        with pytest.raises(Exception):
            _ch(num=0)

    def test_num_le_9999(self):
        with pytest.raises(Exception):
            _ch(num=10000)

    def test_notes_default_empty(self):
        ch = _ch()
        assert ch.notes == []

    def test_end_marker_auto_append(self):
        """If last paragraph isn't an end marker, one gets appended."""
        ch = Chapter(num=1, title='\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 1 T',
                     paragraphs=['\u0e40\u0e19\u0e37\u0e49\u0e2d'], source='ch 1')
        assert ch.paragraphs[-1] == '(\u0e08\u0e1a\u0e1a\u0e17)'

    def test_empty_paragraphs_rejected(self):
        with pytest.raises(Exception):
            _ch(paragraphs=[])

    def test_serialize_deserialize(self):
        orig = _ch()
        data = orig.model_dump()
        restored = Chapter(**data)
        assert restored.num == orig.num
        assert restored.title == orig.title
        assert restored.paragraphs == orig.paragraphs
