"""test_cn_checker.py — CN/JP leak detection + auto-strip (Phase 2 critical path).

Locks down the behavior of:
  - check_chapter()  — counts CN/JP leaks per chapter
  - strip_chapter()  — removes author's thanks blocks
  - should_strip_block() — pattern match for author's thanks
  - strip_whitelist() — removes 【】 and 《》 zones
  - Multi-language: non-CN chapters are skipped

Note: uses `tempfile.mkdtemp()` instead of pytest's `tmp_path` fixture
because pytest's tmp_path hits Windows PermissionError on this host.
"""
import json
import sys
import shutil
import tempfile
from pathlib import Path

# Make tools/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# cn_checker uses module-level CHAPTERS_DIR (relative path), so we patch
# it via the CHAPTERS_DIR global before each test that needs a fixture.
import cn_checker  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture
def tmp_chapters():
    """Provide a fresh chapters/ dir as Path (cleaned up after test)."""
    d = Path(tempfile.mkdtemp(prefix="novelclaw_test_"))
    chapters = d / "chapters"
    chapters.mkdir()
    yield chapters
    shutil.rmtree(d, ignore_errors=True)


class TestStripWhitelist:
    """strip_whitelist removes 【...】 and 《...》 zones so we can leak-check the rest."""

    def test_removes_system_zones(self):
        text = 'before 【SYSTEM: HP 100】 after'
        out = cn_checker.strip_whitelist(text)
        assert '【SYSTEM' not in out
        assert 'before' in out and 'after' in out

    def test_removes_title_zones(self):
        text = 'see 《Game Title》 for details'
        out = cn_checker.strip_whitelist(text)
        assert '《Game' not in out
        assert 'see' in out and 'for details' in out

    def test_keeps_naked_text(self):
        text = 'no zones here'
        assert cn_checker.strip_whitelist(text) == text

    def test_multiple_zones(self):
        text = 'a 【x】 b 《y》 c 【z】 d'
        out = cn_checker.strip_whitelist(text)
        for needle in ('【x】', '《y》', '【z】'):
            assert needle not in out


class TestShouldStripBlock:
    """should_strip_block identifies author's thanks blocks for auto-removal."""

    def test_strip_thai_thanks(self):
        assert cn_checker.should_strip_block('ขอบคุณนักอ่านครับ')

    def test_strip_thai_thanks_with_colon(self):
        assert cn_checker.should_strip_block('ขอบคุณนักอ่าน: ขอบคุณทุกท่าน')

    def test_strip_with_username_in_brackets(self):
        assert cn_checker.should_strip_block('ขอบคุณ《user123》500เหรียญ!')

    def test_strip_chinese_thanks(self):
        assert cn_checker.should_strip_block('感谢书友们的收藏和订阅')

    def test_dont_strip_normal_narration(self):
        assert not cn_checker.should_strip_block('เฉาซิงเดินไปข้างหน้า')

    def test_dont_strip_dialogue(self):
        assert not cn_checker.should_strip_block('「สวัสดี」')

    def test_dont_strip_thanks_inside_text(self):
        # Only matches at the start of the line
        assert not cn_checker.should_strip_block('พูดว่า ขอบคุณนักอ่านครับ')


