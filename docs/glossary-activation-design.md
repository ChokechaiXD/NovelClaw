# Glossary Activation — Lorebook-Style Design

> Based on P'Choke's decision: validate BOTH presence AND correct translation (from CN)
> P2 of roadmap-v2-quality

## Current State

- Glossary: **387 terms**
- Categories: ไอเทม(110) > ทั่วไป(105) > ตัวละคร(81) > สกิล(60) > สถานที่(30) > สถานะ(1)
- Lock types: auto(192) > reference(118) > locked(77)
- Average source term length: **3.6 CN chars**

## Problem

ปัจจุบัน `validate_translation()` เช็ค ALL 387 terms ทุกครั้ง → false positives เยอะ (terms ที่ไม่เกี่ยวกับตอนนี้ก็แจ้งว่าขาด)

## Solution: Keyword Activation (SillyTavern Lorebook-style)

### Flow

```
source_chapter.md
  → extract CN text (clean source)
  → scan for glossary.source terms (Chinese keywords)
  → activated_terms = {terms whose source appears in this chapter's text}
  → validate output against ONLY activated_terms
```

### Expected Activation per Chapter

จาก avg 3.6 chars/term และ chapter size ~200-500 CN chars:
- **~15-35 terms activated/chapter** (จาก 387)
- ประมาณ 4-9% ของ glossary ทั้งหมด
- validate scope ลดลง **>90%**

### Activation Types

| Type | Trigger | Example | Action |
|:-----|:--------|:--------|:-------|
| **exact_match** | source ปรากฏใน text | `"曹星"` ใน source → activate | ต้องมีใน output |
| **prefix_match** | source เป็น prefix ของ text token | `"力量"` prefix ของ `"力量型"` | activate |
| **alias_match** | source_alias ปรากฏใน glossary | ยังไม่มี — future | activate |
| **recursive_chain** | term A activate → term B ที่เกี่ยวข้อง | future | activate B |

### Validation Levels

| Level | Output status | เมื่อ |
|:------|:-------------|:------|
| **PASS** | all activated terms present in translation | ✅ |
| **WARN** | 1-2 activated terms missing (อาจถูกตัดโดย LLM) | ⚠️ |
| **FAIL** | 3+ activated terms missing OR found CN source lingering | ❌ |

### Missing Detection Logic

สำหรับ activated term `"曹星" → "เฉา ซิง"`:
1. term.source (`"曹星"`) อยู่ใน source text → activated
2. เช็ค output paragraphs:
   - ถ้า `"曹星"` (source CN) ยังอยู่ใน output → **FAIL** (CN leak on protected term)
   - ถ้า `"เฉา ซิง"` (thai) อยู่ใน output → **PASS**
   - ถ้าไม่เจอทั้ง CN+TH → **WARN** (term missing)

### Implementation Sketch

```python
def activate_glossary(source_text: str, glossary: list[dict]) -> list[dict]:
    """Return only glossary entries whose source appears in source_text."""
    activated = []
    for term in glossary:
        if term["source"] in source_text:
            activated.append(term)
    return activated

def validate_glossary(output_paragraphs: str, activated_terms: list[dict]) -> GateResult:
    """Check each activated term: translated, not leaked CN."""
    full_text = "\n".join(output_paragraphs)
    issues = []
    missing_source = []  # CN chars still in output
    missing_thai = []    # Thai not found
    
    for term in activated_terms:
        source_leaked = term["source"] in full_text
        thai_found = term["thai"] in full_text
        
        if source_leaked:
            missing_source.append(term)
        if not thai_found:
            missing_thai.append(term)
    
    # Combine for verdict
    if missing_source and missing_thai:
        return FAIL
    if len(missing_thai) > 2:
        return FAIL
    if missing_thai:
        return WARN
    return PASS
```

### Future: Recursive Activation

เมื่อ system โตขึ้น:
```
"คาร์ฮาน" (ตัวละคร)
  → เปิดกฎ "ตอนมี คาร์ฮาน → ใช้สรรพนาม 'เขา' ไม่ใช่ 'ท่าน' "
"มหายุคน้ำแข็ง" (ทั่วไป)
  → เปิดกฎ "เกมชื่อ → ต้องมี《》ครอบ"
```

แต่ยังไม่ต้องทำตอนนี้ — YAGNI จนกว่าพี่โชคจะเห็นว่าจำเป็น

## Benefit Summary

| ตัววัด | ปัจจุบัน (validate all) | หลัง (activation) |
|:-------|:----------------------:|:------------------:|
| Terms check per chapter | 387 | ~15-35 |
| False positive rate | กลาง-สูง (terms ไม่เกี่ยวกับตอน) | **ต่ำมาก** |
| Missing CN detection | ไม่มี (เช็คแค่ thai มีหรือเปล่า) | **มี — เช็คทั้ง CN leak + thai** |
| Performance | ~O(387×N) | ~O(20×N) — **20x faster** |