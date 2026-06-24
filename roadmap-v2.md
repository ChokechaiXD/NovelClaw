# NovelClaw ยกระดับ — Roadmap ละเอียดพร้อมตัวชี้วัด

> **หลักการ**: ไม่รีบ, แต่ละขั้นตอนมี Quality Gate ก่อนเลื่อน, ทุกการเปลี่ยนแปลงวัดผลได้
> "จนกว่าทุกอันจะ 100" — ไม่มีปล่อยผ่าน, ไม่มีเศษเหลือ

---

## 🎯 เกณฑ์ผ่านภาพรวม (Global Quality Gate)

ก่อนประกาศว่าระบบยกระดับเสร็จ ต้องผ่านทั้งหมดนี้:

| # | Check | เกณฑ์ผ่าน |
|:-:|:------|:---------|
| 1 | `python tools/check_all.py` | 47/47 ✅ |
| 2 | `python tools/validate_data.py --all` | ผ่าน 100% |
| 3 | `python tools/tests/test_novelctl.py` | 12/12 ✅ |
| 4 | `node reader/tests/test-api.js` | 10/10 ✅ |
| 5 | Dead code (Vulture + Knip) | 0 unused exports |
| 6 | LLM call paths | ALL ผ่าน `translator/router.py` |
| 7 | Schema mismatch | 0 — JSON schema ↔ Pydantic match 100% |
| 8 | Quality record | ทุก chapter มี structured quality history |

---

## เฟส 1: Contracts + Quality Gates

**เป้าหมาย**: ทำให้ schema เป็น SSOT, ทุก output ผ่าน deterministic validation ก่อนถึง LLM judge  
**เวลาประมาณ**: 3-4 session  
**คำเตือน**: ห้ามเลื่อนไปเฟส 2 ถ้าข้อใดยังไม่ผ่าน Quality Gate

---

### 1.1 Syn schema — JSON schema ↔ Pydantic model

**ปัญหา**: `chapter.schema.json` ใช้ `sourceLang/targetLang` แต่ `tools/schema.py` Chapter model ใช้ `lang/output_lang/profile_lang`

**สิ่งที่ต้องทำ**:

```
Step 1.1.1 — เลือก canonical
✅ chapter.schema.json = SSOT (Draft7 JSON Schema)
✅ tools/schema.py Chapter model = generated/imported จาก JSON schema
❌ ไม่ใช้ field names 2 ชุดอีกแล้ว

Step 1.1.2 — แก้ tools/schema.py
- Chapter model fields → sourceLang, targetLang (แทน lang, output_lang)
- title field → { source, translated } (object, ไม่ใช่ string)
- เพิ่ม fields: model (str), provider (str, enum), qualityRecord (object)
- status field → enum: translated, source_only, source, legacy
- ลบ side-effect model_validator (auto-append จบบท) — ไปเป็น pipeline step แทน

Step 1.1.3 — สร้าง tools/contracts/chapter.py
- Pydantic BaseModel ChapterV2
- auto-generate JSON schema → export เป็น chapter.schema.json
- backward compat reader: รับทั้ง old (sourceLang/targetLang) และ new fields

Step 1.1.4 — migrate ไฟล์ที่มีอยู่
- เพิ่ม model/provider fields จาก audit log (ถ้ามี)
- ถ้าไม่มี → model = "unknown", provider = "unknown"
```

**ตัวชี้วัด**:

| Metric | ก่อน | หลัง |
|:-------|:----|:-----|
| schema.py ↔ chapter.schema.json field match | 0% (field names ต่าง) | 100% |
| validate_data --all ผ่าน | 164/164 (แต่ schema ไม่ตรง) | 164/164 (schema ตรงจริง) |
| ไฟล์ chapter ที่มี model field | 0/73 (0%) | 73/73 (100%) |
| side-effect validator | 1 (model_validator) | 0 (แยกเป็น pipeline step) |

**Done เมื่อ**:
- [ ] `python -c "from tools.schema import Chapter; print(Chapter.model_json_schema())"` → fields ตรงกับ chapter.schema.json
- [ ] `python tools/validate_data.py --all` ผ่าน 100%
- [ ] ทุก chapter.th.json มี field `model` และ `provider`
- [ ] 0 side-effect validator ใน Pydantic model (ย้ายไป pipeline)

