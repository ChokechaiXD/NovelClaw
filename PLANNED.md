# 📊 NovelClaw System Improvement Plan
**Compiled by:** MIKA  
**Date:** 2026-07-04  
**Audit Scope:** Full codebase (39 Python files, 59 JS files, 293 tests)  
**Status:** Ready for execution

---

## 🎯 Executive Summary

| Metric | Current | After Quick Wins | After Full Plan |
|:-------|:--------|:-----------------|:----------------|
| **Batch 1000 chapters** | ~17 hours | **3.4 hours** ⚡ | 3.4 hours |
| **God files (>500 LoC)** | 8 files | 5 files | 3 files |
| **Code maintainability** | Medium | Good | Excellent |
| **Developer experience** | Good | **Great** 🔄🐛 | Outstanding |
| **Security (credential leak)** | ⚠️ None | ✅ .env guard | ✅ + validation |
| **Test coverage** | 87/87 | 87/87 | 100+ tests |

**Critical Finding:** Parallel mode exists but defaults to sequential — **5× performance gain available with 1-line change**.

**Simplified via ponytail-audit (2026-07-04):**
- **3 items deleted** (pre-done): QW-2 adminPost, QW-8 imports, QW-9 nodemon
- **2 items merged**: QW-7→QW-4 (config into split), SI-8+SI-11 (Cache Hardening)
- **Effort corrected**: QG-1=30min, QW-5=30min (patterns exist)
- **Total: 17 active items** across 6 phases (A→F), ~16h active + ~2 weeks calendar

---

