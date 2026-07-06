# PRD: NovelClaw Quality Enhancement — 5-Phase Upgrade

**Status:** Draft v1  
**Author:** Sora  
**Date:** 2026-07-06  
**Commit base:** `41f8cdd` (main)

---

## Summary

ระบบ quality gate ของ NovelClaw ปัจจุบันใช้ heuristic 6 มิติ + LLM judge ธรรมดา  
งานนี้ยกระดับเป็น structured quality engine ที่ detect/classify/repair ข้อผิดพลาดได้  
โดยไม่ต้องเพิ่ม GPU dependency — ใช้ foundation ที่มี (9Router + heuristic scorer) เป็นฐาน

---

## Phase 1: G-Eval LLM Judge Enhancement

**Effort:** ~6-8 ชม. | **Impact:** สูง | **Dependency:** ไม่มี

### ปัญหา
`judge_translation()` ปัจจุบันใช้ prompt ธรรมดา — ขอคะแนน 1-10 ด้าน Naturalness/Consistency/Clarity/Flow  
แต่ไม่มี chain-of-thought, ไม่มี calibration, ไม่มี error type classification

### Solution
เปลี่ยน prompt เป็น **G-Eval protocol**:

1. **Rubric 4 มิติ** (ใช้ LLM judge ผ่าน 9Router เหมือนเดิม):
   - **Accuracy** (weight 0.40) — events, entities intact
   - **Fluency** (weight 0.15) — natural target language
   - **Terminology** (weight 0.25) — glossary compliance
   - **Coherence** (weight 0.20) — logical flow

2. **Chain-of-Thought**: ก่อนให้คะแนน ให้ model reasoning ก่อน 1-2 ประโยคต่อมิติ

3. **Weighted Score**: `Σ(score_i × weight_i)` → calibrated 0-100

4. **Structured Output**: JSON พร้อม error list, severity, position

### สิ่งที่ต้องเปลี่ยน
| File | การเปลี่ยนแปลง |
|:-----|:--------------|
| `pipeline.py` | เปลี่ยน `_JUDGE_SYSTEM` → prompt ใหม่ + G-Eval protocol |
| `pipeline.py` | เปลี่ยน return shape ของ `judge_translation()` |
| `pipeline.py` | ปรับ `_judge_and_auto_repair()` ให้ใช้ error list ใหม่ |
| (ใหม่) | เก็บ rubric weights ใน LANG_CONFIGS หรือ config |

### Risk
- LLM CoT ทำให้ token usage เพิ่ม ~2x ต่อ judge call → ค่าบริการเพิ่ม (แต่ judge ถูกเรียกเฉพาะ chapters ที่ 85 ≤ score < 95)
- แต่ละมิติอาจมี narcissistic bias → mitigation: prompt แยกขั้นตอน

### Success Criteria
- [ ] judge ส่ง structured JSON ทุกครั้ง (ไม่ใช่ free text)
- [ ] weighted score  correlation กับ heuristic score ≥ 0.7
- [ ] ใช้ token ไม่เกิน 300 tokens/response

---

## Phase 2: MQM Error Typology Integration

**Effort:** ~2 วัน | **Impact:** สูง | **Dependency:** Phase 1

### ปัญหา
ปัจจุบัน errors เป็น `list[str]` (ข้อความอิสระ) → repair station ต้อง parse เอาเอง  
ไม่มี type, severity, position → สั่ง repair ไม่ตรงจุด

### Solution
เพิ่ม structured error type ตาม MQM framework:

```python
@dataclass
class MqmError:
    category: str         # accuracy, fluency, terminology, style, locale, script_leak
    subcategory: str      # omission, addition, mistranslation, hangul_leak, ...
    severity: str         # minor, major, critical
    span: str             # ข้อความที่มีปัญหา (first 80 chars)
    position: int         # paragraph index หรือ -1
    detail: str           # คำอธิบาย
```

### สิ่งที่ต้องเปลี่ยน
| File | การเปลี่ยนแปลง |
|:-----|:--------------|
| `scorer.py` | เพิ่ม `MqmError` dataclass |
| `scorer.py` | แต่ละ `_score_*()` ส่ง `MqmError[]` แทน `errors: list[str]` |
| `quality_gate.py` | `evaluate_translation_quality()` ส่ง `mqm_errors` |
| `quality_gate.py` | `build_repair_notes()` → logic-based repair instruction (use error type) |
| `pipeline.py` | `_quality_summary()` + `_build_repair_instruction()` ใช้ error list ใหม่ |
| `scorer.py` | `DimensionScore` เพิ่ม optional `errors: list[MqmError]` |

### Example Flow
```
_score_completeness() → MqmError(
    category="accuracy",
    subcategory="omission",
    severity="major",
    span="output 1200 chars vs source 2000 chars",
    position=-1,
)
→ build_repair_notes() → "Expand missing content and preserve all source events."
→ auto-repair prompt: "The translation is missing ~40% content. Focus on the middle section."
```