---

### 1.2 Schema validation เป็น pre-save gate

**ปัญหา**: `runner.translate_single()` ไม่ validate schema ก่อน save — ไฟล์เสียอาจลงดิสก์ได้

**สิ่งที่ต้องทำ**:

```
Step 1.2.1 — แก้ runner.translate_single()
- หลังจาก translate.py return success
- ก่อน save .th.json → validate_data.validate_with_schema(data, schema)
- ถ้า fail → ไม่ save → log error → needs_review

Step 1.2.2 — แก้ runner.validate_single()
- เพิ่ม schema validation ก่อน score
- ถ้า schema fail → score = 0, error = "schema validation failed"

Step 1.2.3 — เพิ่ม flag novelctl.py
- --schema-gate (default on) — ถ้า schema fail, stop pipeline
```

**ตัวชี้วัด**:

| Metric | ก่อน | หลัง |
|:-------|:----|:-----|
| schema validation timing | post-save (check_all) | pre-save (fail-fast) |
| schema-fail chapter ที่ถึง disk | เป็นไปได้ | 0 (ไม่ save) |
| translate_single() validation calls | 0 | 2 (schema + scorer) |

**Done เมื่อ**:
- [ ] `runner.translate_single()` → schema validate → fail → no file written
- [ ] `runner.validate_single()` → schema validate → fail → score=0, error set
- [ ] ทดสอบ manual: save chapter with missing required field → 422

---

### 1.3 รวม 3 validators เป็น source เดียว

**ปัญหา**: `tools/validation.py` + `tools/scorer.py` + `tools/llm_router/validators.py` — regex CJK/EN leak ซ้ำกัน 3 ที่

**สิ่งที่ต้องทำ**:

```
Step 1.3.1 — สร้าง tools/qa/ package
tools/qa/
├── __init__.py
├── validators.py    ← regex patterns (CJK, EN, source artifacts) — consolidated
├── deterministic.py ← pre-LLM checks (length, paragraph count, markers)
├── scoring.py       ← composite scoring — moved from scorer.py core logic

Step 1.3.2 — refactor ไฟล์เดิม
- tools/validation.py → import from tools/qa/validators (thin wrapper)
- tools/llm_router/validators.py → import from tools/qa/ (thin wrapper)
- tools/scorer.py → import scoring logic from tools/qa/scoring.py

Step 1.3.3 — ลบ regex ที่ซ้ำ
- CJK_LEAK_RE, LATIN_LEAK_RE, SOURCE_ARTIFACT_RE → อยู่ใน tools/qa/validators.py
- ไฟล์อื่น import จากตรงนี้
```

**ตัวชี้วัด**:

| Metric | ก่อน | หลัง |
|:-------|:----|:-----|
| ไฟล์ที่มี CJK leak regex | 3 | 1 (tools/qa/validators.py) |
| ไฟล์ที่มี LATIN leak regex | 3 | 1 |
| duplicate regex patterns | ~15 | 0 |
| import chain length | validation.py → scorer.py → llm_ router | tools/qa/ validators.py ← ทุกตัว |

**Done เมื่อ**:
- [ ] `grep -r "CJK_LEAK_RE\|LATIN_LEAK_RE" tools/` → only in tools/qa/
- [ ] `python tools/check_all.py` ผ่าน
- [ ] `python tools/novelctl.py --slug global-descent validate 74` ได้ score เท่าเดิม

---

### 1.4 Quality record ต่อเนื่อง

**ปัญหา**: `orchestrator/quality.py` บันทึก audit log แบบ flat — translate/validate/repair แต่ละครั้ง แต่ไม่มี structured history

**สิ่งที่ต้องทำ**:

```
Step 1.4.1 — structure quality record
{
  "slug": "global-descent",
  "num": 74,
  "records": [
    {
      "action": "translate",
      "model": "google/gemma-4-31b-it:free",
      "provider": "openrouter",
      "score": 93,
      "mqm": { "accuracy": 0, "fluency": 1, "terminology": 0, "omission": 0 },
      "duration_ms": 45000,
      "timestamp": "2026-06-24T..."
    },
    {
      "action": "validate",
      "score": 95,
      "timestamp": "..."
    }
  ]
}

Step 1.4.2 — quality.write_record(slug, num, record)
- append → jobs/quality/<slug>/<num>.json
- ถ้าไฟล์มีอยู่แล้ว → read → append → write

Step 1.4.3 — เรียกทุก pipeline step
- translate_single() → write_record with action="translate"
- validate_single() → write_record with action="validate"
- repair_chapter() → write_record with action="repair"
```

**ตัวชี้วัด**:

| Metric | ก่อน | หลัง |
|:-------|:----|:-----|
| quality history per chapter | flat log (ไม่ structured) | structured record array |
| สามารถดู trend ได้ | ไม่ (log แยกไฟล์) | ได้ (record array ยาวขึ้นเรื่อยๆ) |
| MQM tagging | ไม่มี | มี structured error types |
| jobs/quality/ ไฟล์ | 0 | ทุก chapter ที่ผ่าน pipeline |

**Done เมื่อ**:
- [ ] ทุก chapter ที่ translate → มี jobs/quality/<slug>/<num>.json
- [ ] record structure ตรงตาม schema
- [ ] `python tools/novelctl.py --slug global-descent validate 76` → quality record โผล่

---

### 1.5 Glossary/TM เป็น first-class gate

**ปัญหา**: glossary.py โหลด terms แต่ไม่ enforce — translate.py แค่ส่งเป็น context ไม่ได้ validate

**สิ่งที่ต้องทำ**:

```
Step 1.5.1 — glossary.validate_translation(text, slug)
- รับ translated text + slug
- return { ok, missing_terms, violated_rules, warnings }
- missing_terms = terms ที่ควรมีแต่ไม่มี
- violated_rules = style rules ที่ถูกละเมิด

Step 1.5.2 — TM / chapter memory
- สร้าง tools/tm/chapter_memory.py
- สำหรับ slug, num → return summary 3-5 บทล่าสุด
- summary format: { characters, skills, important_events, terms }
- inject เข้า prompt prefix ตอน translate

Step 1.5.3 — wire ใน runner.translate_single()
- ก่อน save → glossary.validate_translation()
- ถ้า fail → ไม่ save → needs_review
```

**ตัวชี้วัด**:

| Metric | ก่อน | หลัง |
|:-------|:----|:-----|
| glossary enforcement | 0% (แค่ reference) | 100% (check ก่อน save) |
| chapter memory ใน prompt | ไม่มี | summary 3-5 บทล่าสุด |
| term consistency (manual check) | ไม่วัด | missing_terms ลดลง 80%+ |

**Done เมื่อ**:
- [ ] `glossary.validate_translation("...", "global-descent")` return structured result
- [ ] translation ส่ง chapter memory เข้า prompt
- [ ] runner.translate_single() เรียก glossary check ก่อน save
- [ ] ถ้า glossary fail → ไม่ save → needs_review

---

### 🛑 Quality Gate เฟส 1

| # | Check | เกณฑ์ผ่าน |
|:-:|:------|:---------|
| G1 | schema.py ↔ chapter.schema.json | field match 100% |
| G2 | validate_data --all | ผ่าน 100% |
| G3 | pre-save schema gate | translate_single() ไม่ save schema-fail |
| G4 | duplicate regex | 0 duplicate ใน QA layer |
| G5 | quality record | ทุก chapter ที่ translate มี structured record |
| G6 | glossary enforcement | 100% ของตอน → glossary check ผ่านก่อน save |

> ⛔ **ถ้าข้อใดไม่ผ่าน → หยุด ไม่เลื่อนเฟส 2 — แก้ให้จบก่อน**

---

## เฟส 2: Translator Backend Split

**เป้าหมาย**: แยก "แปล" ออกจาก "วิเคราะห์/จับผิด/ซ่อม", เสียบ dedicated MT backend ได้  
**เวลาประมาณ**: 3-4 session

---

### 2.1 Consolidate provider layer

**ปัญหา**: `tools/providers/api.py` + `tools/llm_router/providers.py` = 2 providers ทำสิ่งเดียวกัน

**สิ่งที่ต้องทำ**:

