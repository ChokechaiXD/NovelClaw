"""build_glossary.py — Build/refresh glossary.db from 3 .md files (single source).

This is the ONLY place that writes to glossary.db. Run when:
  - You edit locked.md / reference.md / auto.md
  - You want to refresh scores from latest ch state
  - You want to resolve inconsistencies / add explanations

The .md files are the human-edited source of truth. The .db is the
queryable/validated view consumed by pre_chapter, validate, doctor.

Schema upgrades vs v1:
  - terms.explanation: human-readable description (what this term means,
    when to use it, what NOT to confuse it with). Required for AI to
    translate correctly without guessing.
  - terms.examples: 1-2 sample translations from real ch. Helps disambiguate
    context-sensitive terms.
  - style_rules.example_before / example_after: concrete TH samples.
  - glossary_changelog: every change logged (who/when/what).
  - conflicts view: when same source → multiple Thai, force resolution.

Usage:
  python tools/build_glossary.py            # build (default: dry-run, shows plan)
  python tools/build_glossary.py --apply    # actually write to DB
  python tools/build_glossary.py --rescore  # also recompute scores from ch usage
  python tools/build_glossary.py --explain  # show explanation gaps
"""
import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import GLOSSARY_DIR, CHAPTERS_DIR  # noqa: E402

DB_PATH = GLOSSARY_DIR / 'glossary.db'

# ────────────────────────────────────────────────────────────────────
# Schema (idempotent — uses CREATE TABLE IF NOT EXISTS)
# ────────────────────────────────────────────────────────────────────

SCHEMA = """
-- Add new columns to existing terms (idempotent ALTER)
-- (SQLite doesn't support IF NOT EXISTS on ALTER COLUMN, so we check first)

CREATE TABLE IF NOT EXISTS terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_cn TEXT NOT NULL,
  source_norm TEXT NOT NULL,
  thai TEXT NOT NULL,
  category TEXT,
  priority INTEGER DEFAULT 3,
  scope TEXT,
  score INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active',
  first_seen_ch INTEGER,
  last_used_ch INTEGER,
  notes TEXT,
  explanation TEXT,
  examples TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_norm, thai)
);

CREATE TABLE IF NOT EXISTS aliases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  term_id INTEGER NOT NULL REFERENCES terms(id),
  source_variant TEXT NOT NULL,
  variant_type TEXT,                -- 'tc'/'nickname'/'old_glossary'/'compound'
  UNIQUE(term_id, source_variant)
);

CREATE TABLE IF NOT EXISTS usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  term_id INTEGER NOT NULL REFERENCES terms(id),
  ch_num INTEGER NOT NULL,
  thai_count INTEGER DEFAULT 0,
  has_issue BOOLEAN DEFAULT 0,
  issue_type TEXT,
  issue_detail TEXT,
  UNIQUE(term_id, ch_num)
);

CREATE TABLE IF NOT EXISTS inconsistencies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_cn TEXT NOT NULL,
  thai_a TEXT NOT NULL,
  ch_a INTEGER,
  thai_b TEXT NOT NULL,
  ch_b INTEGER,
  resolved_at TIMESTAMP,
  resolution TEXT,                  -- 'keep_a'/'keep_b'/'merged'/'false_positive'
  resolved_by TEXT
);

CREATE TABLE IF NOT EXISTS style_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rule_type TEXT,                   -- 'anti_pattern'/'preferred'/'forbidden'/'collocation'
  pattern TEXT NOT NULL,
  replacement TEXT,
  severity TEXT,                    -- 'error'/'warning'/'info'
  scope TEXT,                       -- 'all'/'dialogue'/'narration'/'title'
  source TEXT,                      -- 'style.md'/'manual'
  example_before TEXT,              -- NEW: sample TH that violates
  example_after TEXT,               -- NEW: sample TH that complies
  explanation TEXT                  -- NEW: why this rule exists
);

CREATE TABLE IF NOT EXISTS compounds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_term_id INTEGER NOT NULL REFERENCES terms(id),
  child_term_id INTEGER NOT NULL REFERENCES terms(id),
  position TEXT,                    -- 'prefix'/'suffix'
  UNIQUE(parent_term_id, child_term_id, position)
);

CREATE TABLE IF NOT EXISTS doctor_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ch_num INTEGER NOT NULL,
  issue_type TEXT,
  severity TEXT,
  pattern TEXT,
  location TEXT,
  fix_suggestion TEXT,
  detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ch_meta (
  ch_num INTEGER PRIMARY KEY,
  translated_at TIMESTAMP,
  reviewer TEXT,
  glossary_version TEXT,
  validation_status TEXT,           -- 'pending'/'clean'/'has_warnings'/'has_errors'
  doctor_notes TEXT
);

-- NEW: changelog for audit trail
CREATE TABLE IF NOT EXISTS glossary_changelog (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  actor TEXT,                       -- 'build'/'doctor'/'manual'/'migrate'
  action TEXT,                      -- 'add'/'update'/'archive'/'merge'/'explain'
  target TEXT,                      -- 'terms:42' or 'style:7'
  detail TEXT                       -- JSON or short description
);

-- View: conflicts (terms with multiple Thai versions)
CREATE VIEW IF NOT EXISTS v_conflicts AS
  SELECT source_norm,
         GROUP_CONCAT(DISTINCT thai) as variants,
         COUNT(DISTINCT thai) as n_variants,
         COUNT(*) as n_terms
  FROM terms
  WHERE status = 'active'
  GROUP BY source_norm
  HAVING n_variants > 1;
"""


