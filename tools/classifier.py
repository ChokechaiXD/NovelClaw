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

System Split rule:
  - 【】 MUST be its own paragraph. If mixed with other content → split.

รูปแบบไทยสไตล์ (ตามพี่โชค):
  - DIALOGUE: "..." (default, no special styling)
  - SYSTEM: 【】 (keep as-is, stand-alone paragraph)
  - THOUGHT: <em>...</em> (italic, gray, no brackets)
  - ACTION/NARRATION: plain text
  - No colors anywhere — pure semantic structure
"""

from __future__ import annotations

import re
from typing import Any

# ── Types ───────────────────────────────────────────────────────────────

PARAGRAPH_TYPES = ("narration", "dialogue", "system", "thought", "action")

# ── Classification rules ────────────────────────────────────────────────

# Dialogue markers
_DIALOGUE_RE = re.compile(r'["\u201c\u201d\u300c\u300d]')

# System brackets
_SYSTEM_RE = re.compile(r'【[^】]*】')

# Thought markers
_THOUGHT_MARKER_RE = re.compile(r'『([^』]+)』')

# Thai action verbs — ขึ้นต้นประโยค
_ACTION_VERBS = [
    "หัน", "เดิน", "วิ่ง", "กระโดด", "ยก", "วาง", "ดึง", "ผลัก", "จับ",
    "ยื่น", "เงย", "ก้ม", "เหลียว", "เอี้ยน", "พุ่ง", "กระชาก", "ชัก",
    "ชี้", "ชู", "โบก", "สั่น", "พยัก", "ส่าย", "ถอน", "ถอย", "ก้าว",
    "คุก", "ลุก", "ทรุด", "กลิ้ง", "โยน", "รับ", "ส่ง",
    "เท้า", "ไขว่", "กอด", "โอบ", "ตบ", "ฟาด", "แทง", "ฟัน", "ยิง",
    "ป้องกัน", "หลบ", "เบือน", "ผงะ", "สะดุ้ง", "ชะงัก",
    "เปิด", "ปิด", "หยิบ", "คว้า", "ไขว่คว้า", "ตะเกียกตะกาย",
]

# Thai thought indicators
_THOUGHT_INDICATORS = [
    "รู้สึก", "คิด", "นึก", "สงสัย", "ครุ่นคิด", "นึกในใจ",
    "ในใจ", "ลอบคิด", "คิดว่า", "นึกว่า", "รู้ว่า", "เข้าใจ",
    "ตระหนัก", "ประหลาดใจ", "ตกใจ", "ฉงน", "พิศวง",
]


def classify(text: str) -> str:
    """Classify a paragraph into one of 5 types."""
    stripped = text.strip()
    if not stripped:
        return "narration"

    if _SYSTEM_RE.search(stripped):
        return "system"
    if _DIALOGUE_RE.search(stripped):
        return "dialogue"
    if _THOUGHT_MARKER_RE.search(stripped):
        return "thought"
    for indicator in _THOUGHT_INDICATORS:
        if indicator in stripped[:40]:
            return "thought"
    for verb in _ACTION_VERBS:
        if stripped.startswith(verb):
            return "action"
    return "narration"


def split_system_paragraphs(paragraphs: list[str]) -> list[str]:
    """Split paragraphs that mix system 【】 with other content.

    【】 MUST stand alone. If a paragraph has 【】 + other text, split it.

    Examples:
      '"ข้าไป!" 【ได้รับ 100 EXP】'  →  ['"ข้าไป!"', '【ได้รับ 100 EXP】']
      'เขาเดิน 【ได้รับ EXP】 ไป'    →  ['เขาเดิน', '【ได้รับ EXP】', 'ไป']
    """
    result = []
    for para in paragraphs:
        if not para or not para.strip():
            continue
        # Check if this paragraph has BOTH system markers AND other content
        system_matches = list(_SYSTEM_RE.finditer(para))
        if not system_matches:
            result.append(para)
            continue

        # Has system markers — strip them and check if non-system content exists
        stripped = _SYSTEM_RE.sub("", para).strip()
        if not stripped:
            # Pure system — keep as is
            result.append(para)
            continue

        # Mixed content — split system markers into their own paragraphs
        # Build parts: split by system marker positions
        last_end = 0
        parts = []
        for m in system_matches:
            # Text before this system marker
            if m.start() > last_end:
                before = para[last_end:m.start()].strip()
                if before:
                    parts.append((before, "text"))
            # The system marker itself
            parts.append((m.group(0), "system"))
            last_end = m.end()
        # Text after last system marker
        if last_end < len(para):
            after = para[last_end:].strip()
            if after:
                parts.append((after, "text"))

        # Collapse consecutive non-system parts
        merged: list[str] = []
        for part_text, part_type in parts:
            if part_type == "system":
                if part_text.strip():
                    merged.append(part_text)
            else:
                if merged and merged[-1] not in ("(system_fence)",) and not _SYSTEM_RE.search(merged[-1]):
                    merged[-1] = merged[-1] + " " + part_text
                else:
                    merged.append(part_text)

        for m in merged:
            if m.strip():
                result.append(m.strip())

    return result


def classify_paragraphs(paragraphs: list[str]) -> list[dict[str, str]]:
    """Classify a list of plain text paragraphs.

    Returns:
        [{"type": "narration", "text": "..."}, ...]
    """
    # Step 1: Split system markers first
    split = split_system_paragraphs(paragraphs)

    # Step 2: Classify each
    result = []
    for para in split:
        if not para or not para.strip():
            continue
        t = classify(para)
        text = para.strip()

        # Handle CN thought markers → italic (no brackets)
        if _THOUGHT_MARKER_RE.search(text):
            text = _THOUGHT_MARKER_RE.sub(r"<em>\1</em>", text)

        result.append({"type": t, "text": text})
    return result


def classify_and_format(paragraphs: list[str]) -> list[dict[str, str]]:
    """One-shot: classify + format. Used by pipeline."""
    return classify_paragraphs(paragraphs)


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
