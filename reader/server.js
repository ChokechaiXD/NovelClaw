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
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');

// ── Lib modules ────────────────────────────────────────────────────
const { pad, assertValidSlug, SLUG_RE, novelDir, novelJsonPath, novelCoverPath,
        NOVEL_COVER_EXTENSIONS, sourceMdPath, glossaryJsonPath, glossaryMdPath,
        charactersMdPath, NOVELS_DIR, chapterPath } = require('./lib/paths');
const chapterRepo = require('./lib/chapter-repo');
const novelRepo = require('./lib/novel-repo');
const searchService = require('./lib/search-service');
const importHealth = require('./lib/import-health');
const providerConfigService = require('./lib/provider-config-service');
const translationHealth = require('./lib/translation-health');
const { parseTranslateJsonOutput, parseBatchTranslateSummary } = require('./lib/translate-result');
const { parseMarkdownToBlocks } = require('./lib/blocks');

// Re-export for tests
module.exports = { parseMarkdownToBlocks, chapterRepo, novelRepo, searchService };

// ── Config ─────────────────────────────────────────────────────────
const PORT = Number(process.env.PORT) || 4173;
const BIND_HOST = process.env.HOST || '127.0.0.1';
const PUBLIC_DIR = path.resolve(__dirname, 'public');
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || '';
const TRUSTED_LAN = process.env.TRUSTED_LAN === 'true';
const PERF_LOG = process.env.PERF_LOG === 'true';
const COVER_MAX_BYTES = 4 * 1024 * 1024;
const COVER_MIME_EXT = {
  'image/webp': 'webp',
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/gif': 'gif',
};
const COVER_EXT_MIME = {
  webp: 'image/webp',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
};

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
app.use(express.json({ limit: '8mb' }));

