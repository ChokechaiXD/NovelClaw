#!/usr/bin/env python3
"""
classifier.py — Paragraph classification + Thai style formatting (Station 6-7).

แปลง plain paragraph string → {"type": str, "text": str}
แล้วจัดรูปแบบตาม Thai Style Specification.

กฏการ classify:
  - มี "...」 หรือ "..." → DIALOGUE
  - มี 【】 → SYSTEM
  - ขึ้นต้นด้วยกริยาบอกท่าทาง (action verbs) → ACTION
  - มีคำบอกความคิด/ความรู้สึก → THOUGHT
  - ที่เหลือ → NARRATION

รูปแบบไทยสไตล์ (ตามพี่โชค):
  - DIALOGUE: "..." (default, no special styling needed in text)
  - SYSTEM: 【】 (keep as-is, no color markup)
  - THOUGHT: <em>...</em> (no brackets)
  - ACTION/NARRATION: plain text
  - No colors anywhere — pure semantic structure
"""

from __future__ import annotations

import re
from typing import Any

# ── Types ───────────────────────────────────────────────────────────────

PARAGRAPH_TYPES = ("narration", "dialogue", "system", "thought", "action")

# ── Classification rules ────────────────────────────────────────────────

# Dialogue markers: "..." or 「...」 → translated to "...」
_DIALOGUE_RE = re.compile(r'["\u201c\u201d\u300c\u300d]')

# System brackets: 【】
_SYSTEM_RE = re.compile(r'【[^】]*】')

# Thought markers: 『』 in text (CN style) → we detect and convert to em
_THOUGHT_MARKER_RE = re.compile(r'『([^』]+)』')

# Thai action verbs — ขึ้นต้นประโยคที่บ่งบอกถึง action
_ACTION_VERBS = [
    "หัน", "เดิน", "วิ่ง", "กระโดด", "ยก", "วาง", "ดึง", "ผลัก", "จับ",
    "ยื่น", "เงย", "ก้ม", "เหลียว", "เอี้ยน", "พุ่ง", "กระชาก", "ชัก",
    "ชี้", "ชู", "โบก", "สั่น", "พยัก", "ส่าย", "ถอน", "ถอย", "ก้าว",
    "คุก", "ลุก", "ทรุด", "กลิ้ง", "กระโดน", "โยน", "รับ", "ส่ง",
    "เท้า", "ไขว่", "กอด", "โอบ", "ตบ", "ฟาด", "แทง", "ฟัน", "ยิง",
    "ป้องกัน", "หลบ", "เบือน", "ผงะ", "สะดุ้ง", "ชะงัก", "เรียบร้อย",
    "เปิด", "ปิด", "หยิบ", "คว้า", "ไขว่คว้า", "ตะเกียกตะกาย",
]

# Thai thought indicators — คำที่บอกถึงความคิด/ความรู้สึก
_THOUGHT_INDICATORS = [
    "รู้สึก", "คิด", "นึก", "สงสัย", "ครุ่นคิด", "นึกในใจ",
    "ในใจ", "ลอบคิด", "คิดว่า", "นึกว่า", "รู้ว่า", "เข้าใจ",
    "ตระหนัก", "ประหลาดใจ", "ตกใจ", "ฉงน", "พิศวง",
    "『"  # raw CN thought marker
]


def classify(text: str) -> str:
    """Classify a paragraph into one of 5 types.

    Priority: system > dialogue > thought > action > narration
    """
    stripped = text.strip()
    if not stripped:
        return "narration"

    # 1. SYSTEM — has 【】
    if _SYSTEM_RE.search(stripped):
        return "system"

    # 2. DIALOGUE — has "..." or 「」
    if _DIALOGUE_RE.search(stripped):
        return "dialogue"

    # 3. THOUGHT — has 『』 or starts with thought indicator
    if _THOUGHT_MARKER_RE.search(stripped):
        return "thought"
    for indicator in _THOUGHT_INDICATORS:
        if indicator in stripped[:40]:  # check start of paragraph
            return "thought"

    # 4. ACTION — starts with action verb
    for verb in _ACTION_VERBS:
        if stripped.startswith(verb):
            return "action"

    # 5. NARRATION — everything else
    return "narration"


def classify_paragraphs(paragraphs: list[str]) -> list[dict[str, str]]:
    """Classify a list of plain text paragraphs.

    Returns:
        [{"type": "narration", "text": "..."}, ...]
    """
    result = []
    for para in paragraphs:
        if not para or not para.strip():
            continue
        t = classify(para)
        text = para.strip()

        # Handle CN thought markers → em tags
        if t == "thought" and _THOUGHT_MARKER_RE.search(text):
            text = _THOUGHT_MARKER_RE.sub(r"<em>\1</em>", text)

        result.append({"type": t, "text": text})
    return result


def format_paragraphs(classified: list[dict[str, str]]) -> list[dict[str, str]]:
    """Apply Thai style formatting to classified paragraphs.

    Rules:
      - DIALOGUE: keep "..." as-is (reader will style via CSS)
      - SYSTEM: keep 【】 as-is
      - THOUGHT: <em> tags already applied in classify_paragraphs
      - ACTION/NARRATION: plain text

    Returns list of dicts ready for JSON serialization.
    """
    result = []
    for p in classified:
        if not p["text"]:
            continue
        result.append(p)
    return result


def classify_and_format(paragraphs: list[str]) -> list[dict[str, str]]:
    """One-shot: classify + format. Used by pipeline."""
    classified = classify_paragraphs(paragraphs)
    return format_paragraphs(classified)


# ── Utility for quality gate ───────────────────────────────────────────

def estimate_type_ratios(classified: list[dict[str, str]]) -> dict[str, float]:
    """Calculate percentage of each type for quality analysis."""
    if not classified:
        return {}
    counts: dict[str, int] = {}
    for p in classified:
        t = p["type"]
        counts[t] = counts.get(t, 0) + 1
    total = len(classified)
    return {t: round(c / total * 100, 1) for t, c in sorted(counts.items())}
