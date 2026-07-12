"""Tests for pipeline pure functions (no LLM, no IO)."""
from __future__ import annotations

import logging

import pytest

import pipeline

from pipeline import (
    _build_repair_instruction,
    _failed_translation_result,
    _needs_review_result,
    _quality_repair_decision,
    _quality_summary,
    _split_prompt,
)


def test_logging_reports_file_handler_when_available(monkeypatch):
    messages = []
    monkeypatch.setattr(pipeline, "_LOGGING_CONFIGURED", False)
    monkeypatch.setattr(pipeline.logging, "FileHandler", lambda *_args, **_kwargs: logging.NullHandler())
    monkeypatch.setattr(pipeline.logging, "basicConfig", lambda **_kwargs: None)
    monkeypatch.setattr(pipeline.logger, "info", lambda *args: messages.append(args))

    pipeline._ensure_logging()

    assert messages == [("Logging initialized (file=%s)", pipeline._PROJECT_ROOT / "novelclaw.log")]


def test_logging_reports_stdout_only_when_file_handler_fails(monkeypatch):
    messages = []
    monkeypatch.setattr(pipeline, "_LOGGING_CONFIGURED", False)
    monkeypatch.setattr(
        pipeline.logging,
        "FileHandler",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("read-only filesystem")),
    )
    monkeypatch.setattr(pipeline.logging, "basicConfig", lambda **_kwargs: None)
    monkeypatch.setattr(pipeline.logger, "info", lambda *args: messages.append(args))

    pipeline._ensure_logging()

    assert messages == [("Logging initialized (stdout only)",)]


# ── _split_prompt ──────────────────────────────────────────────────────────


def test_split_prompt_finds_continuity_marker():
    prompt = "You are a translator.\n\n<continuity>\nChapter 5 continues the journey."
    system, user = _split_prompt(prompt)
    assert system == "You are a translator."
    assert user == "<continuity>\nChapter 5 continues the journey."


def test_split_prompt_falls_back_to_glossary_marker():
    prompt = "Translate carefully.\n\n<glossary>\nBlack Dragon = มังกรดำ"
    system, user = _split_prompt(prompt)
    assert system == "Translate carefully."
    assert user.startswith("<glossary>")


def test_split_prompt_no_marker():
    prompt = "Just translate this text directly."
    system, user = _split_prompt(prompt)
    assert system is None
    assert user == prompt


def test_split_prompt_append_repair_instruction():
    prompt = "Translate.\n\n<continuity>\nChapter text."
    system, user = _split_prompt(prompt, repair_instruction="\n<repair>Fix this")
    assert user.endswith("\n<repair>Fix this")


# ── _quality_summary ───────────────────────────────────────────────────────


def test_quality_summary_passed():
    score_result = {
        "passed": True, "score": 92.0, "threshold": 85.0,
        "errors": [], "warnings": [], "repair_notes": [],
        "lengthRatio": 1.2, "scriptLeaks": 0, "structure": {"narration": 5, "dialogue": 3},
    }
    summary = _quality_summary(score_result, [])
    assert summary["passed"] is True
    assert summary["score"] == 92.0


def test_quality_summary_failed():
    score_result = {
        "passed": False, "score": 60.0, "threshold": 85.0,
        "errors": ["Completeness: too short"], "warnings": [],
    }
    summary = _quality_summary(score_result, [])
    assert summary["passed"] is False
    assert "Completeness: too short" in summary["hardFailures"]


def test_quality_summary_falls_back_errors_for_hard_failures():
    score_result = {"passed": False, "score": 50.0, "errors": ["Script leak detected"]}
    summary = _quality_summary(score_result, [])
    assert "Script leak detected" in summary["hardFailures"]


def test_quality_summary_backfills_repair_notes():
    score_result = {"passed": False, "score": 82.0, "repairNotes": ["Fix term: HP → พลังชีวิต"]}
    summary = _quality_summary(score_result, [])
    assert "Fix term: HP → พลังชีวิต" in summary["repairNotes"]


# ── _build_repair_instruction ─────────────────────────────────────────────


def test_repair_instruction_empty_when_no_errors():
    assert _build_repair_instruction({"score": 95, "passed": True}) == ""


def test_repair_instruction_uses_repair_notes():
    result = _build_repair_instruction({
        "repair_notes": ["Replace 'HP' with 'พลังชีวิต'", "Fix end marker"],
    })
    assert "<repair>" in result
    assert "HP" in result
    assert "พลังชีวิต" in result


def test_repair_instruction_falls_back_to_errors():
    result = _build_repair_instruction({
        "errors": ["Completeness: too short", "Script leak detected"],
    })
    assert "Script leak detected" in result
    assert result.count("- ") == 2


def test_repair_instruction_caps_at_5_notes():
    notes = [f"Error {i}" for i in range(10)]
    result = _build_repair_instruction({"errors": notes})
    assert result.count("- ") == 5


# ── _failed_translation_result ────────────────────────────────────────────


def test_failed_translation_result():
    result = _failed_translation_result(
        ch_num=123, reason="LLM timeout",
        attempts=[{"kind": "primary", "status": "error"}],
        source_lang="zh", source_profile={"script": "CJK"},
    )
    assert result["status"] == "failed"
    assert result["ch"] == 123
    assert result["reason"] == "LLM timeout"
    assert result["provider_name"] == ""
    assert result["source_lang"] == "zh"


def test_failed_translation_result_with_quality():
    result = _failed_translation_result(
        ch_num=456, reason="scorer failed",
        attempts=[], source_lang="en", source_profile={},
        quality={"score": 55.0},
    )
    assert result["quality"]["score"] == 55.0


# ── _needs_review_result ─────────────────────────────────────────────────


def test_needs_review_result():
    result = _needs_review_result(
        ch_num=789, reason="judge flagged risk",
        classified=[{"type": "narration", "text": "hello"}],
        score_result={"score": 88.0, "passed": True},
        judge_result={"ok": True, "feedback": "minor leak"},
        attempts=[{"kind": "primary", "status": "passed", "score": 88}],
        provider_name="openrouter", model_name="gpt-4",
        source_lang="zh", source_profile={"script": "CJK"},
    )
    assert result["status"] == "needs_review"
    assert result["ch"] == 789
    assert result["score"] == 88.0
    assert result["provider_name"] == "openrouter"


# ── _quality_repair_decision ──────────────────────────────────────────────


def test_quality_repair_decision_eligible():
    decision = _quality_repair_decision({
        "passed": False, "score": 82.0,
        "repair_notes": ["Fix term translation"],
    })
    assert decision["eligible"] is True
    assert decision["reason"] == "borderline_quality"


def test_quality_repair_decision_not_eligible_when_passed():
    decision = _quality_repair_decision({
        "passed": True, "score": 95.0, "repair_notes": [],
    })
    assert decision["eligible"] is False


def test_quality_repair_decision_not_eligible_when_no_notes():
    decision = _quality_repair_decision({
        "passed": False, "score": 82.0, "repair_notes": [],
    })
    assert decision["eligible"] is False


def test_quality_repair_decision_not_eligible_when_score_too_low():
    decision = _quality_repair_decision({
        "passed": False, "score": 65.0,
        "repair_notes": ["Fix term translation"],
    })
    assert decision["eligible"] is False


# ── _quality_summary edge: empty input ────────────────────────────────────


def test_quality_summary_empty_score_result():
    summary = _quality_summary({}, [])
    assert summary["passed"] is False
    assert summary["score"] == 0
    assert summary["attempts"] == []