# ────────────────────────────────────────────────────────────────────
# CN→SC normalization (Traditional → Simplified)
# ────────────────────────────────────────────────────────────────────

TC_TO_SC = {
    '極': '极', '龍': '龙', '龐': '庞', '絲': '丝', '靈': '灵',
    '戰': '战', '鬥': '斗', '場': '场', '燈': '灯', '燒': '烧',
    '無': '无', '萬': '万', '滿': '满', '漸': '渐', '當': '当',
    '長': '长', '門': '门', '開': '开', '關': '关', '間': '间',
    '東': '东', '陳': '陈', '隊': '队', '陣': '阵', '陣': '阵',
    '絲': '丝', '術': '术', '視': '视', '親': '亲', '謝': '谢',
    '討': '讨', '讓': '让', '議': '议', '變': '变', '質': '质',
    '師': '师', '師': '师', '風': '风', '飛': '飞', '飛': '飞',
    '時': '时', '書': '书', '書': '书', '畫': '画', '畫': '画',
    '線': '线', '總': '总', '練': '练', '練': '练', '級': '级',
    '級': '级', '終': '终', '級': '级', '級': '级', '聲': '声',
    '聲': '声', '殺': '杀', '殺': '杀', '級': '级', '級': '级',
    '級': '级', '級': '级', '級': '级', '級': '级', '級': '级',
    '個': '个', '個': '个', '會': '会', '會': '会', '級': '级',
    '長': '长', '長': '长', '級': '级', '級': '级', '級': '级',
}


def normalize_sc(text: str) -> str:
    """Convert Traditional Chinese to Simplified for canonical key."""
    return ''.join(TC_TO_SC.get(c, c) for c in text)


# ────────────────────────────────────────────────────────────────────
# MD parser
# ────────────────────────────────────────────────────────────────────

def parse_md_file(path: Path) -> list[dict]:
    """Parse a single glossary .md file. Returns list of {source, thai, category, priority, notes}.

    Format: | Source | Thai | Category | Priority | Notes |
    """
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.startswith('| ') or line.startswith('|--') or 'Source' in line or 'Category' in line:
            continue
        cells = [c.strip() for c in line.split('|')]
        if len(cells) >= 6 and cells[1] and cells[1] != '-':
            try:
                prio = int(cells[4]) if cells[4].isdigit() else 3
            except (ValueError, IndexError):
                prio = 3
            entries.append({
                'source': cells[1],
                'thai': cells[2],
                'category': cells[3] or 'ทั่วไป',
                'priority': prio,
                'notes': cells[5] if len(cells) > 5 else '',
            })
    return entries


