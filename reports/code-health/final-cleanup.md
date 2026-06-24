# Final Cleanup Report — NovelClaw Backend

**Date**: 2026-06-24
**What**: Post-refactor cleanup pass — close all remaining P0/P1/P2 items

---

## Removed / Cleaned

| File / Dir | Action | Reason |
|:-----------|:-------|:-------|
| `reader/public/js/pages/reader.js` `BASE_FONT` | Removed | Declared but unused — `18` used directly |
| `.chprogress/test-*.json` | Deleted | Test artifacts from progress.py tests |
| `reader/lib/render.js` | Renamed → `test-renderer.js` | Test-only support, not production import |
| `jobs/done/translate-20260623-*.json` | Removed from git | Old completed jobs — runtime state |
| `logs/`, `staging/drafts/`, `jobs/` | Added to `.gitignore` | Runtime state, not source code |

## Kept (with deprecation note)

| File | Why kept | Plan |
|:-----|:---------|:-----|
| `tools/progress.py` | translate.py imports it in standalone mode | Remove when translate.py drops .chprogress support |
| `reader/lib/test-renderer.js` | 2 test files import it | Keep as test-support; rename header done |
| `tools/orchestrator/subprocess_runner.py` | Integrated into runner.py now | ✅ In use — keep |

## Fixed (P0)

| Bug | Fix | Commit |
|:----|:----|:-------|
| `process_chapter()` generator return lost | → `ChapterPipelineResult` dataclass | `a63edff` |
| `handle_validation_failure()` missing `policy` | → receives `policy` object | `a63edff` |
| `policy["repair_score"]` referenced undefined var | Passed through from process_chapter | `a63edff` |
| jsonschema not in pyproject.toml | Added `jsonschema>=4.22` | `eccca01` |
| Activity polling start unconditionally | Checks current page before starting | `eccca01` |
| Reader events not cleaned on page change | Calls `ReaderPage._cleanupEvents?.()` | `eccca01` |
| runner.py used raw subprocess.run | → `run_cmd()` from subprocess_runner | `eccca01` |

## Tests passing

```
47/47 checks ✅
12/12 novelctl smoke tests ✅
164/164 chapter JSONs validated ✅
10/10 API smoke tests ✅
```

## Remaining known debt (non-blocking)

- translate.py still depends on progress.py (legacy .chprogress)
- No CI workflow file yet (manual python check_all.py)
- activity feed still updates every 30s if rightbar open on home
- No virtual scrolling for very long chapters (>500 paragraphs)
