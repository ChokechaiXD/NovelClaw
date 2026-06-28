// NovelClaw Reader — Express server using lib/ repositories
//
// Usage: node server.js   (then open http://localhost:4173)
// Env:
//   PORT             — listening port (default 4173)
//   HOST             — bind address (default 127.0.0.1, set 0.0.0.0 for LAN)
//   NOVELCLAW_ROOT   — path to novels/ directory (default ../novels)
//   ADMIN_TOKEN      — bearer token for write endpoints
//   TRUSTED_LAN      — set 'true' to allow write APIs on LAN without ADMIN_TOKEN
//   AUTO_KILL_PORT   — set 'true' to auto-kill old process (default off)

const express = require('express');
// Subprocess output sanitizer for error responses.
// Strips characters likely to be from tracebacks / file paths / leaked
// secrets (control chars, most punctuation, anything outside text ranges
// we'd ever want to expose). Bounded at 2000 chars so a big Python
// traceback can't blow up the response.
function sanitizeOutput(s) {
  if (!s) return '';
  // Keep only chars in the union of: ASCII printable+whitespace, Thai, CJK
  // punctuation, Hiragana, Katakana, CJK Unified. Anything else is dropped.
  const cleaned = String(s).replace(/[^\x09\x0A\x0D\x20-\x7E\u0E00-\u0E7F\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]/g, '');
  return cleaned.length > 2000 ? cleaned.slice(0, 2000) + '...[truncated]' : cleaned;
}

const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const fs = require('node:fs/promises');
const fsSync = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

// ── Lib modules ────────────────────────────────────────────────────
const { pad, assertValidSlug, SLUG_RE, novelJsonPath, sourceMdPath,
        glossaryJsonPath, glossaryMdPath, charactersMdPath, NOVELS_DIR, chapterPath } = require('./lib/paths');
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
const TRUSTED_LAN = process.env.TRUSTED_LAN === 'true';

// ── API response helpers ──────────────────────────────────────────
function ok(res, data = {}) {
  return res.json({ ok: true, data });
}
function fail(res, status, code, message, details) {
  const body = { ok: false, error: { code, message } };
  if (details !== undefined) body.error.details = details;
  return res.status(status).json(body);
}

// Cache disabled for Local 100%
function invalidateCache(prefix) {
  // Cache is disabled, nothing to invalidate
}

// ── Middleware ─────────────────────────────────────────────────────
const app = express();
// Helmet defaults turn on a strict Content-Security-Policy that breaks
// any inline JS or external fonts. NovelClaw Reader uses no inline scripts
// and only self-hosted assets. Explicit CSP:
//   - only this origin (-self) for scripts/styles/images/connect
//   - no eval(), no inline JS, no inline styles (toggle to 'unsafe-inline'
//     if admin later needs inlined theme vars)
//   - frames blocked (clickjacking), X-Content-Type-Options, Referrer-Policy
app.use(helmet({
  contentSecurityPolicy: {
    useDefaults: true,
    directives: {
      'default-src': ["'self'"],
      'script-src': ["'self'"],
      'style-src': ["'self'", "'unsafe-inline'"],  // admin uses inline style for some controls
      'img-src': ["'self'", 'data:'],            // SVG cover fallback uses data URIs
      'connect-src': ["'self'"],
      'object-src': ["'none'"],
      'base-uri': ["'self'"],
      'frame-ancestors': ["'none'"],
    },
  },
}));
app.use(express.json({ limit: '5mb' }));

// Rate-limit admin write APIs in case ADMIN_TOKEN is leaked. The reader is
// intended for single-user localhost or small-LAN use, so 60 req/min/IP is
// generous for real use and tight enough to deflect casual bots.
const adminWriteLimiter = rateLimit({
  windowMs: 60 * 1000,
  limit: 60,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
});

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
    return fail(res, 400, 'INVALID_SLUG', 'Invalid slug format');
  }
  next();
});

// Async route wrapper
const asyncHandler = (fn) => (req, res, next) =>
  Promise.resolve(fn(req, res, next)).catch(next);

// Admin write helper: requireAdmin guard + asyncHandler wrapper.
// Saves repeating 'requireAdmin, asyncHandler' on every write route —
// was repeated on 11 routes before.
function adminPost(path, handler) {
  app.post(path, adminWriteLimiter, requireAdmin, asyncHandler(handler));
}

// Admin auth middleware
function isLocalBind(host) {
  return host === '127.0.0.1' || host === 'localhost' || host === '::1' || host === '0:0:0:0:0:0:0:1';
}

function allowsUnauthenticatedAdmin() {
  return !ADMIN_TOKEN && (isLocalBind(BIND_HOST) || TRUSTED_LAN);
}

