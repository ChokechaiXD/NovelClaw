# NovelClaw Central Configuration Design

## 1. ปัญหา (Before)

ตอนนี้ config กระจาย 3 ไฟล์ + ฮาร์ดโค้ด 3 จุดใน code:

| Source | อยู่ที่ | config keys |
|:-------|:-------|:------------|
| **providers.yaml** | `tools/config/` | `active`, `default_model`, `discovery_model`, provider base_url/timeout/temp/model list, profiles |
| **llm.json** | โปรเจกต์ root | API keys 4 keys (openrouter, custom, zai, main) |
| **hardcoded** `pipeline_llm.py:19,24` | — | fallback `active="openrouter"`, `default_model="google/gemma-4-26b-a4b-it:free"` |
| **hardcoded** `pipeline.py:292-294` | — | fallback `model`, `provider` ซ้ำอีกชั้น |
| **CLI args** `novelclaw.py` | — | `--model`, `--provider`, `--profile` override |

**เวลาเปลี่ยน model → ต้องแก้ 5 จุด** (YAML + JSON + 2 hardcodes + อาจจะ CLI)

---

## 2. เป้าหมาย (After)

```
novelclaw.config.yaml   ← Central config (ทุกอย่างยกเว้น API keys)
llm.json                ← API keys เท่านั้น
```

### 2.1 novelclaw.config.yaml schema

```yaml
# novelclaw.config.yaml — Central Pipeline Configuration
# ── Active provider & model ──
provider: openrouter                          # active provider name
model: google/gemma-4-31b-it:free             # translate model
discovery_model: google/gemma-4-31b-it:free   # glossary/judge model (optional, fallback = model)

# ── LLM defaults ──
temperature: 0.28
max_tokens: 8192
timeout_sec: 120
parallel_workers: 3

# ── Pipeline behavior ──
prompt_profile: ""                            # default profile name (faithful_default, faithful_literary, etc.)
sequential: false                             # force single-threaded
judge_enabled: true                           # false = skip LLM Judge entirely
judge_threshold: 95.0                         # score ≥ this → skip Judge
glossary_discovery: true                      # false = skip glossary discovery

# ── Fallback (safety filter bypass) ──
fallback_provider: custom                     # when OpenRouter moderation cuts output → retry via this provider
fallback_model: openrouter/nvidia/nemotron-3-super-120b-a12b:free
```

### 2.2 การอ่าน config (Resolve Order)

```
novelclaw.config.yaml   ← primary (ถ้ามี)
        ↓
providers.yaml          ← supplement: provider base_url, model list, profiles (ถ้า key ไม่มีใน central)
        ↓
llm.json                ← API keys เท่านั้น
        ↓
hardcoded               ← fallback สุดท้าย (ค่า default ใน code)
```

**หลักการ:**
- `provider`, `model`, `discovery_model`, `temperature`, `max_tokens`, `timeout_sec` → อ่านจาก central เป็นอันดับแรก
- `profiles`, provider `base_url`, `model list` → ยังคงอยู่ใน `providers.yaml` (ไม่ต้องย้ายเข้า central เพราะไม่ค่อยเปลี่ยน)
- `api_key` → `llm.json` เท่านั้น (ไม่เอา secret เข้า version control)
- ทั้งหมด `↓` fallback ไป hardcoded เผื่อไฟล์หาย

### 2.3 ส่วนที่จะมีผล

| Component | ปัจจุบัน | เปลี่ยนแปลง |
|:----------|:---------|:------------|
| **`novelclaw.config.yaml`** | ❌ ไม่มี | ✅ สร้างใหม่ |
| **`providers.yaml`** | มี `active`, `default_model`, `discovery_model` | ❌ ลบ 3 keys นี้ออกจาก YAML (ย้ายไป central) |
| **`llm.json`** | มี `default_model`, `default_provider` + API keys | ❌ ลบ `default_model`, `default_provider` (keep เฉพาะ keys) |
| **`pipeline_llm.py:14-39`** (`get_active_config`) | อ่านจาก `config_providers()` + hardcoded fallback | ✅ เปลี่ยนให้อ่าน `novelclaw.config.yaml` ก่อน, fallback ไป YAML → hardcoded |
| **`pipeline.py:291-294`** | ฮาร์ดโค้ด fallback model, provider | ✅ เปลี่ยนเป็นอ่านจาก `get_active_config()` ล้วนๆ (ไม่มี fallback ซ้ำ) |
| **`llm_router/config_providers.py`** | `save_provider_config()` | ✅ ปรับ `save` ให้เขียนไป `novelclaw.config.yaml` |
| **`novelclaw.py CLI`** | `--model`, `--provider`, `--profile` | ✅ ค่า default ของ argparse อ่านจาก `novelclaw.config.yaml` |

---

## 3. Migration path (ปลอดภัย ไม่พัง batch ที่ค้าง)

1. สร้าง `novelclaw.config.yaml` — copy ค่าจาก `providers.yaml` + `llm.json`
2. แกะ `active`, `default_model`, `discovery_model` ออกจาก `providers.yaml`
3. แกะ `default_model`, `default_provider` ออกจาก `llm.json`
4. แก้ `pipeline_llm.py::get_active_config()` — ให้อ่าน `novelclaw.config.yaml` ก่อน
5. แก้ `pipeline.py` — เอาฮาร์ดโค้ด fallback model/provider ออก
6. แก้ `novelclaw.py` — CLI defaults อ่านจาก config
7. ทดสอบกับ 1-2 บทก่อน rollout

**Backward compatibility:** ถ้า `novelclaw.config.yaml` ไม่มี → fallback ไปอ่าน `providers.yaml` แบบเดิม → pipeline ทำงานเหมือนเดิมทุกประการ
