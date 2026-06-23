# Quality Tooling Baseline — Phase B

## Existing Tooling

### ✅ check_all.py (Python quality runner)
- Compiles all Python files (py_compile)
- Runs novelctl smoke tests (no LLM)
- Checks novelctl commands (status/report/check)
- JS syntax checks all reader/public/js/*.js
- API smoke tests (if server running on :4173)
- **Exit code**: 0 = pass, 1 = fail

### ✅ CI Workflow (.github/workflows/ci.yml)
- Runs on: push/PR to main
- OS: ubuntu-latest
- Node.js 22 + Python 3.12
- `npm install` in reader/
- `python tools/check_all.py`
- Status: Functional

### ✅ Pre-commit Hook (.githooks/pre-commit)
- Validates staged chapter JSON files
- Checks: JSON parse, Pydantic schema, CN/JP leaks, validation warnings
- Blocks commit on errors, allows warnings
- Requires: `git config core.hooksPath .githooks`

### ✅ npm Scripts (reader/package.json)
| Script | Command | Status |
|--------|---------|--------|
| `start` | `node server.js` | ✅ |
| `dev` | `node --watch server.js` | ✅ |
| `check` | Syntax-check all JS files (explicit list) | ✅ Works |
| `syntax` | Node-based find + syntax check | ⚠️ Windows-only |
| `test` | `node --check server.js` | ✅ |
| `test:api` | `node tests/test-api.js` | ✅ Needs running server |

### Missing (Optional)
- ESLint — not configured (vanilla JS, no build step)
- Prettier — not configured
- ruff — not in pyproject.toml
- mypy/pyright — not configured

## Recommended Improvements

### 1. Fix `syntax` Script (Cross-Platform)
**Current**: Uses Windows `dir /s /b` — breaks on Linux/CI
**Recommended**: Replace with Node-based glob:

```json
"syntax": "node -e \"const{execSync}=require('child_process');const{globSync}=require('fs');const files=globSync('public/js/**/*.js',{cwd:'reader'});files.forEach(f=>{try{execSync('node --check '+f,{cwd:'reader',stdio:'pipe'})}catch(e){process.exit(1)}});console.log('JS syntax: OK')\""
```

### 2. Add Python Ruff to pyproject.toml
```toml
[tool.ruff]
target-version = "py312"
line-length = 120
```

### 3. Test Baseline One-Liner
```bash
python tools/check_all.py
```
This should be the single command that verifies everything before any commit.

## Current Test Results (Smoke)

As of foundation v1 (2026-06-24):
- novelctl smoke tests: ✅ 4/4 pass
- Python compile: ✅ 21/21 pass
- novelctl commands: ✅ 3/3 pass
- JS syntax: ✅ 9/9 pass
- server.js syntax: ✅ 1/1 pass

## Phase B Deliverables

| File | Status |
|------|--------|
| This report (`reports/audit/tooling-baseline.md`) | ✅ |
| CI workflow `.github/workflows/ci.yml` | ✅ Already exists |
| `npm run syntax` cross-platform fix | ⬜ Not yet done |
| Python ruff config | ⬜ Optional |
