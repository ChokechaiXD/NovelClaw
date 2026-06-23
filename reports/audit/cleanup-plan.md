# NovelClaw Cleanup Plan

Based on audits in `reports/audit/` generated 2026-06-24
Scope: safe, incremental improvements only. No architecture rewrites.

## P0 — Fix Immediately (Safe, Low Risk)

### 1. Remove admin.v3.js if dead
- Check if `index.html` loads `admin.v3.js`
- If not loaded, archive or delete
- Risk: Low — removing an unused file

### 2. Normalize error response shape
- Current: mixed shapes (`{error: "msg"}` vs `{ok:false, error:{}}`)
- Target: `{ ok: false, error: { code: string, message: string } }`
- Risk: Low — only changes error paths

### 3. Add param validation helpers
- Create `safeSlug(s)`, `safeChapterNum(n)`, `safeLang(l)` in server.js
- Replace inline validation in log route and chapter routes
- Risk: Low — validation only, no behavior change

### 4. Add `tools/schema/` with JSON schemas
- `chapter.schema.json` — for `.th.json` / `.cn.json` files
- `job.schema.json` — for `jobs/*.json`
- `novel.schema.json` — for `novel.json`
- Risk: Low — adds validation, doesn't change data

### 5. Standardize localStorage keys
- Current: mixed prefixes
- Target: `nc-theme`, `nc-fontSize`, `nc-lineHeight`, etc.
- Add migration for old keys
- Risk: Medium — affects reader settings persistence

## P1 — Polish After P0

### 6. Migrate inline styles to CSS classes
- 108 inline styles found in JS
- Priority: repeated patterns (badges, buttons, layout divs)
- Risk: Low — CSS only, no behavior change

### 7. Remove hardcoded colors from non-token areas
- 72 color values outside :root tokens
- Replace with CSS variable references
- Risk: Low — visual consistency improvement

### 8. Standardize section/page padding
- Replace `style="margin-top:var(--space-md);"` with CSS class
- Risk: Very Low — visual tweak

### 9. Add JS syntax check to CI
- `find public/js -name '*.js' | xargs -n1 node --check`
- Already partly done in workflow
- Risk: None — CI only

### 10. Archive old test-only slugs
- Check if `test-force`, `test-force-success` still have novel.json
- If yes, move to `novels/_archive/`
- Risk: Low — hidden from frontend already

## P2 — Future (Documented, Not Started)

### 11. Component extraction
- Extract repeated: section header, stat card, table, command pill, toast
- Create `reader/public/js/components/`
- Risk: Medium — JS refactor that touches render code

### 12. CSS file splitting
- Break `design-system.css` (1,575 lines) into sections
- Or at minimum add section headers
- Risk: Medium — CSS load order matters

### 13. Quality profile system
- Add `qualityProfile` config per novel/target language
- Multi-pass pipeline (--passes 2, --passes 3)
- Risk: High — touches translation core

### 14. Search index improvements
- Measure + optimize rebuild time
- Add incremental rebuild
- Split index by language
- Risk: Medium — index format change

### 15. Documentation
- ARCHITECTURE.md, COMMANDS.md, DATA_SCHEMA.md
- Risk: None — docs only

## Risk Summary

| Priority | Items | Total Risk |
|----------|-------|------------|
| P0 | 5 | Low — validation + schema + dead code |
| P1 | 5 | Low — CSS + CI + polish |
| P2 | 5 | Low-Medium — extraction + splitting + quality |

## Rollback Plan

- All changes are reversible via `git checkout`
- Stable tag: `stable-novelctl-foundation-v1`
- Before each P0 change: `git stash` or branch
- After each P0 change: `npm test && npm run test:api`