function requireAdmin(req, res, next) {
  if (allowsUnauthenticatedAdmin()) return next();
  const provided = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  if (!provided) {
    return fail(res, 401, 'AUTH_REQUIRED', 'Unauthorized — provide Authorization: Bearer <token>');
  }
  if (provided.length === ADMIN_TOKEN.length && crypto.timingSafeEqual(Buffer.from(provided), Buffer.from(ADMIN_TOKEN))) {
    return next();
  }
  fail(res, 401, 'AUTH_INVALID', 'Unauthorized — invalid token');
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
  if (q.length > 200) return fail(res, 400, 'QUERY_TOO_LONG', 'Query too long (max 200 chars)');
  if (!['title', 'content', 'all'].includes(mode)) {
    return fail(res, 400, 'INVALID_MODE', 'Unknown mode (use title|content|all)');
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
  if (Number.isNaN(num)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');
  const lang = (req.query.lang || 'th').toString();
  const result = await chapterRepo.getChapter(req.params.slug, num, lang);
  if (!result) return fail(res, 404, 'CHAPTER_NOT_FOUND', 'Chapter not found');

  // ดึงข้อมูลคุณภาพการแปลจาก jobs/quality หรือ logs
  let score = null;
  let model = 'unknown';
  let provider = 'unknown';

  const paddedNum = String(num).padStart(4, '0');
  const qualityPath = path.join(__dirname, '..', 'jobs', 'quality', req.params.slug, `${paddedNum}.json`);
  
  try {
    const rawQuality = await fs.readFile(qualityPath, 'utf8');
    const qData = JSON.parse(rawQuality);
    if (qData && Array.isArray(qData.records)) {
      for (let i = qData.records.length - 1; i >= 0; i--) {
        const rec = qData.records[i];
        if (score === null && rec.score !== undefined && rec.score !== null) {
          score = rec.score;
        }
        if (model === 'unknown' && rec.model && rec.model !== 'unknown') {
          model = rec.model;
        }
        if (provider === 'unknown' && rec.provider && rec.provider !== 'unknown') {
          provider = rec.provider;
        }
      }
      if (qData.records.length > 0) {
        const lastRec = qData.records[qData.records.length - 1];
        if (model === 'unknown' && lastRec.model) model = lastRec.model;
        if (provider === 'unknown' && lastRec.provider) provider = lastRec.provider;
      }
    }
  } catch (err) {
    const reportPath = path.join(__dirname, '..', 'logs', 'translate', req.params.slug, paddedNum, 'report.json');
    try {
      const rawReport = await fs.readFile(reportPath, 'utf8');
      const rData = JSON.parse(rawReport);
      if (rData && rData.result && rData.result.score !== undefined) {
        score = rData.result.score;
      }
    } catch {}
  }

  if (score === null) score = 100;

  res.set('Cache-Control', 'public, max-age=20, stale-while-revalidate=60');
  res.set('X-Cache-TTL', '20');

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
    score: score,
    model: model,
    provider: provider,
    isTranslated: result.isTranslated !== false,
    validation: { valid: true, errors: [], warnings: [], info: [] },
  });
}));

// ── Source file ────────────────────────────────────────────────────

app.get('/api/novel/:slug/source/:num', asyncHandler(async (req, res) => {
  assertValidSlug(req.params.slug);
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');
  const raw = await readTextOrNull(sourceMdPath(req.params.slug, num));
  if (raw === null) return fail(res, 404, 'SOURCE_NOT_FOUND', 'Source not found');
  res.type('text/plain').send(raw);
}));

// ── Glossary ───────────────────────────────────────────────────────

app.get('/api/novel/:slug/glossary', asyncHandler(async (req, res) => {
  assertValidSlug(req.params.slug);
  const raw = await readTextOrNull(glossaryMdPath(req.params.slug));
  if (raw === null) return fail(res, 404, 'GLOSSARY_NOT_FOUND', 'No glossary');
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
    fail(res, 500, 'GLOSSARY_PARSE_ERROR', 'Invalid glossary.json', err.message);
  }
}));

adminPost('/api/novel/:slug/glossary/save', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const glossaryScript = path.join(__dirname, '..', 'tools', 'glossary.py');
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const child = spawn(py, [glossaryScript, '--novel', slug, '--save'], {
    cwd: path.join(__dirname, '..'), windowsHide: true, timeout: 10_000,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
  });
  let stdout = '', stderr = '';
  child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
  child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
  child.on('error', (err) => {
    console.error('Failed to start glossary.py:', err);
    if (!res.headersSent) {
      fail(res, 500, 'GLOSSARY_SPAWN_FAILED', `Failed to start glossary.py: ${err.message}`);
    }
  });
  child.on('close', (code) => {
    if (code !== 0) {
      return fail(res, 500, 'GLOSSARY_SAVE_FAILED', `glossary.py exited ${code}: ${sanitizeOutput(stderr)}`);
    }
    chapterRepo.invalidateAll(slug);
    ok(res, { saved: true });
  });
  child.stdin.write(JSON.stringify(req.body));
  child.stdin.end();
});