def parse_all_glossaries() -> list[dict]:
    """Parse all 3 .md files into a unified list."""
    out = []
    for tier_name, tier_path in [
        ('locked', GLOSSARY_DIR / 'locked.md'),
        ('reference', GLOSSARY_DIR / 'reference.md'),
        ('auto', GLOSSARY_DIR / 'auto.md'),
    ]:
        for e in parse_md_file(tier_path):
            e['tier'] = tier_name
            out.append(e)
    return out


# ────────────────────────────────────────────────────────────────────
# Style rules (parsed from style.md, embedded constants)
# ────────────────────────────────────────────────────────────────────

STYLE_RULES = [
    # ── Forbidden (errors — should never appear)
    ('forbidden', r'ฮ่องกง', 'เซียนเจียง', 'error', 'all', 'style.md',
     'ฮ่องกงถือเป็นเมืองหลวง', 'เซียนเจียงถือเป็นเมืองหลวง',
     'Hong Kong = เซียนเจียง (transliteration hits emotional register better)'),
    # ── Anti-patterns (warnings — show-don't-tell + translated feel)
    ('anti_pattern', r'ดีใจในใจ', None, 'warning', 'narration', 'style.md',
     'เขาดีใจในใจมาก', 'ยิ้มจนเห็นเขี้ยว',
     'emotion lump — use gesture/sensation instead'),
    ('anti_pattern', r'เสียใจในใจ', None, 'warning', 'narration', 'style.md',
     'นางเสียใจในใจ', 'กัดริมฝีปากแน่น',
     'emotion lump — use gesture/sensation instead'),
    ('anti_pattern', r'สีหน้าเปี่ยม(?!ด้วย)', None, 'warning', 'narration', 'style.md',
     'สีหน้าเปี่ยมความยินดี', 'ขมวดคิ้วยิ้ม',
     'use specific face/body action'),
    ('anti_pattern', r'ฉายแวว', None, 'warning', 'narration', 'style.md',
     'ฉายแววดีใจ', 'ยิ้มออก',
     'show-don\'t-tell — describe what eyes actually do'),
    ('anti_pattern', r'รวดเร็วดุจสายฟ้า', None, 'warning', 'narration', 'style.md',
     'เขาเคลื่อนที่รวดเร็วดุจสายฟ้า', 'รีบเดินหน้า',
     'translated-feeling idiom — use action verb'),
    ('anti_pattern', r'ตกใจจนหัวหมุน', None, 'warning', 'narration', 'style.md',
     'ตกใจจนหัวหมุน', 'ตัวสั่น',
     'translated phrase — use body reaction'),
    ('anti_pattern', r'กล่าวว่า', 'พูดว่า', 'warning', 'dialogue', 'style.md',
     'เขากล่าวว่า "ไปกัน"', 'เขาพูดว่า "ไปกัน"',
     'formal verb — too formal for modern dialogue'),
    ('anti_pattern', r'เอ่ยปาก', 'พูด', 'warning', 'dialogue', 'style.md',
     'เธอเอ่ยปากว่า...', 'เธอพูดว่า...',
     'formal verb — use casual "พูด" or "บอก"'),
    ('anti_pattern', r'เอ่ยว่า', 'ว่า', 'warning', 'dialogue', 'style.md',
     'เขาเอ่ยว่า...', 'เขาว่า...',
     'formal verb — drop the verb, just use "ว่า"'),
    # ── Collocation watchlist (P3)
    ('collocation', r'บัลลังก์ระยิบระยับ', 'เปล่งรัศมี', 'warning', 'narration', 'style.md',
     'บัลลังก์ระยิบระยับ', 'บัลลังก์เปล่งรัศมี',
     '璀璨 = เปล่งรัศมี/สว่างไสว/แพรวพราว (not ระยิบระยับ)'),
    ('collocation', r'น้ำผึ้งทองคำ', 'น้ำผึ้งป่า/น้ำผึ้งหอม', 'warning', 'narration', 'style.md',
     'ขวดน้ำผึ้งทองคำ', 'ขวดน้ำผึ้งหอม',
     '黄金蜂蜜 = literal calque. Re-anchor to flavor/source'),
    ('collocation', r'ข้างหน้า(?=.*แรก|.*ก่อน)', 'แรก/ก่อนหน้า', 'warning', 'narration', 'style.md',
     'ข้างหน้าแรก', 'แรก',
     '前面的 = "earlier/preceding", not "ahead" (use แรก/ก่อนหน้า)'),
    # ── Slop (auto-detected, list maintained by learn_slop.py)
    ('anti_pattern', r'อย่างไรก็ตาม', 'drop or rephrase', 'warning', 'narration', 'learn_slop',
     'อย่างไรก็ตาม เขายังคงเดินหน้า', 'เขายังคงเดินหน้า',
     'top slop word (92x) — droppable connector'),
    ('anti_pattern', r'ดังนั้น', 'drop or rephrase', 'warning', 'narration', 'learn_slop',
     'ดังนั้นเขาจึงตัดสินใจ', 'เขาจึงตัดสินใจ',
     'top slop word (44x) — droppable connector'),
    ('anti_pattern', r'แม้ว่า', 'drop or rephrase', 'warning', 'narration', 'learn_slop',
     'แม้ว่าจะยาก แต่เขาก็ทำ', 'ยากแต่เขาก็ทำ',
     'top slop word (21x) — droppable concessive'),
    ('anti_pattern', r'เต็มไปด้วยความ', 'replace with concrete', 'warning', 'narration', 'learn_slop',
     'เต็มไปด้วยความหวัง', 'ตาเป็นประกาย',
     'emotion lump (28x) — make concrete'),
    ('anti_pattern', r'ชาวอาณานิคม(?!ชื่อ)', 'flip to TH order', 'warning', 'narration', 'style.md',
     'ชาวอาณานิคมเฉาอี', 'เฉาอี ชาวอาณานิคม',
     'appositive compound — CN [mod][noun], TH needs flip'),
    # ── Length/sentence rhythm (P5, P7)
    ('anti_pattern', r'^(เฉาซิง.{0,20}[\.\!\?]?)\n(เฉาซิง.{0,20}[\.\!\?]?)\n(เฉาซิง.{0,20})', None,
     'warning', 'narration', 'style.md',
     'เฉาซิงพยักหน้า\nเฉาซิงยิ้ม\nเฉาซิงพูด', 'พยักหน้า ยิ้ม แล้วพูด',
     'subject echo (P5) — 3+ consecutive same subject'),
]


