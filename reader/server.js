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
// Cache the result; invalidate when the chapters/ dir mtime changes (new file)
// or after 5 minutes (defensive TTL).

const chapterListCache = new Map();
const CACHE_TTL_MS = 5 * 60 * 1000;

function invalidateCache(slug) {
  if (slug) chapterListCache.delete(slug);
  else chapterListCache.clear();
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

async function listChapters(slug) {
  const dir = path.join(NOVELS_DIR, slug, 'chapters');
  let stat;
  try {
    stat = await fs.stat(dir);
  } catch (err) {
    if (err.code === 'ENOENT') return [];
    throw err;
  }
  const cached = chapterListCache.get(slug);
  if (cached && cached.mtimeMs === stat.mtimeMs && Date.now() - cached.ts < CACHE_TTL_MS) {
    return cached.list;
  }
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = entries
    .filter((e) => e.isFile() && /^\d{4}\.md$/.test(e.name))
    .map((e) => e.name);
  const out = [];
  for (const f of files) {
    const num = parseInt(f.slice(0, 4), 10);
    let title = '';
    try {
      const raw = await fs.readFile(path.join(dir, f), 'utf8');
      const m = raw.match(/^#\s+(.+?)\r?\n/);
      if (m) title = m[1].trim();
    } catch { /* ignore */ }
    out.push({ num, title });
  }
  out.sort((a, b) => a.num - b.num);
  chapterListCache.set(slug, { ts: Date.now(), mtimeMs: stat.mtimeMs, list: out });
  return out;
}

async function readChapter(slug, num) {
  const padded = String(num).padStart(4, '0');
  const file = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.md`);
  const jsonFile = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.json`);
  // Try JSON first (new canonical format), fallback to .md (legacy)
  let raw;
  let isJson = false;
  try {
    raw = await fs.readFile(jsonFile, 'utf8');
    isJson = true;
  } catch {
    raw = await fs.readFile(file, 'utf8');
  }
  if (isJson) {
    // New format: structured JSON, render directly
    const ch = JSON.parse(raw);
    const html = renderChapterJson(ch);
    return {
      title: ch.title || `ตอนที่ ${ch.num}`,
      body: '', // not used in JSON mode
      meta: (ch.notes || []).join('\n'),
      html,
      metaHtml: '', // notes are inlined as <details>
      isJson: true,
    };
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
 */
function renderChapterJson(ch) {
  const escapeHtml = (s) => s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  const esc = (s) => s;  // our text is already safe (no HTML in source)

  let html = '';
  for (const block of ch.blocks || []) {
    if (block.type === 'narration') {
      html += `<p>${esc(block.text)}</p>\n`;
    } else if (block.type === 'dialogue') {
      // 「...」 is the canonical format; render with subtle indent
      html += `<p class="dialogue">${esc(block.text)}</p>\n`;
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
  const file = path.join(NOVELS_DIR, slug, 'chapters', 'source', `${padded}.md`);
  try {
    return await fs.readFile(file, 'utf8');
  } catch {
    return null;
  }
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
    const { title, body, meta, html, metaHtml, isJson } = await readChapter(req.params.slug, num);
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
  const raw = await readSource(req.params.slug, num);
  if (raw === null) return res.status(404).json({ error: 'Source not found' });
  res.type('text/plain').send(raw);
});

app.get('/api/novel/:slug/glossary', async (req, res) => {
  try {
    const raw = await fs.readFile(path.join(NOVELS_DIR, req.params.slug, 'glossary.md'), 'utf8');
    res.type('text/plain').send(raw);
  } catch (err) {
    if (err.code === 'ENOENT') return res.status(404).json({ error: 'No glossary' });
    throw err;
  }
});

app.get('/api/novel/:slug/characters', async (req, res) => {
  try {
    const raw = await fs.readFile(path.join(NOVELS_DIR, req.params.slug, 'characters.md'), 'utf8');
    res.type('text/plain').send(raw);
  } catch (err) {
    if (err.code === 'ENOENT') return res.status(404).json({ error: 'No characters' });
    throw err;
  }
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