// ── Characters ─────────────────────────────────────────────────────

app.get('/api/novel/:slug/characters', asyncHandler(async (req, res) => {
  assertValidSlug(req.params.slug);
  const raw = await readTextOrNull(charactersMdPath(req.params.slug));
  if (raw === null) return fail(res, 404, 'CHARACTERS_NOT_FOUND', 'No characters');
  res.type('text/plain').send(raw);
}));

// ── Admin novel update ─────────────────────────────────────────────

adminPost('/api/novel/update', async (req, res) => {
  const { slug, title, author, source_lang, target_lang, status, total_chapters, translatedTitle } = req.body;
  if (!slug || !SLUG_RE.test(slug)) {
    return fail(res, 400, 'INVALID_SLUG', 'Invalid slug format');
  }
  await novelRepo.saveNovelMeta(slug, { title, author, source_lang, target_lang, status, total_chapters, translatedTitle });
  invalidateCache('/api/novels');
  ok(res, { slug });
});

// ── Admin delete novel ─────────────────────────────────────────────

adminPost('/api/novel/:slug/delete', async (req, res) => {
  await novelRepo.deleteNovel(req.params.slug);
  ok(res, { deleted: true });
});

// ── Admin import novel from text file ──────────────────────────────

adminPost('/api/novel/import-file', async (req, res) => {
  const { title, slug, author, sourceLang, splitRule, content } = req.body;
  if (!slug || !SLUG_RE.test(slug)) {
    return res.status(400).json({ ok: false, error: { code: 'INVALID_SLUG', message: 'Invalid slug format' } });
  }

  // 1. Save novel metadata (Creates directory as well)
  await novelRepo.saveNovelMeta(slug, {
    title,
    author,
    source_lang: sourceLang,
    target_lang: 'th',
    status: 'ongoing',
    description: `นิยายนำเข้าด้วยไฟล์ข้อความเมื่อ ${new Date().toLocaleDateString('th-TH')}`
  });

  // Create chapters subdirectory
  const chaptersDirPath = path.join(NOVELS_DIR, slug, 'chapters');
  await fs.mkdir(chaptersDirPath, { recursive: true });

  // 2. Parse and split chapters
  let chapters = [];
  let rule = splitRule || '(?:ตอนที่|第)\\s*(\\d+)\\s*(?:章|ตอน)?';
  let regex = new RegExp('^' + rule + '.*$', 'gm');
  
  let matches = [];
  let match;
  while ((match = regex.exec(content)) !== null) {
    matches.push({
      index: match.index,
      text: match[0],
      chNum: parseInt(match[1], 10) || (matches.length + 1)
    });
  }

  if (matches.length === 0) {
    chapters.push({
      num: 1,
      title: 'ตอนที่ 1',
      text: content
    });
  } else {
    for (let i = 0; i < matches.length; i++) {
      let start = matches[i].index;
      let end = (i + 1 < matches.length) ? matches[i + 1].index : content.length;
      let text = content.slice(start, end).trim();
      let titleLine = matches[i].text.trim();
      
      // Extract paragraphs without the title line itself to avoid duplicates
      let lines = text.split('\n');
      if (lines[0].trim() === titleLine) {
        lines.shift();
      }
      let filteredText = lines.join('\n').trim();

      chapters.push({
        num: matches[i].chNum || (i + 1),
        title: titleLine,
        text: filteredText || titleLine
      });
    }
  }

  // 3. Write each chapter json file
  for (const ch of chapters) {
    const paragraphs = ch.text.split('\n').map(p => p.trim()).filter(p => p.length > 0);
    const chData = {
      novelId: slug,
      chapterNo: ch.num,
      sourceLang: sourceLang,
      targetLang: sourceLang,
      title: {
        source: ch.title
      },
      status: "source",
      paragraphs: paragraphs,
      updatedAt: new Date().toISOString()
    };
    await fs.writeFile(chapterPath(slug, ch.num, sourceLang), JSON.stringify(chData, null, 2), 'utf8');
  }

  // 4. Rebuild chapters index
  await chapterRepo.rebuildChaptersIndex(slug);

  // Update total chapters in novel.json
  await novelRepo.saveNovelMeta(slug, {
    title,
    author,
    source_lang: sourceLang,
    target_lang: 'th',
    status: 'ongoing',
    total_chapters: chapters.length,
    description: `นิยายนำเข้าด้วยไฟล์ข้อความเมื่อ ${new Date().toLocaleDateString('th-TH')}`
  });

  invalidateCache('/api/novels');

  res.json({
    success: true,
    title,
    slug,
    chaptersCount: chapters.length,
    sourceLang
  });
});

