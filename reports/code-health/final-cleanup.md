# Final Cleanup — Code Health Summary

**Date**: 2026-06-24
**Scope**: Backend cleanliness pass after Q1-Q4 + final stabilization

## Removed / Cleaned

| File / Artifact | Action | Reason |
|:----------------|:-------|:-------|
| `reader/public/js/pages/reader.js` 40+ lines inline render | Extracted to `reader-renderer.js` | Render logic belongs in dedicated module |
| `reader/lib/render.js` production import | Replaced by `test-renderer.js` | Test-only; production uses frontend renderer |
| `tools/progress.py` (active use) | DEPRECATED label | Legacy — translate.py still imports it as subprocess dependency |
| `tools/novelctl.py` generator `return (job, stop)` | Refactored to `ChapterPipelineResult` | Python generator return values are invisible to for-loop |
| Inline styles in `app.js` rightbar stats/activity | Moved to `.c-mini-stat*` CSS classes | Consistency, maintainability |
| `BASE_FONT` unused const in `reader.js` | Removed | Unused variable |
| `.chprogress/test-*.json` | Deleted | Test artifacts |
| `jobs/` old job files committed | Runtime ignores added | Should never have been in repo |

## Files Added

| File | Purpose |
|:-----|:--------|
| `reader/public/js/reader-renderer.js` | Dedicated chapter render module |
| `tools/orchestrator/policy.py` | Quality thresholds config (no magic numbers) |
| `tools/orchestrator/subprocess_runner.py` | Structured subprocess wrapper with `CommandResult` |
| `tools/schema/search-index.schema.json` | Schema for search index validation |
| `reports/perf/reader-render.md` | Render performance notes |
| `reports/model-bench/openrouter-language.md` | Model comparison reference |
| `reports/api/route-health.md` | API endpoint status |
| `reports/README.md` | Report structure guide |

## Kept Legacy (with reasons)

| Item | Why kept |
|:-----|:---------|
| `tools/progress.py` | `translate.py` standalone mode imports it; will remove when novelctl fully replaces translate.py CLI |
| `reader/lib/test-renderer.js` | 2 Node test files import it; still valuable for test coverage |
| `reader/lib/render.js` | Copied to test-renderer.js; original kept for reference until tests verified |

## Remaining Known Debt

| Item | Severity | Notes |
|:-----|:---------|:------|
| progress.py ↔ translate.py coupling | Medium | novelctl path doesn't use it, but translate.py standalone does |
| activity-feed polling still runs on home (30s) | Low | Designed — home needs fresh stats |
| Search index can grow to ~12MB at 1,239 chapters | Low | Schema caps text at 15K chars per entry |
| CSS still has ~20 inline style usages in JS | Low | Mostly skeleton widths, SVG layout — cosmetic |
| No virtual rendering for 500+ paragraph chapters | Low | Not needed yet; perf metrics measure < 50ms render |

## Commands Tested

```
python tools/check_all.py               → 47/47 ✅
python tools/validate_data.py --all     → ✅
python tools/novelctl.py status         → ✅
python tools/novelctl.py report         → ✅
python tools/novelctl.py check          → ✅
python tools/novelctl.py backup         → ✅ (integrity check)
python tools/tests/test_novelctl.py     → 12/12 ✅
node reader/tests/test-api.js           → 10/10 ✅
node --test reader/tests/*.test.js      → ✅
```
