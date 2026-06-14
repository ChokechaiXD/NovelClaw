"""test_multilang_schema.py — Multi-language schema support (Phase 2).

Verifies that:
  - 5 languages (cn, jp, kr, en, th) all parse cleanly with the right
    brackets per their BRACKETS profile
  - Wrong brackets for a language are rejected
  - Backward compat: existing CN chapters with no `lang` field work
  - End marker auto-set to language-specific value
  - BRACKETS config is the single source of truth (matches schema.py)
"""
import sys
from pathlib import Path

# Make tools/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from schema import Chapter, Language, BRACKETS  # noqa: E402


def make_chapter(lang, dialogue_text=None, system_text=None, end_text=None):
    """Build a minimal valid chapter for a given language."""
    b = BRACKETS[lang]
    return Chapter(
        num=1,
        title='ตอนที่ 1 Test',
        blocks=[
            {'type': 'narration', 'text': 'Once upon a time'},
            {'type': 'dialogue', 'text': dialogue_text or f'{b["dialogue_open"]}hi{b["dialogue_close"]}'},
            {'type': 'system', 'text': system_text or f'{b["system_open"]}HP:100{b["system_close"]}'},
            {'type': 'end', 'text': end_text or b['end_marker']},
        ],
        source='ch 1',
        lang=lang,
    )


class TestLanguageEnum:
    """The 5 supported languages are exposed as enum values."""

    def test_languages_present(self):
        for lang in ('cn', 'jp', 'kr', 'en', 'th'):
            assert lang in BRACKETS, f'BRACKETS missing {lang}'

    def test_brackets_have_required_keys(self):
        for lang, b in BRACKETS.items():
            for key in ('dialogue_open', 'dialogue_close',
                        'system_open', 'system_close',
                        'game_open', 'game_close', 'end_marker'):
                assert key in b, f'BRACKETS[{lang}] missing {key}'
                assert b[key], f'BRACKETS[{lang}][{key}] is empty'


class TestCNDefault:
    """CN (Chinese) — original brackets, default for backward compat."""

    def test_default_lang_is_cn(self):
        ch = Chapter(
            num=1, title='ตอนที่ 1 Test',
            blocks=[
                {'type': 'narration', 'text': 'hi'},
                {'type': 'dialogue', 'text': '「สวัสดี」'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
            source='ch 1',
        )
        assert ch.lang == Language.CN

    def test_cn_brackets_accepted(self):
        ch = make_chapter('cn', dialogue_text='「สวัสดี」', system_text='【HP:100】')
        assert ch.blocks[1].text == '「สวัสดี」'
        assert ch.blocks[2].text == '【HP:100】'


class TestJapanese:
    """JP — same dialogue/system as CN, but title uses 『』 and end is (終)."""

    def test_jp_brackets_accepted(self):
        ch = make_chapter('jp', dialogue_text='「こんにちは」', system_text='【HP:100】')
        assert ch.lang == Language.JP

    def test_jp_end_marker_auto_set(self):
        ch = make_chapter('jp', end_text='x')  # any text gets replaced
        assert ch.blocks[-1].text == BRACKETS['jp']['end_marker']
        assert ch.blocks[-1].text == '（終）'

    def test_jp_game_title_uses_kagi(self):
        ch = Chapter(
            num=1, title='ตอนที่ 1 Test',
            blocks=[
                {'type': 'narration', 'text': 'hi'},
                {'type': 'dialogue', 'text': '「hi」'},
                {'type': 'game_title', 'text': '『Game Title』'},
                {'type': 'end', 'text': '（終）'},
            ],
            source='ch 1', lang='jp',
        )
        assert ch.blocks[2].text == '『Game Title』'


class TestKorean:
    """KR — same as CN but end marker is (끝)."""

    def test_kr_end_marker(self):
        ch = make_chapter('kr')
        assert ch.blocks[-1].text == '(끝)'


class TestEnglish:
    """EN — curly quotes, square brackets, (End) marker."""

    def test_en_curly_quotes_accepted(self):
        ch = make_chapter('en',
                          dialogue_text='\u201CHello\u201D',
                          system_text='[HP:100]')
        assert ch.lang == Language.EN
        assert ch.blocks[1].text == '\u201CHello\u201D'
        assert ch.blocks[2].text == '[HP:100]'

    def test_en_end_marker(self):
        ch = make_chapter('en')
        assert ch.blocks[-1].text == '(End)'

    def test_en_rejects_cjk_brackets(self):
        """EN novels shouldn't have 「」 — they use curly quotes instead."""
        with __import__('pytest').raises(ValueError) as exc_info:
            make_chapter('en', dialogue_text='「wrong brackets」')
        assert 'dialogue[en]' in str(exc_info.value)

    def test_en_rejects_kagi(self):
        with __import__('pytest').raises(ValueError) as exc_info:
            make_chapter('en', dialogue_text='\u300Cwrong\u300D')
        assert 'dialogue[en]' in str(exc_info.value)


class TestThai:
    """TH — curly quotes (TH standard), 【】system kept, (จบบท) end."""

    def test_th_curly_quotes(self):
        ch = make_chapter('th', dialogue_text='\u201Cสวัสดี\u201D')
        assert ch.lang == Language.TH
        assert ch.blocks[1].text == '\u201Cสวัสดี\u201D'

    def test_th_end_marker(self):
        ch = make_chapter('th')
        assert ch.blocks[-1].text == '(จบบท)'


class TestBackwardCompat:
    """Existing chapters with no `lang` field default to 'cn'."""

    def test_no_lang_defaults_to_cn(self):
        ch = Chapter(
            num=1, title='ตอนที่ 1 Test',
            blocks=[
                {'type': 'narration', 'text': 'hi'},
                {'type': 'dialogue', 'text': '「hi」'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
            source='ch 1',
            # no lang field
        )
        assert ch.lang == Language.CN

    def test_existing_cn_chapters_load(self):
        """All existing translated chapters (ch 1-121) should still parse."""
        import json
        chapters_dir = Path(__file__).parent.parent / 'novels' / 'global-descent' / 'chapters'
        if not chapters_dir.exists():
            return  # skip if running from different layout
        ok = 0
        for p in sorted(chapters_dir.glob('0*.json')):
            data = json.loads(p.read_text(encoding='utf-8'))
            Chapter(**data)  # raises if invalid
            ok += 1
        assert ok > 0, 'no chapters found to test'


class TestBracketRejection:
    """Wrong brackets for the chapter's language are rejected."""

    def test_cn_rejects_english_brackets(self):
        with __import__('pytest').raises(ValueError) as exc_info:
            make_chapter('cn', dialogue_text='\u201Cwrong\u201D')
        assert 'dialogue[cn]' in str(exc_info.value)

    def test_jp_rejects_curly(self):
        with __import__('pytest').raises(ValueError) as exc_info:
            make_chapter('jp', dialogue_text='\u201Cwrong\u201D')
        assert 'dialogue[jp]' in str(exc_info.value)