# ────────────────────────────────────────────────────────────────────
# Smart name explanation generator (auto-fills explanations for common cases)
# ────────────────────────────────────────────────────────────────────

NAME_EXPLANATIONS = {
    '曹星': 'พระเอก — นายทหารเกษียณ ผู้นำอาณานิคม ฉายา "อาซิง" (阿星) ใช้เรียกสั้นๆ',
    '柳慕雪': 'พี่สะใภ้ของเฉาซิง (พี่ชายเฉาซิงเสียชีวิต) — ผู้หญิงแกร่ง ใจดี เรียก "พี่สะใภ้" ในชีวิตประจำวัน',
    '大白': 'ช้างแมมมอธเลี้ยงของเฉาซิง ชื่อ "ต้าป่าย" (达白 = ใหญ่+ขาว) สื่อสารด้วยเสียง "มอ—!" เท่านั้น',
    '阿星': 'ชื่อเล่นของเฉาซิง ใช้เรียกสนิทสนม ไม่ใช่คนละคน',
    '陈江': 'อดีตหัวหน้าเฉาซิง (เสียชีวิตแล้ว) — ปรากฏตัวในความทรงจำ/แฟลชแบ็ค',
    '伊勒娜': 'สาวเอลฟ์ผู้มากความสามารถ เป็นหนึ่งในสมาชิกคนสำคัญของปาร์ตี้',
    '妮芙': 'ผู้ติดตามสาว นิ่งๆ เงียบๆ มีความสามารถ',
    '安德鲁': 'นักรบชายร่างใหญ่ ใจกว้าง เป็นมิตร',
    '阿萨姆': 'นักธนูผู้ชำนาญ สมาชิกปาร์ตี้',
    '莎拉': 'สาวเอลฟ์ดำ (暗精靈) ความสามารถด้านเวท',
    '吳家輝': 'นายพลผู้มีอำนาจ ตัวละครฝ่ายรัฐบาล/ทหาร',
}

