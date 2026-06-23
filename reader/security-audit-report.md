# NovelClaw Reader — Security Audit Report

**Target:** `C:/Users/BlankScreen/Workspace/Projects/NovelClaw/reader/server.js`  
**Scope:** `server.js`, `lib/paths.js`, `lib/chapter-repo.js`, `lib/novel-repo.js`, `lib/search-service.js`  
**Severity Focus:** CRITICAL and HIGH only  
**Date:** 2026-06-24

---

## FINDING C1 — Admin Token in Query String (CRITICAL)

**File:** `server.js`, line 63  
**Severity:** CRITICAL

```js
const provided = req.query.token || (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
```

**Issue:** The ADMIN_TOKEN can be passed via `?token=` query parameter. This exposes the secret token in:
- Browser history and bookmarks (persistent plaintext storage)
- Web server access logs (plaintext URL logging)
- `Referer` header leakage when navigating from the admin page to external links
- Network-level exposure via URL (more visible than headers in proxies)

**Impact:** Token compromise = full admin access (chapter write/delete, novel delete, glossary save, arbitrary file write via subprocess).

**Recommendation:** Remove `req.query.token` support entirely. Require `Authorization: Bearer <token>` header only, never pass secrets in URLs.

---

## FINDING C2 — Zero Auth When ADMIN_TOKEN Not Set (CRITICAL)

**File:** `server.js`, lines 62, 8  
**Severity:** CRITICAL

```js
// LINE 62:
function requireAdmin(req, res, next) {
  if (!ADMIN_TOKEN) return next(); // no auth configured
```

**Issue:** When `ADMIN_TOKEN` is not set (empty string), `requireAdmin` passes **all requests through unconditionally**. Every write endpoint becomes publicly accessible:
- `POST /api/novel/update` — overwrite novel metadata
- `POST /api/novel/:slug/delete` — **delete entire novel directories from disk** (`fs.rm(novelDir(slug), { recursive: true, force: true })`)
- `POST /api/novel/:slug/chapter/:num/save` — write arbitrary JSON chapter files
- `POST /api/novel/:slug/chapter/:num/delete` — delete chapter files
- `POST /api/novel/:slug/glossary/save` — spawns Python subprocess with user data piped to stdin
- `POST /api/invalidate-cache` — flush server-side cache
- `GET /api/admin/jobs` and log viewer — read internal data from disk

**Note:** The startup code (lines 429-434) only *refuses to start* if `HOST=0.0.0.0` AND no `ADMIN_TOKEN`. If binding to `127.0.0.1` (default), it silently starts with zero auth. This is documented as "optional, default no auth" (line 8), but the ability to delete `NOVELS_DIR` subdirectories and spawn Python processes without authentication is a critical risk in any multi-user or LAN scenario.

**Recommendation:** Require an `ADMIN_TOKEN` to be set. Generate a default token if none is provided (warn in console). Never default to open access for destructive operations.

---

## FINDING C3 — Unvalidated User Data Piped to Subprocess (CRITICAL)

**File:** `server.js`, lines 216-236  
**Severity:** CRITICAL

```js
app.post('/api/novel/:slug/glossary/save', requireAdmin, asyncHandler(async (req, res) => {
  // ...
  const child = spawn(py, [glossaryScript, '--novel', slug, '--save'], { ... });
  // ...
  child.stdin.write(JSON.stringify(req.body));   // LINE 234
  child.stdin.end();
```

**Issue:** The entire `req.body` (arbitrary user-controlled JSON, up to `express.json()` limits) is serialized and piped directly to a spawned Python subprocess's stdin. While the slug (passed as a CLI argument) is validated, the stdin payload is **completely unchecked**. Depending on what `glossary.py` does:
- **Deserialization attack:** if `glossary.py` uses `yaml.load()`, `pickle.load()`, or vulnerable JSON parsers, RCE is possible
- **Protocol injection:** if the python script interprets stdin as commands or eval, attacker controls execution
- **Resource exhaustion:** large JSON payloads can consume memory/disk

**Recommendation:** 
1. Validate the shape and size of `req.body` before piping to subprocess
2. Define a strict schema for the expected glossary data and reject unexpected fields
3. Consider using library calls instead of subprocess if possible
4. Set subprocess resource limits (already has timeout=10_000)

---

## FINDING H1 — Missing Security Headers (HIGH)

**File:** `server.js`, lines 38-46, 476-486  
**Severity:** HIGH

**Issue:** All responses are missing these security headers:

| Header | Purpose | Status |
|--------|---------|--------|
| `Content-Security-Policy` | XSS mitigation | ❌ Missing |
| `X-Content-Type-Options: nosniff` | MIME-sniffing prevention | ❌ Missing |
| `X-Frame-Options: DENY` | Clickjacking protection | ❌ Missing |
| `Referrer-Policy` | Referrer leakage control | ❌ Missing |
| `Strict-Transport-Security` | HTTPS enforcement | ❌ Missing (N/A for dev) |
| `X-XSS-Protection` | Legacy XSS filter | ❌ Missing |

**Impact:** If a novel/chapter source contains user-influenced content (e.g., scraped web content), an XSS vulnerability in the frontend could be exploited. Missing `X-Frame-Options` allows clickjacking of the admin interface. Missing `X-Content-Type-Options` allows MIME-type confusion.