class TestCheckChapter:
    """check_chapter returns (leak_count, leak_details)."""

    def test_clean_chapter(self, tmp_chapters, monkeypatch):
        clean = {
            'schema_version': 1,
            'num': 1, 'title': 'ตอนที่ 1 Test', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': 'เฉาซิงเดินไป'},
                {'type': 'dialogue', 'text': '「สวัสดี」'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, clean)
        count, leaks = cn_checker.check_chapter(1)
        assert count == 0
        assert leaks == []

    def test_narration_leak(self, tmp_chapters, monkeypatch):
        leaked = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': '曹星เดินไป'},  # 曹星 is CN
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, leaked)
        count, leaks = cn_checker.check_chapter(1)
        assert count >= 2  # 曹 + 星 (2 chars)
        assert leaks[0][1] == 'narration'

    def test_dialogue_leak(self, tmp_chapters, monkeypatch):
        leaked = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1', 'source': 'ch 1',
            'blocks': [
                {'type': 'dialogue', 'text': '「我爱你」'},  # 3 CN chars
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, leaked)
        count, _ = cn_checker.check_chapter(1)
        assert count == 3

    def test_jp_kana_caught(self, tmp_chapters, monkeypatch):
        leaked = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': 'こんにちは'},  # 5 hiragana
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, leaked)
        count, _ = cn_checker.check_chapter(1)
        assert count == 5

    def test_system_zone_whitelisted(self, tmp_chapters, monkeypatch):
        """CN inside 【...】 is allowed (game system message)."""
        data = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1', 'source': 'ch 1',
            'blocks': [
                {'type': 'system', 'text': '【HP: 100/100 等级】'},  # 等级 inside = OK
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, data)
        count, _ = cn_checker.check_chapter(1)
        assert count == 0

    def test_strict_mode_catches_whitelist(self, tmp_chapters, monkeypatch):
        data = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1', 'source': 'ch 1',
            'blocks': [
                {'type': 'system', 'text': '【HP: 100 等级】'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, data)
        count, _ = cn_checker.check_chapter(1, strict=True)
        assert count >= 2  # 等 + 级 caught in strict

    def test_non_cn_chapter_skipped(self, tmp_chapters, monkeypatch):
        """EN chapters don't get leak-checked (their source IS in target lang)."""
        data = {
            'schema_version': 1, 'num': 1, 'title': 'Chapter 1', 'source': 'ch 1',
            'lang': 'en',
            'blocks': [
                {'type': 'narration', 'text': 'normal text'},
                {'type': 'end', 'text': '(End)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, data)
        count, leaks = cn_checker.check_chapter(1)
        assert count == 0
        assert leaks == []

    def test_missing_chapter_returns_zero(self, tmp_chapters, monkeypatch):
        monkeypatch.setattr(cn_checker, 'CHAPTERS_DIR', tmp_chapters)
        count, leaks = cn_checker.check_chapter(999)
        assert count == 0
        assert leaks == []

    def test_thanks_block_skipped(self, tmp_chapters, monkeypatch):
        """Author's thanks blocks are skipped (not flagged as leaks)."""
        data = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': 'เฉาซิงเดิน'},
                {'type': 'narration', 'text': 'ขอบคุณ《user123》500เหรียญ!'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, data)
        count, _ = cn_checker.check_chapter(1)
        assert count == 0


class TestStripChapter:
    """strip_chapter removes author's thanks blocks (with dry_run support)."""

    def test_dry_run_returns_removed_without_writing(self, tmp_chapters, monkeypatch):
        data = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': 'keep this'},
                {'type': 'narration', 'text': 'ขอบคุณนักอ่าน'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, data)
        removed = cn_checker.strip_chapter(1, dry_run=True)
        assert len(removed) == 1
        # File NOT modified in dry_run
        on_disk = json.loads((tmp_chapters / '0001.json').read_text(encoding='utf-8'))
        assert len(on_disk['blocks']) == 3

    def test_actual_run_writes(self, tmp_chapters, monkeypatch):
        data = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': 'keep this'},
                {'type': 'narration', 'text': 'ขอบคุณนักอ่าน'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, data)
        removed = cn_checker.strip_chapter(1, dry_run=False)
        assert len(removed) == 1
        on_disk = json.loads((tmp_chapters / '0001.json').read_text(encoding='utf-8'))
        # End marker still there, but thanks block gone
        assert len(on_disk['blocks']) == 2
        assert on_disk['blocks'][0]['text'] == 'keep this'
        assert on_disk['blocks'][1]['type'] == 'end'

    def test_no_thanks_returns_empty(self, tmp_chapters, monkeypatch):
        data = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': 'no thanks here'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_chapters_dir(monkeypatch, tmp_chapters, data)
        removed = cn_checker.strip_chapter(1, dry_run=True)
        assert removed == []

    def test_missing_chapter_returns_empty(self, tmp_chapters, monkeypatch):
        monkeypatch.setattr(cn_checker, 'CHAPTERS_DIR', tmp_chapters)
        assert cn_checker.strip_chapter(999) == []


# ── Helper ────────────────────────────────────────────────────────────

def _patch_chapters_dir(monkeypatch, chapters_dir, chapter_data):
    """Write a single chapter to chapters_dir and point cn_checker at it."""
    path = chapters_dir / f"{chapter_data['num']:04d}.json"
    path.write_text(json.dumps(chapter_data, ensure_ascii=False, indent=2),
                    encoding='utf-8')
    monkeypatch.setattr(cn_checker, 'CHAPTERS_DIR', chapters_dir)