CLASS_EXPLANATIONS = {
    '极地人': 'เผ่าพันธุ์ "คนเมืองหนาว" อาศัยอยู่ในเขตหิมะ มีร่างกายทนหนาว เป็นชนพื้นเมืองของโลกใหม่',
    '极地人小屋': 'ที่อยู่อาศัยพื้นฐานของคนเมืองหนาว โครงสร้างหิน+ไม้',
    '哥布林': 'มอนสเตอร์สายพันธุ์ก็อบลิน ขนาดเล็ก ฉลาดน้อย โจมตีเป็นกลุ่ม',
    '蛇人': 'มนุษย์งู สายพันธุ์อัจฉริยะ มักเป็นศัตรูหรือผู้ค้า',
    '霜狼': 'หมาป่าน้ำแข็ง มอนสเตอร์ที่พบบ่อยในเขตหนาว',
    '大白': 'ช้างแมมมอธเลี้ยง ชื่อ "ต้าป่าย"',
    '暗精靈': 'เอลฟ์ดำ สายพันธุ์หายาก มีพลังเวทมืด',
    '夏爾族': 'สายพันธุ์ชาร์ (Charr) สัตว์คล้ายแมวขนาดใหญ่',
    '穴居人': 'มนุษย์ถ้ำ สายพันธุ์ดั้งเดิมอาศัยใต้ดิน',
    '腐化地精': 'ก็อบลินที่ถูกพลังมืดครอบงำ ระดับ 18-20 อันตราย',
}

LOCATION_EXPLANATIONS = {
    '香江': 'เซียนเจียง = Hong Kong ในภาษาจีน transliterate เก็บอารมณ์ CN (ไม่ใช่ "ฮ่องกง" ที่อ่านเป็น EN)',
    '伯瑞利斯山脈': 'เทือกเขาขนาดใหญ่ในภูมิภาคหนาวเย็น มีมอนสเตอร์ระดับสูง',
    '蓝星': 'โลกของเรื่อง "Blue Star" เป็นโลกที่ระบบเกมครอบงำ',
    '特洛山': 'ภูเขาลึกลับ เป็นสถานที่สำคัญของ arc แรก',
    '永盛集团': 'กลุ่มบริษัทยักษ์ใหญ่ ฝ่ายทุน/อำนาจ',
    '寒冰弓箭手兵营': 'ค่ายฝึกทหารธนูน้ำแข็ง สร้างเพื่อผลิตหน่วย "寒冰弓箭手"',
    '领主小屋': 'บ้านพักลอร์ด — ที่อยู่อาศัยหลักของผู้เล่น',
}

ITEM_EXPLANATIONS = {
    '《冰封纪元》': 'ชื่อเกม/โลกในเรื่อง "มหายุคน้ำแข็ง" เก็บเครื่องหมาย 《》 ตามต้นฉบับ',
    '冰封纪元': 'ชื่อเกม/ยุคสมัย (ไม่มี 《》) — เหตุการณ์หลังโลกเปลี่ยนเป็นยุคน้ำแข็ง',
    '赐福': 'พร/บัฟ ที่ระบบเกมมอบให้ มักเป็น buff ชั่วคราว',
    '篝火': 'กองไฟ จุดพักผ่อน/ทำอาหาร',
    '营地篝火': 'กองไฟประจำค่าย ใช้เป็นศูนย์กลางของฐาน',
    '篝火': 'กองไฟขนาดเล็ก',
    '木材': 'ไม้แปรรูป วัตถุดิบพื้นฐาน',
    '石块': 'หินก้อน วัตถุดิบพื้นฐาน',
    '克朗': 'สกุลเงินในเกม (โครน)',
    '克朗币': 'เหรียญโครน (เหมือนกับ คลัง แต่เน้นเหรียญ)',
    '資料片': 'เนื้อหาเสริม (expansion) ของเกม — คอนเทนต์เพิ่มเติม',
    '外掛': 'โปรแกรมช่วยเล่น (cheat/hack) ไม่ควรเก็บ CN ใน TH',
}

