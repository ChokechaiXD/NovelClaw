"""test_translate_commit.py — Workflow script (Phase 2 critical path).

Locks down the behavior of:
  - fix_block_types() — auto-fixes common block type issues
  - count_cn_leak() — counts CN/JP leaks in narration/dialogue
  - ch_path() — produces canonical chapter path

The cmd_check/cmd_fix_types/cmd_commit functions are tested by mocking
the file system (no actual git operations in tests).
"""
import json
import sys
import shutil
import tempfile
from pathlib import Path

# Make tools/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import pytest  # noqa: E402

import translate_commit as tc  # noqa: E402


# ── fix_block_types ──────────────────────────────────────────────────

class TestFixBlockTypes:
    """Auto-fix common block type issues."""

    def test_system_message_becomes_system(self):
        data = {'blocks': [{'type': 'system_message', 'text': '【HP】'}]}
        changed, fixes = tc.fix_block_types(data)
        assert changed is True
        assert data['blocks'][0]['type'] == 'system'
        assert any('system_message → system' in f[1] for f in fixes)

    def test_end_marker_becomes_end(self):
        data = {'blocks': [{'type': 'end_marker', 'text': 'x'}]}
        changed, _ = tc.fix_block_types(data)
        assert changed is True
        assert data['blocks'][0]['type'] == 'end'

    def test_parenthetical_system_becomes_narration(self):
        """【...】 that is actually (parenthetical) → narration."""
        data = {'blocks': [{'type': 'system', 'text': '(ถอนหายใจ)'}]}
        changed, fixes = tc.fix_block_types(data)
        assert changed is True
        assert data['blocks'][0]['type'] == 'narration'
        assert any('parenthetical' in f[1] for f in fixes)

    def test_standalone_dots_becomes_narration(self):
        data = {'blocks': [{'type': 'system', 'text': '...'}]}
        changed, _ = tc.fix_block_types(data)
        assert changed is True
        assert data['blocks'][0]['type'] == 'narration'

    def test_normal_blocks_unchanged(self):
        data = {'blocks': [
            {'type': 'narration', 'text': 'hi'},
            {'type': 'dialogue', 'text': '「hi」'},
            {'type': 'end', 'text': '(จบบท)'},
        ]}
        changed, fixes = tc.fix_block_types(data)
        assert changed is False
        assert fixes == []

    def test_mixed_fixes(self):
        data = {'blocks': [
            {'type': 'system_message', 'text': '【ok】'},
            {'type': 'narration', 'text': 'fine'},
            {'type': 'system', 'text': '(breath)'},
        ]}
        changed, fixes = tc.fix_block_types(data)
        assert changed is True
        assert len(fixes) == 2

    def test_empty_blocks(self):
        data = {'blocks': []}
        changed, fixes = tc.fix_block_types(data)
        assert changed is False
        assert fixes == []


# ── count_cn_leak ────────────────────────────────────────────────────

class TestCountCNLeak:
    """Counts CN/JP chars in narration + dialogue only."""

    def test_no_leak(self):
        data = {'blocks': [
            {'type': 'narration', 'text': 'ปกติ'},
            {'type': 'dialogue', 'text': '「สวัสดี」'},
        ]}
        assert tc.count_cn_leak(data) == 0

    def test_narration_leak(self):
        data = {'blocks': [
            {'type': 'narration', 'text': '曹星เดิน'},  # 2 CN
        ]}
        assert tc.count_cn_leak(data) == 2

    def test_dialogue_leak(self):
        data = {'blocks': [
            {'type': 'dialogue', 'text': '「我爱你」'},  # 3 CN
        ]}
        assert tc.count_cn_leak(data) == 3

    def test_system_not_counted(self):
        """CN inside system blocks is whitelisted — not a leak."""
        data = {'blocks': [
            {'type': 'system', 'text': '【等级 10】'},  # 2 CN, but whitelisted
        ]}
        assert tc.count_cn_leak(data) == 0

    def test_jp_kana_counted(self):
        data = {'blocks': [
            {'type': 'narration', 'text': 'こんにちは'},  # 5 hiragana
        ]}
        assert tc.count_cn_leak(data) == 5

    def test_mixed_blocks(self):
        data = {'blocks': [
            {'type': 'narration', 'text': '干净的'},  # 3 CN
            {'type': 'dialogue', 'text': '「你好」'},  # 2 CN
            {'type': 'system', 'text': '【HP】'},
        ]}
        assert tc.count_cn_leak(data) == 5


# ── ch_path ──────────────────────────────────────────────────────────

class TestChPath:
    """Returns canonical chapter path under REPO/novels/global-descent/chapters/."""

    def test_format_4digit(self):
        p = tc.ch_path(1)
        assert p.name == '0001.json'
        p = tc.ch_path(116)
        assert p.name == '0116.json'
        p = tc.ch_path(1239)
        assert p.name == '1239.json'

    def test_path_in_chapters_dir(self):
        p = tc.ch_path(50)
        assert 'chapters' in p.parts
        assert p.parent.name == 'chapters'

    def test_path_in_correct_novel(self):
        p = tc.ch_path(50)
        assert 'global-descent' in p.parts


# ── cmd_check (mocked) ───────────────────────────────────────────────

class TestCmdCheck:
    """cmd_check reports CN leak + schema status."""

    def test_clean_chapter_returns_zero(self, monkeypatch, capsys):
        clean = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1 Test', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': 'hi'},
                {'type': 'dialogue', 'text': '「hi」'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_ch_path(monkeypatch, clean)
        rc = tc.cmd_check(1)
        assert rc == 0
        out = capsys.readouterr().out
        assert 'CN/JP leak: 0' in out
        assert 'Schema: OK' in out

    def test_leaky_chapter_returns_one(self, monkeypatch, capsys):
        leaky = {
            'schema_version': 1, 'num': 1, 'title': 'ตอนที่ 1 Test', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': '曹星'},
                {'type': 'end', 'text': '(จบบท)'},
            ],
        }
        _patch_ch_path(monkeypatch, leaky)
        rc = tc.cmd_check(1)
        assert rc == 1
        out = capsys.readouterr().out
        assert 'CN/JP leak: 2' in out

    def test_schema_fail_returns_one(self, monkeypatch, capsys):
        bad = {
            'schema_version': 1, 'num': 1, 'title': 'BAD', 'source': 'ch 1',
            'blocks': [
                {'type': 'narration', 'text': 'hi'},
                # missing end marker
            ],
        }
        _patch_ch_path(monkeypatch, bad)
        rc = tc.cmd_check(1)
        assert rc == 1
        out = capsys.readouterr().out
        assert 'Schema: FAIL' in out


# ── Helpers ──────────────────────────────────────────────────────────

def _patch_ch_path(monkeypatch, chapter_data):
    """Make ch_path() return a Path to a tmp file with given data."""
    d = Path(tempfile.mkdtemp(prefix="tc_test_"))
    p = d / f"{chapter_data['num']:04d}.json"
    p.write_text(json.dumps(chapter_data, ensure_ascii=False, indent=2),
                 encoding='utf-8')
    monkeypatch.setattr(tc, 'ch_path', lambda n: p)
    return d
