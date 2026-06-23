// NovelClaw Reader — Express server using lib/ repositories
//
// Usage: node server.js   (then open http://localhost:4173)
// Env:
//   PORT             — listening port (default 4173)
//   HOST             — bind address (default 127.0.0.1, set 0.0.0.0 for LAN)
//   NOVELCLAW_ROOT   — path to novels/ directory (default ../novels)
//   ADMIN_TOKEN      — bearer token for write endpoints (optional, default no auth)
//   AUTO_KILL_PORT   — set 'true' to auto-kill old process (default off)

const express = require('express');
const helmet = require('helmet');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const fsSync = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

// ── Lib modules ────────────────────────────────────────────────────
const { pad, assertValidSlug, SLUG_RE, novelJsonPath, sourceMdPath,
        glossaryJsonPath, glossaryMdPath, charactersMdPath, NOVELS_DIR } = require('./lib/paths');
const chapterRepo = require('./lib/chapter-repo');
const novelRepo = require('./lib/novel-repo');
const searchService = require('./lib/search-service');
const { parseMarkdownToBlocks } = require('./lib/blocks');

// Re-export for tests
module.exports = { parseMarkdownToBlocks, chapterRepo, novelRepo, searchService };

// ── Config ─────────────────────────────────────────────────────────
const PORT = Number(process.env.PORT) || 4173;
const BIND_HOST = process.env.HOST || '127.0.0.1';
const PUBLIC_DIR = path.resolve(__dirname, 'public');
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || '';

// ── Middleware ─────────────────────────────────────────────────────
const app = express();
app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use(express.json({ limit: '5mb' }));

// Static files with cache disabled for dev
app.use(express.static(PUBLIC_DIR, {
  etag: false, lastModified: false,
  setHeaders: (res) => {
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
  },
}));

// Slug validation param middleware
app.param('slug', (req, res, next, slug) => {
  if (!SLUG_RE.test(slug)) {
    return res.status(400).json({ error: 'Invalid slug format' });
  }
  next();
});

// Async route wrapper
const asyncHandler = (fn) => (req, res, next) =>
  Promise.resolve(fn(req, res, next)).catch(next);

// Admin auth middleware
function requireAdmin(req, res, next) {
  if (!ADMIN_TOKEN) return next(); // no auth configured
  const provided = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  if (!provided) {
    return res.status(401).json({ error: 'Unauthorized — provide Authorization: Bearer <token>' });
  }
  if (provided.length === ADMIN_TOKEN.length && crypto.timingSafeEqual(Buffer.from(provided), Buffer.from(ADMIN_TOKEN))) {
    return next();
  }
  res.status(401).json({ error: 'Unauthorized — invalid token' });
}

// File read helper
async function readTextOrNull(filepath) {
  try { return await fs.readFile(filepath, 'utf8'); }
  catch (err) { if (err.code === 'ENOENT') return null; throw err; }
}

// ── Novel listing and metadata ─────────────────────────────────────

app.get('/api/novels', asyncHandler(async (_req, res) => {
  const slugs = await novelRepo.listNovels();
  const novels = await Promise.all(
    slugs.map(async (slug) => {
      const meta = await novelRepo.getNovelMeta(slug);
      const chapters = await chapterRepo.listChapters(slug);
      const translatedCount = chapters.filter(c => c.isTranslated).length;
      return {
        slug,
        title: meta.title || slug,
        translatedTitle: meta.translated_title || meta.translatedTitle || '',
        author: meta.author || '',
        source_lang: meta.source_lang || 'cn',
        target_lang: meta.target_lang || 'th',
        chapterCount: chapters.length,
        translatedChapters: translatedCount,
        totalChapters: parseInt(meta.total_chapters, 10) || chapters.length,
        status: meta.status || 'unknown',
        description: meta.description || '',
      };
    }),
  );
  res.json(novels);
}));

app.get('/api/novel/:slug/meta', asyncHandler(async (req, res) => {
  const meta = await novelRepo.getNovelMeta(req.params.slug);
  const chapters = await chapterRepo.listChapters(req.params.slug);
  let enriched = {};
  try {
    enriched = JSON.parse(await fs.readFile(novelJsonPath(req.params.slug), 'utf8'));
  } catch {}
  res.json({
    ...meta, ...enriched, slug: req.params.slug,
    chapterCount: chapters.length,
    translatedChapters: chapters.filter(c => c.isTranslated !== false).length,
  });
}));

// ── Chapter listing ────────────────────────────────────────────────

app.get('/api/novel/:slug/chapters', asyncHandler(async (req, res) => {
  const chapters = await chapterRepo.listChapters(req.params.slug);
  res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.json({ slug: req.params.slug, chapters });
}));

// ── Chapter search ─────────────────────────────────────────────────