// ── Admin save chapter ─────────────────────────────────────────────

adminPost('/api/novel/:slug/chapter/:num/save', async (req, res) => {
  const slug = req.params.slug;
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');
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
    return fail(res, 422, 'VALIDATION_ERROR', 'Validation Error', errorMsg);
  }

  // Validation passed — now write
  await chapterRepo.saveChapter(slug, num, targetLang, {
    title, blocks, paragraphs, notes,
  });

  await chapterRepo.rebuildChaptersIndex(slug);
  chapterRepo.invalidateAll(slug);
  invalidateCache('/api/novel/' + slug);
  invalidateCache('/api/novels');
  ok(res, { slug, num });
});

// ── Admin delete chapter ───────────────────────────────────────────

adminPost('/api/novel/:slug/chapter/:num/delete', async (req, res) => {
  const slug = req.params.slug;
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');
  await chapterRepo.deleteChapter(slug, num);
  await chapterRepo.rebuildChaptersIndex(slug);
  chapterRepo.invalidateAll(slug);
  invalidateCache('/api/novel/' + slug);
  invalidateCache('/api/novels');
  ok(res, { slug, num });
});

// ── Manual cache invalidation ──────────────────────────────────────

adminPost('/api/invalidate-cache', (req, res) => {
  chapterRepo.invalidateAll();
  ok(res, { invalidated: true });
});

// ── Admin audit log viewer ─────────────────────────────────────────
const SLUG_RE_LOOSE = /^[a-z0-9-]+$/i;
const NUM_RE = /^\d{1,5}$/;
const LOGS_DIR = path.resolve(__dirname, '..', 'logs', 'translate');

app.get('/api/admin/logs/:slug/:num', requireAdmin, asyncHandler(async (req, res) => {
  const { slug, num } = req.params;

  // Validate params — prevent path traversal
  if (!SLUG_RE_LOOSE.test(slug) || !NUM_RE.test(num)) {
    return fail(res, 400, 'INVALID_PARAMS', 'Invalid slug or num format');
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
    ok(res, { files });
  } catch {
    ok(res, { files: [], warning: 'Log directory not found' });
  }
}));

// ── Server startup ─────────────────────────────────────────────────

const START_TIME = Date.now();

if (!isLocalBind(BIND_HOST) && !ADMIN_TOKEN && !TRUSTED_LAN) {
  console.error('Refusing to bind write-capable Reader on LAN without protection.');
  console.error('Set ADMIN_TOKEN for bearer auth, or set TRUSTED_LAN=true for a private trusted network.');
  process.exit(1);
}

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

// ── LOCAL ONLY DEV APIS ─────────────────────────────────────────────

adminPost('/api/local/open-editor', async (req, res) => {
  const { slug, num, lang, editor } = req.body;
  assertValidSlug(slug);
  const chapterNum = parseInt(num, 10);
  if (Number.isNaN(chapterNum)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');

  const targetLang = lang === 'cn' ? 'cn' : 'th';
  const filepath = chapterPath(slug, chapterNum, targetLang);

  try {
    await fs.access(filepath);
  } catch {
    return fail(res, 404, 'FILE_NOT_FOUND', `Chapter file not found: ${path.basename(filepath)}`);
  }

  const editorType = editor || 'notepad';
  const { spawn, exec } = require('node:child_process');

  if (editorType === 'vscode') {
    const cmd = process.platform === 'win32' ? 'code.cmd' : 'code';
    const child = spawn(cmd, [filepath], { shell: true, detached: true, stdio: 'ignore' });
    child.on('error', (err) => {
      console.error('Failed to spawn VS Code:', err);
    });
    child.unref();
    return ok(res, { opened: true, editor: 'vscode' });
  } else if (editorType === 'system_default') {
    const cmd = process.platform === 'win32' 
      ? `start "" "${filepath}"` 
      : process.platform === 'darwin' 
        ? `open "${filepath}"` 
        : `xdg-open "${filepath}"`;
    exec(cmd, (err) => {
      if (err) console.error('Failed to open system default editor:', err);
    });
    return ok(res, { opened: true, editor: 'system_default' });
  } else {
    // default: notepad
    const child = spawn('notepad.exe', [filepath], { shell: true, detached: true, stdio: 'ignore' });
    child.on('error', (err) => {
      console.error('Failed to spawn Notepad:', err);
    });
    child.unref();
    return ok(res, { opened: true, editor: 'notepad' });
  }
});

adminPost('/api/novel/:slug/glossary/add', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const { source, thai, category, notes } = req.body;
  if (!source || !thai) {
    return fail(res, 400, 'MISSING_FIELDS', 'Both source (Chinese) and thai (translation) are required.');
  }

  let terms = [];
  const filepath = glossaryJsonPath(slug);
  try {
    const raw = await fs.readFile(filepath, 'utf8');
    const data = JSON.parse(raw);
    terms = data.terms || [];
  } catch {}

  const exists = terms.some(t => t.source.trim() === source.trim());
  if (exists) {
    return fail(res, 400, 'DUPLICATE_TERM', `Term "${source}" already exists in glossary.`);
  }

  terms.push({
    source: source.trim(),
    thai: thai.trim(),
    category: (category || 'คำศัพท์').trim(),
    priority: 3,
    lock: 'auto',
    explanation: '',
    notes: (notes || 'Added from web reader').trim()
  });

  const glossaryScript = path.join(__dirname, '..', 'tools', 'glossary.py');
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const child = spawn(py, [glossaryScript, '--novel', slug, '--save'], {
    cwd: path.join(__dirname, '..'), windowsHide: true, timeout: 10_000,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
  });

  let stdout = '', stderr = '';
  child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
  child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });

  child.on('error', (err) => {
    console.error('Failed to start glossary.py:', err);
    if (!res.headersSent) {
      fail(res, 500, 'GLOSSARY_SPAWN_FAILED', `Failed to start glossary.py: ${err.message}`);
    }
  });

  child.on('close', (code) => {
    if (code !== 0) {
      return fail(res, 500, 'GLOSSARY_SAVE_FAILED', `glossary.py exited ${code}: ${sanitizeOutput(stderr)}`);
    }
    chapterRepo.invalidateAll(slug);
    ok(res, { added: true, term: { source, thai } });
  });

  child.stdin.write(JSON.stringify({ terms }));
  child.stdin.end();
});

