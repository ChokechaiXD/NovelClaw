// NovelClaw Reader — tiny web server, no DB, no build step.
//
// Usage: node server.js   (then open http://localhost:4173)
//
// Env:
//   PORT             — listening port (default 4173)
//   NOVELCLAW_ROOT   — path to the novels/ directory (default ../novels)

const express = require('express');
const fs = require('node:fs/promises');
const path = require('node:path');
const { marked } = require('marked');

const PORT = Number(process.env.PORT) || 4173;
const NOVELS_DIR = process.env.NOVELCLAW_ROOT
  ? path.resolve(process.env.NOVELCLAW_ROOT)
  : path.resolve(__dirname, '../novels');
const PUBLIC_DIR = path.resolve(__dirname, 'public');

// ── Chapter list cache ─────────────────────────────────────────────────
// For 1,239 chapters the title-extraction is N file reads per page load.
// Cache the result; invalidate when the chapters/ dir mtime changes (new
// file added/touched) or after 5 minutes (defensive TTL). Per-file mtime
// is also folded into the cache key so touching a single file invalidates.

const chapterListCache = new Map();
const CACHE_TTL_MS = 5 * 60 * 1000;

function invalidateCache(slug) {
  if (slug) chapterListCache.delete(slug);
  else chapterListCache.clear();
}

// ── Chapter content cache (LRU) ────────────────────────────────────────
// Parsed chapter JSON is expensive (file read + JSON.parse + render).
// Cache the rendered HTML by chapter num, LRU-evicted when size exceeds
// limit. For 1,239 ch × ~10KB rendered = 12MB worst case; cap at 200.

const CHAPTER_CACHE_MAX = 200;
const chapterHtmlCache = new Map();  // num -> { html, mtimeMs, size }

function getCachedChapter(num, fileMtime) {
  const entry = chapterHtmlCache.get(num);
  if (entry && entry.mtimeMs === fileMtime) {
    // LRU touch
    chapterHtmlCache.delete(num);
    chapterHtmlCache.set(num, entry);
    return entry.html;
  }
  return null;
}

