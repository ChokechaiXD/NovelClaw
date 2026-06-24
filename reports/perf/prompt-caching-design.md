# Prompt Caching Design — NovelClaw

## หลักการ

Prefix caching / KV caching ทำงานโดย reuse computation ของ prompt prefix ที่เหมือนกันระหว่าง request.  
สำหรับ chapter-based translation, prompt ส่วนใหญ่ (task, style, rules, glossary) **ไม่เปลี่ยน**ตลอดทั้ง novel.

## ปัจจุบัน (v3)

```
[task] [glossary (filtered per-chapter)] [style] [rules] [continuity] [source] [output]
                     ^^^ break cache every chapter
```

ปัญหา: glossary ถูก filter per-chapter → break prefix cache  
ปัญหา: continuity ถูก append ซ้ำหลัง source → break cache อีก

## v4 — Cache-friendly layout

```
[STATIC — ~84% ของ prompt, cacheable ตลอดทั้ง novel]
├── task definition
├── style rules
├── format rules
└── FULL glossary (ไม่ filter per-chapter)

[SEMI-DYNAMIC — ~5%]
└── TM context (character names + key terms)

[DYNAMIC — ~11%]
└── source text + <now_translate>
```

## วิธีใช้

```python
from translate import build_translate_prompt_v4

prompt = build_translate_prompt_v4(
    ch_num=77,
    source_text=source_text,
    slug="global-descent",
)
```

## ข้อดี

| มิติ | v3 (old) | v4 (cache-optimized) |
|:-----|:---------|:---------------------|
| Cacheable % | ~30% (glossary filter break) | ~84% |
| Glossary scope | per-chapter filtered (เปลี่ยนทุกครั้ง) | full novel (คงที่) |
| Continuity position | หลัง source (break cache) | ก่อน source (continue cache) |
| TM context | continuity (แค่ 3 บทล่าสุด) | format_tm_prompt() (characters + terms) |

## ข้อจำกัด

- ใช้ได้ดีที่สุดกับ provider ที่มี prefix caching (OpenRouter, Anthropic, vLLM)
- กับ provider ที่ไม่มี (openmodel.ai ธรรมดา) — ไม่ได้แย่ลง แค่ไม่เร็วขึ้น
- Glossary แบบ full novel (~100 terms) ดีกว่า per-chapter filtered (~20 terms) เพราะ LLM เห็น scope กว้างกว่า
