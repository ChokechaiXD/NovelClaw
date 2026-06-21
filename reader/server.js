// NovelClaw Reader — tiny web server, no DB, no build step.
//
// Usage: node server.js   (then open http://localhost:4173)
//
// Env:
//   PORT             — listening port (default 4173)
//   NOVELCLAW_ROOT   — path to the novels/ directory (default ../novels)

const express = require('express');
const fs = require('node:fs/promises');
const fsSync = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { marked } = require('marked');

// Export pure functions for testing
// When required as a module, only the renderer + helpers are exported.
// When run directly (`node server.js`), the server starts.
const PORT = Number(process.env.PORT) || 4173;
const NOVELS_DIR = process.env.NOVELCLAW_ROOT
  ? path.resolve(process.env.NOVELCLAW_ROOT)
  : path.resolve(__dirname, '../novels');
const PUBLIC_DIR = path.resolve(__dirname, 'public');

// ── Cache (unified) ──────────────────────────────────────────────────────
// Single Map with prefixed keys: 'list:{slug}', 'html:{slug}:{num}', 'meta:{slug}'
// For 1,239 chapters the title-extraction is N file reads per page load.
// Cache the result; invalidate when the chapters/ dir mtime changes (new
// file added/touched) or after 5 minutes (defensive TTL). Per-file mtime
// is also folded into the cache key so touching a single file invalidates.
// For HTML: parsed chapter JSON is expensive (file read + JSON.parse + render).
// Cache the rendered HTML by chapter num, LRU-evicted when size exceeds limit.

const cache = new Map();
const CACHE_TTL_MS = 5 * 60 * 1000;
const CHAPTER_CACHE_MAX = 200;

function invalidateCache(slug) {
  if (slug) {
    cache.delete('list:' + slug);
    cache.delete('meta:' + slug);
    // Clear HTML entries for this slug
    for (const k of cache.keys()) {
      if (k.startsWith('html:' + slug + ':')) cache.delete(k);
    }
  } else {
    cache.clear();
  }
}

function getCachedChapter(slug, num, fileMtime) {
  const key = 'html:' + slug + ':' + num;
  const entry = cache.get(key);
  if (entry && entry.mtimeMs === fileMtime) {
    cache.delete(key);
    cache.set(key, entry);
    return entry.html;
  }
  return null;
}

function setCachedChapter(slug, num, fileMtime, html) {
  const key = 'html:' + slug + ':' + num;
  if (cache.size >= CHAPTER_CACHE_MAX) {
    const oldest = cache.keys().next().value;
    cache.delete(oldest);
  }
  cache.set(key, { html, mtimeMs: fileMtime, size: ((html && html.html) || '').length });
}

// ── helpers ────────────────────────────────────────────────────────────

async function listNovels() {
  try {
    const entries = await fs.readdir(NOVELS_DIR, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory())
      .map((d) => d.name)
      .sort();
  } catch (err) {
    if (err.code === 'ENOENT') return [];
    throw err;
  }
}

// ── Security helpers ──────────────────────────────────────────────────
// Validate slug to prevent path traversal. Applied at every entry point
// that accepts a slug from the URL.
const SLUG_RE = /^[a-zA-Z0-9_-]+$/;

function assertValidSlug(slug) {
  if (!SLUG_RE.test(slug)) throw Object.assign(new Error('Invalid slug format'), { status: 400 });
}

async function readMeta(slug) {
  assertValidSlug(slug);
  try {
    return await fs.readFile(path.join(NOVELS_DIR, slug, 'meta.md'), 'utf8');
  } catch {
    return '';
  }
}

// ── File helpers — dedupe the try/catch + ENOENT pattern ───────────────
// All these routes read a single file and 404 if missing. One helper.

async function readTextOrNull(filepath) {
  try {
    return await fs.readFile(filepath, 'utf8');
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw err;
  }
}


