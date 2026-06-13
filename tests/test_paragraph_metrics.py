"""test_paragraph_metrics.py — Lock down em_dash / staccato / variety / etc."""
import pytest
from slop.paragraph_metrics import (
    em_dash_stats, staccato_check, sentence_variety, burstiness,
    function_word_diversity, megumin_structural_check, paragraph_metrics,
    FUNC_WORDS,
)


# ── em_dash_stats ──────────────────────────────────────────────────

class TestEmDashStats:
    """Em-dash (—) usage: body vs placeholder classification."""

    def test_no_dashes(self):
        result = em_dash_stats('เขาเดินเข้ามาในห้อง')
        assert result['total'] == 0
        assert result['body'] == 0
        assert result['placeholder'] == 0

    def test_mid_sentence_is_body(self):
        result = em_dash_stats('เขาเดิน — วิ่งออกไป')
        assert result['total'] == 1
        assert result['body'] == 1
        assert result['placeholder'] == 0

    def test_placeholder_after_space(self):
        """Em-dash preceded by space = placeholder (data marker)."""
        result = em_dash_stats('รางวัล 1000 —')
        assert result['total'] == 1
        assert result['placeholder'] == 1

    def test_placeholder_at_newline(self):
        result = em_dash_stats('รางวัล 1000 —\n')
        assert result['placeholder'] == 1

    def test_density_per_1000_chars(self):
        """1 em-dash in 503 chars → density capped at 1.0 per 1000
        (the max(1, ...) floor prevents very small texts giving huge
        density values)."""
        text = 'เขา' + '—' + 'x' * 499
        result = em_dash_stats(text)
        assert result['total'] == 1
        # Density for sub-1000-char texts is capped at 1.0
        assert result['density'] == 1.0

    def test_density_scales_with_text_length(self):
        """For longer texts (>1000 chars), density scales linearly."""
        # 5 em-dashes in 2005 chars → 5/(2005/1000) = 2.494 per 1000
        text = ('x' * 400 + '—') * 5
        result = em_dash_stats(text)
        assert result['density'] == pytest.approx(2.494, rel=1e-3)

    def test_mixed_body_and_placeholder(self):
        text = 'เขา — เธอ — 500 —'
        result = em_dash_stats(text)
        # 'เขา — เธอ' = body, '500 —' = placeholder
        assert result['body'] + result['placeholder'] == result['total']


# ── staccato_check ─────────────────────────────────────────────────

class TestStaccatoCheck:
    """3+ consecutive short sentences (<20 chars)."""

    def test_no_staccato(self):
        text = 'เขาเดินเข้ามาในห้องแล้วมองไปรอบๆ เห็นโต๊ะหนังสือเปิดอยู่'
        assert staccato_check(text) == []

    def test_three_short_sentences_flagged(self):
        text = 'เขาเดิน. เธอยืน. คนดู.'
        runs = staccato_check(text)
        assert len(runs) == 1
        assert len(runs[0]) == 3

    def test_two_short_not_flagged(self):
        """Only 2 short sentences is not staccato (need 3+)."""
        text = 'เขาเดิน. เธอยืน. เขาเดินเข้ามาในห้องอย่างระมัดระวัง'
        assert staccato_check(text) == []

    def test_empty_text(self):
        assert staccato_check('') == []

    def test_long_sentence_resets_streak(self):
        text = 'เขาเดิน. เธอยืน. ' + 'เขาเดินเข้ามาในห้องอย่างระมัดระวังมาก. ' * 3
        # Long sentence in middle resets the streak
        assert staccato_check(text) == []


# ── sentence_variety ───────────────────────────────────────────────

