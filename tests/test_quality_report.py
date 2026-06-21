"""Tests for tools/quality_report.py — quality report CLI."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.quality_report import _clean_list_chapters
from tools.quality_scorer import build_quality_report, ScoreResult


def test_clean_list_chapters_range():
    """Range string produces correct chapter list."""
    result = _clean_list_chapters("1-5", False)
    assert result == [1, 2, 3, 4, 5]


def test_clean_list_chapters_single():
    """Single number produces list of one."""
    result = _clean_list_chapters("42", False)
    assert result == [42]


def test_clean_list_chapters_all(monkeypatch, tmp_path):
    """all_flag with no JSON files returns []."""
    monkeypatch.setattr("tools.quality_report.CHAPTERS_DIR", tmp_path)
    result = _clean_list_chapters("", True)
    assert result == []


def test_clean_list_chapters_invalid():
    """Invalid string should raise ValueError."""
    with pytest.raises(ValueError):
        _clean_list_chapters("abc", False)


def test_build_quality_report_generates_markdown():
    """Quality report produces valid markdown with summary."""
    chapters = [
        {"num": 1, "title": "Ch1"},
        {"num": 2, "title": "Ch2"},
    ]
    results = [
        ScoreResult(overall=8.0, fluency=8.0, accuracy=8.0,
                    terminology=8.0, completeness=8.0, passed=True, errors=[]),
        ScoreResult(overall=6.0, fluency=5.0, accuracy=6.0,
                    terminology=6.0, completeness=7.0, passed=False,
                    errors=[{"category": "fluency", "severity": "major",
                             "detail": "Unnatural phrasing"}]),
    ]
    report = build_quality_report(chapters, results)
    
    assert "## Summary" in report
    assert "Ch1" in report or "Ch 1" in report
    assert "8.0" in report
    assert "❌" in report or "fail" in report.lower()


def test_build_quality_report_empty():
    """Empty chapters list produces minimal report."""
    report = build_quality_report([], [])
    assert "Ch | Title" in report


def test_build_quality_report_none_results():
    """None results (regex-only) produce 'regex' markers."""
    chapters = [{"num": 1, "title": "Ch"}]
    report = build_quality_report(chapters, [None])
    assert "regex" in report


def test_score_result_to_dict():
    """ScoreResult serializes to dict correctly."""
    sr = ScoreResult(overall=7.5, fluency=7.0, accuracy=8.0,
                     terminology=7.5, completeness=8.0, passed=True,
                     errors=[{"severity": "minor", "category": "fluency",
                               "detail": "test"}])
    d = sr.to_dict()
    assert d["overall"] == 7.5
    assert d["passed"] is True
    assert d["error_count"] == 1