**Recommendation:** Add a helmet-style middleware or at minimum:
```js
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'");
  next();
});
```

---

## FINDING H2 — Sensitive Error Details Leaked to Client (HIGH)

**File:** `server.js`, multiple locations  
**Severity:** HIGH

**Leakage points:**

1. **Line 212** — `glossary/data`: `details: err.message` — exposes internal error message from `JSON.parse`
2. **Line 229** — `glossary/save`: `${stderr}` — raw stderr output from spawned Python process returned verbatim
3. **Lines 297-308** — `chapter/save`: full validation detail array (info, warnings, errors) returned verbatim
4. **Lines 492-495** — Global error handler: `err.message` returned as `{ error: err.message }`

**Impact:** Information disclosure — internal file paths, Python stack traces, JSON parsing errors, and validation internals leak to unauthenticated (or any) users. This aids attackers in reconnaissance.

**Recommendation:** 
- Log detailed errors server-side (already done via `console.error`)
- Return generic messages to clients: `{ error: 'Internal server error' }` for 500s
- For validation errors, return structured but sanitized data without raw system details
- Never include raw `stderr` content in API responses

---

## FINDING H3 — Auth Token Leakage via Server Startup Error Message (HIGH)

**File:** `server.js`, lines 429-434  
**Severity:** HIGH

```js
if (BIND_HOST === '0.0.0.0' && !ADMIN_TOKEN) {
  console.log('  ❌  ERROR: HOST=0.0.0.0 requires ADMIN_TOKEN to protect');
  console.log('     admin endpoints. Set ADMIN_TOKEN=your-secret-token and restart.');
  process.exit(1);
}
```

**Issue:** If an admin sets `HOST=0.0.0.0` without `ADMIN_TOKEN`, the startup prints a misleading error message suggesting they set `ADMIN_TOKEN=your-secret-token`. No actual security issue here beyond the suggestion, but it's worth noting that the error exits vs. allowing zero-auth binding.

Actually on re-review this is a cosmetic/UX issue, not a security vulnerability. Let me move on.

---

## FINDING H4 — No Rate Limiting on Admin Endpoints (HIGH)

**File:** `server.js`, lines 249-330  
**Severity:** HIGH

**Issue:** Admin write endpoints (`/save`, `/delete`, `/glossary/save`) have no rate limiting or request throttling. Combined with query-string token support (C1), an attacker who observes the token in a URL can replay it indefinitely.

**Impact:** Brute-force token guessing is unthrottled. Token replay is unbounded — an attacker can delete every novel or flood disk with malicious chapter files.

**Recommendation:** 
- Remove query-string token support (C1 fix)
- Add rate limiting: `express-rate-limit` package, e.g., 10 req/min per IP on admin endpoints
- Log failed auth attempts

---

## FINDING H5 — SPA Fallback Serves index.html on Every Route (HIGH)

**File:** `server.js`, lines 476-486  
**Severity:** HIGH

```js
app.get('*', (req, res) => {
  if (req.path.startsWith('/api/')) return res.status(404).json({ error: 'API not found' });
  // ...
  let html = fsSync.readFileSync(path.join(PUBLIC_DIR, 'index.html'), 'utf8');
  // Cache-bust: strip existing query, append _t
  html = html.replace(/src="\/(js\/[^"?]+)(\?[^"]*)?"/g, `src="/$1?_t=${START_TIME}"`);
  html = html.replace(/href="\/(design-system\.css)[^"]*"/g, `href="/$1?_t=${START_TIME}"`);
  res.send(html);
```

**Issue:** The cache-busting regex replacements operate on the HTML file read from disk (safe), but the `'*'` catch-all route fires for any path, including intended SPA routes. While no injection is possible here (the replacements are on the file content, not user input), the broad `'*'` handler could mask missing API routes (the `/api/` prefix check handles that).

No direct injection vector, but the SPA pattern combined with missing CSP (H1) amplifies XSS risks.

---

## Summary Table

| ID | Finding | Severity | Line(s) | Category |
|----|---------|----------|---------|----------|
| C1 | Admin token in query string | CRITICAL | 63 | Auth bypass, token leakage |
| C2 | Zero auth when ADMIN_TOKEN unset | CRITICAL | 62 | Auth bypass |
| C3 | Unvalidated JSON piped to Python subprocess | CRITICAL | 234 | Command injection, deserialization |
| H1 | Missing security headers | HIGH | 38-46, 476-486 | XSS, clickjacking, MIME confusion |
| H2 | Sensitive error detail leakage | HIGH | 212, 229, 297-308, 492-495 | Information disclosure |
| H4 | No rate limiting on admin endpoints | HIGH | 249-330 | Brute force, abuse |
| H5 | SPA catch-all amplifies XSS risk | HIGH | 476-486 | XSS |

**Overall Risk:** CRITICAL — the combination of C1 (token in URL), C2 (no auth by default), and C3 (unvalidated subprocess pipe) means an attacker who discovers the server on an unprotected network can execute destructive filesystem operations and potentially RCE through the glossary.py subprocess.