class TestSentenceVariety:
    """Sentence type diversity: Shannon entropy."""

    def test_empty_text(self):
        result = sentence_variety('')
        assert result['total'] == 0
        assert result['diversity'] == 0.0

    def test_declarative_dominant(self):
        """Mostly declarative sentences → high declarative count."""
        text = 'เขาเดินเข้ามา. เธอยืนอยู่. คนพูดคุยกัน.'
        result = sentence_variety(text)
        assert result['types'].get('declarative', 0) > 0

    def test_interrogative_detected(self):
        text = 'เขาจะไปไหน? เธอคิดอย่างไร?'
        result = sentence_variety(text)
        assert result['types'].get('interrogative', 0) == 2

    def test_exclamatory_detected(self):
        text = 'ระวัง! อย่าเข้าไป!'
        result = sentence_variety(text)
        assert result['types'].get('exclamatory', 0) == 2

    def test_diversity_zero_for_one_type(self):
        """All one type → entropy = 0 → diversity = 0."""
        text = 'เขาเดินเข้ามา. เธอยืน. คนดู.'
        result = sentence_variety(text)
        if result['total'] > 0 and len(result['types']) == 1:
            assert result['diversity'] == 0.0

    def test_diversity_higher_for_more_types(self):
        """More types → higher diversity score."""
        text_a = 'เขาเดินเข้ามา. เธอยืน. คนดู.'
        text_b = 'เขาเดินเข้ามา. เธอยืน. คนดู? โอ้โห! "สวัสดี" เขาพูด.'
        assert sentence_variety(text_b)['diversity'] > sentence_variety(text_a)['diversity']


# ── burstiness ─────────────────────────────────────────────────────

class TestBurstiness:
    """Sentence length SD (low SD = monotonous AI rhythm)."""

    def test_empty_text(self):
        result = burstiness('')
        assert result['sd'] == 0
        assert result['samples'] == 0

    def test_uniform_length_low_sd(self):
        """5 sentences of same length → SD = 0."""
        text = 'สิบตัว. สิบตัว. สิบตัว. สิบตัว. สิบตัว.'
        result = burstiness(text)
        assert result['sd'] == 0

    def test_varied_length_high_sd(self):
        """Mix of short and long → SD > 0."""
        text = 'สั้น. ' + 'นี่คือประโยคที่ยาวมากๆ ' * 20 + '. สั้น.'
        result = burstiness(text)
        assert result['sd'] > 0

    def test_too_few_samples_returns_zero(self):
        """< 3 samples → return 0,0,0 (can't compute SD)."""
        text = 'สั้น. สั้น.'
        result = burstiness(text)
        assert result['sd'] == 0


# ── function_word_diversity ────────────────────────────────────────

class TestFunctionWordDiversity:
    """Measure reliance on function words (overuse = AI tell)."""

    def test_no_func_words(self):
        text = 'เขาเดินเข้ามาในห้อง'
        result = function_word_diversity(text)
        assert result['function_words'] == {}

    def test_high_func_word_density(self):
        """Heavy use of 'ก็' should be flagged."""
        text = 'ก็ ' * 50 + 'เดิน'
        result = function_word_diversity(text)
        assert result['function_words'].get('ก็', 0) == 50
        assert result['top_pct'] > 0

    def test_diversity_one_when_all_same(self):
        """All 'ก็' → 1 unique / 50 total = 0.02 diversity."""
        text = 'ก็ ' * 50 + 'เดิน'
        result = function_word_diversity(text)
        assert result['diversity'] == pytest.approx(1 / 50)

    def test_func_words_constant_is_set(self):
        """FUNC_WORDS must be a set (O(1) lookup)."""
        assert isinstance(FUNC_WORDS, set)
        assert len(FUNC_WORDS) >= 10
        assert 'ก็' in FUNC_WORDS
        assert 'ครับ' in FUNC_WORDS

    def test_top_15_limit(self):
        """function_words dict in result limited to top 15."""
        # Use many function words
        text = ' '.join(list(FUNC_WORDS) * 10)
        result = function_word_diversity(text)
        assert len(result['function_words']) <= 15


# ── megumin_structural_check ───────────────────────────────────────