function setCachedChapter(num, fileMtime, html) {
  // Evict oldest if over limit
  if (chapterHtmlCache.size >= CHAPTER_CACHE_MAX) {
    const oldest = chapterHtmlCache.keys().next().value;
    chapterHtmlCache.delete(oldest);
  }
  chapterHtmlCache.set(num, { html, mtimeMs: fileMtime, size: html.length });
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

async function readMeta(slug) {
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

async function readJsonOrNull(filepath) {
  const raw = await readTextOrNull(filepath);
  if (raw === null) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

async function listChapters(slug) {
  const dir = path.join(NOVELS_DIR, slug, 'chapters');
  let dirStat;
  try {
    dirStat = await fs.stat(dir);
  } catch (err) {
    if (err.code === 'ENOENT') return [];
    throw err;
  }
  const cached = chapterListCache.get(slug);
  // Cache key = dir mtime + slug. mtime of dir changes when files are
  // added/removed/renamed (not on file content edit, but title extraction
  // is content-derived; we read each file anyway, so a stale hit just
  // re-reads N files once after edit — acceptable).
  if (cached && cached.mtimeMs === dirStat.mtimeMs && Date.now() - cached.ts < CACHE_TTL_MS) {
    return cached.list;
  }
  const entries = await fs.readdir(dir, { withFileTypes: true });
  // Accept .json (new canonical) and .md (legacy)
  const files = entries
    .filter((e) => e.isFile() && /^\d{4}\.(json|md)$/.test(e.name))
    .map((e) => e.name);
  const out = [];
  // Dedupe: if both .json and .md exist for same num, keep .json only
  const seen = new Map();
  for (const f of files) {
    const num = parseInt(f.slice(0, 4), 10);
    const isJson = f.endsWith('.json');
    if (!seen.has(num) || isJson) seen.set(num, f);
  }
  // Read titles in parallel — N small file reads is fine and we cache anyway
  const titleEntries = await Promise.all(
    [...seen.entries()].map(async ([num, f]) => {
      let title = '';
      try {
        const raw = await fs.readFile(path.join(dir, f), 'utf8');
        if (f.endsWith('.json')) {
          const j = JSON.parse(raw);
          title = (j.title || '').toString();
        } else {
          const m = raw.match(/^#\s+(.+?)\r?\n/);
          if (m) title = m[1].trim();
        }
      } catch { /* ignore */ }
      return { num, title };
    }),
  );
  out.push(...titleEntries);
  out.sort((a, b) => a.num - b.num);
  chapterListCache.set(slug, { ts: Date.now(), mtimeMs: dirStat.mtimeMs, list: out });
  return out;
}

async function readChapter(slug, num) {
  const padded = String(num).padStart(4, '0');
  const file = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.md`);
  const jsonFile = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.json`);
  // Try JSON first (new canonical format), fallback to .md (legacy)
  let raw;
  let isJson = false;
  let fileStat;
  try {
    fileStat = await fs.stat(jsonFile);
    raw = await fs.readFile(jsonFile, 'utf8');
    isJson = true;
  } catch {
    try {
      fileStat = await fs.stat(file);
      raw = await fs.readFile(file, 'utf8');
    } catch (err) {
      if (err.code === 'ENOENT') return null;
      throw err;
    }
  }
  if (isJson) {
    // LRU cache hit? fileStat.mtimeMs is the cache key — content edit
    // bumps mtime automatically, no manual invalidation needed.
    const cached = getCachedChapter(num, fileStat.mtimeMs);
    if (cached) {
      return {
        title: cached.title,
        html: cached.html,
        metaHtml: cached.metaHtml,
        isJson: true,
      };
    }
    // New format: structured JSON, render directly
    const ch = JSON.parse(raw);
    const html = renderChapterJson(ch);
    const metaHtml = (ch.meta && ch.meta.length)
      ? `<ul>${ch.meta.map((m) => `<li>${m}</li>`).join('')}</ul>`
      : '';
    const result = {
      title: ch.title || `ตอนที่ ${ch.num}`,
      html,
      metaHtml,
      isJson: true,
    };
    setCachedChapter(num, fileStat.mtimeMs, result);
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
  return { title, body, meta, isJson: false };
}

/**
 * Render a Chapter JSON object directly to HTML.
 * Replaces marked.js for the new format — no parsing, just block-by-block DOM.
 *
 * Quote style (P'Chok's choice, 2026-06-14):
 *   Dialogue   → "..." (curly U+201C / U+201D) — Thai standard
 *   Nested     → '...' (curly U+2018 / U+2019) — inside curly double
 *   System msg → 【...】 (game UI, kept)
 *   Title      → 《...》 (kept)
 *   End        → (จบบท)
 *
 * Source blocks may use 「...」 (CN-style kagikakko); renderer converts to curly.
 */
function renderChapterJson(ch) {
  const esc = (s) => s;  // our text is already safe (no HTML in source)

  // Convert CN/JP kagikakko to curly Thai/EN quotes
  // 「 → " (U+201C),  」 → " (U+201D)
  // 『 → ' (U+2018),  』 → ' (U+2019)
  const toCurly = (s) => s
    .replace(/「/g, '\u201C')   // opening double
    .replace(/」/g, '\u201D')   // closing double
    .replace(/『/g, '\u2018')   // opening single
    .replace(/』/g, '\u2019');  // closing single

  let html = '';
  for (const block of ch.blocks || []) {
    if (block.type === 'narration') {
      html += `<p>${esc(toCurly(block.text))}</p>\n`;
    } else if (block.type === 'dialogue') {
      // dialogue: convert kagikakko to curly quotes
      html += `<p class="dialogue">${esc(toCurly(block.text))}</p>\n`;
    } else if (block.type === 'system') {
      // 【...】 system message — render with subtle background
      html += `<p class="system-msg">${esc(block.text)}</p>\n`;
    } else if (block.type === 'game_title') {
      // 《...》 game title — just text (rare standalone)
      html += `<p>${esc(block.text)}</p>\n`;
    } else if (block.type === 'end') {
      html += `<p class="end-marker">${esc(block.text)}</p>\n`;
    }
  }
  // Source footer
  if (ch.source) {
    html += `<hr/>\n<p class="source-footer">${esc(ch.source)}</p>\n`;
  }
  return html;
}

async function readSource(slug, num) {
  const padded = String(num).padStart(4, '0');
  return readTextOrNull(path.join(NOVELS_DIR, slug, 'chapters', 'source', `${padded}.md`));
}

// ── marked customization ───────────────────────────────────────────────

marked.setOptions({ gfm: true, breaks: false });

// ── routes ─────────────────────────────────────────────────────────────

const app = express();

app.use(express.static(PUBLIC_DIR));

app.get('/api/novels', async (_req, res) => {
  const slugs = await listNovels();
  const novels = await Promise.all(
    slugs.map(async (slug) => {
      const chapters = await listChapters(slug);
      const meta = await readMeta(slug);
      return { slug, chapterCount: chapters.length, meta };
    }),
  );
  res.json(novels);
});

app.get('/api/novel/:slug/chapters', async (req, res) => {
  const chapters = await listChapters(req.params.slug);
  res.json({ slug: req.params.slug, chapters });
});

app.get('/api/novel/:slug/chapter-numbers', async (req, res) => {
  const chapters = await listChapters(req.params.slug);
  res.json(chapters.map((c) => c.num));
});

// Search filter — case-insensitive, matches against num + title + number-prefix
// e.g. ?q=81 returns ch 81 if exists, else 810-819
// e.g. ?q=7  returns ch 7 if exists + ch 70-79
// e.g. ?q=นักธนู returns any chapter with "นักธนู" in title
app.get('/api/novel/:slug/chapters/search', async (req, res) => {
  const q = (req.query.q || '').toString().trim();
  if (!q) return res.json([]);
  const all = await listChapters(req.params.slug);
  const qn = parseInt(q, 10);
  const qLower = q.toLowerCase();
  const results = all.filter((c) => {
    if (Number.isFinite(qn) && c.num === qn) return true;
    if (Number.isFinite(qn) && String(c.num).startsWith(q)) return true;
    return c.title.toLowerCase().includes(qLower);
  });
  res.json(results);
});

app.get('/api/novel/:slug/chapter/:num', async (req, res) => {
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  try {
    const result = await readChapter(req.params.slug, num);
    if (!result) return res.status(404).json({ error: 'Chapter not found' });
    const { title, body, meta, html, metaHtml, isJson } = result;
    res.json({
      slug: req.params.slug,
      num,
      title,
      // For JSON mode, html is pre-rendered. For .md mode, parse with marked.
      html: isJson ? html : (body ? marked.parse(body) : ''),
      metaHtml: metaHtml || (meta ? marked.parse(meta) : ''),
    });
  } catch (err) {
    if (err.code === 'ENOENT') return res.status(404).json({ error: 'Chapter not found' });
    throw err;
  }
});

app.get('/api/novel/:slug/source/:num', async (req, res) => {
  const num = parseInt(req.params.num, 10);
  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
  const padded = String(num).padStart(4, '0');
  const raw = await readTextOrNull(path.join(NOVELS_DIR, req.params.slug, 'chapters', 'source', `${padded}.md`));
  if (raw === null) return res.status(404).json({ error: 'Source not found' });
  res.type('text/plain').send(raw);
});

app.get('/api/novel/:slug/glossary', async (req, res) => {
  const raw = await readTextOrNull(path.join(NOVELS_DIR, req.params.slug, 'glossary.md'));
  if (raw === null) return res.status(404).json({ error: 'No glossary' });
  res.type('text/plain').send(raw);
});

app.get('/api/novel/:slug/characters', async (req, res) => {
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

// ── start ─────────────────────────────────────────────────────────────────
//
// LAN access: bind to 0.0.0.0 (all interfaces) so phones on the same Wi-Fi
// can reach this server. Find your PC's IP with `ipconfig` (Windows) or
// `ifconfig` (mac/Linux). Then from phone: http://<your-ip>:4173/
//
// Windows Firewall: first run may prompt you to allow. If phone can't
// connect, allow Node.js through Windows Defender Firewall.
//
// To revert to localhost-only: change '0.0.0.0' to '127.0.0.1'

app.listen(PORT, '0.0.0.0', () => {
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