// Rate-limit admin write APIs in case ADMIN_TOKEN is leaked. The reader is
// intended for single-user localhost or small-LAN use, so 60 req/min/IP is
// generous for real use and tight enough to deflect casual bots.
const adminWriteLimiter = rateLimit({
  windowMs: 60 * 1000,
  limit: 60,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
  skip: () => isTrustedAdminMode(),
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

function isTrustedAdminMode() {
  return TRUSTED_LAN || isLocalBind(BIND_HOST);
}

function isValidAdminToken(provided) {
  if (!ADMIN_TOKEN || !provided) return false;
  const providedBuffer = Buffer.from(provided);
  const tokenBuffer = Buffer.from(ADMIN_TOKEN);
  return providedBuffer.length === tokenBuffer.length
    && crypto.timingSafeEqual(providedBuffer, tokenBuffer);
}

function requireAdmin(req, res, next) {
  if (isTrustedAdminMode()) return next();
  if (!ADMIN_TOKEN) {
    return fail(res, 403, 'ADMIN_LOCKED', 'Admin write APIs require ADMIN_TOKEN unless HOST is local or TRUSTED_LAN=true');
  }
  const provided = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  if (!provided) {
    return fail(res, 401, 'AUTH_REQUIRED', 'Unauthorized — provide Authorization: Bearer <token>');
  }
  if (isValidAdminToken(provided)) {
    return next();
  }
  fail(res, 401, 'AUTH_INVALID', 'Unauthorized — invalid token');
}

function logTiming(label, startedAt) {
  if (!PERF_LOG) return;
  console.log(`[perf] ${label} ${Date.now() - startedAt}ms`);
}

const qualityMetaCache = new Map();
const QUALITY_META_TTL_MS = 30 * 1000;

function getCachedQualityMeta(cacheKey) {
  const cached = qualityMetaCache.get(cacheKey);
  if (!cached || Date.now() - cached.time > QUALITY_META_TTL_MS) return null;
  return cached.value;
}

function invalidateQualityMeta(slug, num = null) {
  if (num !== null && num !== undefined) {
    qualityMetaCache.delete(`${slug}:${num}`);
    return;
  }
  for (const key of qualityMetaCache.keys()) {
    if (key.startsWith(`${slug}:`)) qualityMetaCache.delete(key);
  }
}

async function readChapterQualityMeta(slug, num) {
  const cacheKey = `${slug}:${num}`;
  const cached = getCachedQualityMeta(cacheKey);
  if (cached) return cached;

  const paddedNum = String(num).padStart(4, '0');
  const qualityPath = path.join(__dirname, '..', 'jobs', 'quality', slug, `${paddedNum}.json`);
  const meta = { score: null, model: 'unknown', provider: 'unknown', promptProfile: '', quality: null };

  try {
    const rawChapter = await fs.readFile(chapterPath(slug, num, 'th'), 'utf8');
    const chapterData = JSON.parse(rawChapter);
    const chapterMeta = chapterData.meta || {};
    const qualityRecord = chapterData.qualityRecord && typeof chapterData.qualityRecord === 'object'
      ? chapterData.qualityRecord
      : null;
    meta.model = chapterMeta.model || chapterData.model || meta.model;
    meta.provider = chapterMeta.provider || chapterData.provider || meta.provider;
    meta.promptProfile = chapterMeta.promptProfile || '';
    meta.quality = qualityRecord;
    if (qualityRecord && qualityRecord.score !== undefined) meta.score = qualityRecord.score;
    else if (chapterData.score !== undefined) meta.score = chapterData.score;
  } catch {}

  try {
    const rawQuality = await fs.readFile(qualityPath, 'utf8');
    const qData = JSON.parse(rawQuality);
    if (qData && Array.isArray(qData.records)) {
      for (let i = qData.records.length - 1; i >= 0; i--) {
        const rec = qData.records[i];
        if (meta.score === null && rec.score !== undefined && rec.score !== null) meta.score = rec.score;
        if (meta.model === 'unknown' && rec.model && rec.model !== 'unknown') meta.model = rec.model;
        if (meta.provider === 'unknown' && rec.provider && rec.provider !== 'unknown') meta.provider = rec.provider;
      }
      if (qData.records.length > 0) {
        const lastRec = qData.records[qData.records.length - 1];
        if (meta.model === 'unknown' && lastRec.model) meta.model = lastRec.model;
        if (meta.provider === 'unknown' && lastRec.provider) meta.provider = lastRec.provider;
      }
    }
  } catch {
    const reportPath = path.join(__dirname, '..', 'logs', 'translate', slug, paddedNum, 'report.json');
    try {
      const rawReport = await fs.readFile(reportPath, 'utf8');
      const rData = JSON.parse(rawReport);
      if (rData && rData.result && rData.result.score !== undefined) meta.score = rData.result.score;
    } catch {}
  }

  if (meta.score === null) meta.score = 100;
  qualityMetaCache.set(cacheKey, { time: Date.now(), value: meta });
  return meta;
}

// File read helper
async function readTextOrNull(filepath) {
  try { return await fs.readFile(filepath, 'utf8'); }
  catch (err) { if (err.code === 'ENOENT') return null; throw err; }
}

function buildCoverUrl(slug, updatedAt = '') {
  const suffix = updatedAt ? `?v=${encodeURIComponent(updatedAt)}` : '';
  return `/api/novel/${slug}/cover${suffix}`;
}

async function findNovelCover(slug) {
  for (const ext of NOVEL_COVER_EXTENSIONS) {
    const filepath = novelCoverPath(slug, ext);
    try {
      const stat = await fs.stat(filepath);
      return { filepath, ext, mime: COVER_EXT_MIME[ext] || 'application/octet-stream', stat };
    } catch (err) {
      if (err.code !== 'ENOENT') throw err;
    }
  }
  return null;
}

function parseCoverImageData(imageData) {
  const match = String(imageData || '').match(/^data:(image\/(?:webp|png|jpeg|gif));base64,([A-Za-z0-9+/=\s]+)$/);
  if (!match) {
    throw Object.assign(new Error('Cover must be a PNG, JPEG, WebP, or GIF data URL'), { status: 400, code: 'INVALID_COVER' });
  }
  const mime = match[1];
  const ext = COVER_MIME_EXT[mime];
  const buffer = Buffer.from(match[2].replace(/\s/g, ''), 'base64');
  if (!buffer.length || buffer.length > COVER_MAX_BYTES) {
    throw Object.assign(new Error('Cover image must be 1 byte to 4 MB'), { status: 400, code: 'COVER_TOO_LARGE' });
  }
  return { mime, ext, buffer };
}

function runPythonJson(args, options = {}) {
  const { input = null, timeout = 300_000 } = options;
  return new Promise((resolve, reject) => {
    const child = spawn(getPythonCommand(), args, {
      cwd: path.join(__dirname, '..'),
      windowsHide: true,
      timeout,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
    child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(sanitizeOutput(stderr || stdout) || `Python exited ${code}`));
        return;
      }
      try {
        const payload = JSON.parse(stdout);
        if (payload && payload.ok === false) {
          reject(new Error(payload.error?.message || 'Import command failed'));
          return;
        }
        resolve(payload && payload.data !== undefined ? payload.data : payload);
      } catch (err) {
        reject(new Error('Failed to parse import JSON: ' + sanitizeOutput(stdout)));
      }
    });
    if (input !== null) child.stdin.write(input);
    child.stdin.end();
  });
}