### Success Criteria
- [ ] ทุก `_score_*()` ส่ง `list[MqmError]` แทน flat string
- [ ] `build_repair_notes()` สร้าง repair instruction ตาม type + severity
- [ ] ข้อมูล error structure พร้อมใช้ใน auto-correction (Phase 4)

---

## Phase 3: Adaptive Threshold

**Effort:** ~3 ชม. | **Impact:** กลาง | **Dependency:** ไม่มี

### ปัญหา
Hardcoded `PASS_THRESHOLD = 85.0` — ไม่ต่างกันระหว่าง novel ที่แปลง่าย vs ยาก  
บาง novel มี baseline สูง (>90) แต่ไปพลาดตอนเดียวที่ 86 → ถือว่าผ่าน  
บาง novel baseline ต่ำ (82) แต่ตอนไหนที่ 84 → ควร flag

### Solution
```python
@dataclass
class ScorerHistory:
    scores: list[float] = field(default_factory=list)
    threshold_override: float | None = None

    def update(self, score: float):
        self.scores.append(score)
        n = len(self.scores)
        if n >= 3:
            mean = sum(self.scores) / n
            std = (sum((s - mean)**2 for s in self.scores) / n)**0.5
            self.threshold_override = max(85.0, mean - 1.5 * std)

    @property
    def effective_threshold(self) -> float:
        return self.threshold_override or PASS_THRESHOLD
```

- ส่งต่อ `ScorerHistory` ใน pipeline state (ผ่าน `translate_one()` params)
- `threshold` ใน `evaluate_translation_quality()` ใช้ `effective_threshold`

### สิ่งที่ต้องเปลี่ยน
| File | การเปลี่ยนแปลง |
|:-----|:--------------|
| `scorer.py` | เพิ่ม `ScorerHistory` dataclass |
| `pipeline.py` | `translate_one()` รับ `optional scorer_history` |
| `pipeline.py` | หลัง scoring → `scorer_history.update(score)` |
| `novelclaw.py` | สร้าง `ScorerHistory` 1 ตัวต่อ batch |

### Risk
- 3 chapters แรกยังไม่มี baseline → ใช้ threshold 85.0 (fallback)
- ถ้า novel มี chapters ที่ score ต่ำตั้งแต่ต้น → threshold adapt เร็วไป → mitigation: ใช้ min 3 chapters ก่อน adjust

### Success Criteria
- [ ] หลังจาก 3 chapters, threshold adjust ตาม performance จริง
- [ ] chapters ที่ deviate >1.5σ → flag โดยไม่สน absolute 85
- [ ] backward compatible — ถ้าไม่ส่ง `ScorerHistory` → ใช้ 85.0

---

## Phase 4: Script Leak Auto-Correction

**Effort:** ~1 วัน | **Impact:** สูง | **Dependency:** Phase 2 (MQM errors)

### ปัญหา
ตอนนี้ถ้าเจอ script leak → `_score_and_report()` ส่ง `passed=False` → retry ใหม่ทั้งหมด  
ทั้งที่จริงแค่ 2-3 paragraph ที่มี leak — retry ทั้งบทเสียเวลาและเปลือง tokens

### Solution
เพิ่ม **repair station** ที่ target เฉพาะ paragraphs ที่ leak:

```
detect leak → identify paragraph index → 
Repair station 5.5:
  - ส่งเฉพาะ paragraphs ที่ leak ไปให้ LLM fix
  - prompt: "Translate only the foreign text in these paragraphs: ..."
  - หลัง replace → re-score → ถ้าผ่านก็ใช้ต่อ
```

### สิ่งที่ต้องเปลี่ยน
| File | การเปลี่ยนแปลง |
|:-----|:--------------|
| `pipeline.py` | Station ใหม่หลัง Station 5 (parse) ก่อน Station 6 (classify) |
| `pipeline.py` | `_repair_script_leaks(parsed, target_lang)` → detect → fix → merge |
| `scorer.py` | `_score_script_purity()` ส่ง `MqmError` พร้อม `position` (paragraph index) |
| (เพิ่ม) | fallback: ถ้า LLM repair ไม่สำเร็จ → ใช้ repair prompt แบบเก่า |

### Flow
```
parse output → ["๑. ซำซิงพูดว่า "okay", ...", "(จบบท)"]
                ↓
detect leak → paragraph 0: "okay" is English
                ↓
repair prompt (model=primary, system=none):
  "Fix only the foreign text in these paragraphs. 
   Replace "okay" with Thai equivalent.
   Return ONLY the fixed paragraph text."
                ↓
merge → ["๑. ซำซิงพูดว่า "โอเค", ...", "(จบบท)"]
                ↓
classify + score → ผ่าน → save (ไม่ต้อง retry)
```

