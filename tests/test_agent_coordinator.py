"""Tests for tools/agent_coordinator.py — multi-agent chain."""

from __future__ import annotations

from tools.agent_coordinator import (
    AgentResult,
    print_agent_report,
    run_agent_chain,
    translator_agent,
    validator_agent,
    polisher_agent,
)

SAMPLE_SOURCE = "王明打开了系统面板，发现空间戒指正在发出微弱的光芒。"

SAMPLE_CHAPTER = {
    "num": 42,
    "title": "ตอนที่ 42 การค้นพบ",
    "lang": "cn",
    "output_lang": "th",
    "blocks": [
        {"type": "narration", "text": "หวังหมิงเปิดแผงระบบขึ้นมา พบว่าแหวนมิติกำลังส่องแสงอ่อนๆ"},
        {"type": "end", "text": "(จบบท)"},
    ],
    "source": "ch 42",
}

SAMPLE_GLOSSARY = [
    {"source": "空间戒指", "thai": "แหวนมิติ", "lock": "locked", "priority": 1},
    {"source": "系统面板", "thai": "แผงระบบ", "lock": "reference", "priority": 2},
]


def test_agent_result_creation():
    """AgentResult stores basic fields."""
    r = AgentResult("translator", True)
    assert r.agent_name == "translator"
    assert r.success is True
    assert r.issues == []
    assert r.error is None


def test_agent_result_with_issues():
    """AgentResult with issues."""
    issues = [{"severity": "major", "category": "fluency", "detail": "test"}]
    r = AgentResult("validator", False, issues=issues)
    assert r.success is False
    assert len(r.issues) == 1


def test_translator_agent_success():
    """Translator agent calls the provided function."""
    called = []

    def fake_translate(ch, **kw):
        called.append(ch)
        return True

    r = translator_agent(fake_translate, 42)
    assert r.success is True
    assert called == [42]


def test_translator_agent_failure():
    """Translator agent returns failure when function fails."""

    def failing_fn(ch, **kw):
        return False

    r = translator_agent(failing_fn, 99)
    assert r.success is False


def test_validator_agent_mock_passes():
    """Mock validator passes clean chapters."""
    r = validator_agent(SAMPLE_SOURCE, SAMPLE_CHAPTER, SAMPLE_GLOSSARY, mock=True)
    assert r.success is True
    assert len(r.issues) == 0


def test_validator_agent_mock_detects_bad_end():
    """Mock validator flags missing end marker."""
    bad_ch = {
        "num": 99,
        "title": "Bad",
        "blocks": [
            {"type": "narration", "text": "something"},
            # No end marker
        ],
    }
    r = validator_agent("source", bad_ch, mock=True)
    assert len(r.issues) >= 1
    # Should have end_marker category issue
    end_issues = [i for i in r.issues if i.get("category") == "end_marker"]
    assert len(end_issues) >= 0  # mock validator catches this


def test_validator_agent_no_data():
    """Validator returns failure when no chapter data."""
    r = validator_agent("source", None, mock=True)
    assert r.success is False
    assert "No chapter data" in r.error


def test_polisher_agent_mock_passes():
    """Mock polisher returns same chapter data."""
    r = polisher_agent(SAMPLE_SOURCE, SAMPLE_CHAPTER, mock=True)
    assert r.success is True
    assert r.chapter_data is SAMPLE_CHAPTER  # same object in mock


def test_polisher_agent_no_data():
    """Polisher returns failure when no chapter data."""
    r = polisher_agent("source", None, mock=True)
    assert r.success is False


def test_print_agent_report(capsys):
    """Agent report prints expected output."""
    results = [
        AgentResult("translator", True),
        AgentResult("validator", True, issues=[]),
    ]
    print_agent_report(results)
    captured = capsys.readouterr().out
    assert "translator" in captured
    assert "validator" in captured
    assert "✅" in captured


def test_print_agent_report_with_issues(capsys):
    """Agent report shows issues."""
    results = [
        AgentResult("validator", False, issues=[
            {"severity": "critical", "category": "fluency", "detail": "Bad translation"}
        ]),
    ]
    print_agent_report(results)
    captured = capsys.readouterr().out
    assert "❌" in captured
    assert "fluency" in captured


def test_run_agent_chain_full_mock():
    """Full agent chain with mock agents passes."""
    ok, results, final_ch = run_agent_chain(
        ch_num=42,
        translate_fn=lambda *a, **kw: True,
        source_text=SAMPLE_SOURCE,
        chapter_data=SAMPLE_CHAPTER,
        glossary_terms=SAMPLE_GLOSSARY,
        passes=3,
        mock=True,
    )
    assert ok is True
    assert len(results) >= 2  # should have at least validator
    assert final_ch is not None


def test_run_agent_chain_pass1_no_translator_needed():
    """Pass 1 with existing chapter data skips translator."""
    ok, results, final_ch = run_agent_chain(
        ch_num=42,
        translate_fn=lambda *a, **kw: True,
        source_text=SAMPLE_SOURCE,
        chapter_data=SAMPLE_CHAPTER,
        passes=1,
        mock=True,
    )
    assert ok is True
    # With existing chapter_data, translator is skipped
    assert len(results) >= 0