async function finalizeSourceImport(slug) {
  assertValidSlug(slug);
  await chapterRepo.rebuildChaptersIndex(slug);
  chapterRepo.invalidateAll(slug);
  invalidateCache('/api/novel/' + slug);
  invalidateCache('/api/novels');
}

// ── Novel listing and metadata ─────────────────────────────────────

app.get('/api/novels', asyncHandler(async (_req, res) => {
  const startedAt = Date.now();
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
        coverImage: meta.coverImage || (meta.coverExt ? buildCoverUrl(slug, meta.coverUpdatedAt) : ''),
        coverUpdatedAt: meta.coverUpdatedAt || '',
      };
    }),
  );
  logTiming('GET /api/novels', startedAt);
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
  const startedAt = Date.now();
  const withQuality = req.query.withQuality === '1' || req.query.withQuality === 'true';
  const chapters = await chapterRepo.listChapters(req.params.slug, { includeQuality: withQuality });
  res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
  logTiming(`GET /api/novel/${req.params.slug}/chapters`, startedAt);
  res.json({ slug: req.params.slug, chapters });
}));

app.get('/api/novel/:slug/cover', asyncHandler(async (req, res) => {
  const cover = await findNovelCover(req.params.slug);
  if (!cover) return fail(res, 404, 'COVER_NOT_FOUND', 'Cover image not found');
  const data = await fs.readFile(cover.filepath);
  res.set('Cache-Control', 'public, max-age=60, stale-while-revalidate=300');
  res.type(cover.mime).send(data);
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
    const { results: titleResults } = searchService.searchTitle(all, q, limit);
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
  const startedAt = Date.now();
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');
  const lang = (req.query.lang || 'th').toString();
  const result = await chapterRepo.getChapter(req.params.slug, num, lang);
  if (!result) return fail(res, 404, 'CHAPTER_NOT_FOUND', 'Chapter not found');
  const qualityMeta = await readChapterQualityMeta(req.params.slug, num);

  res.set('Cache-Control', 'public, max-age=20, stale-while-revalidate=60');
  res.set('X-Cache-TTL', '20');
  logTiming(`GET /api/novel/${req.params.slug}/chapter/${num}?lang=${lang}`, startedAt);

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
    score: qualityMeta.score,
    model: qualityMeta.model,
    provider: qualityMeta.provider,
    promptProfile: qualityMeta.promptProfile,
    quality: qualityMeta.quality,
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

async function readGlossaryTerms(slug) {
  const raw = await readTextOrNull(glossaryJsonPath(slug));
  if (!raw) return [];
  const data = JSON.parse(raw);
  return Array.isArray(data.terms) ? data.terms : [];
}

async function writeGlossaryTerms(slug, terms) {
  const filepath = glossaryJsonPath(slug);
  await fs.mkdir(path.dirname(filepath), { recursive: true });
  await fs.writeFile(filepath, JSON.stringify({ terms: Array.isArray(terms) ? terms : [] }, null, 2), 'utf8');
  chapterRepo.invalidateAll(slug);
}

adminPost('/api/novel/:slug/glossary/save', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const terms = Array.isArray(req.body?.terms) ? req.body.terms : [];
  await writeGlossaryTerms(slug, terms);
  ok(res, { saved: true, count: terms.length });
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

adminPost('/api/novel/:slug/cover', async (req, res) => {
  const slug = req.params.slug;
  const { imageData } = req.body;
  let parsed;
  try {
    parsed = parseCoverImageData(imageData);
  } catch (err) {
    return fail(res, err.status || 400, err.code || 'INVALID_COVER', err.message);
  }
  await fs.mkdir(novelDir(slug), { recursive: true });

  for (const ext of NOVEL_COVER_EXTENSIONS) {
    if (ext !== parsed.ext) {
      await fs.rm(novelCoverPath(slug, ext), { force: true }).catch(() => {});
    }
  }

  await fs.writeFile(novelCoverPath(slug, parsed.ext), parsed.buffer);
  const coverUpdatedAt = new Date().toISOString();
  const coverImage = buildCoverUrl(slug, coverUpdatedAt);
  await novelRepo.saveNovelMeta(slug, {
    coverImage,
    coverExt: parsed.ext,
    coverUpdatedAt,
  });
  invalidateCache('/api/novels');
  ok(res, { slug, coverImage, coverExt: parsed.ext, coverUpdatedAt });
});

adminPost('/api/novel/:slug/cover/delete', async (req, res) => {
  const slug = req.params.slug;
  for (const ext of NOVEL_COVER_EXTENSIONS) {
    await fs.rm(novelCoverPath(slug, ext), { force: true }).catch(() => {});
  }
  await novelRepo.saveNovelMeta(slug, {
    coverImage: '',
    coverExt: '',
    coverUpdatedAt: new Date().toISOString(),
  });
  invalidateCache('/api/novels');
  ok(res, { slug, deleted: true });
});

// ── Admin delete novel ─────────────────────────────────────────────

adminPost('/api/novel/:slug/delete', async (req, res) => {
  await novelRepo.deleteNovel(req.params.slug);
  ok(res, { deleted: true });
});

// ── Admin source import ──────────────────────────────────────────────

app.get('/api/import/sites', asyncHandler(async (_req, res) => {
  try {
    const data = await runPythonJson([
      path.join(__dirname, '..', 'novelclaw.py'),
      'import-sites',
    ], { timeout: 30_000 });
    ok(res, data);
  } catch (err) {
    fail(res, 500, 'IMPORT_SITES_FAILED', err.message);
  }
}));

app.get('/api/import/health', asyncHandler(async (req, res) => {
  try {
    const slug = (req.query.slug || '').toString().trim();
    const includeChapters = req.query.includeChapters === '1' || req.query.includeChapters === 'true';
    const data = slug
      ? await importHealth.getNovelImportHealth(slug, { includeChapters })
      : await importHealth.getAllImportHealth();
    ok(res, data);
  } catch (err) {
    fail(res, err.status || 500, 'IMPORT_HEALTH_FAILED', err.message);
  }
}));

app.get('/api/import/source-inspect', asyncHandler(async (req, res) => {
  const slug = (req.query.slug || '').toString().trim();
  const num = parseInt(req.query.num, 10);
  if (!slug || !SLUG_RE.test(slug)) return fail(res, 400, 'INVALID_SLUG', 'Invalid slug format');
  if (Number.isNaN(num)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');
  try {
    const data = await importHealth.inspectSourceChapter(slug, num);
    ok(res, data);
  } catch (err) {
    fail(res, err.status || 500, 'SOURCE_INSPECT_FAILED', err.message);
  }
}));

adminPost('/api/import/repair', async (req, res) => {
  const { slug, action, dryRun } = req.body;
  if (!slug || !SLUG_RE.test(slug)) return fail(res, 400, 'INVALID_SLUG', 'Invalid slug format');
  try {
    const result = await importHealth.repairNovelImport(slug, action || 'rebuild-index', { dryRun: dryRun === true });
    if (dryRun !== true) {
      invalidateCache('/api/novel/' + slug);
      invalidateCache('/api/novels');
    }
    ok(res, { slug, action: action || 'rebuild-index', ...result });
  } catch (err) {
    fail(res, err.status || 500, 'IMPORT_REPAIR_FAILED', err.message);
  }
});

adminPost('/api/import/recover-toc', async (req, res) => {
  const { slug, site, url, dryRun } = req.body;
  if (!slug || !SLUG_RE.test(slug)) return fail(res, 400, 'INVALID_SLUG', 'Invalid slug format');
  const args = [
    path.join(__dirname, '..', 'tools', 'import_sources.py'),
    'recover-toc',
    '--slug',
    slug,
    '--site',
    site || 'auto',
  ];
  if (url) args.push('--url', String(url));
  if (dryRun === true) args.push('--dry-run');

  try {
    const result = await runPythonJson(args, { timeout: 120_000 });
    ok(res, result);
  } catch (err) {
    fail(res, err.status || 500, 'IMPORT_TOC_RECOVERY_FAILED', err.message);
  }
});

adminPost('/api/import/preview', async (req, res) => {
  const { url, site } = req.body;
  if (!url) return fail(res, 400, 'MISSING_URL', 'Source URL is required');

  try {
    const data = await runPythonJson([
      path.join(__dirname, '..', 'novelclaw.py'),
      'import-url',
      String(url),
      '--slug',
      'preview',
      '--site',
      site || 'auto',
      '--preview',
    ], { timeout: 120_000 });
    ok(res, data);
  } catch (err) {
    fail(res, 400, 'IMPORT_PREVIEW_FAILED', err.message);
  }
});

adminPost('/api/import/run', async (req, res) => {
  const { url, slug, site, range, force } = req.body;
  if (!url) return fail(res, 400, 'MISSING_URL', 'Source URL is required');
  if (!slug || !SLUG_RE.test(slug)) return fail(res, 400, 'INVALID_SLUG', 'Invalid slug format');

  const args = [
    path.join(__dirname, '..', 'novelclaw.py'),
    'import-url',
    String(url),
    '--slug',
    slug,
    '--site',
    site || 'auto',
  ];
  if (range) args.push('--range', String(range));
  if (force) args.push('--force');

  try {
    const data = await runPythonJson(args, { timeout: 600_000 });
    await finalizeSourceImport(slug);
    ok(res, data);
  } catch (err) {
    fail(res, 500, 'IMPORT_RUN_FAILED', err.message);
  }
});

adminPost('/api/import/paste', async (req, res) => {
  const { slug, title, author, sourceLang, splitRule, content, force } = req.body;
  if (!slug || !SLUG_RE.test(slug)) return fail(res, 400, 'INVALID_SLUG', 'Invalid slug format');
  if (!content || !String(content).trim()) return fail(res, 400, 'MISSING_CONTENT', 'Import content is required');

  const args = [
    path.join(__dirname, '..', 'tools', 'import_sources.py'),
    'paste',
    '--slug',
    slug,
    '--title',
    title || slug,
    '--source-lang',
    sourceLang || 'cn',
  ];
  if (author) args.push('--author', String(author));
  if (splitRule) args.push('--split-rule', String(splitRule));
  if (force) args.push('--force');

  try {
    const data = await runPythonJson(args, { input: String(content), timeout: 180_000 });
    await finalizeSourceImport(slug);
    ok(res, data);
  } catch (err) {
    fail(res, 500, 'IMPORT_PASTE_FAILED', err.message);
  }
});

// ── Admin import novel from text file ──────────────────────────────

adminPost('/api/novel/import-file', async (req, res) => {
  const { title, slug, author, sourceLang, splitRule, content } = req.body;
  if (!slug || !SLUG_RE.test(slug)) {
    return fail(res, 400, 'INVALID_SLUG', 'Invalid slug format');
  }
  if (!content || !String(content).trim()) {
    return fail(res, 400, 'MISSING_CONTENT', 'Import content is required');
  }

  const args = [
    path.join(__dirname, '..', 'tools', 'import_sources.py'),
    'paste',
    '--slug',
    slug,
    '--title',
    title || slug,
    '--source-lang',
    sourceLang || 'cn',
  ];
  if (author) args.push('--author', String(author));
  if (splitRule) args.push('--split-rule', String(splitRule));

  try {
    const data = await runPythonJson(args, { input: String(content), timeout: 180_000 });
    await finalizeSourceImport(slug);
    res.json({ ...data, success: true, chaptersCount: data.chapterCount });
  } catch (err) {
    fail(res, 500, 'IMPORT_FILE_FAILED', err.message);
  }
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
const JOBS_DIR = path.resolve(__dirname, '..', 'jobs');

async function collectJobBucket(bucket) {
  const dir = path.join(JOBS_DIR, bucket);
  const files = [];
  async function walk(current, depth = 0) {
    if (depth > 2) return;
    let entries;
    try { entries = await fs.readdir(current, { withFileTypes: true }); }
    catch (err) {
      if (err.code === 'ENOENT') return;
      throw err;
    }
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        await walk(fullPath, depth + 1);
      } else if (entry.isFile()) {
        const stat = await fs.stat(fullPath);
        files.push({
          name: path.relative(dir, fullPath).replace(/\\/g, '/'),
          mtimeMs: stat.mtimeMs,
          size: stat.size,
        });
      }
    }
  }
  await walk(dir);
  files.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return files;
}

app.get('/api/admin/translation-health', requireAdmin, asyncHandler(async (req, res) => {
  const buckets = ['active', 'done', 'failed', 'needs_review'];
  const result = {};
  for (const bucket of buckets) {
    const files = await collectJobBucket(bucket);
    result[bucket] = {
      count: files.length,
      latest: files.slice(0, 5).map(file => ({
        name: file.name,
        size: file.size,
        updatedAt: new Date(file.mtimeMs).toISOString(),
      })),
    };
  }
  const batchLogs = await translationHealth.readBatchLogs(path.resolve(__dirname, '..'));
  ok(res, { buckets: result, batchLogs });
}));

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
  try {
    terms = await readGlossaryTerms(slug);
  } catch (err) {
    return fail(res, 500, 'GLOSSARY_PARSE_ERROR', 'Invalid glossary.json', err.message);
  }

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

  await writeGlossaryTerms(slug, terms);
  ok(res, { added: true, term: { source, thai } });
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

  ok(res, {
    source: String(term).trim(),
    thai: '',
    confidence: 'manual',
    notes: 'LLM term suggestion is not wired yet. Enter the Thai term manually.',
    context: context || '',
  });
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
  await writeGlossaryTerms(slug, terms);
  ok(res, { verified: terms[idx].verified });
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

function providerKeyField(providerId) {
  if (providerId === 'openmodel') return 'openmodel_api_key';
  if (providerId === 'openrouter') return 'openrouter_api_key';
  if (providerId === 'custom') return 'custom_api_key';
  return `${providerId}_api_key`;
}

function providerHasKey(providerId, localKeys = {}) {
  const envName = `${providerId.toUpperCase()}_API_KEY`;
  return !!(
    localKeys[providerKeyField(providerId)]
    || localKeys.api_key && providerId === 'openmodel'
    || process.env[envName]
    || process.env.LLM_API_KEY && providerId === 'openmodel'
  );
}

function buildLlmConfigResponse(providerConfig = {}, localKeys = {}) {
  const defaultProvider = providerConfig.active || localKeys.default_provider || 'openrouter';
  const defaultModel = providerConfig.default_model || localKeys.default_model || 'google/gemma-4-26b-a4b-it:free';
  const providers = (providerConfig.providers || []).map(provider => {
    const providerId = provider.name || provider.id;
    return {
      id: providerId,
      label: provider.display_name || provider.label || providerId,
      description: provider.base_url || '',
      keyField: providerKeyField(providerId),
      hasKey: providerHasKey(providerId, localKeys),
      modelSource: provider.model_source || 'static',
      modelError: provider.model_error || '',
      models: (provider.models || []).map(model => ({
        id: model.id,
        label: model.name || model.label || model.id,
        tier: model.tier || provider.model_source || 'static',
      })),
    };
  });

  const activeProvider = providers.find(p => p.id === defaultProvider) || providers[0];
  if (activeProvider && !activeProvider.models.some(m => m.id === defaultModel)) {
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

// Compatibility wrapper for older Reader controls. The provider catalog and
// model selection still come from providerConfigService as the single source.
app.get('/api/local/llm-config', asyncHandler(async (req, res) => {
  const refreshModels = req.query.refreshModels === '1' || req.query.refreshModels === 'true';
  let localKeys = {};
  try {
    const raw = await fs.readFile(LLM_JSON_PATH, 'utf8');
    localKeys = JSON.parse(raw);
  } catch (err) {}
  const providerConfig = await providerConfigService.readProviderConfig({ refreshModels });
  res.json(buildLlmConfigResponse(providerConfig, localKeys));
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

  if (openrouter_api_key || openmodel_api_key || api_key) {
    await fs.writeFile(LLM_JSON_PATH, JSON.stringify(data, null, 2), 'utf8');
  }
  if (default_model || default_provider) {
    await providerConfigService.saveProviderConfig({
      active: default_provider || null,
      default_model: default_model || null,
      discovery_model: null,
      custom_base_url: null,
      custom_api_key: null,
    });
  }
  const providerConfig = await providerConfigService.readProviderConfig();
  ok(res, { saved: true, config: buildLlmConfigResponse(providerConfig, data) });
});

app.get('/api/admin/provider-config', asyncHandler(async (req, res) => {
  const startedAt = Date.now();
  try {
    const data = await providerConfigService.readProviderConfig({
      refreshModels: req.query.refreshModels === '1' || req.query.refreshModels === 'true',
    });
    logTiming('GET /api/admin/provider-config', startedAt);
    res.json(data);
  } catch (err) {
    fail(res, 500, 'SERVER_ERROR', err.message);
  }
}));

adminPost('/api/admin/provider-config', async (req, res) => {
  const { active, default_model, discovery_model, custom_base_url, custom_api_key, api_key_provider, api_key } = req.body;
  if (!active && !default_model && !discovery_model && !custom_base_url && !custom_api_key && !api_key) {
    return fail(res, 400, 'INVALID_INPUT', 'Provide at least active, default_model, discovery_model, or custom endpoint settings');
  }
  try {
    await providerConfigService.saveProviderConfig({
      active: active || null,
      default_model: default_model || null,
      discovery_model: discovery_model || null,
      custom_base_url: custom_base_url || null,
      custom_api_key: custom_api_key || null,
      api_key_provider: api_key_provider || active || null,
      api_key: api_key || null,
    });
    ok(res, { saved: true, active, default_model, discovery_model, custom_base_url: custom_base_url || null });
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
  if (options.provider) args.push('--provider', options.provider);
  if (options.promptProfile) args.push('--profile', options.promptProfile);
  if (options.json) args.push('--json');
  return args;
}

function parseChapterRangeSpec(range) {
  const nums = new Set();
  const parts = String(range || '').split(',').map(part => part.trim()).filter(Boolean);
  for (const part of parts) {
    const match = part.match(/^(\d+)(?:-(\d+))?$/);
    if (!match) continue;
    const start = parseInt(match[1], 10);
    const end = match[2] ? parseInt(match[2], 10) : start;
    if (!Number.isFinite(start) || !Number.isFinite(end)) continue;
    const lo = Math.max(1, Math.min(start, end));
    const hi = Math.max(start, end);
    for (let n = lo; n <= hi && nums.size < 5000; n++) nums.add(n);
  }
  return [...nums].sort((a, b) => a - b);
}

async function assertSourceReadyForTranslate(slug, nums, options = {}) {
  if (options.force === true) return [];
  const blocking = await importHealth.getBlockingSourceIssues(slug, nums);
  if (!blocking.length) return [];
  const sample = blocking.slice(0, 8).map(chapter => {
    const codes = chapter.issues.map(issue => issue.code).join(', ');
    return `ตอน ${chapter.num}: ${codes}`;
  }).join('; ');
  const err = new Error(`Source ยังไม่พร้อมแปล พบ source error ${blocking.length} ตอน (${sample})`);
  err.status = 409;
  err.code = 'SOURCE_NOT_READY';
  err.details = {
    blockingCount: blocking.length,
    blocking: blocking.slice(0, 20),
  };
  throw err;
}

adminPost('/api/novel/:slug/translate/single', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const { num, score, model, provider, promptProfile, force } = req.body;
  const chapterNum = parseInt(num, 10);
  if (Number.isNaN(chapterNum)) return fail(res, 400, 'INVALID_NUM', 'Invalid chapter number');
  try {
    await assertSourceReadyForTranslate(slug, [chapterNum], { force: force === true });
  } catch (err) {
    return fail(res, err.status || 500, err.code || 'SOURCE_CHECK_FAILED', err.message, err.details);
  }

  const args = buildNovelctlTranslateArgs(slug, chapterNum, {
    mock: false,
    model: model || undefined,
    provider: provider || undefined,
    promptProfile: promptProfile || undefined,
    json: true,
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
    
    const results = parseTranslateJsonOutput(stdout);
    const result = results[results.length - 1] || null;
    if (!result || result.status !== 'ok') {
      const reason = result?.reason || sanitizeOutput(stderr || stdout) || 'Translation did not produce an ok result';
      if (!res.headersSent) {
        return fail(res, 500, 'TRANSLATE_FAILED', reason, result || undefined);
      }
      return;
    }

    chapterRepo.invalidateAll(slug);
    invalidateQualityMeta(slug, chapterNum);
    ok(res, { success: true, result, stdout });
  });
});

adminPost('/api/novel/:slug/translate/batch', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const { range, concurrent, model, provider, promptProfile, force } = req.body;
  if (!range) return fail(res, 400, 'MISSING_RANGE', 'Chapter range (e.g. 5-10) is required.');
  const nums = parseChapterRangeSpec(range);
  if (!nums.length) return fail(res, 400, 'INVALID_RANGE', 'Invalid chapter range. Use examples like 5, 5-10, or 1,3-5.');
  try {
    await assertSourceReadyForTranslate(slug, nums, { force: force === true });
  } catch (err) {
    return fail(res, err.status || 500, err.code || 'SOURCE_CHECK_FAILED', err.message, err.details);
  }

  const args = buildNovelctlTranslateArgs(slug, range, {
    workers: concurrent || 1,
    model: model || undefined,
    provider: provider || undefined,
    promptProfile: promptProfile || undefined,
    json: true,
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
    
    const summary = parseBatchTranslateSummary(stdout);
    chapterRepo.invalidateAll(slug);
    invalidateQualityMeta(slug);
    if (summary.failed > 0) {
      if (!res.headersSent) {
        return fail(res, 500, 'TRANSLATE_PARTIAL_FAILED', `Batch finished with ${summary.failed} failed chapter(s)`, { summary, stdout });
      }
      return;
    }
    ok(res, { success: true, result: { range: String(range), status: 'done', summary, chapters: summary.chapters || [] }, stdout });
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