SKILL_EXPLANATIONS = {
    '冰箭雨': 'สกิล AOE น้ำแข็ง "ฝนลูกศรน้ำแข็ง" 36 hits พร้อมกัน',
    '冰甲术': 'เกราะน้ำแข็ง — buff ป้องกัน',
    '冰疗术': 'เวทรักษาเยือกแข็ง — heal HP',
    '极光祝福': 'พรแสงออโรร่า — buff ทั้งปาร์ตี้',
    '勇气祝福': 'พรแห่งความกล้า — buff พลังโจมตี',
    '黑烟图腾': 'ตุ๊กตาควันดำ — DoT spell',
    '共鸣图腾': 'ตุ๊กตาสั่นสะเทือน — AoE buff/debuff',
    '正义之剑': 'ดาบแห่งความยุติธรรม — AOE slash',
}

STAT_EXPLANATIONS = {
    '力量': 'ค่าสถานะ "พลัง" (stat) ในเกม ใช้ "พลัง" ตามมาตรฐานเกม ไม่ใช่ "กำลัง"',
    '敏捷': 'ค่าสถานะ "ความเร็ว" (dexterity stat)',
    '體質': 'ค่าสถานะ "ค่าพละ" (constitution stat)',
    'HP': 'พลังชีวิต — เก็บคำย่อ HP ตามธรรมเนียมเกม ไม่แปล "พลังชีวิต"',
    '生命值': 'พลังชีวิต — ความหมายเดียวกับ HP แต่ใช้ HP ในฉากเกม',
    '暴擊率': 'อัตราคริติคอล (critical hit rate) — %',
    '元素親和度': 'ความสอดคล้องกับธาตุ (elemental affinity stat)',
    '飽食度': 'ค่าความอิ่ม (fullness stat) — ตัวละครต้องกินอาหาร',
    '法术': 'เวทมนตร์ (magic spell category)',
    '體': 'ร่างกาย (body) — ใช้ "ค่าพละ" เมื่อเป็น stat',
}


def infer_explanation(source: str, category: str, thai: str) -> str:
    """Generate explanation for a term. Check known patterns first."""
    if source in NAME_EXPLANATIONS:
        return NAME_EXPLANATIONS[source]
    if source in CLASS_EXPLANATIONS:
        return CLASS_EXPLANATIONS[source]
    if source in LOCATION_EXPLANATIONS:
        return LOCATION_EXPLANATIONS[source]
    if source in ITEM_EXPLANATIONS:
        return ITEM_EXPLANATIONS[source]
    if source in SKILL_EXPLANATIONS:
        return SKILL_EXPLANATIONS[source]
    if source in STAT_EXPLANATIONS:
        return STAT_EXPLANATIONS[source]
    # Generic fallback
    if category == 'ตัวละคร':
        return f'ตัวละครชื่อ "{source}" → "{thai}"'
    if category == 'สถานที่':
        return f'สถานที่ "{source}" → "{thai}"'
    if category == 'ไอเทม':
        return f'ไอเทม "{source}" → "{thai}"'
    if category == 'สกิล':
        return f'สกิล "{source}" → "{thai}"'
    return f'คำทั่วไป "{source}" → "{thai}"'


# ────────────────────────────────────────────────────────────────────
# Conflict resolution
# ────────────────────────────────────────────────────────────────────

# Map: source_norm → canonical Thai (for resolving inconsistencies)
# When multiple Thai versions exist, this is which one to KEEP.
CONFLICT_RESOLUTIONS = {
    '力量': 'พลัง',  # 力量 = "power" (stat) — "พลัง" reads more game-like
                      # vs "กำลัง" reads more as physical force
                      # Ch 101+ consistently uses "พลัง" so we lock that
}


# ────────────────────────────────────────────────────────────────────
# Main build
# ────────────────────────────────────────────────────────────────────

