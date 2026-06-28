from types import SimpleNamespace

import pytest

import quality_gate
import scorer


def _paragraphs(texts):
    return [{"type": "narration", "text": text} for text in texts]


def test_term_compliance_only_requires_terms_present_in_source(monkeypatch):
    policy = SimpleNamespace(
        terms={
            "black dragon": SimpleNamespace(action="replace", value="มังกรดำ"),
            "ice seal": SimpleNamespace(action="replace", value="ผนึกน้ำแข็ง"),
            "silver wolf": SimpleNamespace(action="replace", value="หมาป่าเงิน"),
            "flame sword": SimpleNamespace(action="replace", value="ดาบเพลิง"),
        }
    )

    monkeypatch.setattr("qa.term_policy.get_term_policy", lambda _lang: policy)

    result = scorer._score_term_compliance(
        _paragraphs(["เฉาซิงเห็นมังกรดำบินผ่านท้องฟ้า"]),
        source_text="The black dragon crossed the sky.",
    )

    assert result.passed is True
    assert result.score == 1.0


def test_term_compliance_flags_missing_source_term_value(monkeypatch):
    policy = SimpleNamespace(
        terms={
            "black dragon": SimpleNamespace(action="replace", value="มังกรดำ"),
            "ice seal": SimpleNamespace(action="replace", value="ผนึกน้ำแข็ง"),
        }
    )

    monkeypatch.setattr("qa.term_policy.get_term_policy", lambda _lang: policy)

    result = scorer._score_term_compliance(
        _paragraphs(["เฉาซิงเห็นมังกรดำบินผ่านท้องฟ้า"]),
        source_text="The black dragon broke the ice seal.",
    )

    assert result.passed is False
    assert "ผนึกน้ำแข็ง" in result.detail


def test_scorer_does_not_clear_term_policy_cache(monkeypatch):
    def fail_if_cleared():
        raise AssertionError("cache_clear should not run during scoring")

    import qa.term_policy as term_policy

    monkeypatch.setattr(term_policy.get_term_policy, "cache_clear", fail_if_cleared)

    result = scorer.score_chapter(
        [
            {"type": "narration", "text": "เฉาซิงเดินไปข้างหน้า"},
            {"type": "dialogue", "text": '"ไปกันเถอะ"'},
            {"type": "narration", "text": "ทุกคนพยักหน้า"},
            {"type": "end", "text": "(จบบท)"},
        ],
        source_char_count=50,
        target_lang="th",
        source_text="",
    )

    assert isinstance(result.weighted_total, float)


def test_quality_gate_fails_when_dimension_fails_even_if_weighted_total_is_high(monkeypatch):
    fake_result = SimpleNamespace(
        weighted_total=90.0,
        dimensions=[SimpleNamespace(name="Script Purity", score=0.9)],
        errors=["Script Purity: leak"],
    )

    monkeypatch.setattr(quality_gate, "score_chapter", lambda *_args, **_kwargs: fake_result)
    monkeypatch.setattr(quality_gate, "score_report", lambda _result: "report")

    result = quality_gate.evaluate_translation_quality([], "source", threshold=85.0)

    assert result["passed"] is False
