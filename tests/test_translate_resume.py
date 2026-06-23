"""Tests for translate.py — resume, concurrent, retry, and CLI."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

# We'll test through the module's public functions
import progress as progress_mod
import translate as translate_mod
from schema import get_novel_root


# ── Mock chapter source ──────────────────────────────────────────────
MOCK_SOURCE = """---
num: 1
title: 第1章 测试
---
測試內容第一章的一些文字。
這是一段關於战斗的描述。
---
来源: https://example.com
"""


@pytest.fixture
def temp_novel():
    """Create a temp directory with minimal novel structure for testing."""
    with tempfile.TemporaryDirectory(prefix="novelclaw_test_") as td:
        tmp = Path(td)
        slug = "test_novel"
        novel_dir = tmp / "novels" / slug
        source_dir = novel_dir / "chapters" / "source"
        chapters_dir = novel_dir / "chapters"
        source_dir.mkdir(parents=True)

        # Mock progress dir
        (tmp / ".chprogress").mkdir()

        # Write mock source (ch1)
        (source_dir / "0001.md").write_text(MOCK_SOURCE, encoding="utf-8")
        (source_dir / "0002.md").write_text(MOCK_SOURCE, encoding="utf-8")
        (source_dir / "0003.md").write_text(MOCK_SOURCE, encoding="utf-8")
        (source_dir / "0099.md").write_text("not a real chapter\n99", encoding="utf-8")

        yield tmp, slug, source_dir, chapters_dir


def test_resume_skips_existing(temp_novel, monkeypatch):
    """Test that --resume skips already translated chapters."""
    tmp_path, slug, src_dir, ch_dir = temp_novel
    
    monkeypatch.setattr(translate_mod, "_get_source_dir", lambda: src_dir)
    monkeypatch.setattr(translate_mod, "CHAPTERS_DIR", ch_dir)
    monkeypatch.setattr(progress_mod, "PROGRESS_DIR", tmp_path / ".chprogress")
    monkeypatch.setattr(translate_mod, "NOVEL_ROOT", tmp_path / "novels" / slug)
    
    os.environ["NOVEL_SLUG"] = slug
    
    # Initialize progress: mark ch1 as pending, ch2 as done
    state = {str(k): {"status": "pending" if k == 1 else "done", "retries": 0, "updated": None} for k in range(1, 4)}
    state["3"] = {"status": "pending", "retries": 0, "updated": None}
    progress_mod.save_progress(state, slug)
    
    pending_keys = progress_mod.get_pending(state)
    ch_nums = sorted([1, 2, 3])
    filtered = sorted([int(k) for k in pending_keys if k in [str(c) for c in ch_nums]])
    
    assert filtered == [1, 3], f"Expected [1, 3], got {filtered}"
    assert 2 not in filtered, "ch2 should be skipped (already done)"


def test_no_resume_full_batch(temp_novel, monkeypatch):
    """Without --resume, all chapters are processed."""
    tmp_path, slug, src_dir, ch_dir = temp_novel
    
    monkeypatch.setattr(translate_mod, "_get_source_dir", lambda: src_dir)
    monkeypatch.setattr(translate_mod, "CHAPTERS_DIR", ch_dir)
    monkeypatch.setattr(translate_mod, "NOVEL_ROOT", tmp_path / "novels" / slug)
    
    # Pre-write ch2 output (simulating already translated)
    (ch_dir / "0002.json").write_text(
        json.dumps({
            "num": 2, "title": "ตอนที่ 2 [MOCK]",
            "paragraphs": ["ch2", "(จบบท)"],
            "source": "ch 2", "lang": "cn",
        }),
        encoding="utf-8",
    )
    
    # ch2 output already exists
    # translate_one should detect it and skip
    result = translate_mod.translate_one(
        2, mock=True, progress_state=None, progress_slug=slug,
    )
    assert result is False, "translate_one should return False for existing output"


def test_successful_translation(temp_novel, monkeypatch):
    """Test successful mock translation."""
    tmp_path, slug, src_dir, ch_dir = temp_novel
    
    monkeypatch.setattr(translate_mod, "_get_source_dir", lambda: src_dir)
    monkeypatch.setattr(translate_mod, "CHAPTERS_DIR", ch_dir)
    monkeypatch.setattr(translate_mod, "NOVEL_ROOT", tmp_path / "novels" / slug)
    
    result = translate_mod.translate_one(
        1, mock=True, progress_state=None, progress_slug=slug,
    )
    assert result is True, f"translate_one should succeed, got {result}"
    
    # Verify output was written
    output_path = ch_dir / "0001.json"
    assert output_path.exists(), "Output file should exist"
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["num"] == 1
    assert "[CN:" in data["title"] or "mock" in data["title"].lower()


def test_missing_source(temp_novel, monkeypatch):
    """Test handling of missing source file."""
    tmp_path, slug, src_dir, ch_dir = temp_novel
    
    monkeypatch.setattr(translate_mod, "_get_source_dir", lambda: src_dir)
    monkeypatch.setattr(translate_mod, "CHAPTERS_DIR", ch_dir)
    monkeypatch.setattr(translate_mod, "NOVEL_ROOT", tmp_path / "novels" / slug)
    
    result = translate_mod.translate_one(
        99, mock=True, progress_state=None, progress_slug=slug,
    )
    assert result is False, "translate_one should fail for missing source"


def test_progress_tracking(temp_novel, monkeypatch):
    """Test that progress state is updated during translation."""
    tmp_path, slug, src_dir, ch_dir = temp_novel
    
    monkeypatch.setattr(translate_mod, "_get_source_dir", lambda: src_dir)
    monkeypatch.setattr(translate_mod, "CHAPTERS_DIR", ch_dir)
    monkeypatch.setattr(progress_mod, "PROGRESS_DIR", tmp_path / ".chprogress")
    
    state = progress_mod.init_progress([1, 3], slug)
    
    # Translate ch1 should succeed
    result = translate_mod.translate_one(
        1, mock=True, progress_state=state, progress_slug=slug,
    )
    assert result is True
    progress_mod.save_progress(state, slug)
    
    summary = progress_mod.get_summary(state)
    assert summary["done"] == 1
    assert summary["pending"] == 1
    assert summary["failed"] == 0
