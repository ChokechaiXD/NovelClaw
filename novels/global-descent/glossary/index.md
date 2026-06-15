# Glossary Index — 全球降臨：帶著嫂嫂末世種田

> Master view of the glossary system. For the AI translation rules, see
> `PROMPT.md`. For workflow docs, see `TRANSLATION_MANUAL.md`.

## How the glossary works

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  .md files      │  build  │   glossary.yml   │  query  │  AI translation │
│  (human edit)   │ ──────► │   (YAML)         │ ──────► │  validation     │
│  locked/ref/auto│         │  + glossary.db   │         │  glossary_doctor│
└─────────────────┘         └──────────────────┘         └─────────────────┘
```

**Single source of truth:** the 3 `.md` files. Edit them, run
`python tools/build_yaml.py` to regenerate `glossary.yml`.

**Priority:** locked (P1) > reference (P2) > auto (P3) > style.md

## Files

| File | Priority | Role | Edit by hand? |
|------|----------|------|---------------|
| `locked.md` | P1 | Main cast, core terms, style-mandated | YES (rarely) |
| `reference.md` | P2 | Recurring NPCs, items, skills | YES (occasionally) |
| `auto.md` | P3 | One-off terms | YES (append-only) |
| `glossary.yml` | — | Auto-built from above | NEVER — auto-generated |
| `glossary.db` | — | SQLite cache (rebuild via build_glossary.py) | NEVER |
| `index.md` | — | This file (overview) | YES (occasionally) |

## Adding a new term

1. Decide tier (locked / reference / auto)
2. Add to corresponding `.md` file in table format:
   ```
   | Source | Thai | Category | Priority | Notes |
   | 蕾妮丝·鹰眼 | เลนนิส ฮอว์อาย | ตัวละคร | 1 | elite archer |
   ```
3. Run `python tools/build_yaml.py`

## Common commands

```bash
# After editing .md files — rebuild glossary.yml
python tools/build_yaml.py

# Validate a chapter
python tools/validate_chapter.py <N>

# Run glossary doctor on a chapter
python tools/glossary_doctor.py --ch <N>

# Show glossary stats
python tools/glossary_stats.py
```

## Guard rails

| Severity | When | Action |
|----------|------|--------|
| ERROR | Forbidden pattern (ฮ่องกง, CN leakage) | BLOCKS save |
| WARNING | Anti-pattern, title mismatch, length ratio | Saves with warning |
| INFO | New CN term, no explanation | Logged for later |

## Auto-detected slop (informational)

Top banned phrases (auto-learned from translations):
อย่างไรก็ตาม, ดังนั้น, แม้ว่า, เต็มไปด้วยความ, ชาวอาณานิคม, etc.

These are tracked in `style_rules.yml` with `rule_type='anti_pattern'`.
Doctor flags any appearance in translated text.

## Stats

- Locked: 59 terms (P1 — never deviate)
- Reference: 50 terms (P2 — use consistently)
- Auto: 389 terms (P3 — suggestion only)
- Total: 497 unique terms