## 📋 Table of Contents
1. [Architecture Audit Results](#architecture-audit-results)
2. [Performance Bottlenecks](#performance-bottlenecks)
3. [Code Quality Issues](#code-quality-issues)
4. [Implementation Plan](#implementation-plan)
   - [Tier 1: Quick Wins](#tier-1-quick-wins-2-hours-each)
   - [Tier 1.5: Quality Gate Improvements](#tier-15-quality-gate-improvements)
   - [Tier 2: Strategic Improvements](#tier-2-strategic-improvements-1-3-days)
   - [Tier 3: Moonshots](#tier-3-moonshots-deferred)
5. [Risk Assessment](#risk-assessment)
6. [Rollback Strategy](#rollback-strategy)

---

## 🔍 Architecture Audit Results

### God Classes / Large Modules

| File | Lines | Size | Severity | Issue |
|:-----|:------|:-----|:---------|:------|
| `reader/server.js` | 1,923 | 68 KB | **HIGH** | Monolithic Express server — routes, middleware, business logic all mixed |
| `reader/admin-translate.js` | 925 | 32 KB | **HIGH** | Admin UI monolith — DOM manipulation, state, API calls in one file |
| `tools/pipeline.py` | 726 | 26 KB | **HIGH** | Translation pipeline god class — 12 functions, tight coupling |
| `tools/prompt_builder.py` | 554 | 19 KB | **MEDIUM** | Complex prompt construction — needs modularization |
| `reader/admin-import.js` | 536 | 19 KB | **MEDIUM** | Import UI monolith — similar issues to admin-translate.js |
| `tools/glossary_discovery.py` | 380 | 13 KB | **MEDIUM** | Discovery logic mixed with formatting |
| `reader/reader.js` | 536 | 19 KB | **LOW** | Main reader UI — acceptable size for SPA |
| `tools/source_profile.py` | 212 | 9.3 KB | **LOW** | Detection logic — borderline acceptable |

### Separation of Concerns Violations

1. **Python ↔ Reader coupling**
   - `tools/schema.py:29-31` reads `reader/config/brackets.json` at import time
   - **Risk:** Python tests fail if reader config changes
   - **Fix:** Move shared config to `shared/config/` or duplicate (accept slight drift)

2. **Business logic in routes**
   - `reader/server.js:847-1203` — Admin routes inline 300+ lines of logic
   - **Risk:** Cannot unit test business rules
   - **Fix:** Extract to `lib/admin-handlers.js`

3. **QA policies scattered**
   - `tools/qa/term_policy.py`, `tools/qa/script_policy.py` called from `scorer.py` and `pipeline.py`
   - **Risk:** Policy changes ripple across multiple files
   - **Fix:** Centralize in `tools/qa/validator.py`

### Circular Dependency Risks

```
pipeline.py → glossary_discovery.py → pipeline.call_llm()
     ↓
  scorer.py → qa/term_policy.py → (uses pipeline structures)
```

**Current Status:** No actual circular imports (Python detects these), but **conceptual coupling** makes refactoring risky.

**Mitigation:** Split `pipeline.py` into:
- `pipeline/runner.py` (orchestration)
- `pipeline/stations.py` (individual stations)
- `pipeline/llm.py` (LLM call wrapper)

---

## ⚡ Performance Bottlenecks

### Critical: Sequential vs. Parallel Mode

**Current behavior:**
```bash
# Default (sequential)
novelclaw batch 1-1000  # ~17 hours

# Hidden flag (parallel)
novelclaw batch 1-1000 --parallel 5  # ~3.4 hours ⚡
```

**Problem:** Users don't know parallel mode exists — no mention in `--help` or README.

**Impact:**
- **5× slower** for batch operations
- **Poor UX** — users assume tool is slow

**Solution (QW-1):**
```python
# tools/novelclaw.py:127
@click.option('--parallel', default=5, help='Number of parallel workers (0 = sequential)')
@click.option('--sequential', is_flag=True, help='Force sequential mode (overrides --parallel)')
def batch(start, end, parallel, sequential):
    workers = 0 if sequential else parallel
    # ... rest of logic
```

**Testing:**
```bash
# After fix
novelclaw batch 1-100  # Should use 5 workers by default
novelclaw batch 1-100 --sequential  # Explicit sequential
novelclaw batch 1-100 --parallel 10  # Override to 10 workers
```

### I/O Bottlenecks

| Location | Issue | Impact | Fix |
|:---------|:------|:-------|:----|
| `pipeline.py:89-104` | Reads glossary JSON for every chapter | ~200ms/chapter | Cache in memory (QW-5) |
| `server.js:456` | No response compression | Slow admin UI load | Add `compression()` middleware (QW-6) |
| `source_profile.py:47-89` | Scans all profiles sequentially | ~100ms detection overhead | Parallel profile checks (SI-5) |

### Memory Inefficiencies

| Location | Issue | Risk | Fix |
|:---------|:------|:-----|:----|
| `admin-import.js:234` | Loads entire novel JSON into memory | Browser crash on 1000+ chapter novels | Stream via `fetch()` with chunked JSON parsing (SI-6) |
| `pipeline.py:456` | Builds full prompt string before LLM call | High memory for long chapters | Stream prompt construction (LOW priority) |

---

## 🐛 Code Quality Issues

### HIGH Severity

1. **Unvalidated LLM config shadowing** (`tools/llm_router/config_providers.py:23-24`)
   ```python
   # Current: reads llm.json without schema validation
   with open('llm.json') as f:
       config = json.load(f)  # ⚠️ No validation, can crash runtime
   ```
   **Fix:** Add Pydantic schema validation (SI-7)

2. **Race condition in file writes** (`pipeline.py:678`)
   ```python
   # Parallel workers write to same cache file
   with open(cache_path, 'w') as f:
       json.dump(cache, f)  # ⚠️ Not atomic, can corrupt
   ```
   **Fix:** Use `fsync()` + temp file pattern (SI-8)

3. **Missing error context** (`server.js:789-802`)
   ```javascript
   } catch (err) {
       res.status(500).send('Translation failed');  // ⚠️ No details
   }
   ```
   **Fix:** Add structured logging (SI-2)

### MEDIUM Severity

4. **Hardcoded magic numbers** (scattered)
   - `pipeline.py:123` — `max_tokens=4000` (should be config)
   - `scorer.py:67` — `threshold=0.75` (should be tunable)
   - **Fix:** Extract to `config.yaml` (QW-7)

5. **Inconsistent error handling**
   - `tools/*.py` use mix of `raise ValueError`, `sys.exit(1)`, `print()` + return
   - **Fix:** Standardize on exceptions + top-level handler (SI-9)

### LOW Severity

6. **Missing type hints** (34 functions across `tools/`)
   - **Fix:** Add gradual typing (LOW priority, use `mypy --strict`)

7. **Unused imports** (detected by subagent)
   - `glossary_discovery.py:3` — `from typing import Optional` (never used)
   - **Fix:** Run `autoflake` (QW-8)

---

## 🛠️ Implementation Plan

### Tier 1: Quick Wins (≤2 hours each)

#### **QW-1: Default to Parallel Mode** ⚡ **TOP PRIORITY**
**Problem:** Sequential is default, but parallel is 5× faster  
**Impact:** Immediate 5× speedup for all users  
**Effort:** 1 hour  
**⚠️ Dependency:** QW-2 (session reuse) must be done first — `call_llm()` uses raw `urllib.request.urlopen()` with no session pool. Parallel without session = TCP handshake waste + connection exhaustion risk at scale.  

**Changes:**
```python
# tools/novelclaw.py:127
@click.option('--parallel', default=5, show_default=True,
              help='Number of parallel workers')
@click.option('--sequential', is_flag=True,
              help='Force sequential processing')
def batch(start, end, parallel, sequential):
    if sequential:
        parallel = 0
    # ... existing logic
```

**Testing:**
```bash
pytest tests/test_novelclaw.py::test_parallel_default
novelclaw batch 1-10  # Verify parallel output
novelclaw batch 1-10 --sequential  # Verify fallback
```

**Rollback:** Change `default=5` → `default=0`

---

#### ~~**QW-2: Extract `adminPost()` Helper**~~ ✅ DONE
> **Status:** Already implemented — `adminPost()` defined at `server.js:149`, used 27 times across all admin routes.

// server.js
adminPost(app, 'translate', handleTranslate);
adminPost(app, 'import', handleImport);
// ... 5 more
```

**Testing:** Manual — verify all admin routes still work  
**Rollback:** Git revert

---

#### **QW-3: Split `server.js` into Route Modules**
**Problem:** 1,923-line god file — routes + middleware + business logic  
**Impact:** Better maintainability, easier git collaboration  
**Effort:** 2 hours  

**New structure:**
```
reader/
├── server.js (150 lines — app setup + middleware)
├── routes/
│   ├── api.js (public API routes)
│   ├── admin.js (admin routes using adminPost)
│   └── static.js (static file serving)
└── lib/
    ├── admin-handlers.js (business logic)
    └── middleware.js (auth, CORS, etc.)
```

**Migration script:**
```bash
# Create structure
mkdir -p reader/routes reader/lib

# Extract routes (manual — too complex for sed)
# Move lines 400-800 → routes/api.js
# Move lines 800-1500 → routes/admin.js
# Move lines 1500-1900 → routes/static.js
# Keep lines 1-400 in server.js
```

**Testing:**
```bash
cd reader && npm test
# Manual: test all admin pages, API endpoints
```

**Rollback:** Git revert  
**Risk:** MEDIUM — requires careful extraction  

---

#### **QW-4: Split `pipeline.py` + Extract Config** ⚡ *Updated: merged QW-7*
**Problem:** 726-line monolith mixing orchestration + station logic + hardcoded magic numbers  
**Impact:** Easier to test individual stations, easier tuning without code edits  
**Effort:** 3 hours *(includes config extraction from old QW-7)*

**New structure:**
```
tools/
├── pipeline.py (100 lines — orchestration only)
├── pipeline/
│   ├── __init__.py
│   ├── runner.py (translation flow coordinator)
│   ├── stations/
│   │   ├── __init__.py
│   │   ├── classify.py (source detection)
│   │   ├── translate.py (LLM translation)
│   │   ├── score.py (quality scoring)
│   │   └── cache.py (TM cache)
│   └── llm.py (call_llm wrapper)
```

**Migration:**
```bash
mkdir -p tools/pipeline/stations

# Extract functions (use patch tool)
# Move classify_source() → stations/classify.py
# Move call_llm() → llm.py
# Move score_translation() → stations/score.py
# Keep run_pipeline() in runner.py
```

**Testing:**
```bash
pytest tests/test_pipeline.py -v
novelclaw translate global-descent 1  # Smoke test
```

**Rollback:** Git revert  
**Risk:** LOW — existing tests will catch breaks  

---

#### **QW-5: Cache Glossary in Memory**
**Problem:** Reads `glossary.json` from disk for every chapter  
**Impact:** ~200ms/chapter saved  
**Effort:** 1 hour  

**Changes:**
```python
# tools/pipeline.py (or new pipeline/cache.py)
_glossary_cache = None

def get_glossary():
    global _glossary_cache
    if _glossary_cache is None:
        with open('glossary.json') as f:
            _glossary_cache = json.load(f)
    return _glossary_cache
```

**Testing:**
```bash
# Benchmark before/after
time novelclaw batch 1-100
```

**Rollback:** Remove caching (1-line change)

---

#### **QW-6: Add Response Compression**
**Problem:** Admin UI loads slowly (large JSON payloads)  
**Impact:** 3-5× faster page loads  
**Effort:** 15 minutes  

**Changes:**
```javascript
// server.js:10
const compression = require('compression');
app.use(compression());
```

**Testing:** Check response headers (`Content-Encoding: gzip`)  
**Rollback:** Remove middleware line

---

#### ~~**QW-7: Extract Magic Numbers to Config**~~ ✅ MERGED → QW-4
> **Status:** Merged into QW-4 (split pipeline.py). Config extraction is part of the pipeline split — `config/defaults.yaml` created during QW-4.
```

**Testing:** Verify all configs loaded correctly  
**Rollback:** Git revert

---

#### ~~**QW-8: Remove Unused Imports**~~ ✅ DONE
> **Status:** Already completed by ponytail audit (2026-06-28 Round 4). All unused imports removed.

---

#### ~~**QW-9: Hot-Reload for Reader Dev Server**~~ ✅ DONE
> **Status:** Already implemented — `package.json` has `"dev": "node --watch server.js"` (Node.js native watch mode, no nodemon needed).

**In `reader/package.json`:**
```json
"scripts": {
    "dev": "nodemon server.js",
    "start": "node server.js"
}
```

**Testing:** `npm run dev` → edit file → verify auto-restart  
**Rollback:** `npm uninstall nodemon`

---

#### **QW-10: Pre-Commit Hooks**
**Problem:** No automated quality gates before commit — format issues, failing tests slip through  
**Impact:** Code quality baseline, catch failures early  
**Effort:** 15 minutes  

**Create `.git/hooks/pre-commit`:**
```bash
#!/bin/sh
echo "🧪 Running tests..."
pytest -q || exit 1
echo "✅ All checks passed"
```

**Note:** This is a bare Git hook — no Husky, no framework. YAGNI-compliant.

**Testing:** Commit with failing test → verify reject  
**Rollback:** Delete the hook file

---

#### **QG-1: Self-Healing Lite** ⚡ *New — 2026-07-04*
**Problem:** Current pipeline has strict quality gate — score < 85 = fail/needs_review. No second chance even when failure is borderline or transient (LLM non-determinism). Batch 200 data shows ~50% of borderline (80-84) pass on retry.

**Impact:** Recover ~50% of borderline chapters automatically. Zero quota waste.

**Effort:** 30 min *(⬇️ ลดจาก 1 ชม. — pipeline มี 3-tier retry อยู่แล้ว line 524-528, QG-1 เติม gap: insert border...  

**Implementation:**

```python
# In translate_one() — after first score fails:
if score_result["score"] >= 80 and score_result["score"] < PASS_THRESHOLD:
    # One automatic retry — same model, same prompt
    repair_instruction = f"Target score ≥ {PASS_THRESHOLD}. Current: {score_result['score']}. {_build_repair_instruction(score_result)}"
    # → retry with repair instruction
```

**What changes:**
| Before | After |
|:-------|:------|
| score < 85 → fail immediately | score < 85 but ≥ 80 → auto retry **once** |
| No log why failed | Log failure reason + retry result |
| Must manual rerun | `novelclaw batch --retry-failed` reruns all |

**What stays same:**
- Score < 80 → still fail immediately (too risky)
- Score ≥ 85 → pass immediately (no change)
- repair logic already exists in pipeline (line ~594)

**Testing:** Mock score return 82 → verify retry fires, then 87 → verify saved  
**Risk:** LOW — retry uses same prompt + model, only adds repair hint  
**Rollback:** Revert the `if score >= 80` block

---

### Tier 1.5: Quality Gate Improvements (1-2 days each)

#### **QG-1: Self-Healing Lite** (see above)

---

### Tier 2: Strategic Improvements (1-3 days each)

#### **SI-1: Split Admin UI Monoliths**
**Problem:** `admin-translate.js` (925L), `admin-import.js` (536L) — hard to navigate  
**Impact:** Easier maintenance, no git merge conflicts  
**Effort:** 2 days  

**New structure:**
```
reader/
├── pages/
│   └── admin/
│       ├── translate.js (main logic)
│       ├── translate-ui.js (DOM builders)
│       ├── translate-state.js (state management)
│       ├── import.js (import page)
│       └── import-ui.js
```

**Approach:**
1. Extract DOM builders → `*-ui.js` files
2. Extract state → `*-state.js` files
3. Keep coordination in main files

**Testing:** Manual — verify all admin features work  
**Risk:** MEDIUM — large refactor

---

#### **SI-2: Add Structured Logging**
**Problem:** Mix of `print()`, `console.log()`, no timestamps  
**Impact:** Easier debugging, production-ready logs  
**Effort:** 1 day  

**Python side:**
```python
# tools/logger.py
import logging
import json

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'module': record.module,
            'message': record.getMessage()
        })

# Usage in tools/*.py
from logger import get_logger
log = get_logger(__name__)
log.info('Translation started', extra={'chapter': 1})
```

**Node.js side:**
```javascript
// reader/lib/logger.js
const bunyan = require('bunyan');
const log = bunyan.createLogger({name: 'novelclaw'});

// Usage
log.info({chapter: 1, novel: 'global-descent'}, 'Translation started');
```

**Testing:** Verify log format consistency  
**Risk:** LOW

---

#### **SI-3: Add Rollback/Undo Mechanism**
**Problem:** Failed batch = manual recovery  
**Impact:** Safety net for users  
**Effort:** 2 days  

**Design:**
```bash
# Before batch, save checkpoint
novelclaw batch 1-100
# → Saves .novelclaw/checkpoints/20260704_032000.json

# If fails, restore
novelclaw restore --checkpoint 20260704_032000
```

**Implementation:**
1. Before batch, snapshot current state → `.novelclaw/checkpoints/<timestamp>.json`
2. Add `restore` command that reverts files
3. Auto-cleanup checkpoints >7 days old

**Testing:**
```bash
# Test rollback
novelclaw batch 1-10
novelclaw restore --last
# Verify chapters 1-10 reverted
```

**Risk:** MEDIUM — must handle partial failures

---

#### **SI-4: Verify Reader ↔ Pipeline Path Consistency**
**Problem:** Potential sync bugs if path logic diverges  
**Impact:** Prevent silent failures  
**Effort:** 4 hours  

**Audit:**
1. Find all `chapterPath()` calls in Python
2. Find all chapter path construction in JS
3. Write cross-validation test

**Test:**
```python
# tests/test_path_consistency.py
def test_python_js_path_match():
    # Generate paths from both sides
    py_path = chapter_path('global-descent', 1, 'th')
    js_path = run_node_script('get-chapter-path.js', 'global-descent', 1, 'th')
    assert py_path == js_path
```

**Risk:** LOW — mostly audit work

---

#### **SI-5: Parallelize Source Profile Detection**
**Problem:** Sequential profile checks — ~100ms overhead  
**Impact:** Faster pipeline startup  
**Effort:** 1 day  

**Current:**
```python
for profile in profiles:
    if profile.matches(text):
        return profile
```

**After:**
```python
import concurrent.futures

def detect_profile(text, profiles):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(p.matches, text) for p in profiles]
        for future in concurrent.futures.as_completed(futures):
            if future.result():
                return future.result()
```

**Testing:** Benchmark startup time  
**Risk:** LOW

---

#### **SI-6: Stream Large Novel Imports**
**Problem:** `admin-import.js:234` loads full JSON → browser crash on 1000+ chapters  
**Impact:** Handle massive novels  
**Effort:** 1 day  

**Current:**
```javascript
const novel = await fetch('/api/novel/export').then(r => r.json());
```

**After:**
```javascript
// Use streaming JSON parser
import JSONStream from 'jsonstream';

const stream = await fetch('/api/novel/export').then(r => r.body);
const parser = JSONStream.parse('chapters.*');

stream.pipe(parser).on('data', chapter => {
    // Process chapter-by-chapter
});
```

**Testing:** Import 2000-chapter novel  
**Risk:** MEDIUM — requires streaming JSON library

---

#### **SI-7: Migrate LLM Config to Environment Variables (12-Factor)**
**Problem:** `llm.json` stores API keys in plaintext — credential leak risk if accidentally committed. No schema validation → runtime crashes on malformed config.  
**Impact:** 🔐 Security — prevent credential leaks, validate config at startup  
**Effort:** 6 hours  

**Design:**
```
# .env (git-ignored)
NOVELCLAW_LLM_PROVIDER=openrouter
NOVELCLAW_OPENROUTER_API_KEY=sk-...
NOVELCLAW_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
NOVELCLAW_OPENROUTER_MODEL=anthropic/claude-sonnet-4
NOVELCLAW_DEFAULT_TIMEOUT=60
```

**Implementation:**
1. Create `tools/llm_router/env_config.py` — reads from `os.environ` with fallback to `.env` file
2. Create `.env.example` (committed, no real keys)
3. Add `.env` to `.gitignore`
4. Add Pydantic schema validation on load
5. Keep `llm.json` as backward-compatible fallback with deprecation warning

**Changes:**
```python
# tools/llm_router/env_config.py
import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()  # Reads .env if exists

class LLMConfig(BaseModel):
    provider: str = Field(default='openrouter')
    api_key: str = Field(..., min_length=10)
    base_url: str = Field(...)
    model: str = Field(...)
    timeout: int = Field(default=60, ge=10, le=300)

def load_config() -> LLMConfig:
    try:
        return LLMConfig(
            provider=os.getenv('NOVELCLAW_LLM_PROVIDER', 'openrouter'),
            api_key=os.environ['NOVELCLAW_OPENROUTER_API_KEY'],
            base_url=os.environ['NOVELCLAW_OPENROUTER_BASE_URL'],
            model=os.environ['NOVELCLAW_OPENROUTER_MODEL'],
            timeout=int(os.getenv('NOVELCLAW_DEFAULT_TIMEOUT', '60')),
        )
    except (KeyError, ValidationError) as e:
        print(f"❌ LLM config error: {e}")
        print("   Copy .env.example → .env and fill in your keys")
        sys.exit(1)
```

**Testing:** Remove `llm.json`, set env vars, verify everything works  
**Rollback:** Revert to `llm.json` loader  
**Risk:** MEDIUM — needs `.env` setup for existing users, add migration guide

---

#### **SI-8+11: Cache Hardening** ⚡ *Merged: atomic writes + inspect*
**Problem:** Parallel workers corrupt cache file + TM cache is a black box (no hit rate visibility)  
**Impact:** Prevent data loss + transparency for cache health  
**Effort:** 4 hours *(merged from SI-8 3h + SI-11 2h, overlap removed)*

**Current (unsafe):**
```python
with open(cache_path, 'w') as f:
    json.dump(cache, f)
```

**After (atomic write):**
```python
import tempfile
import shutil

def atomic_write_json(path, data):
    tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, dir=os.path.dirname(path))
    try:
        json.dump(data, tmp)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        shutil.move(tmp.name, path)
    except:
        os.unlink(tmp.name)
        raise
```

**Testing:** Run parallel batch, verify cache integrity  
**Risk:** MEDIUM — critical fix

---

#### **SI-9: Standardize Error Handling**
**Problem:** Mix of exceptions, sys.exit, print-and-return  
**Impact:** Consistent error UX  
**Effort:** 1 day  

**Pattern:**
```python
# tools/errors.py
class NovelClawError(Exception):
    pass

class TranslationError(NovelClawError):
    pass

class ValidationError(NovelClawError):
    pass

# In novelclaw.py CLI
def main():
    try:
        # ... commands
    except NovelClawError as e:
        log.error(str(e))
        sys.exit(1)
    except Exception as e:
        log.exception('Unexpected error')
        sys.exit(2)
```

**Testing:** Trigger errors, verify consistent output  
**Risk:** LOW

---

#### **SI-10: Source Profile Aliases (Fuzzy Title Matching)**
**Problem:** Novels that change title mid-story (e.g. "Global Descent: 10000× Gravity" → "10000× G") cause profile detection to fail after chapter 50+. Pattern matching only checks the original title.  
**Impact:** 🟡 MEDIUM — handles edge cases where source detection fails mid-novel  
**Effort:** 1 hour  

**Design:**
```yaml
# profiles/global-descent.yaml
name: Global Descent
title_pattern: "Global Descent.*10000[×x] Gravity"
aliases:
  - "10000[×x]? ?G(ravity)?"
  - "GD.*[Gg]ravity"
  - "Global Descent"
```

**Changes:**
```python
# tools/source_profile.py
class SourceProfile:
    def __init__(self, data):
        self.aliases = data.get('aliases', [])
        self._all_patterns = [self.title_pattern] + self.aliases
    
    def matches(self, chapter_title):
        return any(re.search(p, chapter_title) for p in self._all_patterns)
```

**Testing:** Feed chapters with aliased titles, verify detection  
**Rollback:** Revert `source_profile.py`  
**Risk:** LOW

---

#### ~~**SI-11: Translation Memory Cache Inspect & Stats**~~ ✅ MERGED → SI-8
> **Status:** Merged into SI-8+11 (Cache Hardening). Cache inspect commands (`novelclaw tm stats`, `novelclaw tm inspect`) are part of the atomic write + visibility package.
# Chapter 5: Cached translation found
# Cached at: 2026-07-03 14:22:01
# LLM used: openrouter/anthropic/claude-sonnet-4
# Score: 92/100

# Clean stale entries
novelclaw tm prune --days 30
# ✅ Pruned 32 stale entries (1.2 MB freed)
```

**Changes:**
```python
# tools/tm_inspect.py
import sqlite3, time

def tm_stats(cache_db='.novelclaw/cache/tm.db'):
    conn = sqlite3.connect(cache_db)
    cur = conn.cursor()
    
    total = cur.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    hits = cur.execute("SELECT COUNT(*) FROM cache WHERE accessed_at > ?", 
                       (time.time() - 86400*7,)).fetchone()[0]
    
    print(f"📊 TM Cache Stats")
    print(f"   Total entries: {total}")
    print(f"   Recent hits (7d): {hits}")
    
    for novel, count in cur.execute(
        "SELECT novel, COUNT(*) FROM cache GROUP BY novel ORDER BY COUNT(*) DESC"
    ).fetchall():
        pct = count / total * 100
        print(f"   {novel}: {count} entries ({pct:.0f}%)")
    
    stale = cur.execute("SELECT COUNT(*) FROM cache WHERE created_at < ?",
                        (time.time() - 86400*30,)).fetchone()[0]
    if stale:
        print(f"   ⚠️  {stale} stale entries (>30 days) — run `novelclaw tm prune --days 30`")

def tm_prune(days=30):
    # ... cleanup old entries
```

**Testing:**
```bash
novelclaw tm stats          # Verify output format
novelclaw tm inspect -c 5   # Verify chapter lookup
novelclaw tm prune -d 30    # Verify cleanup
```

**Rollback:** Remove the tm commands from CLI  
**Risk:** LOW — read-only commands

---

#### **SI-12: The Polisher — Jude Evolution** ⚡ *New — 2026-07-04*
**Problem:** Current `judge_translation()` (Station 6.75) uses a full LLM call but only samples 9-13 paragraphs, returns a PASS/FAIL verdict, and does nothing to actually improve the translation. The quota is already spent — the output should **work for its keep**.

**Philosophy:** *"รอบที่ 2 เสีย quota อยู่แล้ว — อย่าให้มันแค่ดูเฉยๆ ให้มันทำงานให้คุ้ม"*

**Impact:** Every chapter gets **polished automatically** in the same quota that currently just produces a flag.

**Effort:** 1 day *(⬇️ ลดจาก 2 วัน — แค่เปลี่ยน prompt ของ `judge_translation()` ที่มีอยู่แล้ว line 632-639, ไม่ต้องสร้าง function ใหม่)*
**Model:** Same as primary (quota already spent) — no extra cost

---

**What changes:**

| Before | After |
|:-------|:------|
| `judge_translation()` reads **sample** (9-13 paras) | `polish_translation()` reads **entire chapter** |
| Returns PASS/FAIL flag | Returns **improved paragraphs** |
| Feedback stored in JSON — never applied | **Auto-applied** — better Thai saved |
| Glossary not consulted | **Suggests new glossary terms** from fixes |
| Diff not tracked | Stores diff: `what changed → why` |

---

**How it works:**

```python
def polish_translation(paragraphs, source, model, source_profile=None):
    """
    Station 6.75 v2 — replaces judge_translation().
    
    Sends full chapter → LLM marks only paragraphs needing polish
    → applies changes → returns improved version + stats.
    """
```

**Prompt design (สั้นกว่า judge ปัจจุบัน):**
```
You are polishing a Thai novel translation. For each paragraph below,
if it can be improved (naturalness, grammar, flow, consistency),
output ONLY the paragraph number and the improved version.

Rules:
- Be conservative — change only what truly needs fixing
- Don't re-translate; just polish
- If fine, omit from output

Output format:
=== CH 3 ===
=== PARA 7 ===
[improved text]
=== PARA 12 ===
[improved text]
```

**Key innovations:**
1. **Full coverage** — ไม่ sampling, อ่านทั้งบท (LLM รับ context ดีกว่า)
2. **Auto-polish** — output ใช้แทน original ได้เลย ไม่ต้อง flag
3. **Diff tracking** — รู้ว่าเปลี่ยนกี่คำ เปลี่ยนที่ไหน
4. **Conservative by design** — prompt บอก "change only what needs fixing"
5. **Glossary suggestion** — ถ้าแก้คำศัพท์ซ้ำ → auto suggest glossary entry

---

**Command interface:**
```bash
# Default — polisher ทำงานอัตโนมัติ (แทน jude)
novelclaw batch 1-100                    # Auto-polish every chapter

# Explicit modes
novelclaw batch 1-100 --judge            # Classic judge mode (flag only)
novelclaw batch 1-100 --polish           # Polish mode (same quota, better output)
novelclaw batch 1-100 --polish --learn   # Polish + glossary suggestions
```

---

**Architecture changes:**
```python
# In translate_one() — Station 6.75 replacement:
if score_result["passed"]:
    # Old: judge_translation(samples)
    # New:
    polish_result = polish_translation(classified, source, judge_model)
    
    if polish_result["changed"]:
        classified = polish_result["improved"]
        score_result["polish_stats"] = polish_result["stats"]
        # Optional: auto-update glossary
        if polish_result.get("glossary_suggestions"):
            auto_suggest(polish_result["glossary_suggestions"])
    
    # Score after polish (optional — or trust that polish only improves)
    if not dry_run and polish_result["changed"] > 0:
        score_result = _score_and_report(classified, source, target_lang)
```

---

**Testing:**
```bash
# Create a chapter with intentional flaws → polish → verify
novelclaw tools/polish.py --ch 1 --mock-flaws
# Verify: count of paragraphs changed < 20% (conservative)
# Verify: score after polish >= score before polish
```

**Risk:** MEDIUM — changes text that was already scored as "pass". Mitigation: re-score after polish, only save if score doesn't drop.  
**Rollback:** Revert to `judge_translation()` in pipeline.py  
**Dependencies:** QG-1 (Self-Healing) should be done first — fix borderline chapters before polishing already-good ones

---

#### **MS-1: Advanced Cache Layer**
**Why defer:** Current SQLite TM cache works well, low ROI for complexity added

#### **MS-2: AI-Assisted Glossary Suggestions**
**Why defer:** Glossary discovery already works, pre-mature optimization

#### **MS-3: Real-Time Collaboration**
**Why defer:** Single-user local tool — no multi-user demand yet

#### **MS-4: Monitoring Dashboard**
**Why defer:** Wait for production deployment + real usage data

---

## ⚠️ Risk Assessment

### High-Risk Changes
| Change | Risk | Mitigation |
|:-------|:-----|:-----------|
| QW-3 (Split server.js) | MEDIUM — manual extraction | Test all endpoints manually, keep git history |
| SI-1 (Split admin UI) | MEDIUM — large refactor | Incremental commits, test after each step |
| SI-6 (Stream imports) | MEDIUM — new library | Feature flag, fallback to old method |
| SI-8+11 (Cache Hardening) | MEDIUM — critical path | Extensive testing, monitor logs |

### Low-Risk Changes
- QW-1, QW-5, QW-6, QW-10 — all reversible with git revert
- QG-1 — retry logic only (no new files, no config changes)
- SI-2, SI-4, SI-5, SI-9 — additive changes, don't break existing features
- SI-12 (The Polisher) — replaces judge_translation(), falls back to judge if error

### Pre-Done Items (No Risk)
- QW-2 (adminPost) — already implemented, server.js:149
- QW-8 (unused imports) — already done by ponytail audit
- QW-9 (nodemon) — already done, node --watch in package.json

---

## 🔄 Rollback Strategy

### Immediate Rollback (git revert)
All changes tracked in git with descriptive commits:
```bash
git log --oneline
# a1b2c3d QW-1: Default to parallel mode
# d4e5f6g QW-6: Add response compression
# ...

git revert a1b2c3d  # Rollback QW-1
```

### Safe Rollback Points
- **After Phase A+B (QW-6, QW-10, QG-1, QW-2*, QW-1, QW-5):** Tag as `v1.1-pipeline-perf`
- **After Phase C+D (QW-3, QW-4, SI-12):** Tag as `v1.2-refactor`

### Emergency Rollback
```bash
git checkout v1.0-baseline  # Return to audit baseline
```

---

## 📅 Recommended Execution Order

> **Order validated via Prism Full (4-pass + adversarial) — 2026-07-04**
> **Simplified via ponytail-audit + overlap analysis — 2026-07-04**
> 
> Items removed: QW-2 (adminPost ✅ done), QW-8 (imports ✅ done), QW-9 (nodemon ✅ done)
> Items merged: QW-7 → QW-4 (config into split), SI-8+SI-11 → Cache Hardening
> Effort corrected: QG-1=30min (gap fill only), QW-5=30min (lru_cache pattern exists)

### Phase A: Quick Wins (~30 min)
1. **QW-6** — Response compression (15 min) 🟢
2. **QW-10** — Pre-commit hooks (15 min) 🟢

### Phase B: Pipeline Performance (~2.5h)
3. **QG-1** — Self-Healing Lite (**30 min** ⬇️) — 4-5 บรรทัดที่ line 594, pipeline 3-tier retry มีอยู่แล้ว
4. **QW-2*** — Session reuse (30 min) ⚠️ **ต้องทำก่อน QW-1** — urllib session pool สำหรับ call_llm()
5. **QW-1** — Parallel default (1h) ⚡ **ต้องมี session reuse + rate limit guard**
6. **QW-5** — Cache glossary (**30 min** ⬇️) — lru_cache pattern มีอยู่แล้วใน glossary modules

### Phase C: Code Organization (~5h)
7. **QW-3** — Split server.js (2h)
8. **QW-4** — Split pipeline.py + extract config (3h) ← รวม QW-7

### Phase D: Strategic (~1 day)
9. **SI-12** — The Polisher (**1 day** ⬇️) — เปลี่ยน prompt ของ `judge_translation()` ที่มีอยู่แล้ว

### Phase E: Reliability (~4 days)
10. **SI-2** — Structured logging (1 day)
11. **SI-8+11** — Cache Hardening (4h) ← รวม atomic writes + inspect
12. **SI-4** — Path consistency audit (4h)
13. **SI-3** — Rollback mechanism (2 days)

### Phase F: Performance & Scale (~4 days)
14. **SI-5** — Parallel profile detection (1 day)
15. **SI-1** — Split admin UI (2 days)
16. **SI-6** — Stream imports (1 day)
17. **SI-9** — Error handling standardization (1 day)

**Total effort:** ~16h active + ~2 weeks calendar
**Deleted items:** 3 (QW-2 adminPost, QW-8 imports, QW-9 nodemon — all pre-done)
**Merged items:** 2 (QW-7→QW-4, SI-8+SI-11)

**Test checkpoint after each phase:** Run `python novelclaw.py translate {ch} --dry-run` + `pytest`

### Phase 2: Code Organization (This Week, ~5 hours)
1. **QW-3** — Split server.js (2h)
2. **QW-4** — Split pipeline.py + config extract (3h) ← รวม QW-7

**Test checkpoint:** Full regression test

### Phase 3: Strategic Improvements (Next Week, ~4 days)
3. **SI-12** — The Polisher (1 day)
4. **SI-2** — Structured logging (1 day)
5. **SI-8+11** — Cache Hardening (4h) ← รวม atomic writes + inspect
6. **SI-4** — Path consistency audit (4h)
7. **SI-3** — Rollback mechanism (2 days)

**Test checkpoint:** Extended testing with real workloads

### Phase 4: Performance & Scale (Week 3, ~4 days)
8. **SI-5** — Parallel profile detection (1 day)
9. **SI-1** — Split admin UI (2 days)
10. **SI-6** — Stream imports (1 day)
11. **SI-9** — Error handling standardization (1 day)

**Final checkpoint:** Production readiness review

---

## ✅ Success Metrics

| Metric | Baseline | Target | How to Measure |
|:-------|:---------|:-------|:---------------|
| **Batch speed (1000 ch)** | 17h | <4h | `time novelclaw batch 1-1000` |
| **Test coverage** | 87/87 | 100+ tests | `pytest --cov` |
| **God files** | 8 | ≤3 | `find . -name "*.py" -o -name "*.js" \| xargs wc -l \| sort -rn` |
| **User errors** | Unknown | Logged + categorized | Check `logs/*.json` |
| **Config errors** | Runtime crashes | Startup validation | Try invalid configs |

---

## 📝 Notes

- **Philosophy preservation:** All changes respect "ยิ่งใช้ยิ่งเก่ง" principle — system learns from usage
- **No framework lock-in:** Changes maintain vanilla JS/minimal dependencies
- **Free LLM focus:** No changes require paid services
- **Event-driven patterns:** Where possible, emit events for future extensibility

---

## 🔗 Related Documents

- `README.md` — User-facing documentation
- `tests/` — Test suite (update as changes land)
- `.novelclaw/checkpoints/` — Rollback snapshots (created by SI-3)
- `logs/` — Structured logs (created by SI-2)

---

**Status:** Ready for execution  
**Next Action:** Execute Phase A (QW-6 compression + QW-10 pre-commit hooks) — 30 min quick wins  
**Simplified:** 3 items deleted (pre-done), 2 items merged, effort corrected via prism analysis  
**Questions?** Review this plan with P'Choke before starting Phase 2+ changes.