```
Step 2.1.1 — สร้าง tools/translator/backends/
translator/backends/
├── __init__.py
├── base.py              ← abstract class TranslatorBackend
│   def translate(self, prompt, system) -> str
│   def model_name(self) -> str
│   def provider_name(self) -> str
├── openmodel.py         ← existing from providers/api.py
├── openrouter.py        ← existing from llm_router/providers.py
├── translate_gemma.py   ← placeholder (dedicated MT)
└── qwen_mt.py           ← placeholder (dedicated MT)

Step 2.1.2 — abstract interface
class TranslatorBackend:
    """Common interface for all translation backends."""
    def translate(self, text: str, system: str | None = None, **kwargs) -> str: ...
    @property
    def model(self) -> str: ...
    @property
    def provider(self) -> str: ...

Step 2.1.3 — backward compat wrapper
- tools/providers/api.py → import from translator.backends (thin re-export)
- tools/llm_router/providers.py → import from translator.backends (thin re-export)
```

**ตัวชี้วัด**:

| Metric | ก่อน | หลัง |
|:-------|:----|:-----|
| provider implementations | 2 (api.py + llm_router/providers.py) | 1 (translator/backends/) |
| interface consistency | ต่างกัน (anthropic vs openai) | abstract base class |
| backward compat | N/A | providers/api.py ยัง import ได้ |

**Done เมื่อ**:
- [ ] `call_provider("openrouter", prompt)` ผ่าน translator/backends/
- [ ] `call_llm(prompt)` จาก providers/api.py → transparent wrapper
- [ ] `python tools/novelctl.py --slug global-descent translate 76` (draft) ยังทำงาน

---

### 2.2 Router abstraction layer

**ปัญหา**: `llm_router/router.py` มี `call_profile()` ดี แต่ orchestrator/runner.py ไม่ใช้ — ใช้ providers/api.py โดยตรง

**สิ่งที่ต้องทำ**:

```
Step 2.2.1 — สร้าง tools/translator/router.py
- Router class
- select_backend(profile: str, session_id: str | None) → TranslatorBackend
- Session stickiness: session_id เดิม → backend เดิม
- fallback chain: read from translator/policy.py

Step 2.2.2 — Profile system
- PROFILE = { translate_fast, translate_quality, judge, validate }
- แต่ละ profile มี { backend, fallback, timeout, temperature }

Step 2.2.3 — Wire เข้า runner.py
- runner.translate_single() → translator/router.py → translate
- runner.validate_single() → translator/router.py → validate (ถ้าต้อง LLM)
- runner.rebuild_index() → ไม่ต้อง (pure JS)
```

**ตัวชี้วัด**:

| Metric | ก่อน | หลัง |
|:-------|:----|:-----|
| LLM call path | providers/api.py โดยตรง | translator/router.py เสมอ |
| session stickiness | ไม่มี | session_id → backend เดิม |
| translate pipeline LLM calls | ผ่าน providers/api.py | ผ่าน translator/router.py |

**Done เมื่อ**:
- [ ] `grep -r "call_llm" tools/orchestrator/runner.py` → 0 (ใช้ router)
- [ ] `grep -r "from providers import call_llm" tools/*.py` → 0 (ยกเว้น wrapper)
- [ ] translate 76 draft → ผ่าน router

---

### 2.3 Judge model แยกจาก translator

**ปัญหา**: ปัจจุบัน model ที่แปล = model ที่ validate = self-judge

**สิ่งที่ต้องทำ**:

```
Step 2.3.1 — สร้าง tools/translator/judge.py
- Judge class
- deterministic_check(text) → { ok, reasons } (ก่อน LLM)
- llm_judge(text, reference) → { score, mqm_tags } (หลัง deterministic ผ่าน)
- ใช้ profile "judge" → cheaper/faster model กว่า translate

Step 2.3.2 — Wire เข้า pipeline
- runner.translate_single() → translate → deterministic QA → LLM judge → save
- ถ้า judge score < threshold → needs_review (ไม่ save)

Step 2.3.3 — Quality record integration
- judge result → quality.write_record(action="judge", ...)
```

**ตัวชี้วัด**:

| Metric | ก่อน | หลัง |
|:-------|:----|:-----|
| translate model = judge model | yes (self-judge) | no (different models) |
| deterministic QA ก่อน LLM | ไม่มี (LLM ก่อน) | deterministic → LLM judge |
| judge record in quality history | ไม่มี | มี (action="judge") |

**Done เมื่อ**:
- [ ] deterministic QA block คือ pipeline step ไม่ใช่ LLM call
- [ ] judge model ≠ translate model (verify จาก quality record)
- [ ] ถ้า judge < threshold → needs_review

---

### 2.4 Fallback policy explicit

**ปัญหา**: fallback chain hardcode ใน `llm_router/config.py` — orchestrator ไม่ใช้

**สิ่งที่ต้องทำ**:

```
Step 2.4.1 — translator/policy.py
from dataclasses import dataclass

@dataclass
class BackendConfig:
    backend: str          # "openrouter", "openmodel", etc.
    model: str
    timeout_sec: int
    max_tokens: int
    temperature: float

@dataclass
class ProfileChain:
    name: str
    primary: BackendConfig
    fallbacks: list[BackendConfig]
    session_sticky: bool = True

FALLBACK_CHAINS = {
    "translate_fast": ProfileChain(
        primary=BackendConfig("openrouter", "google/gemma-4-26b-a4b-it:free", 80, 4096, 0.28),
        fallbacks=[
            BackendConfig("openrouter", "google/gemma-4-31b-it:free", 100, 4096, 0.28),
            BackendConfig("openrouter", "openai/gpt-oss-120b:free", 90, 4096, 0.2),
            BackendConfig("openrouter", "openrouter/free", 75, 2048, 0.25),
        ]
    ),
    "judge": ProfileChain(
        primary=BackendConfig("openrouter", "google/gemma-4-26b-a4b-it:free", 60, 2048, 0.1),
        fallbacks=[...]
    ),
}
```

**ตัวชี้วัด**:

| Metric | ก่อน | หลัง |
|:-------|:----|:-----|
| fallback config location | llm_router/config.py (hardcode) | translator/policy.py (dynamic) |
| orchestrator ใช้ fallback มั้ย | ไม่ (bypass) | ใช้ |
| change threshold โดยไม่แก้ code | ไม่ได้ | ได้ (แค่ policy.py) |

**Done เมื่อ**:
- [ ] `orchestrator/runner.py` ใช้ `translator/policy.py` สำหรับ fallback
- [ ] `llm_router/config.py` → thin re-export (หรือลบ)
- [ ] `python tools/novelctl.py --slug global-descent translate 76 draft` ทำงานผ่าน policy

---

### 🛑 Quality Gate เฟส 2

| # | Check | เกณฑ์ผ่าน |
|:-:|:------|:---------|
| G1 | LLM call path | ALL ผ่าน translator/router.py |
| G2 | providers/api.py usage | translate_single() ไม่เรียกโดยตรง |
| G3 | Judge model ≠ translate model | ตรวจจาก quality record |
| G4 | Fallback chain dynamic | ไม่ hardcode — config ใน policy.py |
| G5 | check_all.py | 47/47 ✅ |

> ⛔ **ถ้า LLM call bypass router → หยุด**

---

## เฟส 3: Simplification + Registry

**เป้าหมาย**: ลด complexity debt, ลบ wrapper ไร้ค่า, ทำให้ code path สั้นที่สุด  
**เวลาประมาณ**: 2-3 session

---

### 3.1 Registry กลาง

```
tools/registry/
├── __init__.py
├── contracts.py     ← schema/models registry
├── policy.py        ← thresholds, fallback chains
└── templates.py     ← prompts, repair rules, report formats
```

**Done เมื่อ**: import path ลดลง 40% สำหรับ modules ที่ใช้ registry

---

### 3.2 progress.py → delete

```
Step 3.2.1 — ลบ from progress import ... ใน translate.py
Step 3.2.2 — ใช้ orchestrator/jobs.py แทน
Step 3.2.3 — ลบ tools/progress.py
Step 3.2.4 — ลบ .chprogress/ directory
```

**Measure**: `grep -r "progress" tools/*.py` → 0 (ยกเว้น tests)

---