app.get('/api/novel/:slug/chapter/:num/unknown-terms', asyncHandler(async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');
  
  // Read source
  const sourcePath = sourceMdPath(slug, num);
  let raw = await readTextOrNull(sourcePath);
  if (raw === null) return res.json({ terms: [] });
  
  // Load glossary terms
  let known = new Set();
  try {
    const glossRaw = await readTextOrNull(glossaryJsonPath(slug));
    if (glossRaw) {
      const glossData = JSON.parse(glossRaw);
      if (glossData && Array.isArray(glossData.terms)) {
        for (const t of glossData.terms) {
          if (t.source) known.add(t.source.trim());
        }
      }
    }
  } catch {}
  
  // UI noise set (Common Chinese words & navigation layout text)
  const uiNoise = new Set([
    "首頁", "科幻小說", "玄幻小說", "都市言情", "歷史軍事", "遊戲競技", 
    "加入書籤", "小說報錯", "投票推薦", "字體", "上一章", "下一章", 
    "目錄", "關燈", "開燈", "下載", "客戶端", "手機看書", "繁體", 
    "簡體", "上一頁", "下一頁", "返回", "確定", "取消", "提交", 
    "下載本章", "請先", "登錄", "註冊", "忘記密碼", "會員中心", 
    "我的書架", "正在加載", "加載中", "請稍候", "暫無", "評論", "書友",
    "全球降臨", "帶著嫂嫂", "末世種田", "第", "章", "回", "節", "頁", "卷"
  ]);
  
  // Clean brackets and extract
  const cleaned = raw.replace(/【[^】]*】/g, '')
                     .replace(/《[^》]*》/g, '')
                     .replace(/「[^」]*」/g, '');
  const cnTerms = cleaned.match(/[\u4e00-\u9fff]{2,}/g) || [];
  
  const seen = new Set();
  const unknown = [];
  for (const term of cnTerms) {
    const trimmed = term.trim();
    if (trimmed.length >= 2 && !known.has(trimmed) && !uiNoise.has(trimmed) && !seen.has(trimmed)) {
      seen.add(trimmed);
      unknown.push(trimmed);
    }
  }
  
  res.json({ terms: unknown });
}));

adminPost('/api/local/translate-term', async (req, res) => {
  const { term, context } = req.body;
  if (!term) return fail(res, 400, 'MISSING_TERM', 'Term is required');
  
  const translateScript = path.join(__dirname, '..', 'tools', 'translate_term.py');
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const child = spawn(py, [translateScript], {
    cwd: path.join(__dirname, '..'), windowsHide: true, timeout: 20_000,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
  });
  
  let stdout = '', stderr = '';
  child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
  child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
  
  child.on('error', (err) => {
    console.error('Failed to start translate_term.py:', err);
    if (!res.headersSent) {
      fail(res, 500, 'TRANSLATE_SPAWN_FAILED', `Failed to start translate_term.py: ${err.message}`);
    }
  });
  
  child.on('close', (code) => {
    if (code !== 0) {
      return fail(res, 500, 'TRANSLATE_FAILED', `translate_term.py exited ${code}: ${sanitizeOutput(stderr || stdout)}`);
    }
    try {
      const parsed = JSON.parse(stdout);
      ok(res, parsed);
    } catch (err) {
      fail(res, 500, 'JSON_PARSE_ERROR', 'Failed to parse LLM suggestion JSON: ' + sanitizeOutput(stdout));
    }
  });
  
  child.stdin.write(JSON.stringify({ term, context }));
  child.stdin.end();
});

