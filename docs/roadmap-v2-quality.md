# Roadmap v2 — Universal Quality & Simplified Router

> **เป้าหมาย:** ลด complexity ลด LLM burden สร้าง quality gate ที่ universal
> ไม่ hardcode ไม่ต้อง rewrite gate ทุกครั้งที่เปลี่ยนภาษา
>
> กฎ 7 ข้อของพี่โชค (มิ.ย. 2026):
> 1. ให้ schema มาก่อน prompt
> 2. ให้ termbase/TM มาก่อน style polishing
> 3. ให้ specialized translator มาก่อน generic LLM
> 4. ให้ explicit routing มาก่อน random router
> 5. ให้ deterministic QA มาก่อน LLM judge
> 6. ให้ silent benchmarking มาก่อนสลับ production model
> 7. ให้การลบชั้น abstraction ที่ไม่จำเป็น มาก่อนการเพิ่ม framework ใหม่ทุกครั้ง

---

## Phase 0 — Consolidate Router (ก่อน quality gate)

**เป้าหมาย:** LLM routing = 1 ชั้นเดียว ไม่ซ้อน ไม่ตาย

| ทำ | ไฟล์ | LOC | เหตุผล |
|:----|:-----|:---:|:-------|
| เก็บ | `llm_router/` | 880 | active ใช้จริงใน translate.py |
| เก็บ | `translator/backends/` | 743 | shared backend classes |
| ลบ | `translator/router.py` | 159 | dead code — ไม่มี caller |
| ลบ | `translator/policy.py` | 93 | duplicate ของ llm_router/config.py |
| ลบ | `translator/judge.py` | 192 | dead code + duplicate logic กับ qa/ |
| ลบ | `translator/__init__.py` | 17 | re-export dead |
| ลบ | `registry/` | 71 | re-export wrapper ล้วน |
| ลบ | `providers/` | 59 | thin wrapper → import backends ตรง |

**รวมลบ: -591 LOC, -8 ไฟล์**

**ผลลัพธ์:** route path translate → llm_router → backends เท่านั้น  
**ความเสี่ยง:** ต่ำ — import chain trace แล้ว 0 จุดพัง

---

## Phase 1 — Language Leakage Gate (A)

**เป้าหมาย:** เปลี่ยน hardcode "Latin=fail, Han=fail" → config-driven language profile
gate code ไม่ต้องรู้อะไรคือ leak — แค่ load profile + compare

### 1.1 สร้าง Language Profile

```json
// tools/profiles/languages/th.json
{
  "lang": "th",
  "name": "Thai",
  "expected_scripts": ["Thai"],
  "allowed_scripts": ["Common", "Inherited"],
  "allowed_digit_sets": ["ASCII", "Thai"],
  "allowed_span_patterns": [
    "url", "email", "version",
    "model_name", "file_path",
    "markdown_link", "numeric_unit"
  ],
  "protected_glossary_categories": [
    "character_name", "place_name",
    "skill_name", "title"
  ],
  "leak_rules": {
    "fail_if_source_script_ratio_over": 0.01,
    "fail_if_foreign_span_length_over": 12,
    "warn_if_foreign_span_count_over": 3
  }
}
```

**รายละเอียด:**
- `expected_scripts`: ภาษาเป้าหมาย (Thai, Lao, Khmer, ฯลฯ)
- `allowed_scripts`: Common (punctuation, whitespace), Inherited (combining marks)
- `allowed_digit_sets`: ASCII digits 0123456789 + native digits ถ้ามี (Thai digits ๐๑๒...)
- `allowed_span_patterns`: regex patterns ที่อนุญาตให้มี foreign text (URL, version string)
- `protected_glossary_categories`: terms ที่ไม่นับเป็น leak
- `leak_rules`: threshold สำหรับ fail/warn

### 1.2 สรุปการใช้ Unicode Script Property

ใช้ `unicodedata` (stdlib) — zero dependency:
- `unicodedata.category(ch)` — L, N, P, S, Z, M
- `unicodedata.name(ch)` — ใช้ detect script
- หรือใช้ `unicodedata.lookup()` กับ regex Unicode script property

**Rule engine:**
1. load language profile
2. for each char in output:
   - ถ้า category ∈ {M} (combining marks) → Inherited → allowed
   - ถ้า script ∈ expected_scripts → pass
   - ถ้า script ∈ allowed_scripts (Common, Inherited) → pass
   - ถ้า char ∈ allowed_digit_sets → pass
   - ถ้า char ∈ allowed_span_patterns → pass
   - ถ้า char ∈ protected_glossary_categories → warn (not fail)
   - **นอกจากนี้ → leak**
3. apply leak_rules → PASS / WARN / FAIL

### 1.3 แก้ไข quality_gate.py

- เปลี่ยน `GATE_MODES` dict → `LanguageProfile` loader
- เปลี่ยน `script_leaks` check → Universal Unicorn Leak Detector
- เก็บ scoring logic เดิมไว้ แต่เปลี่ยนที่มาของ allowed sets

### 1.4 สิ่งที่ต้องระวัง

| ปัญหา | วิธีรับมือ |
|:------|:-----------|
| punctuation ไม่ใช่ Thai script | Common script allowance |
| emoji (Emoji_Presentation) | จัดอยู่ใน Common หรือเพิ่ม emoji: "warn" |
| วรรณยุกต์ + สระ (Combining Marks) | Inherited → allowed auto |
| ชื่อเฉพาะ (ตัวละครต่างชาติ) | protected glossary + allowed_span |
| URL/version/model name | allowed_span_patterns regex |
| Multiple scripts in one char | Grapheme cluster detection → optional |