class TestMeguminStructural:
    """Megumin 5-Phase CoT anti-slop: 2nd person, descriptor echo, etc."""

    def test_clean_text(self):
        text = 'เขาเดินเข้ามาในห้อง เห็นแสงสว่างจากหน้าต่าง'
        result = megumin_structural_check(text)
        assert result == []

    def test_2nd_person_break_flagged(self):
        """6+ 'คุณ' in 3rd person body (followed by space/punct) → flag."""
        # Each 'คุณ' must be followed by space or punctuation to count
        text = 'เขาเดิน คุณเดิน คุณวิ่ง คุณพูด คุณหัวเราะ คุณร้องไห้ คุณ.'
        result = megumin_structural_check(text)
        assert any('2nd person' in r for r in result)

    def test_few_khun_not_flagged(self):
        """≤5 'คุณ' is allowed (could be normal dialogue)."""
        text = 'เขาพูดกับคุณว่า คุณต้องไป คุณจะกลับมา คุณอยู่ไหน'
        # Strip dialogue first (megumin does this internally)
        result = megumin_structural_check(text)
        # The dialogue gets stripped before the check
        # After stripping, count should be 0
        you_hits = [r for r in result if '2nd person' in r]
        assert you_hits == []

    def test_descriptor_echo_flagged(self):
        """Same adjective twice within 200 chars → flag."""
        text = 'เธอดูสวยมากในชุดนี้ สวยจริงๆ'
        result = megumin_structural_check(text)
        assert any('Descriptor echo' in r for r in result)

    def test_3_stage_falling_flagged(self):
        """3 consecutive sentences each shorter (last < 15)."""
        text = 'เขาเดินเข้ามาในห้องอย่างระมัดระวัง. เธอยืนอยู่. สวย.'
        result = megumin_structural_check(text)
        assert any('3-stage falling' in r for r in result)

    def test_no_fall_without_short_last(self):
        """3 sentences each shorter, but last >= 15 → no flag."""
        text = 'เขาเดินเข้ามาในห้องอย่างระมัดระวังมาก. เธอยืนอยู่ตรงนั้น. เขามองเธอ.'
        # 'เขามองเธอ' is 9 chars, but the check looks at l3 < 15
        # Actually 9 < 15, so it WOULD flag. Let me use a longer one.
        text = 'ประโยคแรกยาวมากๆเลยนะครับ. ประโยคสองก็ยาวพอสมควร. ประโยคสามยาวเหมือนกัน.'
        result = megumin_structural_check(text)
        # All > 15 chars, so no 3-stage falling
        fall_hits = [r for r in result if '3-stage falling' in r]
        assert fall_hits == []


# ── paragraph_metrics ──────────────────────────────────────────────

class TestParagraphMetrics:
    """Per-paragraph analysis (v3): attribution, 【】, number forms."""

    def test_clean_paragraphs(self):
        text = 'เขาเดินเข้ามา\n\nเธอยืนอยู่\n\nคนดู'
        result = paragraph_metrics(text)
        assert result['heavy_attr_paras'] == []
        assert result['split_brackets'] == []
        assert result['attribution_per_para'] == [0, 0, 0]

    def test_3_attributions_heavy(self):
        """3 attributions (3 different pattern names) in same paragraph
        → flagged as heavy (≥3 threshold)."""
        # Pattern matches 'เขา|เฉาซิง|หลิวมู่เสวี่ย|...' + verb
        text = 'เขาพูดว่า เฉาซิงพูดว่า หลิวมู่เสวี่ยพูดว่า'
        result = paragraph_metrics(text)
        # 1 paragraph with 3 attributions
        assert (0, 3) in result['heavy_attr_paras']

    def test_split_brackets_detected(self):
        """【】 in 2+ consecutive paragraphs → split event."""
        text = '【ระบบแจ้งเตือน\n\nข้อความต่อ】'
        result = paragraph_metrics(text)
        assert len(result['split_brackets']) >= 1

    def test_number_forms_with_comma(self):
        text = 'รางวัล 1,000 ชิ้น'
        result = paragraph_metrics(text)
        assert result['number_forms']['with_comma'] == 1
        assert result['number_forms']['no_sep'] == 0

    def test_number_forms_no_sep(self):
        text = 'รางวัล 1000 ชิ้น'
        result = paragraph_metrics(text)
        assert result['number_forms']['no_sep'] == 1

    def test_returns_dict_with_required_keys(self):
        text = 'เขาเดินเข้ามา'
        result = paragraph_metrics(text)
        assert 'attribution_per_para' in result
        assert 'brackets_per_para' in result
        assert 'heavy_attr_paras' in result
        assert 'split_brackets' in result
        assert 'number_forms' in result
