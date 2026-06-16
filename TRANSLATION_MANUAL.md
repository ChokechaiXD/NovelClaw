# NovelClaw — Translation Manual
=================================

> Human reference for maintaining the NovelClaw translation system.
> For the AI translation rules, see `PROMPT.md`.

## System Overview

```
Source (CN) → AI Translation (TH) → Validation → Save → Commit
                      ↑
              PROMPT.md (AI rules)
              style.md (per-novel)
              glossary/ (terms)
```

## File Structure

```
NovelClaw/
├── PROMPT.md              ← AI system prompt (S0-S9) — send to AI before translating
├── TRANSLATION_MANUAL.md  ← This file — human reference
├── TRANSLATION_GUIDE.md   — Quick workflow guide
├── docs/
│   └── THAI_NATURALNESS.md — Deep Thai writing guide
├── tools/                  — Validation, glossary, format tools
│   ├── validate_chapter.py
│   ├── save_chapter.py
│   ├── glossary_doctor.py
│   ├── build_yaml.py
│   └── ...
└── novels/
    └── <slug>/
        ├── style.md           — Per-novel style choices (locked terms, brackets, pitfalls)
        ├── format_spec.md     — File format spec (v2 JSON schema)
        ├── glossary/
        │   ├── locked.md       — P1: Never deviate
        │   ├── reference.md    — P2: Use consistently
        │   ├── auto.md         — P3: Suggestion only
        │   └── glossary.yml    — Auto-generated (build_yaml.py)
        └── chapters/
            └── NNNN.json      — Translated chapters (schema v2)
```

## Translation Workflow

### Per Chapter

```bash
# 1. Get context
python tools/translate_ch.py <N> --context --search

# 2. AI translates (Mika follows PROMPT.md + style.md + glossary)

# 3. Save + validate
python tools/save_chapter.py <N>
python tools/validate_chapter.py <N>

# 4. Commit
git add novels/<slug>/chapters/NNNN.json
git commit -m "translate ch <N>"
```

### Batch (multiple chapters)

```bash
# Context for range
python tools/translate_ch.py <start> <end> --context

# Validate all
python tools/validate_chapter.py <start> <end>
```

## Glossary Maintenance

### Adding a new term

1. Check which tier it belongs to:
   - **Locked (P1)**: Main cast, key locations, core game terms → `glossary/locked.md`
   - **Reference (P2)**: Recurring NPCs, common skills/items → `glossary/reference.md`
   - **Auto (P3)**: One-off terms → `glossary/auto.md`

2. Add row to the appropriate .md file

3. Rebuild:
   ```bash
   python tools/build_yaml.py
   ```

### Priority Resolution

`locked.md` > `reference.md` > `auto.md` > `style.md`

## Validation

```bash
# Single chapter
python tools/validate_chapter.py <N>

# Range
python tools/validate_chapter.py <start> <end>

# With glossary doctor
python tools/glossary_doctor.py --ch <N>
```

### Validation Checks

| Check | Severity | Blocks Save |
|-------|----------|-------------|
| CJK chars in body | ERROR | ✅ |
| Missing paragraphs | ERROR | ✅ |
| Length ratio < 60% | ERROR | ✅ |
| Locked term violation | ERROR | ✅ |
| Length ratio > 250% | WARNING | ❌ |
| New CN terms not in glossary | INFO | ❌ |

## Tools Reference

| Tool | Purpose |
|------|---------|
| `translate_ch.py N --context` | Get context (glossary, style, FTS) |
| `save_chapter.py N` | Validate + save chapter JSON |
| `validate_chapter.py N` | Validate chapter |
| `glossary_doctor.py --ch N` | Check chapter for issues |
| `build_yaml.py` | Rebuild glossary.yml from .md |
| `reformat_chapter.py N` | Reformat chapter to v2 spec |

## Chapter File Format (v2)

```json
{
  "schema_version": 2,
  "num": 113,
  "title": "ตอนที่ 113 ...",
  "lang": "cn",
  "blocks": [
    {"type": "narration", "text": "..."},
    {"type": "dialogue", "text": "「...」", "speaker": "เฉาซิง"},
    {"type": "system", "text": "【...】"},
    {"type": "game_title", "text": "《...》"},
    {"type": "end", "text": "(จบบท)"}
  ],
  "source": "ch 113",
  "notes": []
}
```

### Bracket Conventions

| Use | Bracket | Forbidden |
|-----|---------|-----------|
| Dialogue | `「…」` | `"…"` straight |
| System | `【…】` | `[…]` |
| Game title | `《…》` | `<…>` |

## Adding a New Novel

1. Create `novels/<slug>/` directory
2. Copy `style.md` and `format_spec.md` from existing novel, customize
3. Create `glossary/` with locked.md, reference.md, auto.md
4. Add source chapters to `chapters/source/`
5. Run `python tools/build_yaml.py` to generate glossary.yml

## Design Principles

1. **Transmittor, not editor** — AI transmits author's voice, doesn't "improve"
2. **Completeness is non-negotiable** — every word translated, no gaps
3. **Zero CJK leakage** — body text is pure Thai
4. **Glossary is law** — locked terms never deviate
5. **Validate before commit** — tools catch errors AI misses

## Maintenance Notes

- When PROMPT.md changes, all novels benefit (it's the universal rule set)
- When style.md changes, only that novel is affected
- glossary.yml is auto-generated — edit .md files, then run build_yaml.py
- Run `validate_chapter.py` on existing chapters after major rule changes

---

**Last updated:** 2026-06-15