---

## Phase 2 — Lorebook-Style Glossary (C)

**เป้าหมาย:** validate เฉพาะ terms ที่เกี่ยวข้องกับตอนนี้ ไม่ validate ทั้ง 387 terms

### 2.1 Glossary Activation Engine

```
source_chapter.md
  → extract keywords (Chinese terms from glossary.json)
  → matched_terms = intersect(glossary.source_terms, source_text)
  → validate chỉ matched_terms (ไม่ใช่ทั้งหมด 387 terms)
```

เติม `glossary.json` structure:
```json
{
  "source": "曹星",
  "thai": "เฉา ซิง",
  "category": "character_name",
  "notes": "พระเอกของเรื่อง"
}
```

### 2.2 Recursive Activation (advanced)

SillyTavern มี recursive: entry A activate entry B → B activate C  
ของเราไม่ต้องขนาดนั้น แต่รองรับ future:
```
character_name →  activate สรรพนาม rules สำหรับตัวละครนั้น
skill_name     →  activate format rules สำหรับ skill นั้น
```

### 2.3 Output

- PASS: ทุก active terms อยู่ใน output
- WARN: active terms ขาด 1-2 (อาจอยู่ใน paragraph ที่ LLM ตัด)
- FAIL: active terms ขาด > 3 หรือถูกแปลผิด

---

## Phase 3 — Unified Quality Gate (B)

**เป้าหมาย:** merge qa/quality_gate.py + scorer.py → 1 gate ตัวเดียว
dual output: deterministic (ทุก chapter) + optional LLM judge (batch report)

### 3.1 Architecture

```
UnifiedGate.run(paragraphs, source_text, target_lang)
  │
  ├─ Layer 1: Structure Check     (deterministic, 0 LLM)
  │    end marker, paragraph count, empty para
  │
  ├─ Layer 2: Language Leakage    (deterministic, 0 LLM)
  │    language_profile → Unicode script check
  │
  ├─ Layer 3: Glossary Activation (deterministic, 0 LLM)
  │    keyword intersect → validate active terms
  │
  ├─ Layer 4: Corpus Profile      (deterministic, 0 LLM) — report only
  │    trigram drift score → WARN threshold tuning
  │
  ├─ Layer 5: LLM Judge           (optional, cost)
  │    เฉพาะ batch report / needs_review review
  │
  └─ Result: { verdict: PASS|WARN|FAIL, score, issues, reports }
```

### 3.2 Threshold Inheritance

```
orchestrator/policy.py  ← SSOT
  ├─ safe:     pass_score=70, auto_repair=false, stop_on_fail=true
  ├─ autopilot: pass_score=70, auto_repair=true,  stop_on_fail=false
  └─ strict:   pass_score=85, auto_repair=false, stop_on_fail=true

Leak gate thresholds:
  ├─ safe:     FAIL on source_script_ratio>0.01
  ├─ autopilot: FAIL on source_script_ratio>0.02, WARN on >0.01
  └─ strict:   FAIL on source_script_ratio>0.005
```

---

## Phase 4 — Reduce LLM Calls

**เป้าหมาย:** 1 LLM call/chapter (จาก 2-3)

| ปัจจุบัน | หลัง |
|:---------|:------|
| translate → 1 call | translate → 1 call |
| quality retry → +1 call (ถ้าตก) | retry เฉื่อย deterministic fail จริง |
| scorer → +1 call (ทุก chapter) | scorer → batch report เท่านั้น |

**ประหยัด: 50-67% tokens → 40-60 นาที/100 ตอน**

---

## Timeline

| Phase | เนื้อหา | ไฟล์ที่เกี่ยวข้อง | ประมาณเวลา |
|:------|:--------|:-----------------|:----------:|
| P0 | Consolidate Router | llm_router/, translator/, registry/, providers/ | ~1 ชม. |
| P1 | Language Leakage Gate | qa/quality_gate.py, qa/script_policy.py, profiles/languages/ | ~2-3 ชม. |
| P2 | Lorebook Glossary | glossary.py, qa/term_policy.py | ~1-2 ชม. |
| P3 | Unified Gate | qa/*, scorer.py → merge | ~2 ชม. |
| P4 | LLM Call Reduction | novelctl.py, runner.py | ~0.5 ชม. |
| | **รวม** | | **~6-8 ชม.** |

---

## Dependencies

```
P0 (Router)  — ไม่มี, standalone
P1 (Leak)    — รอ P0 เสร็จก่อน (gate เรียกผ่าน llm_router)
P2 (Glossary) — ทำคู่ P1 ได้ (touch ไฟล์ต่างกัน)
P3 (Unified)  — รอ P1+P2 เสร็จ (merge logic)
P4 (Reduce)   — รอ P3 เสร็จ (เปลี่ยนจาก call scorer แต่ละ chapter)
```

ข้าม P0 ไม่ได้ — dead code จะรกตอน merge quality gate

---

## Quick Wins ก่อนเริ่ม (ทำได้เลย ไม่รอใคร)

1. **ลบ registry/ ทั้งหมด** — 71 LOC dead re-export → -4 ไฟล์
2. **ลบ translator/router.py + policy.py + judge.py + __init__.py** — 450 LOC dead code → -4 ไฟล์
3. **เปลี่ยน providers/api.py → import backends ตรง** — 1 บรรทัด
4. **validate_single fix** → commit แล้ว (39823d2)

**รวม:** -521 LOC, -8 ไฟล์, complexity ลดทันที