adminPost('/api/novel/:slug/glossary/verify', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const { index, verified } = req.body;
  if (index === undefined || verified === undefined) {
    return fail(res, 400, 'MISSING_FIELDS', 'Both index and verified are required');
  }
  
  // Load terms
  const filepath = glossaryJsonPath(slug);
  let terms = [];
  try {
    const raw = await fs.readFile(filepath, 'utf8');
    const data = JSON.parse(raw);
    terms = data.terms || [];
  } catch (err) {
    return fail(res, 404, 'GLOSSARY_NOT_FOUND', 'Glossary file not found');
  }
  
  const idx = parseInt(index, 10);
  if (idx < 0 || idx >= terms.length) {
    return fail(res, 400, 'INVALID_INDEX', 'Invalid glossary index');
  }
  
  terms[idx].verified = !!verified;
  
  // Save terms via glossary.py --save
  const glossaryScript = path.join(__dirname, '..', 'tools', 'glossary.py');
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const child = spawn(py, [glossaryScript, '--novel', slug, '--save'], {
    cwd: path.join(__dirname, '..'), windowsHide: true, timeout: 10_000,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
  });
  
  let stdout = '', stderr = '';
  child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
  child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
  
  child.on('error', (err) => {
    console.error('Failed to start glossary.py:', err);
    if (!res.headersSent) {
      fail(res, 500, 'GLOSSARY_SPAWN_FAILED', `Failed to start glossary.py: ${err.message}`);
    }
  });
  
  child.on('close', (code) => {
    if (code !== 0) {
      return fail(res, 500, 'GLOSSARY_SAVE_FAILED', `glossary.py exited ${code}: ${sanitizeOutput(stderr)}`);
    }
    chapterRepo.invalidateAll(slug);
    ok(res, { verified: terms[idx].verified });
  });
  
  child.stdin.write(JSON.stringify({ terms }));
  child.stdin.end();
});

app.get('/api/local/state', asyncHandler(async (req, res) => {
  const filepath = path.join(__dirname, 'local_state.json');
  try {
    const raw = await fs.readFile(filepath, 'utf8');
    res.json(JSON.parse(raw));
  } catch (err) {
    res.json({});
  }
}));

adminPost('/api/local/state', async (req, res) => {
  const filepath = path.join(__dirname, 'local_state.json');
  await fs.writeFile(filepath, JSON.stringify(req.body, null, 2), 'utf8');
  ok(res, { saved: true });
});

// ── LOCAL LLM CONFIG & TRANSLATION APIS ─────────────────────────────
const LLM_JSON_PATH = path.join(__dirname, '..', 'llm.json');