def build_db(apply: bool = False, rescore: bool = False) -> dict:
    """Build glossary.db from .md files.

    Returns: dict with stats about what changed (for dry-run reporting).
    """
    stats = {
        'terms_total': 0,
        'terms_added': 0,
        'terms_updated': 0,
        'terms_archived': 0,
        'aliases_added': 0,
        'style_rules_added': 0,
        'conflicts_found': 0,
        'conflicts_resolved': 0,
    }

    if apply:
        # Ensure DB exists with full schema
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(SCHEMA)
        # MIGRATE: add new columns to existing tables (idempotent)
        cur_check = conn.cursor()
        cur_check.execute("PRAGMA table_info(terms)")
        term_cols = {row[1] for row in cur_check.fetchall()}
        for col, typedef in [
            ('explanation', 'TEXT'),
            ('examples', 'TEXT'),
        ]:
            if col not in term_cols:
                conn.execute(f'ALTER TABLE terms ADD COLUMN {col} {typedef}')
        cur_check.execute("PRAGMA table_info(style_rules)")
        rule_cols = {row[1] for row in cur_check.fetchall()}
        for col, typedef in [
            ('example_before', 'TEXT'),
            ('example_after', 'TEXT'),
            ('explanation', 'TEXT'),
        ]:
            if col not in rule_cols:
                conn.execute(f'ALTER TABLE style_rules ADD COLUMN {col} {typedef}')
    else:
        conn = sqlite3.connect(DB_PATH)
        # For dry-run, just read what's there

    cur = conn.cursor()

    # 1. Parse all 3 .md files
    entries = parse_all_glossaries()
    stats['terms_total'] = len(entries)

    # 2. Build canonical entries (resolve conflicts first)
    by_source = defaultdict(list)
    for e in entries:
        src_norm = normalize_sc(e['source'])
        e['source_norm'] = src_norm
        by_source[src_norm].append(e)

    # Detect conflicts
    for src_norm, variants in by_source.items():
        thais = set(v['thai'] for v in variants)
        if len(thais) > 1:
            stats['conflicts_found'] += 1
            if src_norm in CONFLICT_RESOLUTIONS:
                canonical = CONFLICT_RESOLUTIONS[src_norm]
                # Keep only canonical thai in this batch
                by_source[src_norm] = [v for v in variants if v['thai'] == canonical]
                # Mark non-canonical as archived in DB
                if apply:
                    non_canonical_thais = [v['thai'] for v in variants if v['thai'] != canonical]
                    for bad_thai in non_canonical_thais:
                        cur.execute('''UPDATE terms SET status = 'archived',
                                      updated_at = ?, notes = COALESCE(notes, '') ||
                                        ' [auto-archived: superseded by ' || ? || ']'
                                      WHERE source_norm = ? AND thai = ?''',
                                    (datetime.now().isoformat(), canonical,
                                     src_norm, bad_thai))
                stats['conflicts_resolved'] += 1
            else:
                # No resolution known — keep highest-priority entry
                by_source[src_norm] = [max(variants, key=lambda v: -v['priority'])]

    # 3. Write terms
    if apply:
        # Get existing terms
        cur.execute('SELECT id, source_norm, thai FROM terms')
        existing = {(r[1], r[2]): r[0] for r in cur.fetchall()}

        for src_norm, variants in by_source.items():
            for e in variants:
                key = (src_norm, e['thai'])
                explanation = infer_explanation(e['source'], e['category'], e['thai'])
                if key in existing:
                    # Update (in case explanation added)
                    cur.execute('''UPDATE terms
                                  SET explanation = ?, category = ?, priority = ?,
                                      scope = ?, notes = ?, updated_at = ?
                                  WHERE id = ?''',
                                (explanation, e['category'], e['priority'],
                                 e['tier'], e['notes'], datetime.now().isoformat(),
                                 existing[key]))
                    stats['terms_updated'] += 1
                else:
                    # Insert
                    cur.execute('''INSERT INTO terms
                                  (source_cn, source_norm, thai, category, priority,
                                   scope, notes, explanation, status)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')''',
                                (e['source'], src_norm, e['thai'], e['category'],
                                 e['priority'], e['tier'], e['notes'], explanation))
                    stats['terms_added'] += 1

        # 4. Write style rules
        cur.execute('SELECT pattern, rule_type FROM style_rules')
        existing_rules = {(r[0], r[1]) for r in cur.fetchall()}

        for rule in STYLE_RULES:
            (rtype, pattern, replacement, severity, scope, source,
             example_before, example_after, explanation) = rule
            key = (pattern, rtype)
            if key in existing_rules:
                # Update with new fields if added
                cur.execute('''UPDATE style_rules
                              SET replacement = ?, severity = ?, scope = ?,
                                  source = ?, example_before = ?, example_after = ?,
                                  explanation = ?
                              WHERE pattern = ? AND rule_type = ?''',
                            (replacement, severity, scope, source,
                             example_before, example_after, explanation,
                             pattern, rtype))
            else:
                cur.execute('''INSERT INTO style_rules
                              (rule_type, pattern, replacement, severity, scope,
                               source, example_before, example_after, explanation)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (rtype, pattern, replacement, severity, scope, source,
                             example_before, example_after, explanation))
                stats['style_rules_added'] += 1

        # 5. Log build action
        cur.execute('''INSERT INTO glossary_changelog (actor, action, detail)
                      VALUES (?, ?, ?)''',
                    ('build', 'rebuild', f'terms_added={stats["terms_added"]} '
                    f'terms_updated={stats["terms_updated"]} '
                    f'style_added={stats["style_rules_added"]} '
                    f'conflicts_resolved={stats["conflicts_resolved"]}'))

        conn.commit()

    # 6. Rescore from current ch state
    if apply and rescore:
        ch_files = sorted(CHAPTERS_DIR.glob('[0-9]*.md'),
                          key=lambda p: int(p.stem) if p.stem.isdigit() and len(p.stem) == 4 else 0)
        ch_files = [c for c in ch_files if c.is_file()]
        # Build thai -> term_id
        cur.execute('SELECT id, thai FROM terms WHERE status = "active"')
        thai_to_id = {t: i for i, t in cur.fetchall()}
        # Clear usage + repopulate
        cur.execute('DELETE FROM usage')
        for ch_file in ch_files:
            ch_num = int(ch_file.stem)
            text = ch_file.read_text(encoding='utf-8')
            for thai, tid in thai_to_id.items():
                count = text.count(thai)
                if count > 0:
                    cur.execute('''INSERT OR REPLACE INTO usage
                                  (term_id, ch_num, thai_count) VALUES (?, ?, ?)''',
                                (tid, ch_num, count))
        # Recompute scores
        cur.execute('''UPDATE terms SET score = (
            COALESCE((SELECT SUM(thai_count) FROM usage WHERE term_id = terms.id), 0) * 2
            + (SELECT COUNT(DISTINCT ch_num) FROM usage WHERE term_id = terms.id) * 5
        )''')
        cur.execute('UPDATE terms SET score = score + 50 WHERE priority = 1')
        conn.commit()

    conn.close()
    return stats


def show_explanation_gaps():
    """Show terms that don't have explanations (so user can fill in)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT source_cn, thai, category, explanation FROM terms WHERE explanation IS NULL OR explanation = ""')
    gaps = cur.fetchall()
    conn.close()
    if gaps:
        print(f'\n⚠️  {len(gaps)} terms without explanations:')
        for src, thai, cat, _ in gaps[:30]:
            print(f'   {src} → {thai}  ({cat})')
        if len(gaps) > 30:
            print(f'   ... and {len(gaps) - 30} more')
    else:
        print('\n✓ All terms have explanations')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Write to DB (default: dry-run)')
    ap.add_argument('--rescore', action='store_true', help='Also recompute scores from ch state')
    ap.add_argument('--explain', action='store_true', help='Show terms missing explanations')
    args = ap.parse_args()

    if args.explain:
        show_explanation_gaps()
        return

    print('━' * 60)
    print(f'  Building glossary.db ({("APPLY" if args.apply else "DRY-RUN")})')
    print('━' * 60)
    stats = build_db(apply=args.apply, rescore=args.rescore)
    for k, v in stats.items():
        print(f'  {k:30} {v}')
    print()
    if not args.apply:
        print('  → Re-run with --apply to write changes')
    else:
        print('  ✓ glossary.db updated')


if __name__ == '__main__':
    main()
