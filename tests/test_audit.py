"""Tests for audit.py (Phase 1 — 5-Phase CoT audit log)."""
import re
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))


# ── Phase 1: Ground Truth ─────────────────────────────────────────
def test_ground_truth_basic():
    from audit import ground_truth_phase
    body = 'เฉาซิงพูดกับหลิวมู่เสวี่ยว่า "ไปกัน"\n\n' * 10
    gt = ground_truth_phase(80, body)
    assert gt['chapter'] == 80
    assert gt['translation_chars'] == len(body)
    assert gt['paragraphs'] == 10
    assert 'ratio_ok' in gt


def test_ground_truth_detects_thai_names():
    from audit import ground_truth_phase
    body = 'เฉาซิง เลนนิส ฮอว์อาย พบกัน' * 5
    gt = ground_truth_phase(71, body)
    assert any('เฉาซิง' in n for n in gt['thai_names_detected'])
    assert any('เลนนิส' in n for n in gt['thai_names_detected'])


def test_ground_truth_detects_cn_names():
    from audit import ground_truth_phase
    body = '曹星 蕾妮絲 曹星 曹星 蕾妮絲 蕾妮絲' * 3
    gt = ground_truth_phase(71, body)
    cn = ' '.join(gt['cn_names_detected'])
    assert '曹星' in cn
    assert '蕾妮絲' in cn


# ── Phase 2: Plot Engine ──────────────────────────────────────────
def test_plot_engine_counts_beats():
    from audit import plot_engine_phase
    body = '\n\n'.join(['para'] * 30)
    pe = plot_engine_phase(80, body)
    assert pe['estimated_beats'] >= 10
    assert pe['dialogue_paragraphs'] + pe['narration_paragraphs'] == 30


def test_plot_engine_counts_system_messages():
    from audit import plot_engine_phase
    body = '【ระบบ: HP -10】\n\nเฉาซิง 【ได้รับ 50 EXP】 โจมตี'
    pe = plot_engine_phase(80, body)
    assert pe['system_messages_count'] == 2


def test_plot_engine_counts_titles():
    from audit import plot_engine_phase
    body = 'เล่น 《冰封纪元》 อยู่ แล้ว 《มหายุคน้ำแข็ง》 ก็สนุก'
    pe = plot_engine_phase(80, body)
    assert pe['titles_referenced'] == 2


# ── Phase 3: Scene Design ─────────────────────────────────────────
def test_scene_design_detects_3rd_person():
    from audit import scene_design_phase
    body = 'เฉาซิง ' * 20 + ' ผม ' * 2
    sd = scene_design_phase(80, body)
    assert sd['pov'] == '3rd-person (เฉาซิง)'
    assert sd['3rd_person_count'] >= 20


def test_scene_design_tone_calm_vs_intense():
    from audit import scene_design_phase
    calm = 'เฉาซิง เดิน ' * 50
    sd = scene_design_phase(80, calm)
    assert sd['tone'] == 'calm'

    intense = 'เฉาซิง! ' * 200
    sd2 = scene_design_phase(80, intense)
    assert sd2['tone'] == 'intense'


def test_scene_design_entry_dialogue():
    from audit import scene_design_phase
    body = '"สวัสดี" เฉาซิงทักทาย\n\nอีกย่อหน้า'
    sd = scene_design_phase(80, body)
    assert sd['entry_point'] == 'dialogue'


def test_scene_design_entry_narration():
    from audit import scene_design_phase
    # Pure narration paragraph (no leading dialogue quote)
    body = 'บรรยากาศเงียบสงัด\n\nเฉาซิง เดินเข้าป่า'
    sd = scene_design_phase(80, body)
    assert sd['entry_point'] in ('narration', 'action')


# ── Phase 5: Correction Loop ─────────────────────────────────────
def test_correction_loop_cjk_detection():
    from audit import correction_loop_phase
    body = 'clean text'
    cl = correction_loop_phase(80, body)
    assert cl['cjk_chars'] == 0
    assert cl['issues_found'] == 0


def test_correction_loop_cjk_leak_flagged():
    from audit import correction_loop_phase
    body = 'มี CJK 曹星 หลงเหลือ'
    cl = correction_loop_phase(80, body)
    assert cl['cjk_chars'] > 0
    assert any('CJK' in issue for issue in cl['issues'])


def test_correction_loop_em_dash_overuse():
    from audit import correction_loop_phase
    body = 'text — ' * 20
    cl = correction_loop_phase(80, body)
    assert cl['em_dash_count'] >= 5
    assert any('em-dash' in issue for issue in cl['issues'])


def test_correction_loop_bracket_imbalance():
    from audit import correction_loop_phase
    body = '【เปิด แต่ไม่ปิด'
    cl = correction_loop_phase(80, body)
    assert not cl['brackets_balanced']


# ── Full audit generation ─────────────────────────────────────────
def test_generate_audit_structure():
    from audit import generate_audit
    body = 'เฉาซิง เดิน ไป\n\n' * 20
    audit = generate_audit(80, body)
    assert '# Audit — Ch 80' in audit
    assert '## Phase 1: Ground Truth' in audit
    assert '## Phase 2: Plot Engine' in audit
    assert '## Phase 3: Scene Design' in audit
    assert '## Phase 4: Active Draft' in audit
    assert '## Phase 5: Correction Loop' in audit


def test_generate_audit_includes_title():
    from audit import generate_audit
    body = 'test'
    audit = generate_audit(80, body)
    # Title comes from chapter file, not body; should still have placeholder
    assert 'Ch 80' in audit