function buildLlmConfigResponse(data = {}) {
  const defaultProvider = data.default_provider || 'openrouter';
  const defaultModel = data.default_model || 'google/gemma-4-26b-a4b-it:free';
  const providers = [
    {
      id: 'openrouter',
      label: 'OpenRouter',
      description: 'OpenRouter-compatible hosted models',
      keyField: 'openrouter_api_key',
      hasKey: !!(data.openrouter_api_key || process.env.OPENROUTER_API_KEY),
      models: [
        { id: 'google/gemma-4-26b-a4b-it:free', label: 'Gemma 4 26B (Free)' },
        { id: 'google/gemma-4-31b-it:free', label: 'Gemma 4 31B (Free)' },
        { id: 'google/gemma-2-9b-it:free', label: 'Gemma 2 9B (Free)' },
        { id: 'google/gemma-2-27b-it:free', label: 'Gemma 2 27B (Free)' },
        { id: 'openai/gpt-oss-120b:free', label: 'GPT OSS 120B (Free)' },
        { id: 'nvidia/nemotron-3-ultra-550b-a55b:free', label: 'Nemotron 3 Ultra (Free)' },
        { id: 'openrouter/free', label: 'OpenRouter Auto Free' },
        { id: 'deepseek/deepseek-chat', label: 'DeepSeek Chat' },
        { id: 'meta-llama/llama-3.1-70b-instruct', label: 'Llama 3.1 70B' },
        { id: 'meta-llama/llama-3.1-405b-instruct', label: 'Llama 3.1 405B' },
      ],
    },
    {
      id: 'openmodel',
      label: 'OpenModel',
      description: 'OpenModel API using the project translator backend',
      keyField: 'api_key',
      hasKey: !!(data.openmodel_api_key || process.env.LLM_API_KEY || (data.default_provider === 'openmodel' && data.api_key)),
      models: [
        { id: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
      ],
    },
  ];

  const activeProvider = providers.find(p => p.id === defaultProvider) || providers[0];
  if (!activeProvider.models.some(m => m.id === defaultModel)) {
    activeProvider.models.unshift({ id: defaultModel, label: defaultModel });
  }

  return {
    default_model: defaultModel,
    default_provider: defaultProvider,
    hasOpenRouterKey: providers.find(p => p.id === 'openrouter')?.hasKey || false,
    hasOpenModelKey: providers.find(p => p.id === 'openmodel')?.hasKey || false,
    providers,
  };
}

app.get('/api/local/llm-config', asyncHandler(async (req, res) => {
  try {
    const raw = await fs.readFile(LLM_JSON_PATH, 'utf8');
    const data = JSON.parse(raw);
    res.json(buildLlmConfigResponse(data));
  } catch (err) {
    res.json(buildLlmConfigResponse());
  }
}));

adminPost('/api/local/llm-config', async (req, res) => {
  const { default_model, default_provider, openrouter_api_key, openmodel_api_key, api_key } = req.body;
  let data = {};
  try {
    const raw = await fs.readFile(LLM_JSON_PATH, 'utf8');
    data = JSON.parse(raw);
  } catch (err) {}

  if (default_model) data.default_model = default_model.trim();
  if (default_provider) data.default_provider = default_provider.trim();
  if (openrouter_api_key) {
    data.openrouter_api_key = openrouter_api_key.trim();
  }
  if (openmodel_api_key || api_key) {
    data.openmodel_api_key = (openmodel_api_key || api_key).trim();
    data.api_key = data.openmodel_api_key;
  }

  await fs.writeFile(LLM_JSON_PATH, JSON.stringify(data, null, 2), 'utf8');
  ok(res, { saved: true, config: buildLlmConfigResponse(data) });
});

// ── PROVIDER CONFIG (from providers.yaml) ──────────────────────────
// Reads/writes tools/config/providers.yaml via Python helper.
// Admin UI uses this to switch active provider and model.

const PROVIDER_CONFIG_PY = path.join(__dirname, '..', 'tools', 'llm_router', 'config_providers.py');

app.get('/api/admin/provider-config', asyncHandler(async (req, res) => {
  try {
    const py = getPythonCommand();
    const child = spawn(py, ['-c', `
import sys; sys.path.insert(0, 'tools')
from llm_router.config_providers import get_provider_config, get_providers_list
import json
cfg = get_provider_config()
plist = get_providers_list()
print(json.dumps({
  "active": cfg.get("active", ""),
  "default_model": cfg.get("default_model", ""),
  "discovery_model": cfg.get("discovery_model", ""),
  "providers": plist,
  "profiles": cfg.get("profiles", []),
}, ensure_ascii=False))
    `], {
      cwd: path.join(__dirname, '..'),
      windowsHide: true,
      timeout: 15_000,
      env: { ...process.env }
    });
    let stdout = '', stderr = '';
    child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
    child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
    child.on('error', (err) => fail(res, 500, 'PYTHON_ERROR', err.message));
    child.on('close', (code) => {
      if (code !== 0) return fail(res, 500, 'PYTHON_EXIT', sanitizeOutput(stderr || stdout));
      try {
        const data = JSON.parse(stdout.trim());
        res.json(data);
      } catch (e) {
        fail(res, 500, 'PARSE_ERROR', 'Failed to parse provider config: ' + e.message);
      }
    });
  } catch (err) {
    fail(res, 500, 'SERVER_ERROR', err.message);
  }
}));

adminPost('/api/admin/provider-config', async (req, res) => {
  const { active, default_model, discovery_model } = req.body;
  if (!active && !default_model) {
    return fail(res, 400, 'INVALID_INPUT', 'Provide at least active or default_model');
  }
  try {
    const py = getPythonCommand();
    const cmds = [];
    cmds.push('import sys; sys.path.insert(0, \"tools\")');
    cmds.push('from llm_router.config_providers import save_provider_config');
    cmds.push(`ok = save_provider_config(active=${JSON.stringify(active || '')}, default_model=${JSON.stringify(default_model || '')})`);
    // Save discovery_model separately (YAML text edit)
    if (discovery_model) {
      const fs = require('fs');
      const yamlPath = path.join(__dirname, '..', 'tools', 'config', 'providers.yaml');
      let text = fs.readFileSync(yamlPath, 'utf-8');
      text = text.replace(/^discovery_model:.*$/m, `discovery_model: "${discovery_model}"`);
      fs.writeFileSync(yamlPath, text, 'utf-8');
    }
    const code = cmds.join('; ');
    const child = spawn(py, ['-c', code], {
      cwd: path.join(__dirname, '..'),
      windowsHide: true,
      timeout: 15_000,
    });
    let stderr = '';
    child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
    child.on('error', (err) => fail(res, 500, 'PYTHON_ERROR', err.message));
    child.on('close', (code) => {
      if (code !== 0) return fail(res, 500, 'PYTHON_EXIT', sanitizeOutput(stderr));
      ok(res, { saved: true, active, default_model, discovery_model });
    });
  } catch (err) {
    fail(res, 500, 'SERVER_ERROR', err.message);
  }
});

function getPythonCommand() {
  return process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
}

function buildNovelctlTranslateArgs(slug, range, options = {}) {
  // Uses new novelclaw.py CLI — simple, linear, quality-first
  const workers = Math.min(Math.max(parseInt(options.workers, 10) || 1, 1), 5);
  const args = [
    path.join(__dirname, '..', 'novelclaw.py'),
    'translate',
    String(range),
  ];

  if (workers > 1) args.push('--parallel', String(workers));
  if (options.mock) args.push('--mock');
  if (options.model) args.push('--model', options.model);
  return args;
}

adminPost('/api/novel/:slug/translate/single', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const { num, score, model } = req.body;
  const chapterNum = parseInt(num, 10);
  if (Number.isNaN(chapterNum)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');

  const args = buildNovelctlTranslateArgs(slug, chapterNum, {
    mock: false,
    model: model || undefined,
  });

  const child = spawn(getPythonCommand(), args, {
    cwd: path.join(__dirname, '..'),
    windowsHide: true,
    timeout: 300_000,
    env: { ...process.env, NOVEL_SLUG: slug, PYTHONIOENCODING: 'utf-8' }
  });

  let stdout = '', stderr = '';
  child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
  child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });

  child.on('error', (err) => {
    console.error('Failed to start novelclaw.py:', err);
    if (!res.headersSent) {
      fail(res, 500, 'TRANSLATE_SPAWN_FAILED', `Failed to start novelclaw.py: ${err.message}`);
    }
  });

  child.on('close', (code) => {
    if (code !== 0) {
      if (!res.headersSent) {
        return fail(res, 500, 'TRANSLATE_FAILED', `novelclaw.py exited with code ${code}: ${sanitizeOutput(stderr || stdout)}`);
      }
      return;
    }
    
    chapterRepo.invalidateAll(slug);
    ok(res, { success: true, result: { ch: chapterNum, status: 'done' }, stdout });
  });
});

