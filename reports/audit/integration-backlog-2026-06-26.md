# NovelClaw Integration Backlog

Date: 2026-06-26

## Snapshot

- Source audited: `reader/`, `tools/`, `tests/`
- Scope size: 101 source/doc/test files, about 17,088 lines
- Largest files:
  - `reader/public/design-system.css` — 1,708 lines
  - `reader/public/js/pages/admin.js` — 1,382 lines
  - `tools/translate.py` — 1,175 lines
  - `reader/server.js` — 1,124 lines
- Current smoke status:
  - `npm run check` passes
  - `npm run test:api` passes 10/10
  - `tools/validate_data.py --novel global-descent` passes

## Highest-Leverage Fixes

### P0: Split Local Personal Mode From Shareable LAN Mode

Problem:
- `reader/server.js` defaults to `HOST=0.0.0.0`, but comments still say default localhost.
- `requireAdmin()` bypasses all admin auth when `ADMIN_TOKEN` is unset.
- Several write/spawn routes do not use `requireAdmin`.

Unprotected write or spawn routes:
- `POST /api/local/open-editor`
- `POST /api/novel/:slug/glossary/add`
- `POST /api/local/translate-term`
- `POST /api/local/state`
- `POST /api/local/llm-config`
- `POST /api/novel/:slug/translate/single`
- `POST /api/novel/:slug/translate/batch`

Recommended decision:
- Default to localhost personal mode.
- Require `ADMIN_TOKEN` when `HOST=0.0.0.0`, or introduce an explicit `TRUSTED_LAN=true` escape hatch.
- Protect all routes that write files, spawn processes, open editors, or mutate config.

Acceptance criteria:
- LAN mode cannot start with write APIs open unless explicitly authorized.
- All write/spawn/config routes have a consistent guard policy.
- API smoke tests cover both allowed and rejected write behavior.

### P0: Route Translation Through `novelctl.py`

Problem:
- Reader/Admin translate routes call `tools/translate.py` directly.
- Project rules say translation must go through `tools/novelctl.py translate`.
- UI console still says it is calling `python tools/translate.py`.

Files:
- `reader/server.js`
- `reader/public/js/api.js`
- `reader/public/js/pages/admin.js`
- `reader/public/js/pages/novel.js`
- `reader/public/js/pages/reader.js`

Recommended move:
- Replace `/translate/single` and `/translate/batch` internals with `novelctl.py --slug <slug> translate <range>`.
- Decide UI mode mapping: quick translate = safe, batch = autopilot, retry = strict/force.

Acceptance criteria:
- No Reader/Admin route spawns `translate.py` directly.
- The UI command preview names `novelctl.py`.
- Chapter index and cache are updated only through canonical workflow.

### P1: Disable Or Clearly Mark Mock Web Import

Problem:
- `POST /api/novel/import-web` writes real novel/chapter files using generated mock content.
- UI presents it as web scraping.

Recommended move:
- Either remove the web import tab until real scraping exists, or label it as "Mock/Demo" and write only to a test slug.

Acceptance criteria:
- Production novel slugs cannot be populated with mock scraped text by accident.
- Import UI clearly distinguishes text import, real scrape, and demo/mock.

## Structural Refactors

### P1: Decompose `reader/public/js/pages/admin.js`

Problem signals:
- 1,382 lines
- 147 inline `style=` occurrences
- 30 `innerHTML` assignments
- 26 `alert()` calls
- Multiple responsibilities: dashboard, novels, chapters, glossary, jobs, logs, translate, import, bookmarks

Recommended split:
- `admin/dashboard.js`
- `admin/novels.js`
- `admin/chapters.js`
- `admin/glossary.js`
- `admin/jobs.js`
- `admin/logs.js`
- `admin/translate.js`
- `admin/import.js`
- Shared `admin/components.js` for nav, tables, form rows, status console, destructive confirm.

