# Dead Code Audit — Phase A

## 1. Dead / Deprecated Code

### 1.1 `reader/lib/render.js` — Test-Only, No Production Import
**Risk**: Low
**Evidence**: 
- `require('./lib/render')` appears ONLY in test files: `tests/render-edge-cases.test.js`, `tests/render-profile.test.js`
- server.js does NOT import render.js
- No production code calls `renderChapterJson()` or `renderParagraphs()`
- Frontend reader.js does its own inline rendering

**Action**: Keep or consolidate. Tests exist, so code has value. But consider if tests should be updated or if render.js should be removed and tests updated.

### 1.2 `tools/progress.py` — Legacy Progress Tracker
**Risk**: Medium
**Evidence**:
- Only imported by `translate.py` (line: `from progress import ...`)
- `orchestrator/` modules do NOT import progress.py
- `orchestrator/jobs.py` handles job state via `jobs/` directory instead
- `.chprogress/` files exist with test data (test-draft.json, test-force.json, test-force-success.json)

**Action**: Verify if translate.py actually calls progress.py functions. If orchestrator handles progress, mark progress.py as deprecated.

### 1.3 `.chprogress/test-*.json` — Test Artifacts Leaked
**Risk**: Low
**Files**:
- `.chprogress/test-draft.json`
- `.chprogress/test-force.json`
- `.chprogress/test-force-success.json`

**Action**: Delete after verifying they're not needed.

## 2. Code Duplication

### 2.1 `esc()` Function Duplicated
**Risk**: Low
- `reader/lib/helpers.js`: Exports `esc()` for server-side
- `reader/public/js/components.js` (`Ui.esc()`): Same logic for client-side

**Assessment**: Separate domains (Node vs Browser), but logic is identical. Acceptable but worth noting.

### 2.2 `readTextOrNull()` Duplicated
**Risk**: Low
- Defined in `server.js` (line 77) — local helper
- Defined in `chapter-repo.js` (line 31) — module helper

**Assessment**: Different scopes. `readTextOrNull` in server.js is used by route handlers. Could be centralized into a utility.

## 3. Inconsistencies

### 3.1 Divergent localStorage Key: `nc-bookmarks`
**File**: `admin.js` line 262
**Code**: `JSON.parse(localStorage.getItem('nc-bookmarks'))`
**Standard**: All other state uses `novelclaw-state`, `novelclaw-settings`, `novelclaw-profile` prefixes
**Risk**: Low — bookmarks are separate from reading state, but naming convention is broken.

### 3.2 `renderAdminNav()` Missing "logs" Tab
**File**: `admin.js` line 8-17
**Issue**: The admin nav has 5 tabs but logs page exists. Clicking to logs page from jobs page works via separate `<a>` link, but the nav component itself has no logs entry.

### 3.3 `AdminGlossaryPage` Hardcoded to `novels[0]?.slug`
**File**: `admin.js` line 209
**Issue**: Cannot select which novel's glossary to view.

## 4. Admin Novel Edit Page Incomplete

**File**: `admin.js` lines 243-253
**The `render()` method only shows title + author form fields. Missing:
- source_lang / target_lang
- status
- total_chapters
- description

Despite server.js' `/api/novel/update` endpoint supporting all of these.

## 5. Scripts That Should Not Be Called Directly

Per AGENTS.md: `translate.py` should NOT be called directly — use `novelctl.py translate`.

**Scripts to avoid direct invocation:**
- `tools/translate.py` — must use novelctl
- `tools/glossary.py` — called by server.js via spawn, not direct CLI
- `tools/migrate_json.py` — migration tool, one-time
- `tools/scorer.py` — older quality check, may be superseded by orchestrator/quality.py
- `tools/progress.py` — legacy, superseded by orchestrator/jobs.py
