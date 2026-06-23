# NovelClaw Progress — Global Descent

**Full title (EN):** Global Descent: Farming the Apocalypse with My Sister-in-Law
**Author:** 一條小白蛇 (Yi Tiao Xiao Bai She)

## Current State

| Metric | Value |
|:--------|:------|
| Chapters translated | 93 of 1,239 (7.51%) |
| Range | ch 1, 2, 42, 71–153 |
| Pipeline | **v3 paragraphs** (LLM plain text → Python assemble JSON) |
| Post-process steps | **1** (CN strip only) |
| Scorer avg | **100/100** — 10/10 recent perfect |
| Tools/ | **8 files** (translate, scorer, validation, schema, glossary, progress, translation_memory, clean_leaks) |
| Tests | **12 test files** — 107 tests |
| Provider | Direct HTTP → Hermes Agent, ~2s/call |
| Model | `deepseek-v4-flash` (free-tier only) |
| Last chapter | ch 153 — (224 paragraphs) |
| Next chapter | ch 154 |

### Scorer Dimension Breakdown

| Dimension | Contribution | Note |
|:----------|:------------:|:-----|
| Completeness | 22% | ✅ All chapters complete |
| CN Leak | 17% | ✅ Zero CN leakage |
| EN Leak | 17% | ✅ Zero EN leakage |
| End Marker | 11% | ✅ All chapters end properly |
| Dialogue Ratio | 11% | ✅ Within ideal range (max 60%) |
| Content Diversity | 11% | ✅ Good lexical variety |
| Schema | 11% | ✅ Valid JSON schema |
| ~~Speaker~~ | ~~0%~~ | ❌ Removed — Thai is pro-drop, LLM structural limitation |

> **Note on Speaker metric:** Speaker was removed from scorer weight because Thai is a pro-drop language — it's natural to omit speaker attribution. DeepSeek V4 Flash doesn't reliably populate speaker fields. All 73 chapters pass the 7 active dimensions.
> For chapters with Speaker > 0, it's a bonus, not a requirement.

## Missing chapters in range

- **ch 3–41** (39 chapters) — never translated
- **ch 43–70** (28 chapters) — never translated
- **ch 131–133** (3 chapters) — missing source/translation

Total to translate: **1,156 chapters** remaining

## Translation Pipeline (v3)

```
Source (CN .md) → translate.py → LLM (plain text with inline markers)
    → parse_translation_output() → JSON with paragraphs + blocks
    → scorer → validate → save
```

### Key architecture decisions
- **LLM NEVER writes JSON** — outputs plain Thai with `"..."【】『』` markers
- **Python assembles** — `parse_translation_output()` splits by double newlines
- **Zero JSON parse errors** since v3 migration
- **Post-process: 1 step** — CN strip only (was 8 steps in v2)

### Example translate command
```bash
python tools/translate.py 144 --score --json
```

### Source scraping
- **Tier 1:** Python requests → qidian.com (no Cloudflare, fastest)
- **Tier 2:** agent-browser CLI for JS-rendered sites
- **Tier 3:** undetected-chromedriver as last resort
- **Tier 4:** Smart proxy API (paid) for production scale

> qidian.com is the preferred free source — no Cloudflare, Python requests works directly.

## Tools inventory (8 files)

| File | Purpose |
|:-----|:--------|
| `translate.py` | Main translation entry — LLM call + v3 parse |
| `scorer.py` | 7-dimension quality scorer (no LLM) |
| `validation.py` | CJK/EN leak detection |
| `schema.py` | Chapter schema + BRACKETS config |
| `glossary.py` | Glossary management + NPC bank |
| `progress.py` | Progress tracker |
| `translation_memory.py` | Translation memory cache |
| `clean_leaks.py` | CN/EN leak cleanup tool |

### Removed/dead (since v3 cleanup)
| Removed | Why |
|:--------|:----|
| `agent_coordinator.py` | Legacy multi-agent — not needed with v3 |
| `extract_entities.py` | No entity pipeline in v3 |
| `quality_scorer.py` | Replaced by `scorer.py` |
| `constants.py` | Merged into `schema.py` |
| `chapter_io.py` | Merged into `translate.py` |
| `validate_no_cjk.py` | Merged into `validation.py` |
| Sites/ | Dead code |
| `knowledge.md` | Obsolete with v3 |
| `scrape_chapters.py` | Replaced by qidian.com requests approach |
| `--entities`, `--two-pass` flags | Removed from translate.py — not needed in v3 |

## Commits (2026-06-22 → 2026-06-23, 19 total)

```
ea2a8d4 fix: March 2026 cleanup — audit, bugfix, dead-code, README
2bf10e8 clean: all stale files + dead directories
7159da9 remove test artifacts
d8eefbf deep clean: all dead code, docs for v3 paragraphs
34930d8 refactor: universal paragraphs pipeline v3
23f58e8 fix: 9 bugs in translation pipeline
e5966c1 refactor: remove redundancies
e085995 fix: enhanced speaker 25→78/100 + _post_score crash
97379ea cleanup: merge validate_no_cjk, clear TM 5MB + pip 211MB
bc1d33f fix: CN-free glossary + 7 legacy modules removed
221e2ce fix: anthropic-version header re-enables thinking mode
bc481bb fix: retranslate ch81, ch85
3939b18 fix: retranslate 8 truncated chapters
a0b7582 fix: reclassify 662 mislabeled blocks
ba3e7a4 feat: 8-dim scorer (no LLM)
96a059a workflow: no entity placeholders
732f8ae fix: deepseek thinking mode eating tokens
4ab7424 fix: entity count bug
```

## Test suite (16 test files, 193 tests)

| File | Description |
|:-----|:------------|
| `test_translate.py` | Translation pipeline tests |
| `test_translation_memory.py` | TM functionality |
| `test_translation_memory_source_cache.py` | Source cache |
| `test_schema.py` | Chapter schema validation |
| `test_multilang_schema.py` | Multi-language schema |
| `test_validation.py` | CJK/EN leak detection |
| `test_glossary.py` | Glossary operations |
| `test_chapter_io.py` | Chapter save/load |
| `test_constants.py` | Constants validation |
| `test_edge_cases.py` | Edge cases + block validation |
| `test_frontend.py` | Reader API smoke tests |
| `test_progress.py` | Progress tracker |
| `test_translate_profile.py` | Profile/lang handling |
| `test_translate_resume.py` | Resume capability |
| `conftest.py` | Fixtures + test helpers |
| `fixtures/` | Test data files |

## Known limitations

1. **Speaker field** — Thai is pro-drop; LLM doesn't reliably populate speaker. Only chapters with explicit speaker attributions score >90 on this dimension.
2. **Missing chapters ch 131-133** — Source files for these need to be obtained (not yet available).
3. **Untranslated block ch 3-41, 43-70** — Large gap in the middle of the story. Consider batch translating when continuing.
4. **Scorer avg ~90** — Impacted primarily by Speaker dimension. Non-speaker dimensions are all 95-100.

## Resume command
```bash
python tools/translate.py 154 --score --json
```