app.get('/api/novel/:slug/chapters/search', asyncHandler(async (req, res) => {
  const q = (req.query.q || '').toString().trim();
  const mode = (req.query.mode || 'title').toString();
  const lang = (req.query.lang || 'all').toString();
  const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
  if (!q) return res.json([]);
  if (q.length > 200) return res.status(400).json({ error: 'Query too long (max 200 chars)' });
  if (!['title', 'content', 'all'].includes(mode)) {
    return res.status(400).json({ error: 'Unknown mode (use title|content|all)' });
  }

  let results = [];
  const all = await chapterRepo.listChapters(req.params.slug);

  if (mode === 'title' || mode === 'all') {
    const { results: titleResults, skip } = searchService.searchTitle(all, q, limit);
    results = titleResults;
    if (mode === 'title') return res.json(results);
  }

  if (mode === 'content' || mode === 'all') {
    const skip = new Set(results.map(r => r.num));
    const contentResults = await searchService.searchContent(req.params.slug, q, { limit, lang, skip });
    if (mode === 'content') return res.json(contentResults);
    results = [...results, ...contentResults];
  }

  res.json(results.slice(0, limit));
}));

// ── Single chapter ─────────────────────────────────────────────────

app.get('/api/novel/:slug/chapter/:num', asyncHandler(async (req, res) => {
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  const lang = (req.query.lang || 'th').toString();
  const result = await chapterRepo.getChapter(req.params.slug, num, lang);
  if (!result) return res.status(404).json({ error: 'Chapter not found' });

  res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');

  res.json({
    slug: req.params.slug,
    num,
    title: result.title,
    isJson: result.isJson,
    paragraphs: result.paragraphs || [],
    blocks: result.blocks || [],
    source: result.source || '',
    lang: result.lang || 'cn',
    notes: result.notes || [],
    score: 100,
    isTranslated: result.isTranslated !== false,
    validation: { valid: true, errors: [], warnings: [], info: [] },
  });
}));

// ── Source file ────────────────────────────────────────────────────

app.get('/api/novel/:slug/source/:num', asyncHandler(async (req, res) => {
  assertValidSlug(req.params.slug);
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  const raw = await readTextOrNull(sourceMdPath(req.params.slug, num));
  if (raw === null) return res.status(404).json({ error: 'Source not found' });
  res.type('text/plain').send(raw);
}));

// ── Glossary ───────────────────────────────────────────────────────

app.get('/api/novel/:slug/glossary', asyncHandler(async (req, res) => {
  assertValidSlug(req.params.slug);
  const raw = await readTextOrNull(glossaryMdPath(req.params.slug));
  if (raw === null) return res.status(404).json({ error: 'No glossary' });
  res.type('text/plain').send(raw);
}));

app.get('/api/novel/:slug/glossary/data', asyncHandler(async (req, res) => {
  assertValidSlug(req.params.slug);
  const raw = await readTextOrNull(glossaryJsonPath(req.params.slug));
  if (raw === null) return res.json({ terms: [] });
  try {
    const data = JSON.parse(raw);
    res.json({ terms: data.terms || [] });
  } catch (err) {
    res.status(500).json({ error: 'Invalid glossary.json', details: err.message });
  }
}));

app.post('/api/novel/:slug/glossary/save', requireAdmin, asyncHandler(async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const glossaryScript = path.join(__dirname, '..', 'tools', 'glossary.py');
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const child = spawn(py, [glossaryScript, '--novel', slug, '--save'], {
    cwd: path.join(__dirname, '..'), windowsHide: true, timeout: 10_000,
  });
  let stdout = '', stderr = '';
  child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
  child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
  child.on('close', (code) => {
    if (code !== 0) {
      return res.status(500).json({ error: `glossary.py exited ${code}: ${stderr}` });
    }
    chapterRepo.invalidateAll(slug);
    res.json({ ok: true });
  });
  child.stdin.write(JSON.stringify(req.body));
  child.stdin.end();
}));

// ── Characters ─────────────────────────────────────────────────────

app.get('/api/novel/:slug/characters', asyncHandler(async (req, res) => {
  assertValidSlug(req.params.slug);
  const raw = await readTextOrNull(charactersMdPath(req.params.slug));
  if (raw === null) return res.status(404).json({ error: 'No characters' });
  res.type('text/plain').send(raw);
}));

// ── Admin novel update ─────────────────────────────────────────────

app.post('/api/novel/update', requireAdmin, asyncHandler(async (req, res) => {
  const { slug, title, author, source_lang, target_lang, status, total_chapters, translatedTitle } = req.body;
  if (!slug || !SLUG_RE.test(slug)) {
    return res.status(400).json({ error: 'Invalid slug format' });
  }
  await novelRepo.saveNovelMeta(slug, { title, author, source_lang, target_lang, status, total_chapters, translatedTitle });
  res.json({ ok: true });
}));

