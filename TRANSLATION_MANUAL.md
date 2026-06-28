# NovelClaw — Translation Manual

> Human reference for maintaining the NovelClaw translation system.

**Last updated:** 2026-06-22 (v3 paragraphs pipeline)

---

## System Overview

```
Source (CN/Multi) → AI Translation (TH) → Python assemble paragraphs → Validate → Save → Commit
                            ↑
                    glossary/ (terms)
                    style rules
                    brackets.json (markers config)
```

## File Structure

```
NovelClaw/
├── tools/                   — Translation & validation toolkit
│   ├── translate.py         — Main pipeline: read → LLM → parse → validate → save
│   ├── schema.py            — Pydantic Chapter schema (v3 with paragraphs)
│   ├── validation.py        — Quality gate: CJK/EN/artifact leak checks
│   ├── scorer.py            — 8-dimension objective quality scorer
│   ├── glossary.py          — Glossary loading & term management
│   ├── progress.py          — Batch progress tracking
│   ├── translation_memory.py— Block-level translation cache
│   └── providers/
│       ├── __init__.py
│       └── api.py           — LLM HTTP provider (direct HTTP)
├── reader/                  — Express.js web reader
│   └── lib/
│       ├── render.js        — renderChapterJson() + renderParagraphs()
│       └── brackets.js      — Language bracket config loader
└── novels/
    └── <slug>/
        ├── glossary/
        │   ├── locked.md    — P1: Never deviate
        │   ├── reference.md — P2: Use consistently
        │   ├── auto.md      — P3: Suggestion only
        │   └── glossary.yml — Auto-generated (build_yaml.py)
        └── chapters/
            ├── NNNN.json    — Translated chapters (schema v3)
            └── source/
                └── NNNN.md  — Raw source chapters
```

## Translation Pipeline (v3)

### One chapter

```bash
python tools/translate.py <N> --score --json
```

### Batch

```bash
python tools/translate.py <start>-<end> --score --json --concurrent 3
```

### What happens

| Step | What | Who |
|:----|:-----|:----|
| 1 | Read & clean source | Python |
| 2 | Build prompt (glossary + style + continuity) | Python |
| 3 | LLM translates → outputs plain Thai text with inline markers | LLM |
| 4 | `parse_translation_output()` → split paragraphs | Python |
| 5 | CN strip & append `(จบบท)` end marker | Python |
| 6 | Pydantic schema validation | Python |
| 7 | Quality gate (CJK/EN/artifact leak checks) | Python |
| 8 | Save `NNNN.json` | Python |

### Post-processing steps: from 8 → **1** ✅

Post-process no longer handles: block type fixing, JSON repair, dialogue reclassification, speaker extraction, bracket wrapping, EN guard, empty block removal — all obsolete.

## Chapter File Format (v3 — current)

```json
{
  "schema_version": 3,
  "num": 142,
  "title": "ตอนที่ 142 การเติบโตของวอลลี่แบร์",
  "lang": "cn",
  "output_lang": "th",
  "paragraphs": [
    "ข้อความแจ้งเตือนระบบสองบรรทัด ทำให้ใบหน้าของเฉาซิงมีสีหน้าดีใจ",
    "\"ท่านลอร์ดที่รัก เสด็จมาแล้วหรือเจ้าคะ\"",
    "【วิญญาณระดับหัวกะทิของสัตว์ประหลาดเพาะพันธุ์วิญญาณ】",
    "(จบบท)"
  ],
  "source": "ch 142"
}
```

### Inline Markers (universal — all languages, all genres)

| Marker | Meaning | CSS class |
|:-------|:--------|:----------|
| `"..."` | Dialogue (straight quotes) | `.c-marker--dialogue` |
| `「...」` | Dialogue (CJK brackets) | `.c-marker--dialogue` |
| `"…"` (curly) | Dialogue | `.c-marker--dialogue` |
| `【...】` | System notification | `.c-marker--system` |
| `『...』` | Inner thought (JP/CN) | `.c-marker--thought` |
| `(จบบท)` | End marker | `.c-marker--end` |

No block types needed — markers in text drive the styling via regex.

## Quality

### Quality gate (pre-save)

```bash
python tools/translate.py 130 --score --json
```

Validates: CJK leak, EN leak, source artifact leak, length ratio.

### Post-translation quality scorer

```bash
python tools/scorer.py chapters/ --source source/
```

8 dimensions: completeness, CN leak, EN leak, end marker, dialogue ratio, block diversity, schema. Returns 0-100 weighted score.

## Glossary Maintenance

### Adding a new term

1. Check which tier it belongs to:
   - **Locked (P1)**: Main cast, key locations, core game terms → `glossary/locked.md`
   - **Reference (P2)**: Recurring NPCs, common skills/items → `glossary/reference.md`
   - **Auto (P3)**: One-off terms → `glossary/auto.md`

2. Add row to the appropriate `.md` file (format: `| CN | TH | notes |`)

3. No need to rebuild — `translate.py` loads directly from `.md` files.

### Priority Resolution

`locked.md` > `reference.md` > `auto.md`

## Adding a New Novel

1. Create `novels/<slug>/` directory
2. Add source chapters to `chapters/source/` as `NNNN.md`
3. Create `glossary/` with `locked.md`, `reference.md`, `auto.md`
4. Add to `novels/<slug>/meta.md` for reader discovery

## Design Principles

1. **Transmittor, not editor** — AI transmits author's voice, doesn't "improve"
2. **Completeness is non-negotiable** — every word translated, no gaps
3. **Zero CJK leakage** — body text is pure Thai
4. **Glossary is law** — locked terms never deviate
5. **Validate before commit** — tools catch errors AI misses
6. **Python does structure, LLM does translation** — never ask LLM to output JSON