async function listChapters(slug) {
  // Security: reject path traversal attempts
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) return [];
  const dir = path.join(NOVELS_DIR, slug, 'chapters');
  let dirStat;
  try {
    dirStat = await fs.stat(dir);
  } catch (err) {
    if (err.code === 'ENOENT') return [];
    throw err;
  }

  let sourceDirMtimeMs = 0;
  try {
    const sourceStat = await fs.stat(path.join(dir, 'source'));
    sourceDirMtimeMs = sourceStat.mtimeMs;
  } catch {}
  const cacheKeyMtime = dirStat.mtimeMs + sourceDirMtimeMs;

  const cached = cache.get('list:' + slug);
  // Cache key = dir mtime + source dir mtime + slug.
  if (cached && cached.mtimeMs === cacheKeyMtime && Date.now() - cached.ts < CACHE_TTL_MS) {
    return cached.list;
  }
  const entries = await fs.readdir(dir, { withFileTypes: true });
  // Accept .json (new canonical) and .md (legacy)
  const files = entries
    .filter((e) => e.isFile() && /^\d{4}\.(json|md)$/.test(e.name))
    .map((e) => e.name);

  // Also list source files
  let sourceFiles = [];
  try {
    const sourceEntries = await fs.readdir(path.join(dir, 'source'), { withFileTypes: true });
    sourceFiles = sourceEntries
      .filter((e) => e.isFile() && /^\d{4}\.md$/.test(e.name))
      .map((e) => e.name);
  } catch {}

  const out = [];
  // Dedupe: if both .json and .md exist for same num, keep .json only.
  // If only source exists, mark it as source.
  const seen = new Map();
  for (const f of files) {
    const num = parseInt(f.slice(0, 4), 10);
    const isJson = f.endsWith('.json');
    if (!seen.has(num) || isJson) seen.set(num, { name: f, isSource: false });
  }
  for (const sf of sourceFiles) {
    const num = parseInt(sf.slice(0, 4), 10);
    if (!seen.has(num)) {
      seen.set(num, { name: sf, isSource: true });
    }
  }

  // Read titles in parallel — N small file reads is fine and we cache anyway
  const titleEntries = await Promise.all(
    [...seen.entries()].map(async ([num, entry]) => {
      let title = '';
      let isTranslated = !entry.isSource;
      try {
        if (entry.isSource) {
          const raw = await fs.readFile(path.join(dir, 'source', entry.name), 'utf8');
          const m = raw.match(/^#\s+(.+?)\r?\n/);
          if (m) title = m[1].trim();
          else title = `ตอนที่ ${num} [ยังไม่แปล]`;
        } else {
          const raw = await fs.readFile(path.join(dir, entry.name), 'utf8');
          if (entry.name.endsWith('.json')) {
            const j = JSON.parse(raw);
            title = (j.title || '').toString();
          } else {
            const m = raw.match(/^#\s+(.+?)\r?\n/);
            if (m) title = m[1].trim();
          }
        }
      } catch { /* ignore */ }
      if (!title) {
        title = entry.isSource ? `ตอนที่ ${num} [ยังไม่แปล]` : `ตอนที่ ${num}`;
      }
      return { num, title, isTranslated };
    }),
  );
  out.push(...titleEntries);
  out.sort((a, b) => a.num - b.num);
  cache.set('list:' + slug, { ts: Date.now(), mtimeMs: cacheKeyMtime, list: out });
  return out;
}

async function readChapter(slug, num) {
  assertValidSlug(slug);
  const padded = String(num).padStart(4, '0');
  const file = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.md`);
  const jsonFile = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.json`);
  const sourceFile = path.join(NOVELS_DIR, slug, 'chapters', 'source', `${padded}.md`);

  // Try JSON first (new canonical format), fallback to .md (legacy), fallback to source
  let raw;
  let isJson = false;
  let fileStat;
  let isTranslated = true;
  try {
    fileStat = await fs.stat(jsonFile);
    raw = await fs.readFile(jsonFile, 'utf8');
    isJson = true;
  } catch {
    try {
      fileStat = await fs.stat(file);
      raw = await fs.readFile(file, 'utf8');
    } catch (err) {
      try {
        fileStat = await fs.stat(sourceFile);
        raw = await fs.readFile(sourceFile, 'utf8');
        isTranslated = false;
        isJson = true; // Use blocks parsing on raw source file
      } catch (sourceErr) {
        if (sourceErr.code === 'ENOENT') return null;
        throw sourceErr;
      }
    }
  }

  if (!isTranslated) {
    const parsed = parseMarkdownToBlocks(raw, num);
    const html = renderChapterJson(parsed);
    return {
      title: parsed.title || `ตอนที่ ${num} [ยังไม่แปล]`,
      html,
      metaHtml: '',
      isJson: true,
      blocks: parsed.blocks,
      source: `ch ${num} (Original Source)`,
      lang: 'cn',
      notes: [],
      markdownText: raw,
      isTranslated: false
    };
  }

  if (isJson) {
    // LRU cache hit? fileStat.mtimeMs is the cache key — content edit
    // bumps mtime automatically, no manual invalidation needed.
    const cached = getCachedChapter(slug, num, fileStat.mtimeMs);
    let ch;
    try {
      ch = JSON.parse(raw);
    } catch (parseErr) {
      throw Object.assign(new Error(`Invalid JSON in ${padded}.json: ${parseErr.message}`), { status: 500 });
    }
    
    if (cached) {
      return {
        title: cached.title,
        html: cached.html,
        metaHtml: cached.metaHtml,
        isJson: true,
        blocks: cached.blocks || ch.blocks || [],
        source: cached.source || ch.source || '',
        lang: cached.lang || ch.lang || 'cn',
        notes: cached.notes || ch.notes || [],
        markdownText: cached.markdownText || convertBlocksToMarkdown(ch.title || `ตอนที่ ${num}`, ch.blocks || [], ch.source || '', ch.notes || []),
        isTranslated: true
      };
    }
    // New format: structured JSON, render directly
    const html = renderChapterJson(ch);
    const metaHtml = (ch.notes && ch.notes.length)
      ? `<ul>${ch.notes.map((m) => `<li>${esc(m)}</li>`).join('')}</ul>`
      : '';
    const markdownText = convertBlocksToMarkdown(ch.title || `ตอนที่ ${num}`, ch.blocks || [], ch.source || '', ch.notes || []);
    const result = {
      title: ch.title || `ตอนที่ ${ch.num}`,
      html,
      metaHtml,
      isJson: true,
      blocks: ch.blocks || [],
      source: ch.source || '',
      lang: ch.lang || 'cn',
      notes: ch.notes || [],
      markdownText,
      isTranslated: true
    };
    setCachedChapter(slug, num, fileStat.mtimeMs, result);
    return result;
  }
  // Legacy .md path
  const parts = raw.split(/\n---\n/);
  let body = (parts[0] || '').trim();
  // If there's a 2nd --- in the body itself, keep it (Source footer separator)
  let meta = '';
  if (parts.length >= 3) {
    body = body + '\n\n---\n\n' + (parts[1] || '').trim();
    meta = (parts[2] || '').trim();
  } else if (parts.length === 2) {
    const subparts = parts[1].split(/\n---\n/);
    if (subparts.length >= 2) {
      body = body + '\n\n---\n\n' + subparts[0].trim();
      meta = subparts.slice(1).join('\n\n---\n').trim();
    } else {
      body = body + '\n\n---\n\n' + parts[1].trim();
    }
  }
  let title = '';
  const m = body.match(/^#\s+(.+?)\r?\n/);
  if (m) {
    title = m[1].trim();
    body = body.slice(m[0].length).trim();
  }
  
  const parsed = parseMarkdownToBlocks(raw, num);
  
  return {
    title,
    body,
    meta,
    isJson: false,
    blocks: parsed.blocks,
    source: parsed.notes.length > 0 ? '' : `ch ${num}`,
    lang: 'cn',
    notes: parsed.notes,
    markdownText: raw
  };
}

// ── Chapter rendering (delegated to lib/render.js for profile support) ──
const { renderChapterJson } = require('./lib/render');
const { esc } = require('./lib/helpers');
const { validateChapterJs } = require('./services/validation');

// ── Markdown Parser & Generator helpers ───────────────────────────

function parseMarkdownToBlocks(mdText, chapterNum) {
  const normalized = mdText.replace(/\r\n/g, '\n').trim();
  const parts = normalized.split(/\n-{3,}\n/);
  
  let body = '';
  let metaText = '';
  
  if (parts.length >= 3) {
    const firstPart = parts[0].trim();
    const lines = firstPart.split('\n');
    if (lines.length <= 6) {
      body = parts[1].trim();
      metaText = parts.slice(2).join('\n\n');
    } else {
      body = parts.slice(0, -1).join('\n\n---\n\n');
      metaText = parts[parts.length - 1];
    }
  } else if (parts.length === 2) {
    const firstPart = parts[0].trim();
    const lines = firstPart.split('\n');
    if (lines.length <= 6) {
      body = parts[1].trim();
      metaText = '';
    } else {
      body = parts[0].trim();
      metaText = parts[1].trim();
    }
  } else {
    body = parts[0].trim();
    metaText = '';
  }
  
  let title = '';
  const titleMatch = body.match(/^#\s+(.+)/);
  if (titleMatch) {
    title = titleMatch[1].trim();
    body = body.slice(titleMatch[0].length).trim();
  } else {
    const fallbackMatch = parts[0].trim().match(/^#\s+(.+)/);
    if (fallbackMatch) {
      title = fallbackMatch[1].trim();
    }
  }
  
  const notes = [];
  if (metaText) {
    for (const line of metaText.split('\n')) {
      const trimmed = line.trim();
      if (trimmed.startsWith('- ')) {
        notes.push(trimmed.slice(2));
      }
    }
  }
  
  const paragraphs = body.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
  const blocks = [];
  
  for (const p of paragraphs) {
    if (p === '(จบบท)' || p === '（終）' || p === '(끝)' || p === '(End)') {
      blocks.push({ type: 'end', text: p });
      continue;
    }
    
    if (p.startsWith('【') && p.endsWith('】')) {
      blocks.push({ type: 'system', text: p });
    } else if (p.startsWith('「') && p.endsWith('」')) {
      blocks.push({ type: 'dialogue', text: p, speaker: '' });
    } else if (p.startsWith('“') && p.endsWith('”') || p.startsWith('\u201C') && p.endsWith('\u201D')) {
      blocks.push({ type: 'dialogue', text: p, speaker: '' });
    } else if (p.startsWith('《') && p.endsWith('》')) {
      blocks.push({ type: 'game_title', text: p });
    } else {
      const speakerRegex = /^([^「」“”\u201C\u201D:\n]+)(?:พูด|กล่าว|ถาม|ตะโกน|บอก|:|\s)+([「“”\u201C\u201D][^「」“”\u201C\u201D]+[」“”\u201C\u201D])$/;
      const dialogueMatch = p.match(speakerRegex);
      if (dialogueMatch) {
        blocks.push({
          type: 'dialogue',
          text: dialogueMatch[2],
          speaker: dialogueMatch[1].trim()
        });
      } else {
        blocks.push({ type: 'narration', text: p });
      }
    }
  }
  
  if (!blocks.some(b => b.type === 'end')) {
    blocks.push({ type: 'end', text: '(จบบท)' });
  }
  
  return { title, blocks, notes };
}

function convertBlocksToMarkdown(title, blocks, source, notes = []) {
  let md = `# ${title}\n\n`;
  
  for (const block of blocks) {
    if (block.type === 'end') {
      md += `${block.text}\n\n`;
    } else if (block.type === 'dialogue') {
      if (block.speaker) {
        md += `${block.speaker}พูด: ${block.text}\n\n`;
      } else {
        md += `${block.text}\n\n`;
      }
    } else {
      md += `${block.text}\n\n`;
    }
  }
  
  md = md.trim() + '\n';
  
  if (source || (notes && notes.length > 0)) {
    md += '\n---\n\n';
    if (source) {
      md += `*Source: ch ${source.replace(/^(ch\s*)+/gi, '')}*\n\n`;
    }
    if (notes && notes.length > 0) {
      md += 'หมายเหตุการแปล:\n';
      for (const n of notes) {
        md += `- ${n}\n`;
      }
      md += '\n';
    }
  }
  
  return md.trim() + '\n';
}

// ── marked customization ───────────────────────────────────────────────

marked.setOptions({ gfm: true, breaks: false });

// ── routes ─────────────────────────────────────────────────────────────

const app = express();
app.use(express.json())

// ── i18n Middleware ─────────────────────────────────────────────
// Load locale files for TH/EN
const LOCALE_DIR = path.join(__dirname, 'locales');
let locales = {};
try {
    const files = fsSync.readdirSync(LOCALE_DIR);
    for (const f of files) {
        if (f.endsWith('.json')) {
            const lang = f.replace('.json', '');
            const content = fsSync.readFileSync(path.join(LOCALE_DIR, f), 'utf-8');
            locales[lang] = JSON.parse(content);
            console.log(`i18n: loaded ${lang}`);
        }
    }
} catch (e) {
    console.error('i18n: no locales directory, using fallback');
}

// Resolve language from cookie > Accept-Language > 'th'
function getLang(req) {
    // Manual cookie parsing (no cookie-parser dependency)
    const raw = req.headers.cookie || '';
    const m = raw.match(/\blang=([^;]+)/);
    if (m && locales[m[1]]) return m[1];
    const accept = (req.headers['accept-language'] || '').split(',')[0] || '';
    const base = accept.split('-')[0].trim().toLowerCase();
    if (base && locales[base]) return base;
    return 'th';
}

// t() helper available in all route handlers
app.use((req, res, next) => {
    const lang = getLang(req);
    const locale = locales[lang] || locales['th'] || {};
    req.t = function (key, fallback) {
        const parts = key.split('.');
        let val = locale;
        for (const p of parts) {
            val = val?.[p];
            if (val === undefined) break;
        }
        return val ?? fallback ?? key;
    };
    req.locale = lang;
    next();
});

// Language switcher endpoint
app.get('/api/lang/:lang', (req, res) => {
    const lang = req.params.lang;
    if (locales[lang]) {
        res.cookie('lang', lang, { maxAge: 365 * 24 * 60 * 60 * 1000, httpOnly: false });
        res.json({ lang, messages: locales[lang] });
    } else {
        res.status(404).json({ error: `Unknown locale: ${lang}` });
    }
});

// Get current locale messages (for client-side)
app.get('/api/lang', (req, res) => {
    const lang = getLang(req);
    res.json({ lang, messages: locales[lang] || locales['th'] });
});
;

// Disable caching for static files during development — prevents stale JS/CSS
// from blocking bug fixes. Remove or set maxAge for production.
app.use(express.static(PUBLIC_DIR, {
  etag: false,
  lastModified: false,
  setHeaders: (res, filePath) => {
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
  },
}));

// ── Slug validation middleware ──────────────────────────────────────────
// Prevents path traversal: only allow alphanumeric, hyphens, underscores.
// Applied to every route that takes a :slug parameter.
app.param('slug', (req, res, next, slug) => {
  if (!SLUG_RE.test(slug)) {
    return res.status(400).json({ error: 'Invalid slug format' });
  }
  next();
});

// ── Novel metadata cache (Phase 2 — multi-novel support) ──────────────
// Reads meta.md YAML frontmatter once per novel. Cached like the
// chapter list. Frontmatter format:
//   ---
//   slug: global-descent
//   title: 全球降臨...
//   source_lang: cn
//   target_lang: th
//   ...
//   ---



async function readNovelMeta(slug) {
  assertValidSlug(slug);
  const mk = "meta:" + slug; if (cache.has(mk)) return cache.get(mk);
  const metaPath = path.join(NOVELS_DIR, slug, 'meta.md');
  let raw = '';
  try {
    raw = await fs.readFile(metaPath, 'utf8');
  } catch {
    const fallback = { slug, title: slug, source_lang: 'cn', target_lang: 'th' };
    cache.set(mk, fallback);
    return fallback;
  }
  // Parse YAML frontmatter
  const m = raw.match(/^---\s*\n([\s\S]*?)\n---/);
  const meta = { slug, title: slug, source_lang: 'cn', target_lang: 'th' };
  if (m) {
    for (const line of m[1].split('\n')) {
      const kv = line.match(/^(\w[\w_]*):\s*(.+?)\s*$/);
      if (kv) {
        let val = kv[2].replace(/^['"]|['"]$/g, '');
        meta[kv[1]] = val;
      }
    }
  }
  cache.set(mk, meta);
  return meta;
}

app.get('/api/novels', async (_req, res) => {
  const slugs = await listNovels();
  const novels = await Promise.all(
    slugs.map(async (slug) => {
      const meta = await readNovelMeta(slug);
      const chapters = await listChapters(slug);
      return {
        slug,
        title: meta.title || slug,
        author: meta.author || '',
        source_lang: meta.source_lang || 'cn',
        target_lang: meta.target_lang || 'th',
        chapterCount: chapters.length,
        totalChapters: parseInt(meta.total_chapters, 10) || chapters.length,
        status: meta.status || 'unknown',
        meta: await readMeta(slug),
      };
    }),
  );
  res.json(novels);
});

app.get('/api/novel/:slug/chapters', async (req, res) => {
  const chapters = await listChapters(req.params.slug);
  res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.json({ slug: req.params.slug, chapters });
});

app.get('/api/novel/:slug/chapter-numbers', async (req, res) => {
  const chapters = await listChapters(req.params.slug);
  res.json(chapters.map((c) => c.num));
});

// Search filter — case-insensitive, matches against num + title + number-prefix
// e.g. ?q=81 returns ch 81 if exists, else 810-819
// e.g. ?q=7  returns ch 7 if exists + ch 70-79
// e.g. ?q=นักธนู returns any chapter with "นักธนู" in title or content
//
// mode=title (default): in-memory filter on title + num (fast, no Python).
// mode=content: in-memory text search (no Python dependency). Best for finding
//               where a character/place/event was mentioned.
// mode=all: union of both (deduped, title hits ranked first).
app.get('/api/novel/:slug/chapters/search', async (req, res) => {
  const q = (req.query.q || '').toString().trim();
  const mode = (req.query.mode || 'title').toString();
  const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
  if (!q) return res.json([]);
  if (q.length > 200) return res.status(400).json({ error: 'Query too long (max 200 chars)' });
  if (!['title', 'content', 'all'].includes(mode)) {
    return res.status(400).json({ error: `Unknown mode '${mode}' (use title|content|all)` });
  }

  let results = [];
  const skip = new Set();
  if (mode === 'title' || mode === 'all') {
    const all = await listChapters(req.params.slug);
    const qn = parseInt(q, 10);
    const qLower = q.toLowerCase();
    for (const c of all) {
      if (Number.isFinite(qn) && c.num === qn) {
        if (!skip.has(c.num)) { results.push({ num: c.num, title: c.title, source: 'title' }); skip.add(c.num); }
        continue;
      }
      if (Number.isFinite(qn) && String(c.num).startsWith(q)) {
        if (!skip.has(c.num)) { results.push({ num: c.num, title: c.title, source: 'title' }); skip.add(c.num); }
        continue;
      }
      if (c.title && c.title.toLowerCase().includes(qLower)) {
        if (!skip.has(c.num)) { results.push({ num: c.num, title: c.title, source: 'title' }); skip.add(c.num); }
      }
    }
  }

  // In-memory content search (replaces Python subprocess FTS5)
  if (mode === 'content' || mode === 'all') {
    const dir = path.join(NOVELS_DIR, req.params.slug, 'chapters');
    const all = await listChapters(req.params.slug);
    const qLower = q.toLowerCase();
    let found = 0;
    for (const ch of all) {
      if (found >= limit) break;
      if (skip.has(ch.num)) continue;
      const padded = String(ch.num).padStart(4, '0');
      try {
        const raw = await fs.readFile(path.join(dir, `${padded}.json`), 'utf8');
        const data = JSON.parse(raw);
        const text = (data.blocks || []).map(b => b.text || '').join('\n');
        const idx = text.toLowerCase().indexOf(qLower);
        if (idx !== -1) {
          const start = Math.max(0, idx - 40);
          const end = Math.min(text.length, idx + q.length + 40);
          let snippet = (idx > 40 ? '…' : '') + text.slice(start, end).trim() + (end < text.length ? '…' : '');
          results.push({ num: ch.num, title: ch.title, snippet, score: 1, source: 'content' });
          skip.add(ch.num);
          found++;
        }
      } catch { /* skip unreadable files */ }
    }
  }

  res.json(results.slice(0, limit));
});

app.get('/api/novel/:slug/chapter/:num', async (req, res) => {
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  try {
    const result = await readChapter(req.params.slug, num);
    if (!result) return res.status(404).json({ error: 'Chapter not found' });
    const { title, body, meta, html, metaHtml, isJson } = result;

    // Run validation to compute score card only if translated
    let valResult = { score: 100, valid: true, errors: [], warnings: [], info: [] };
    if (result.isTranslated !== false) {
      valResult = await validateChapterJs(req.params.slug, num, title, result.blocks || [], result.source || '', result.lang || 'cn', { novelRoot: NOVELS_DIR });
    }

    // Cache control: always revalidate with server before using cached response
    res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.set('Pragma', 'no-cache');
    res.set('Expires', '0');

    res.json({
      slug: req.params.slug,
      num,
      title,
      html: isJson ? html : (body ? marked.parse(body) : ''),
      metaHtml: metaHtml || (meta ? marked.parse(meta) : ''),
      isJson,
      blocks: result.blocks || [],
      source: result.source || '',
      lang: result.lang || 'cn',
      notes: result.notes || [],
      markdownText: result.markdownText || '',
      score: valResult.score,
      isTranslated: result.isTranslated !== false,
      validation: {
        valid: valResult.valid,
        errors: valResult.errors,
        warnings: valResult.warnings,
        info: valResult.info
      }
    });
  } catch (err) {
    if (err.code === 'ENOENT') return res.status(404).json({ error: 'Chapter not found' });
    throw err;
  }
});

app.get('/api/novel/:slug/source/:num', async (req, res) => {
  assertValidSlug(req.params.slug);
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  const padded = String(num).padStart(4, '0');
  const raw = await readTextOrNull(path.join(NOVELS_DIR, req.params.slug, 'chapters', 'source', `${padded}.md`));
  if (raw === null) return res.status(404).json({ error: 'Source not found' });
  res.type('text/plain').send(raw);
});

app.get('/api/novel/:slug/glossary', async (req, res) => {
  assertValidSlug(req.params.slug);
  const raw = await readTextOrNull(path.join(NOVELS_DIR, req.params.slug, 'glossary.md'));
  if (raw === null) return res.status(404).json({ error: 'No glossary' });
  res.type('text/plain').send(raw);
});

app.get('/api/novel/:slug/glossary/data', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const glossaryScript = path.join(__dirname, '..', 'tools', 'glossary.py');
  const execFileAsync = require('util').promisify(require('child_process').execFile);
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  try {
    const { stdout } = await execFileAsync(py, [glossaryScript, '--novel', slug, '--load'], {
      env: { ...process.env, NOVEL_SLUG: slug }
    });
    res.json(JSON.parse(stdout));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/novel/:slug/glossary/save', async (req, res) => {
  assertValidSlug(req.params.slug);
  const slug = req.params.slug;
  const glossaryScript = path.join(__dirname, '..', 'tools', 'glossary.py');
  const { spawn } = require('child_process');
  
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const args = [glossaryScript, '--novel', slug, '--save'];
  
  const child = spawn(py, args, { cwd: path.join(__dirname, '..'), windowsHide: true, timeout: 10_000 });
  let stdout = '';
  let stderr = '';
  
  child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
  child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
  
  child.on('close', (code) => {
    if (code !== 0) {
      res.status(500).json({ error: `glossary.py exited ${code}: ${stderr}` });
      return;
    }
    
    invalidateCache(slug);
    invalidateCache(slug);
    res.json({ ok: true });
  });
  
  child.stdin.write(JSON.stringify(req.body));
  child.stdin.end();
});

app.get('/api/novel/:slug/characters', async (req, res) => {
  assertValidSlug(req.params.slug);
  const raw = await readTextOrNull(path.join(NOVELS_DIR, req.params.slug, 'characters.md'));
  if (raw === null) return res.status(404).json({ error: 'No characters' });
  res.type('text/plain').send(raw);
});

// Manual cache invalidation (called after a new chapter is translated).
// Useful for scripting: `curl -X POST /api/invalidate-cache` after writing.
app.post('/api/invalidate-cache', (req, res) => {
  invalidateCache();
  res.json({ ok: true });
});

// ── Admin & Translation API Endpoints (Ponytail Style) ─────────────────

app.post('/api/novel/update', async (req, res) => {
  const { slug, title, author, source_lang, target_lang, status, total_chapters } = req.body;
  if (!slug || !SLUG_RE.test(slug)) return res.status(400).json({ error: 'Invalid slug format' });
  const novelDir = path.join(NOVELS_DIR, slug);
  const chaptersDir = path.join(novelDir, 'chapters');
  try {
    await fs.mkdir(chaptersDir, { recursive: true });
    const metaContent = `---
slug: ${slug}
title: ${title || slug}
author: ${author || ''}
source_lang: ${source_lang || 'cn'}
target_lang: ${target_lang || 'th'}
status: ${status || 'ongoing'}
total_chapters: ${total_chapters || '100'}
---
# ${title || slug}`;
    await fs.writeFile(path.join(novelDir, 'meta.md'), metaContent, 'utf8');
    cache.delete("meta:" + slug);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/novel/:slug/delete', async (req, res) => {
  const slug = req.params.slug;
  const novelDir = path.join(NOVELS_DIR, slug);
  try {
    await fs.rm(novelDir, { recursive: true, force: true });
    cache.delete("meta:" + slug);
    invalidateCache(slug);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});
app.post('/api/novel/:slug/chapter/:num/save', async (req, res) => {
  const slug = req.params.slug;
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  const padded = String(num).padStart(4, '0');
  let { title, blocks, source, lang, markdownText } = req.body;

  let notes = [];
  if (markdownText) {
    const parsed = parseMarkdownToBlocks(markdownText, num);
    blocks = parsed.blocks;
    if (!title) title = parsed.title;
    notes = parsed.notes;
  }

  const jsonPath = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.json`);
  const chapterData = {
    num,
    title: title || `ตอนที่ ${num}`,
    lang: lang || 'cn',
    blocks: blocks || [],
    source: source || '',
    notes: notes || []
  };

  const valResult = await validateChapterJs(slug, num, chapterData.title, chapterData.blocks, chapterData.source, chapterData.lang, { novelRoot: NOVELS_DIR });
  
  if (!valResult.valid) {
    const errorMsg = [
      '━'.repeat(70),
      `  VALIDATION — Ch ${num} (JS Native)`,
      '━'.repeat(70),
      '',
      ...valResult.info.map(line => `  ℹ  ${line}`),
      '',
      ...valResult.warnings.map(line => `  ⚠  ${line}`),
      ...valResult.errors.map(line => `  ✗  ${line}`),
      '',
      `❌ FAILED — ${valResult.errors.length} error(s) found`
    ].join('\n');
    
    return res.status(422).json({
      error: 'Validation Error',
      details: errorMsg
    });
  }

  try {
    await fs.mkdir(path.dirname(jsonPath), { recursive: true });
    await fs.writeFile(jsonPath, JSON.stringify(chapterData, null, 2), 'utf8');

    invalidateCache(slug);

    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/admin/users', async (req, res) => {
  const usersPath = path.join(__dirname, 'users.json');
  try {
    const data = await fs.readFile(usersPath, 'utf8');
    res.json(JSON.parse(data));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/admin/users/save', async (req, res) => {
  const usersPath = path.join(__dirname, 'users.json');
  const users = req.body;
  try {
    await fs.writeFile(usersPath, JSON.stringify(users, null, 2), 'utf8');
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/novel/:slug/chapter/:num/delete', async (req, res) => {
  const slug = req.params.slug;
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  const padded = String(num).padStart(4, '0');
  const jsonPath = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.json`);
  const mdPath = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.md`);
  try {
    await fs.rm(jsonPath, { force: true });
    await fs.rm(mdPath, { force: true });
    invalidateCache(slug);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Reviews & Comments APIs (Phase B Social) ───────────────────────────
//
// LAN access: bind to 0.0.0.0 (all interfaces) so phones on the same Wi-Fi
// can reach this server. Find your PC's IP with `ipconfig` (Windows) or
// `ifconfig` (mac/Linux). Then from phone: http://<your-ip>:4173/
//
// Windows Firewall: first run may prompt you to allow. If phone can't
// connect, allow Node.js through Windows Defender Firewall.
//
// To revert to localhost-only: change '0.0.0.0' to '127.0.0.1'

const server = app.listen(PORT, '0.0.0.0', () => {
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
  if (ips.length) {
    console.log(`  (LAN access — open on phone on same Wi-Fi):`);
    for (const ip of ips) console.log(ip);
  }
  console.log(`Serving novels from: ${NOVELS_DIR}`);
});

let _eaddrRetries = 0;
server.on('error', (err) => {
  if (err.code === 'EADDRINUSE' && _eaddrRetries < 3) {
    _eaddrRetries++;
    console.log(`⚠️  Port ${PORT} already in use — killing old server (attempt ${_eaddrRetries}/3)...`);
    const { execSync } = require('node:child_process');
    try {
      if (process.platform === 'win32') {
        const out = execSync(`netstat -ano | findstr :${PORT}`, { encoding: 'utf8' });
        const lines = out.trim().split('\n');
        for (const line of lines) {
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
    setTimeout(() => {
      server.listen(PORT, '0.0.0.0');
    }, 500);
  } else {
    console.error('Server error:', err);
  }
});

const START_TIME = Date.now();

// ── SPA fallback ──────────────────────────────────────────────────────
// Any route that isn't an API call or a static file serves index.html
// so the frontend JS can handle routing via URL params.
// Inject ?_t=START_TIME to bust browser cache for JS/CSS after server restart.
app.get('*', (req, res) => {
  if (req.path.startsWith('/api/')) return res.status(404).json({ error: 'API not found' });
  res.set('Cache-Control', 'no-store, no-cache, must-revalidate');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');
  let html = fsSync.readFileSync(path.join(PUBLIC_DIR, 'index.html'), 'utf8');
  // Cache-bust: append server start timestamp to script src URLs
  html = html.replace('src="/virtual-scroll.js"', `src="/virtual-scroll.js?_t=${START_TIME}"`);
  html = html.replace('src="/app.js"', `src="/app.js?_t=${START_TIME}"`);
  res.send(html);
});

// ── Global error handler ────────────────────────────────────────────────
// Catches unhandled sync throws and unawaited promise rejections from
// async route handlers. Without this, any uncaught error crashes the
// process (Node 15+ terminates on unhandled rejections).
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  if (!res.headersSent) {
    const status = err.status && Number.isInteger(err.status) ? err.status : 500;
    res.status(status).json({ error: err.message || 'Internal server error' });
  }
});

// ── Exports (for testing) ─────────────────────────────────────────────
// When this file is required as a module (test_server.js, future
// in-process consumers), export the pure functions. When run via
// `node server.js`, the app.listen above is the entry point.

module.exports = { renderChapterJson };