Acceptance criteria:
- Each admin page file stays under about 300 lines.
- No new admin page uses raw `alert()` for expected errors.
- Repeated table/status/card patterns are shared.

### P1: Move Inline Layout Styles Into CSS Classes

Problem signals:
- `admin.js`: 147 inline styles
- `pages.js`: 27 inline styles
- `reader.js`: 27 inline styles
- `home.js`: 8 inline styles

Recommended sequence:
- Admin dashboard cards and grids first.
- Admin form/control rows next.
- Reader modal/context menu last.

Acceptance criteria:
- Layout spacing uses design-system classes/tokens.
- Components can be visually adjusted without editing JS templates.
- Mobile layout no longer depends on one-off inline widths.

### P1: Split `reader/server.js`

Problem:
- 1,124 lines, mixing public read APIs, admin write APIs, local dev APIs, import, translation, jobs/logs, startup behavior.

Recommended split:
- `routes/public.js`
- `routes/admin.js`
- `routes/local.js`
- `routes/import.js`
- `routes/translate.js`
- `services/llm-config.js`
- `services/process-runner.js`

Acceptance criteria:
- `server.js` only wires middleware, routes, startup, and shutdown.
- Route modules expose a small `register(app, deps)` function.
- Process spawning is centralized and testable.

## Cleanup Candidates

### delete: `tools/_tmp_fix_check.py`

Reason:
- Debug script for chapters 12 and 58.
- Hardcoded `global-descent`.
- Not referenced by tests or tooling.

Replacement:
- Delete after confirming no active manual workflow uses it.

### delete or rewrite: `tools/_build_all_cn.py`

Reason:
- Hardcoded stale absolute path: `C:\Users\BlankScreen\Workspace\Projects\NovelClaw\...`
- Hardcoded `global-descent`.
- Overlaps with current canonical chapter/source tooling.

Replacement:
- Either delete, or rewrite as a parameterized `novelctl`/migration command.

### delete: `reader/lib/render.js`

Reason:
- `reader/lib/test-renderer.js` is the test renderer used by tests.
- `render.js` is not referenced by current tests.
- Both export the same concept.

Replacement:
- Keep `test-renderer.js`; remove `render.js` after one final import check.

### verify: unused CSS classes

Static cross-reference found 28 possibly unused classes, including:
- `c-app__header`
- `c-main`
- `c-rightbar`
- `c-sidebar__link`
- `c-sidebar__link--active`
- `c-settings__group`
- `c-profile__avatar`
- `reader-exit-btn`
- `reader-stat`

Replacement:
- Remove in small batches only after browser screenshot verification.

## Workflow Gaps

### API Test Coverage

Currently covered:
- Public novel/chapter/glossary/search routes
- Chapter save/delete smoke path

Missing:
- LLM config route
- Translation route behavior
- Import-file route
- Import-web blocked/mock behavior
- Local state sync
- Auth policy in LAN mode

### State Model

Current:
- Browser `localStorage`
- Server `reader/local_state.json`
- `llm.json`
- Runtime jobs/logs

Risk:
- Personal state and shared LAN state are not clearly separated.

Recommended move:
- Define state ownership:
  - user reading state: local browser first, optional sync
  - operator config: server-side `llm.json`
  - runtime jobs/logs: server-only

## Suggested Order

1. Security/mode policy: localhost vs LAN, route guards.
2. Translation route: use `novelctl.py`.
3. Mock import: disable or label clearly.
4. Admin split: extract one admin page at a time.
5. CSS cleanup: move admin inline styles into classes.
6. Dead code cleanup: delete temp/duplicate files in small batches.
7. Browser verification pass: desktop/mobile reader/admin/import/settings.

## Do Not Start With

- Full visual redesign.
- Renaming all localStorage keys.
- Removing legacy chapter compatibility.
- Deleting CSS classes without browser verification.
- Refactoring `translate.py` before the Reader/Admin boundary is fixed.