### Success Criteria
- [ ] detect + repair script leaks โดยไม่ต้อง retry ทั้งบท
- [ ] ลด retry rate สำหรับ script leak failures ≥ 50%
- [ ] ปลอดภัย — ถ้า repair failed → fallback ไป retry ทั้งบท

---

## Phase 5: COMETKiwi Semantic Score (Optional)

**Effort:** ~1 วันทดลอง | **Impact:** สูง (ถ้าเวิร์ค) | **Dependency:** ลง PyTorch CPU

### ปัญหา
Heuristic scorer วัด completeness/script/term แต่ไม่วัด **semantic equivalence**  
เช่น แปลถูกต้องแต่ความหมายผิดเพี้ยน → heuristic ไม่จับ

### Solution
เพิ่ม COMETKiwi เป็น dimension ที่ 7:

```python
from comet import download_model, load_from_checkpoint

_KIWI_MODEL = None

def _load_kiwi():
    global _KIWI_MODEL
    if _KIWI_MODEL is None:
        path = download_model("Unbabel/wmt22-cometkiwi-da")
        _KIWI_MODEL = load_from_checkpoint(path)

def _score_semantic(paragraphs, source_text, target_lang):
    if target_lang not in ("th", "en"):  # fallback
        return DimensionScore("Semantic", 0.10, 1.0, "not supported")
    _load_kiwi()
    # segment-level; สำหรับ TH→EN/EN→TH
    data = [{"src": source_text, "mt": full_text}]
    scores = _KIWI_MODEL.predict(data, batch_size=1)
    score = scores[0]  # 0-1
    return DimensionScore("Semantic", 0.10, score,
                          f"COMETKiwi: {score:.2f}")
```

### สิ่งที่ต้องเปลี่ยน
| File | การเปลี่ยนแปลง |
|:-----|:--------------|
| `scorer.py` | เพิ่ม `_score_semantic()` |
| `scorer.py` | `score_chapter()` เพิ่ม dimension ที่ 7 (weight 0.10, ปรับลด weight อื่น) |
| `requirements.txt` | เพิ่ม `unbabel-comet` (PyTorch CPU) |

### Constraints
- COMETKiwi ~550M params → CPU inference ~2-5 วินาทีต่อ chapter
- รองรับเฉพาะ TH/EN (InfoXLM base)  
- ขนาด model ~1.5GB disk + ~4GB RAM

### ทางเลือกถ้า COMETKiwi ไม่ได้
- **xCOMET-lite** (<600M params, distilled) — ต้องลอง benchmark  
- **SentenceTransformer + cosine similarity** — ง่ายกว่า แต่จับ semantic ละเอียดน้อยกว่า

### Success Criteria
- [ ] inference < 5 วินาทีต่อ chapter บน CPU
- [ ] correlation กับ human judgment ≥ 0.6
- [ ] เพิ่ม false positive rate ≤ 5% (ไม่ reject งานดีบ่อยเกิน)

---

## Implementation Priority

```
สัปดาห์ 1:   Phase 1 (G-Eval) ─────────────────────────────── 6-8 ชม.
             Phase 3 (Adaptive Threshold) ─────────────────── 3 ชม.

สัปดาห์ 2:   Phase 2 (MQM Errors) ─────────────────────────── 2 วัน
             Phase 4 (Script Leak Auto-Correction) ────────── 1 วัน

สัปดาห์ 3:   Phase 5 (COMETKiwi) ──────────────────────────── 1 วัน (ทดลอง)
```

---

## Metrics (ก่อน/หลัง)

| Metric | ก่อน | หลัง (คาดหวัง) |
|:-------|:-----|:--------------|
| **Retry rate** | ~20-30% | < 15% |
| **False reject** | ไม่มี structured tracking | < 5% |
| **False accept** | ไม่มี structured tracking | < 5% |
| **Script leak auto-fix** | 0% (retry ใหม่) | ≥ 50% (fix in-place) |
| **Error traceability** | flat string list | structured MQM + position |
| **Threshold adaptability** | hardcoded 85 | dynamic 1.5σ |

---

## Appendix: MQM Category Mapping สำหรับ NovelClaw

```
MQM Category    │ Subtypes ที่เราจับได้            │ Scorer Dimension
────────────────┼────────────────────────────────┼─────────────────
Accuracy        │ omission, addition              │ Completeness
Fluency         │ grammar, punctuation            │ (ใหม่/script_policy)
Terminology     │ leak, missing_coverage          │ Term Compliance
Style           │ register_mismatch               │ Type Diversity + Dialogue Ratio
Locale          │ date_format, numbering          │ (future)
Non-translation │ script_leak (Hangul/CN/JP/KR)   │ Script Purity
Structure       │ missing_end_marker              │ End Marker
                │ missing_dialogue_paras          │ Structure Contract
```