// ── Admin delete novel ─────────────────────────────────────────────

app.post('/api/novel/:slug/delete', requireAdmin, asyncHandler(async (req, res) => {
  await novelRepo.deleteNovel(req.params.slug);
  res.json({ ok: true });
}));

// ── Admin save chapter ─────────────────────────────────────────────

app.post('/api/novel/:slug/chapter/:num/save', requireAdmin, asyncHandler(async (req, res) => {
  const slug = req.params.slug;
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  let { title, blocks, source, lang, paragraphs, markdownText } = req.body;
  let notes = [];

  if (markdownText) {
    const parsed = parseMarkdownToBlocks(markdownText, num);
    blocks = parsed.blocks;
    if (!title) title = parsed.title;
    notes = parsed.notes;
  }

  const targetLang = lang || 'th';

  // Build draft blocks for validation (no file write yet)
  const draftBlocks = [];
  if (paragraphs && paragraphs.length) {
    // Convert paragraphs to narration blocks for ratio validation
    draftBlocks.push(...paragraphs.map(text => ({ type: 'narration', text })));
  } else if (blocks && blocks.length) {
    draftBlocks.push(...blocks);
  } else if (markdownText) {
    draftBlocks.push(...blocks || []);
  }

  // Validate before write
  const { validateChapterJs } = require('./services/validation');
  const valResult = await validateChapterJs(slug, num, title || `ตอนที่ ${num}`, draftBlocks, source || '', targetLang, { novelRoot: NOVELS_DIR });
  if (!valResult.valid) {
    const errorMsg = [
      '━'.repeat(70),
      `  VALIDATION — Ch ${num} (JS Native)`,
      '━'.repeat(70), '',
      ...valResult.info.map(line => `  ℹ  ${line}`), '',
      ...valResult.warnings.map(line => `  ⚠  ${line}`),
      ...valResult.errors.map(line => `  ✗  ${line}`), '',
      `❌ FAILED — ${valResult.errors.length} error(s) found`,
    ].join('\n');
    return res.status(422).json({ error: 'Validation Error', details: errorMsg });
  }

  // Validation passed — now write
  await chapterRepo.saveChapter(slug, num, targetLang, {
    title, blocks, paragraphs, notes,
  });

  await chapterRepo.rebuildChaptersIndex(slug);
  chapterRepo.invalidateAll(slug);
  res.json({ ok: true });
}));

// ── Admin delete chapter ───────────────────────────────────────────

app.post('/api/novel/:slug/chapter/:num/delete', requireAdmin, asyncHandler(async (req, res) => {
  const slug = req.params.slug;
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  await chapterRepo.deleteChapter(slug, num);
  await chapterRepo.rebuildChaptersIndex(slug);
  chapterRepo.invalidateAll(slug);
  res.json({ ok: true });
}));

// ── Manual cache invalidation ──────────────────────────────────────

app.post('/api/invalidate-cache', requireAdmin, (req, res) => {
  chapterRepo.invalidateAll();
  res.json({ ok: true });
});

// ── Admin Jobs Dashboard API ───────────────────────────────────────
// Reads jobs/active, jobs/done, jobs/failed, jobs/needs_review from disk.

const JOBS_DIR = path.resolve(__dirname, '..', 'jobs');
const LOGS_DIR = path.resolve(__dirname, '..', 'logs', 'translate');

async function readJsonDir(dirPath) {
  try {
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    const results = [];
    for (const e of entries) {
      if (e.isFile() && e.name.endsWith('.json')) {
        try {
          const data = JSON.parse(await fs.readFile(path.join(dirPath, e.name), 'utf8'));
          results.push({ file: e.name, data });
        } catch { /* skip unparseable */ }
      }
    }
    return results;
  } catch { return []; }
}

app.get('/api/admin/jobs', requireAdmin, asyncHandler(async (req, res) => {
  const [active, done, failed, needsReview] = await Promise.all([
    readJsonDir(path.join(JOBS_DIR, 'active')),
    readJsonDir(path.join(JOBS_DIR, 'done')),
    readJsonDir(path.join(JOBS_DIR, 'failed')),
    readJsonDir(path.join(JOBS_DIR, 'needs_review')),
  ]);
  res.json({ active, done, failed, needsReview });
}));

// ── Admin audit log viewer ─────────────────────────────────────────
const SLUG_RE_LOOSE = /^[a-z0-9-]+$/i;
const NUM_RE = /^\d{1,5}$/;

