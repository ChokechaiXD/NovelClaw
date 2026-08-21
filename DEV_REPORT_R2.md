# DEV_REPORT_R2 — Commit stale pre-existing changes

**Agent:** SORA | **Round:** 2 (from MIKA) | **Commit:** `819d5df`

## Scope
Pre-existing uncommitted changes (predated round 1): `internal/web/static/app.js`, `internal/web/static/style.css`, `run.bat`.
Round-1 artifacts (`qa_*.py`, `QA_REPORT*.md`, `DEV_REPORT*.md`, `novels/qa_full_scan.json`) left untracked as instructed.

## Diff analysis

### app.js (1 line)
Toast message typo fix: `เสร็จสิ้่น` → `เสร็จสิ้้น` (sara-i + mai-tho stacking corrected). Cosmetic, safe.

### style.css (+5 lines)
Adds `--bg-hover` to all 4 themes (dark/sepia/light/black) and `--radius-full: 999px` to root.
**Not dead code:** these vars are already referenced — `--bg-hover` at style.css:623 and index.html:432, `--radius-full` at style.css:582/631. Before this change they resolved to undefined `var()` (silent fallback). This is a real fix.

### run.bat (+11/-5)
- Always rebuilds (was: build only if exe missing) with `|| echo [WARN]` fallback to existing exe.
- New port-4173 check via `netstat | findstr ":4173 .*LISTENING"` — warns and exits /b 1 if already in use.
- Minor: no trailing newline at EOF (harmless for .bat).

## Verification (real runs)
- `go build ./...` → OK
- `go test ./... -count=1` → all packages pass (api 8.2s, config 3.3s, scraper 5.8s, storage 4.1s, translator 2.4s)
- JS/CSS eyeballed: no syntax breakage; vars confirmed in use.

## Decision
All 3 changes legit and low-risk → committed as ONE commit:
`fix: define missing --bg-hover/--radius-full CSS vars, toast typo, run.bat port-4173 guard`

Nothing held back.
