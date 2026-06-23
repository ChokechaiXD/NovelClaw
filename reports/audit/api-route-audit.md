# API Route Audit — Phase A

## Overview

Server: Express.js, 523 lines (reduced from 1,019 in architecture cleanup round)
Middleware: helmet, express.json (5mb limit)
Auth: Bearer token via `requireAdmin` middleware
SPA fallback: All non-API routes serve index.html

## Route Security

### ✅ Protected (requireAdmin)
- `POST /api/novel/:slug/glossary/save`
- `POST /api/novel/update`
- `POST /api/novel/:slug/delete`
- `POST /api/novel/:slug/chapter/:num/save`
- `POST /api/novel/:slug/chapter/:num/delete`
- `POST /api/invalidate-cache`
- `GET /api/admin/jobs`
- `GET /api/admin/logs/:slug/:num`

### ✅ Public (no auth needed — read-only)
- `GET /api/novels` — novel list (filtered in frontend for test novels)
- `GET /api/novel/:slug/meta` — novel metadata
- `GET /api/novel/:slug/chapters` — chapter index
- `GET /api/novel/:slug/chapters/search` — search (rate-limited in JS: max 100 results, 200 char query)
- `GET /api/novel/:slug/chapter/:num` — single chapter
- `GET /api/novel/:slug/source/:num` — source file
- `GET /api/novel/:slug/glossary` — glossary (md)
- `GET /api/novel/:slug/glossary/data` — glossary (json)
- `GET /api/novel/:slug/characters` — characters
- `GET *` — SPA fallback

## Path Traversal Protection

### ✅ Slug validation
- `app.param('slug')` in server.js checks `/^[a-zA-Z0-9_-]+$/` — rejects path traversal
- `assertValidSlug()` in paths.js — double-checked, same regex
- `chapter-repo.js` scanChapters() also validates `[a-zA-Z0-9_-]+`
- `listChapters()` validates `[a-zA-Z0-9_-]+`

### ✅ Log route param validation
- `SLUG_RE_LOOSE` = `/^[a-z0-9-]+$/i` 
- `NUM_RE` = `/^\d{1,5}$/`
- Both checked before path construction

### ✅ Chapter number validation
- `parseInt(req.params.num, 10)` + `Number.isNaN()` check on all chapter routes
- `chapterPath()` and `chapterRepo` methods use `pad()` internally

### 🟡 Source route (`/source/:num`)
- `assertValidSlug()` called, `parseInt` on num
- Path uses `sourceMdPath()` which joins safely

## Error Response Shape

### Current: Inconsistent
- Some routes return `{ error: "message" }`
- Admin routes try to return `{ ok: false, error: {...} }`
- No standardized shape across all routes

### Missing Standardization
- No `error.code` field
- No consistent HTTP status mapping for business logic errors
- Frontend does `err.message` for display — works but fragile

## Admin Startup Guard

### ✅ Fixed (from architecture cleanup)
```
if (BIND_HOST === '0.0.0.0' && !ADMIN_TOKEN) {
    process.exit(1);  // LAN mode requires token
}
```

## Issues Found

### 1. `requireAdmin` Allows All Requests When Token Not Set
**Line**: server.js:65
**Code**: `if (!ADMIN_TOKEN) return next();`
When ADMIN_TOKEN is empty (localhost-only), the middleware passes all requests. This is intentional for local dev but means:
- Local-only access has zero admin auth
- If HOST is 127.0.0.1, no token needed
- If HOST is 0.0.0.0, startup prevents without token

**Assessment**: Acceptable design for LAN/local mode, but worth documenting.

### 2. `readJsonDir` Error Handling
**Line**: server.js:353-367
Catches all errors silently. If a JSON file is corrupted, the error is swallowed. Not a security issue but reduces debuggability.

### 3. Log Viewer Content Limit
**Line**: server.js:401
```js
content: isJson ? JSON.parse(content) : content.slice(0, 50000)
```
Text files are capped at 50KB. JSON files are NOT capped — large JSON could blow up response size. Risky if translation log JSON grows large.

### 4. POST Glossary Save Uses `spawn()` on User Data
**Line**: server.js:224-244
Writes `req.body` to the spawned process's stdin. If glossary.py crashes, the partial stdin data might cause issues. Uses timeout=10_000 which could be short for large glossaries.

### 5. No Request Size Validation Beyond JSON Body
Size limit = 5mb for JSON body, but no per-field length validation on any POST route.

## Recommended Fixes

1. Add `err.code` to all error responses
2. Cap JSON log file output (log route)
3. Add field-level length validation to POST endpoints
4. Standardize error shape: `{ ok: true, data: ... }` / `{ ok: false, error: { code, message } }`
5. Add content-type validation on POST endpoints