app.get('/api/admin/logs/:slug/:num', requireAdmin, asyncHandler(async (req, res) => {
  const { slug, num } = req.params;

  // Validate params — prevent path traversal
  if (!SLUG_RE_LOOSE.test(slug) || !NUM_RE.test(num)) {
    return res.status(400).json({ ok: false, error: 'Invalid slug or num format' });
  }

  const logDir = path.join(LOGS_DIR, slug, num);
  try {
    const entries = await fs.readdir(logDir, { withFileTypes: true });
    const files = [];
    for (const e of entries) {
      if (e.isFile()) {
        const fullPath = path.join(logDir, e.name);
        const content = await fs.readFile(fullPath, 'utf8');
        const isJson = e.name.endsWith('.json');
        files.push({
          name: e.name,
          content: content.slice(0, 50000),
          isJson,
        });
      }
    }
    res.json({ ok: true, files });
  } catch {
    res.json({ ok: false, error: 'Log directory not found' });
  }
}));

// ── Server startup ─────────────────────────────────────────────────

const START_TIME = Date.now();

const server = app.listen(PORT, BIND_HOST, () => {
  const os = require('node:os');
  const ifaces = os.networkInterfaces();
  const ips = [];
  for (const [name, list] of Object.entries(ifaces)) {
    for (const i of list || []) {
      if (i.family === 'IPv4' && !i.internal) {
        ips.push(`  http://${i.address}:${PORT}/`);
      }
    }
  }
  console.log(`NovelClaw Reader running on:`);
  console.log(`  http://localhost:${PORT}/`);
  if (BIND_HOST === '0.0.0.0' && ips.length) {
    console.log(`  (LAN access — open on phone on same Wi-Fi):`);
    for (const ip of ips) console.log(ip);
  }
  if (BIND_HOST !== '0.0.0.0') {
    console.log(`  (localhost only — set HOST=0.0.0.0 for LAN access)`);
  }
  if (BIND_HOST === '0.0.0.0' && !ADMIN_TOKEN) {
    console.log('  ❌  ERROR: HOST=0.0.0.0 requires ADMIN_TOKEN to protect');
    console.log('     admin endpoints. Set ADMIN_TOKEN=your-secret-token and restart.');
    console.log('     Or bind to 127.0.0.1 (default) for local-only access.');
    process.exit(1);
  }
  console.log(`Serving novels from: ${NOVELS_DIR}`);
});

// ── Graceful shutdown ─────────────────────────────────────────────

function shutdown(signal) {
  console.log(`\n${signal} received — shutting down gracefully...`);
  server.close(() => {
    console.log('All connections closed.');
    process.exit(0);
  });
  setTimeout(() => {
    console.error('Forced exit after 10s timeout.');
    process.exit(1);
  }, 10000);
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

// ── EADDRINUSE recovery (opt-in) ───────────────────────────────────

let _eaddrRetries = 0;
const AUTO_KILL = process.env.AUTO_KILL_PORT === 'true';
server.on('error', (err) => {
  if (err.code === 'EADDRINUSE' && AUTO_KILL && _eaddrRetries < 3) {
    _eaddrRetries++;
    console.log(`⚠️  Port ${PORT} already in use — killing old server (attempt ${_eaddrRetries}/3)...`);
    const { execSync } = require('node:child_process');
    try {
      if (process.platform === 'win32') {
        const out = execSync(`netstat -ano | findstr :${PORT}`, { encoding: 'utf8' });
        for (const line of out.trim().split('\n')) {
          const parts = line.trim().split(/\s+/);
          const pid = parts[parts.length - 1];
          if (pid && pid !== '0') {
            execSync(`taskkill /PID ${pid} /F`, { encoding: 'utf8' });
            console.log(`  Killed old process (PID ${pid})`);
          }
        }
      } else {
        execSync(`lsof -ti:${PORT} | xargs kill -9 2>/dev/null || true`, { encoding: 'utf8' });
      }
    } catch (e) { /* ignore */ }
    setTimeout(() => { server.listen(PORT, BIND_HOST); }, 500);
  } else {
    console.error('Server error:', err);
  }
});

// ── Unhandled rejection guard ──────────────────────────────────────

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// ── SPA fallback — serve index.html for all non-API routes ─────────

const INDEX_HTML = fsSync.readFileSync(path.join(PUBLIC_DIR, 'index.html'), 'utf8');

app.get('*', (req, res) => {
  if (req.path.startsWith('/api/')) return res.status(404).json({ error: 'API not found' });
  res.set('Cache-Control', 'no-store, no-cache, must-revalidate');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');
  // Cache-bust: strip existing query, append _t
  let html = INDEX_HTML.replace(/src="\/(js\/[^"?]+)(\?[^"]*)?"/g, `src="/$1?_t=${START_TIME}"`);
  html = html.replace(/href="\/(design-system\.css)[^"]*"/g, `href="/$1?_t=${START_TIME}"`);
  res.send(html);
});

// ── Global error handler ───────────────────────────────────────────

// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  if (!res.headersSent) {
    const status = err.status && Number.isInteger(err.status) ? err.status : 500;
    res.status(status).json({ error: err.message || 'Internal server error' });
  }
});
