"""Tests: MQM Error Typology (Phase 2)."""
import pytest
from scorer import MqmError, _mqm_map, score_chapter, DimensionScore


# ── MqmError dataclass ──────────────────────────────────────────────


def test_mqm_error_minimal():
    e = MqmError(category="accuracy", subcategory="omission", severity="major")
    assert e.category == "accuracy"
    assert e.subcategory == "omission"
    assert e.severity == "major"
    assert e.span == ""
    assert e.position == -1
    assert e.detail == ""


def test_mqm_error_full():
    e = MqmError(
        category="accuracy", subcategory="addition",
        severity="critical",
        span="extra sentence about weather",
        position=3,
        detail="Output contains 2 sentences not present in source.",
    )
    assert e.position == 3
    assert "weather" in e.span
    assert "2 sentences" in e.detail


def test_mqm_error_to_short():
    e = MqmError(category="script_leak", subcategory="foreign_script",
                 severity="major", detail="3 Latin tokens in Thai output")
    short = e.to_short()
    assert "[major]" in short
    assert "script_leak/foreign_script" in short
    assert len(short) <= 120


def test_mqm_error_severity_values():
    """Only minor, major, critical are valid."""
    for sev in ("minor", "major", "critical"):
        e = MqmError(category="style", subcategory="monotonous_type", severity=sev)
        assert e.severity == sev


# ── _mqm_map ────────────────────────────────────────────────────────


def test_mqm_map_completeness_short():
    cat, sub, sev = _mqm_map("Completeness", "too short")
    assert cat == "accuracy"
    assert sub == "omission"
    assert sev == "critical"


def test_mqm_map_completeness_long():
    cat, sub, sev = _mqm_map("Completeness", "too long")
    assert cat == "accuracy"
    assert sub == "addition"
    assert sev == "critical"


def test_mqm_map_script_purity():
    cat, sub, sev = _mqm_map("Script Purity", "3 leaks (Latin×2 Han×1)")
    assert cat == "script_leak"
    assert sub == "foreign_script"
    assert sev == "major"


def test_mqm_map_end_marker():
    cat, sub, sev = _mqm_map("End Marker", "no end marker (last: 'done')")
    assert cat == "structure"
    assert sub == "missing_end_marker"
    # "no" not in the critical heuristic → defaults to major
    assert sev == "major"

def test_mqm_map_end_marker_critical():
    """When detail contains 'missing' → critical."""
    cat, sub, sev = _mqm_map("End Marker", "missing end marker")
    assert sev == "critical"


def test_mqm_map_type_diversity():
    cat, sub, sev = _mqm_map("Type Diversity", "no dialogue")
    assert cat == "style"
    assert sub == "monotonous_type"
    assert sev == "major"


def test_mqm_map_dialogue_ratio():
    cat, sub, sev = _mqm_map("Dialogue Ratio", "too little")
    assert cat == "style"
    assert sub == "dialogue_imbalance"
    assert sev == "major"


def test_mqm_map_term_compliance():
    cat, sub, sev = _mqm_map("Term Compliance", "missing term")
    assert cat == "terminology"
    assert sub == "term_mismatch"
    # "missing" in detail → critical
    assert sev == "critical"


def test_mqm_map_minor_severity():
    cat, sub, sev = _mqm_map("Dialogue Ratio", "slight imbalance")
    assert sev == "minor"


def test_mqm_map_unknown_dimension():
    """Unknown dimension falls back to accuracy/general."""
    cat, sub, sev = _mqm_map("Unknown", "something")
    assert cat == "accuracy"
    assert sub == "general"


# ── Integration: score_chapter produces MQM errors ──────────────────


def test_score_chapter_emits_mqm_on_failure():
    leaky = [
        {"type": "narration", "text": "AI system reboot confirmed"},
        {"type": "narration", "text": "HP and MP fully restored"},
        {"type": "narration", "text": "ทุกอย่างกลับมาเป็นปกติ"},
        {"type": "end", "text": "(จบบท)"},
    ]
    r = score_chapter(leaky, source_char_count=80,
                      source_text="AI系统重启确认。HP和MP已恢复。")
    assert len(r.mqm_errors) >= 1
    for e in r.mqm_errors:
        assert isinstance(e, MqmError)
        assert e.severity in ("minor", "major", "critical")


def test_score_chapter_no_mqm_on_perfect():
    """A chapter with adequate length should produce zero MQM errors."""
    perfect = [
        {"type": "narration", "text": "เฉาซิงเดินไปข้างหน้าอย่างเงียบงันท่ามกลางความมืดมิด"},
        {"type": "dialogue", "text": '"ไปกันเถอะ"'},
        {"type": "narration", "text": "ทุกคนพยักหน้าเห็นด้วยกับความคิดของเขา"},
        {"type": "end", "text": "(จบบท)"},
    ]
    r = score_chapter(perfect, source_char_count=60,
                      source_text='"ไปกันเถอะ" อีกาพูด')
    assert len(r.mqm_errors) == 0, f"got {len(r.mqm_errors)} MQM errors for {r.weighted_total}/100"