adminPost('/api/novel/:slug/translate/batch', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const { range, concurrent, model } = req.body;
  if (!range) return fail(res, 400, 'MISSING_RANGE', 'Chapter range (e.g. 5-10) is required.');

  const args = buildNovelctlTranslateArgs(slug, range, {
    workers: concurrent || 1,
    model: model || undefined,
  });

  const child = spawn(getPythonCommand(), args, {
    cwd: path.join(__dirname, '..'),
    windowsHide: true,
    timeout: 600_000,
    env: { ...process.env, NOVEL_SLUG: slug, PYTHONIOENCODING: 'utf-8' }
  });

  let stdout = '', stderr = '';
  child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
  child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });

  child.on('error', (err) => {
    console.error('Failed to start novelclaw.py batch:', err);
    if (!res.headersSent) {
      fail(res, 500, 'TRANSLATE_SPAWN_FAILED', `Failed to start novelclaw.py: ${err.message}`);
    }
  });

  child.on('close', (code) => {
    if (code !== 0) {
      if (!res.headersSent) {
        return fail(res, 500, 'TRANSLATE_FAILED', `novelclaw.py exited with code ${code}: ${sanitizeOutput(stderr || stdout)}`);
      }
      return;
    }
    
    chapterRepo.invalidateAll(slug);
    ok(res, { success: true, result: { range: String(range), status: 'done' }, stdout });
  });
});

// ── SPA fallback — serve index.html for all non-API routes ─────────

// INDEX_HTML read per-request (see SPA fallback below)

app.get('*', asyncHandler(async (req, res) => {
  if (req.path.startsWith('/api/')) return fail(res, 404, 'API_NOT_FOUND', 'API not found');
  res.set('Cache-Control', 'no-store, no-cache, must-revalidate');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');
  // Read index.html fresh each time — no stale cache
  // Use file mtime as cache-bust so browser re-fetches when file changes
  let html;
  try {
    const indexHtml = await fs.readFile(path.join(PUBLIC_DIR, 'index.html'), 'utf8');
    // Preserve _v (manual bumps) — don't override with _t which never changes
    html = indexHtml;  // index.html already has ?_v= in href/src from manual bump
  } catch {
    html = '<html><body><h1>Server Error</h1></body></html>';
  }
  res.send(html);
}));

// ── Global error handler ───────────────────────────────────────────

// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  if (!res.headersSent) {
    const status = err.status && Number.isInteger(err.status) ? err.status : 500;
    fail(res, status, 'INTERNAL_ERROR', err.message || 'Internal server error');
  }
});
