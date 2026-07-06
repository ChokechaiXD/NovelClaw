"""Tests: scorer language-agnostic configuration."""
import scorer
from scorer import (
    _get_lang_config,
    _score_end_marker,
    _score_completeness,
    _score_dialogue_ratio,
    DimensionScore,
)


class TestGetLangConfig:
    def test_thai_defaults(self):
        cfg = _get_lang_config("th")
        assert cfg["end_marker_regex"] is not None
        assert cfg["completeness_min"] == 0.85
        assert cfg["dialogue_ratio_max"] == 0.80

    def test_english_config(self):
        cfg = _get_lang_config("en")
        assert cfg["end_marker_regex"] is not None
        assert cfg["completeness_min"] == 0.70  # EN allows tighter output
        assert cfg["completeness_max"] == 2.50

    def test_korean_config(self):
        cfg = _get_lang_config("ko")
        assert cfg["end_marker_regex"] is not None
        assert cfg["completeness_min"] == 0.75
        assert cfg["dialogue_ideal_max"] == 0.65

    def test_unknown_lang_falls_back_to_thai(self):
        cfg = _get_lang_config("jp")
        assert cfg["completeness_min"] == 0.85  # TH defaults
        assert cfg["end_marker_regex"] == _get_lang_config("th")["end_marker_regex"]


class TestEndMarkerMultiLang:
    def test_thai_end_marker(self):
        paras = [{"text": "hello", "type": "narration"}, {"text": "(จบบท)", "type": "end"}]
        r = _score_end_marker(paras, "th")
        assert r.score == 1.0, f"TH end marker failed: {r.detail}"

    def test_english_end_marker(self):
        paras = [{"text": "hello", "type": "narration"}, {"text": "(End of chapter)", "type": "end"}]
        r = _score_end_marker(paras, "en")
        assert r.score == 1.0, f"EN end marker failed: {r.detail}"

    def test_korean_end_marker(self):
        paras = [{"text": "hello", "type": "narration"}, {"text": "(끝)", "type": "end"}]
        r = _score_end_marker(paras, "ko")
        assert r.score == 1.0, f"KO end marker failed: {r.detail}"

    def test_bare_english_end(self):
        paras = [{"text": "hello", "type": "narration"}, {"text": "(End)", "type": "end"}]
        r = _score_end_marker(paras, "en")
        assert r.score == 1.0, f"EN bare end failed: {r.detail}"

    def test_japanese_ending_uses_thai_fallback(self):
        paras = [{"text": "hello", "type": "narration"}, {"text": "(終)", "type": "end"}]
        r = _score_end_marker(paras, "jp")  # fallback to TH
        assert r.score == 1.0, f"JP fallback failed: {r.detail}"

    def test_missing_end_marker_fails(self):
        paras = [{"text": "hello", "type": "narration"}]
        r = _score_end_marker(paras, "th")
        assert r.score == 0.0, f"should have failed: {r.detail}"


class TestCompletenessMultiLang:
    def test_thai_short_penalty(self):
        paras = [{"text": "a" * 200, "type": "narration"}, {"text": "b" * 200, "type": "narration"}, {"text": "c" * 200, "type": "narration"}, {"text": "(จบบท)", "type": "end"}]
        # 600 chars vs 800 source = 0.75x → below TH min of 0.85
        r = _score_completeness(paras, 800, "th")
        assert r.score < 1.0, f"TH short should have penalty: {r.detail}"

    def test_english_short_but_ok(self):
        paras = [{"text": "a" * 200, "type": "narration"}, {"text": "b" * 200, "type": "narration"}, {"text": "c" * 200, "type": "narration"}, {"text": "(End)", "type": "end"}]
        # 600 chars vs 800 source = 0.75x → EN min is 0.70, OK
        r = _score_completeness(paras, 800, "en")
        assert r.score >= 0.6, f"EN short should be gentler: {r.detail}"


class TestDialogueRatioMultiLang:
    def test_normal_dialogue(self):
        paras = [{"text": "A", "type": "narration"}, {"text": "B", "type": "dialogue"}, {"text": "C", "type": "narration"}, {"text": "(จบบท)", "type": "end"}]
        r = _score_dialogue_ratio(paras, True, "th")
        assert r.score >= 0.8, f"TH dialogue ratio unexpected: {r.detail}"

    def test_very_high_dialogue_english_tolerant(self):
        # EN: 90% dialogue is within max of 0.85? Let's check
        paras = [{"text": "A", "type": "dialogue"} for _ in range(9)] + [{"text": "N", "type": "narration"}, {"text": "(End)", "type": "end"}]
        r = _score_dialogue_ratio(paras, True, "en")
        assert r.score > 0, f"EN high dialogue too penalized: {r.detail}"