### 3.3 commands.py → merge + delete

```
Step 3.3.1 — merge comma-separated range parsing
- novelctl.py parse_range() → รองรับ "140,142,145"
- ลบ tools/commands.py
```

**Measure**: `novelctl.py 140,142,145` → แปล 3 ตอน

---

### 3.4 report.py duplicate fix

```
Step 3.4.1 — import quality.count_needs_review() แทน local
```

**Measure**: `grep "def _count_needs_review" tools/*.py` → 0

---

### 3.5 lock TTL

```
Step 3.5.1 — locks.cleanup_stale(ttl_secs=3600)
Step 3.5.2 — เรียกตอน start handle_translate()
```

**Measure**: `jobs/locks/*.json` ที่อายุ > 1h → ถูกลบ auto

---

### 3.6 Dead code cleanup

```
Python: ruff check tools/ ; vulture tools/ --min-confidence 70
JavaScript: npx eslint reader/public/js/ ; npx knip
```

**Measure**: vulture = 0 (หรือ documented exceptions), knip = 0 unused exports

---

### 🛑 Quality Gate เฟส 3

| # | Check | เกณฑ์ผ่าน |
|:-:|:------|:---------|
| G1 | check_all.py | 47/47 ✅ |
| G2 | progress.py reference | 0 |
| G3 | commands.py reference | 0 |
| G4 | duplicate functions | 0 |
| G5 | stale lock | 0 |
| G6 | vulture report | 0 (หรือ documented) |
| G7 | knip report | 0 unused exports |

---

## เฟส 4: Speed + UX

**เป้าหมาย**: เร็วขึ้นโดยไม่เสีย quality  
**เวลาประมาณ**: 2-3 session

---

### 4.1 Concurrent translation

```
--workers N (default 3)
ThreadPoolExecutor → I/O-bound LLM calls
```

**Measure**: speedup = sequential_time / parallel_time

---

### 4.2 Prompt caching structure

```
Prompt = [static prefix] + [dynamic source]
Static = role + style + glossary + schema + policy → cache-friendly
Dynamic = source chapter text → ต่อท้าย
```

**Measure**: cache hit rate (ถ้า provider รายงาน)

---

### 4.3 Reader performance

```
- content-visibility: auto สำหรับ long chapters
- IntersectionObserver แทน scroll listener
```

**Measure**:
- LCP < 2.5s
- INP < 200ms
- CLS < 0.1

---

### 4.4 Telegram command surface

```
- setMyCommands → { /translate, /retry, /review, /resume, /report, /publish }
- deep links + inline keyboards
```

**Measure**: user interaction steps ลดลง 50%

---

### 🛑 Quality Gate เฟส 4

| # | Check | เกณฑ์ผ่าน |
|:-:|:------|:---------|
| G1 | translate --workers 3 | ทำงานถูกต้อง, ไม่ทับไฟล์กัน |
| G2 | regression | check_all.py 47/47 ✅ |
| G3 | Web Vitals | LCP < 2.5s, INP < 200ms, CLS < 0.1 |
| G4 | Telegram commands | map กับ novelctl commands |

---

## 📊 ตารางรวมตัวชี้วัดทั้งหมด

| ตัวชี้วัด | ก่อน | หลัง (target) |
|:---------|:----|:--------------|
| Schema field match (JSON ↔ Pydantic) | 0% | 100% |
| Pre-save schema validation | ไม่มี | 100% ทุก save |
| Duplicate regex patterns | ~15 | 0 |
| Quality record per chapter | 0/73 | 73/73 |
| Glossary enforcement | 0% | 100% |
| Translator providers | 2 files (api.py + llm_router) | 1 interface (backends/) |
| LLM calls ผ่าน router | 0% | 100% |
| Judge ≠ translator model | ไม่มี judge แยก | yes |
| progress.py references | 4+ in translate.py | 0 |
| commands.py | duplicate file | deleted |
| Dead code (vulture) | ไม่วัด | 0 (หรือ documented) |
| Translation speedup | sequential | workers N → Nx |
| Reader Web Vitals | ไม่วัด | LCP<2.5, INP<200 |
| check_all.py | 47/47 | 47/47 ไม่ regression |
