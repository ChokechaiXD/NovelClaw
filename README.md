# NovelClaw 🦀

> Translation workspace for web novels (CN → TH).
> Mika translates in chat; this repo is the persistent context
> (glossary, style, chapters) that keeps quality consistent across sessions.

## Principles

- **Transmittor, not editor** — transmit author's voice, don't "improve"
- **Completeness is law** — every word translated, zero gaps
- **Zero CJK leakage** — body text is pure Thai
- **Glossary is absolute** — locked terms never deviate
- **Validate before save** — tools catch errors AI misses

## Project Layout

```
NovelClaw/
├── PROMPT.md                  ← AI system prompt (S0-9) — Mika's prime directive
├── TRANSLATION_MANUAL.md       ← Human reference (workflow, tools, maintenance)
├── docs/
│   └── THAI_NATURALNESS.md     ← Deep Thai writing guide
├── tools/                      ← Validation + glossary scripts
│   ├── validate_chapter.py     ← Chapter validation
│   ├── save_chapter.py         ← Save + schema check
│   ├── glossary_doctor.py      ← Translation quality analysis
│   ├── translate_ch.py         ← Context loader
│   ├── build_yaml.py           ← Rebuild glossary.yml from .md
│   └── ...
└── novels/
    └── <slug>/
        ├── style.md            ← Per-novel style choices
        ├── format_spec.md      ← File format spec (v2 JSON)
        ├── glossary/
        │   ├── locked.md       ← P1: Never deviate
        │   ├── reference.md    ← P2: Use consistently
        │   ├── auto.md         ← P3: Suggestion only
        │   └── glossary.yml    ← Auto-generated (build_yaml.py)
        └── chapters/
            └── NNNN.json       ← Translated chapters (schema v2)
```

## Translation Session

1. Load `PROMPT.md` (AI rules) + `style.md` (novel-specific) + `glossary/` (terms)
2. Read source text
3. Translate per S1-S9 rules (transmittor principle, completeness, zero CJK)
4. Self-review (S5 gate)
5. Save as `chapters/NNNN.json`
6. Run `python tools/validate_chapter.py N`
7. Commit

## Glossary

| File | Priority | Rule |
|------|----------|------|
| `locked.md` | P1 | Never deviate |
| `reference.md` | P2 | Use consistently |
| `auto.md` | P3 | Suggestion only |

Rebuild after edits: `python tools/build_yaml.py`

## Active Novel

`global-descent` — 全球降臨：帶著嫂嫂末世種田 by 一条小白蛇

---
See `TRANSLATION_MANUAL.md` for detailed workflow, tools reference, and maintenance guide.
