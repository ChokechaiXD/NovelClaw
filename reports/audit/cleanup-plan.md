# Cleanup Plan — Phase A Findings

## Priority Legend
P0 = Must fix before continuing  
P1 = Important, do after P0  
P2 = Nice to have

## ✅ Safe to Fix Immediately (No Risk)

### P0: Delete Test Artifacts
**Files**: `.chprogress/test-draft.json`, `.chprogress/test-force.json`, `.chprogress/test-force-success.json`
**Action**: Delete files (test data from tests, not needed)
**Risk**: None — orchestrator uses `jobs/` not `.chprogress/`

### P1: Fix `nc-bookmarks` localStorage Key
**File**: `reader/public/js/pages/admin.js` line 262
**Action**: Change `'nc-bookmarks'` → `'novelclaw-bookmarks'` to match naming convention
**Risk**: Low — users lose existing bookmarks on upgrade

### P1: Complete AdminNovelEditPage Form Fields
**File**: `reader/public/js/pages/admin.js` lines 243-253
**Action**: Add missing fields (source_lang, target_lang, status, total_chapters, description) matching the API's `/api/novel/update` support
**Risk**: None — just adding form fields

### P2: Add "logs" Tab to Admin Nav
**File**: `reader/public/js/pages/admin.js` function `renderAdminNav()`
**Action**: Add `{ name: 'logs', label: 'ล็อก', page: 'admin/logs' }` to nav links array
**Risk**: None

## ⚠️ Requires Verification Before Fix

### P1: `tools/progress.py` Deprecation
**Action**: Verify `translate.py` dependency on `progress.py`. If orchestrator handles all progress, mark progress.py as deprecated.
**Risk**: If translate.py still uses progress.py for state tracking, removal could break resume/crash-recovery.

### P1: `reader/lib/render.js` Fate
**Action**: Either:
- Remove render.js and update tests to test frontend rendering (larger effort)
- Or keep render.js but mark as "test support only"
**Risk**: Tests will fail if removed without updating.

## 🔍 Needs Investigation

### P2: Missing `npm run syntax` Script
**File**: `reader/package.json`
**Issue**: `check_all.py` references `npm run syntax` but no such script exists in package.json
**Action**: Add `"syntax": "find public/js -name '*.js' -print0 | xargs -0 node --check"` to scripts

### P2: CI Windows Compatibility
**File**: `.github/workflows/ci.yml`
**Issue**: CI runs on ubuntu-latest but development is on Windows. Shell commands may not work cross-platform.
**Action**: Verify check_all.py runs correctly on both, or provide platform-specific scripts.

## 📋 Recommended Phase A Execution Order

### Batch 1 (Safe fixes — do now)
1. Delete `.chprogress/test-*.json`
2. Fix `nc-bookmarks` key name

### Batch 2 (Risk review)
3. Verify progress.py usage in translate.py
4. Decide render.js fate

### Batch 3 (Enhancements)
5. Complete AdminNovelEditPage form fields
6. Add logs tab to admin nav
7. Add `npm run syntax` to package.json

## Rollback Plan

Each fix should be:
1. One commit per independent fix
2. Test before commit (start reader, load relevant page)
3. If tests pass, commit with message format: `chore: fix [item]`
4. If tests fail, revert and investigate
