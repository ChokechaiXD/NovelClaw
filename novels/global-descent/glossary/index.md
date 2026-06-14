# Glossary Index — 全球降臨：帶著嫂嫂末世種田

> Master view of the glossary. Translation work uses `glossary.db`
> (queryable SQLite, auto-built from these .md files). For P'Chok's
> reading: this file is the human-friendly map of how the system works.

## How the glossary works (v2)

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  .md files      │  build  │   glossary.db    │  query  │  pre_chapter    │
│  (human edit)   │ ──────► │   (SQLite)       │ ──────► │  glossary_doctor│
│  locked/ref/auto│         │  + explanations  │         │  save_chapter   │
└─────────────────┘         └──────────────────┘         └─────────────────┘
```

**Single source of truth:** the 3 .md files. Edit them, run
`python novelclaw.py glossary build --apply --rescore` to refresh the DB.

**Auto-everything:**
- `glossary.db` rebuilds from .md (no manual SQL)
- `glossary_doctor.py` runs after each save to catch issues
- `pre_chapter.py` reads DB to inject explanations into next-ch context
- `save_chapter.py` blocks save if errors found

## Files

| File | Role | Edit by hand? |
|------|------|---------------|
| `locked.md` | Mandated terms (main cast, style.md) | YES (rarely) |
| `reference.md` | Recurring NPCs/items/skills | YES (occasionally) |
| `auto.md` | One-off terms | YES (append-only) |
| `glossary.db` | Built from above (auto) | NEVER — auto-rebuilt |
| `index.md` | This file (workflow docs) | YES (occasionally) |

## On disagreement (priority order)

1. `style.md` — wins for any in-world term (it's the user's stated choice)
2. `locked.md` — wins for main cast / core mechanics
3. `reference.md` — wins for recurring names
4. `auto.md` — wins for first encounter; promote if used 3+ times
5. `glossary.db` — built from above, never source of truth

## Common commands

```bash
# After editing .md files — refresh the DB
python novelclaw.py glossary build --apply --rescore

# Run doctor on all ch (after batch translation)
python novelclaw.py glossary doctor --all

# Run doctor on single ch
python novelclaw.py glossary doctor --ch 50

# Show full glossary state
python novelclaw.py glossary report

# Validate ch before commit (BLOCKS on errors)
python novelclaw.py glossary save 50

# Show fix hints for a ch
python novelclaw.py glossary doctor --fix-hints 50

# Get next ch context (includes glossary explanations)
python novelclaw.py prep
```

## Schema (glossary.db v2)

| Table | Purpose |
|-------|---------|
| `terms` | Each source→thai mapping + explanation + examples |
| `aliases` | TC/nickname/old_glossary variants |
| `usage` | term_id + ch_num + thai_count (auto-tracked) |
| `inconsistencies` | same source → multiple Thai (forced resolution) |
| `style_rules` | anti-pattern / forbidden / preferred with examples |
| `compounds` | parent/child term relations (e.g., 极地人 + 小屋) |
| `doctor_log` | validation findings per ch |
| `ch_meta` | per-ch translation state + validation status |
| `glossary_changelog` | every change logged (audit trail) |
| `v_conflicts` | view: terms with multiple Thai versions |

## Adding a new term

1. Decide tier (locked / reference / auto)
2. Add to corresponding .md file in table format:
   ```
   | source_cn | thai | category | priority | notes |
   | 蕾妮丝·鹰眼 | เลนนิส ฮอว์อาย | ตัวละคร | 3 | hunter nickname |
   ```
3. Run `python novelclaw.py glossary build --apply`

## Resolving an inconsistency (force decision)

When `glossary_doctor --inconsistencies` shows 力量 → [กำลัง, พลัง]:

1. Decide the canonical Thai (look at ch usage, style.md guidance)
2. Edit `tools/build_glossary.py` → add to `CONFLICT_RESOLUTIONS`:
   ```python
   CONFLICT_RESOLUTIONS = {
       '力量': 'พลัง',  # 力量 = "power" (stat)
   }
   ```
3. Run `python novelclaw.py glossary build --apply`
4. Re-scan ch: the non-canonical Thai gets auto-archived

## Guard rails (P'Chok's mandate: don't break)

| Severity | When | Action |
|----------|------|--------|
| ERROR | Forbidden pattern (ฮ่องกง, CN leakage) | BLOCKS save |
| WARNING | Anti-pattern, title mismatch, length ratio | Saves with warning |
| INFO | New CN term, no explanation | Logged for later |

Run `python novelclaw.py glossary save N --strict` to also block on warnings.

## Auto-detected slop (informational)

Top banned phrases (auto-learned from translations):
- อย่างไรก็ตาม, ดังนั้น, แม้ว่า, เต็มไปด้วยความ, ชาวอาณานิคม, etc.

These are tracked in `style_rules` table with `rule_type='anti_pattern'`
and `source='learn_slop'`. Doctor flags any appearance in translated text.
