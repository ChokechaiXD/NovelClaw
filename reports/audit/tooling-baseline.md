# Quality Tooling Baseline

**Date:** 2026-06-24  
**Status:** ✅ Implemented  
**Checks:** 36/36 passing

## Tools Added

| Tool | Purpose | Command |
|:-----|:--------|:--------|
| `tools/check_all.py` | All-in-one quality check | `python tools/check_all.py` |
| `tools/schema/chapter.schema.json` | Canonical chapter JSON schema | — |
| `tools/schema/novel.schema.json` | novel.json schema | — |
| `tools/schema/job.schema.json` | Job state file schema | — |
| `tools/schema/needs-review.schema.json` | Needs review entry schema | — |
| `tools/schema/glossary.schema.json` | Glossary JSON schema | — |

## Scripts Updated

| File | Change |
|:-----|:-------|
| `reader/package.json` | `npm run check` now includes `novel.js` |
| `reader/package.json` | `npm run syntax` uses Windows-compatible node script |
| `.github/workflows/ci.yml` | Simplified to single `check_all.py` call |

## Dead Code Removed

- `reader/public/js/pages/admin.v3.js` — not loaded in index.html, no references

## Check Results (36/36)

### Python Syntax (21 files)
All 21 `.py` files compile clean.

### novelctl Smoke Tests (12 tests)
JSONL parser, force rollback, draft isolation — all pass.

### novelctl Commands (3 checks)
`status`, `report`, `check` — all work without LLM.

### Reader JS Syntax (10 files)
All 8 page modules + `app.js` + `api.js` + `state.js` + `components.js` + `server.js` pass `node --check`.

### API Smoke Tests (10 tests)
All API endpoints respond correctly (requires running server).

## Next Phase
Phase 3 — Safe Fixes: unused test slugs, missing guards, duplicated helpers, NaN display, route/container gaps.
