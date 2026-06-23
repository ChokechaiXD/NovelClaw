/**
 * lib/search-service.js — Chapter search (title + content)
 *
 * Prefers search-index.{lang}.json when available for O(1) lookups.
 * Falls back to chapter-repo directory scan when index is missing.
 */

const fs = require('node:fs/promises');
const path = require('node:path');
const { chapterDir, chapterPath, searchIndexPath, pad } = require('./paths');
const { listChapters } = require('./chapter-repo');

// ── Title search (fast, in-memory) ─────────────────────────────────

function searchTitle(chapters, q, limit) {
  const results = [];
  const skip = new Set();
  const qn = parseInt(q, 10);
  const qLower = q.toLowerCase();

  for (const c of chapters) {
    if (results.length >= limit) break;

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
  return { results, skip };
}
exports.searchTitle = searchTitle;

// ── Content search (scan or index) ─────────────────────────────────

async function searchContent(slug, q, options = {}) {
  const limit = options.limit || 20;
  const lang = options.lang || 'all'; // 'th', 'cn', or 'all'
  const skip = options.skip || new Set();
  const qLower = q.toLowerCase();
  const results = [];
  const chapters = await listChapters(slug);
  const dir = chapterDir(slug);

  // Try search-index if available for the requested lang
  if (lang !== 'all') {
    try {
      const idxRaw = await fs.readFile(searchIndexPath(slug, lang), 'utf8');
      const idx = JSON.parse(idxRaw);
      for (const entry of idx.entries || []) {
        if (results.length >= limit) break;
        if (skip.has(entry.num)) continue;
        const text = (entry.text || '').toLowerCase();
        const idxPos = text.indexOf(qLower);
        if (idxPos !== -1) {
          const start = Math.max(0, idxPos - 40);
          const end = Math.min(text.length, idxPos + q.length + 40);
          const snippet = (idxPos > 40 ? '…' : '') + text.slice(start, end).trim() + (end < text.length ? '…' : '');
          results.push({ num: entry.num, title: entry.title || '', snippet, score: 1, source: 'content' });
          skip.add(entry.num);
        }
      }
      return results;
    } catch { /* index not found, fall through to scan */ }
  }

  // Fallback: scan chapter files
  let extensions;
  if (lang === 'all') extensions = ['th.json', 'cn.json', 'json', 'md'];
  else if (lang === 'th') extensions = ['th.json'];
  else if (lang === 'cn') extensions = ['cn.json'];
  else extensions = ['th.json', 'cn.json', 'json', 'md'];

  let found = 0;
  for (const ch of chapters) {
    if (found >= limit) break;
    if (skip.has(ch.num)) continue;
    const padded = pad(ch.num);

    let raw = null;
    let data = null;
    for (const ext of extensions.map(e => `${padded}.${e}`)) {
      try {
        raw = await fs.readFile(path.join(dir, ext), 'utf8');
        data = JSON.parse(raw);
        break;
      } catch {}
    }
    if (!data) continue;

    const text = (data.paragraphs || []).join('\n') || (data.blocks || []).map(b => b.text || '').join('\n');
    const idxPos = text.toLowerCase().indexOf(qLower);
    if (idxPos !== -1) {
      const start = Math.max(0, idxPos - 40);
      const end = Math.min(text.length, idxPos + q.length + 40);
      const snippet = (idxPos > 40 ? '…' : '') + text.slice(start, end).trim() + (end < text.length ? '…' : '');
      results.push({ num: ch.num, title: ch.title, snippet, score: 1, source: 'content' });
      skip.add(ch.num);
      found++;
    }
  }
  return results;
}
exports.searchContent = searchContent;

// ── Build search index (call after translate/save) ─────────────────

async function rebuildSearchIndex(slug, lang) {
  const chapters = await listChapters(slug);
  const dir = chapterDir(slug);
  const entries = [];

  for (const ch of chapters) {
    const padded = pad(ch.num);
    const ext = `${padded}.${lang}.json`;
    try {
      const raw = await fs.readFile(path.join(dir, ext), 'utf8');
      const data = JSON.parse(raw);
      const text = (data.paragraphs || []).join('\n') || (data.blocks || []).map(b => b.text || '').join('\n');
      entries.push({ num: ch.num, title: ch.title, text: text.slice(0, 10000) }); // cap per entry
    } catch {}
  }

  const idx = { slug, lang, updatedAt: new Date().toISOString(), entries };
  await fs.writeFile(searchIndexPath(slug, lang), JSON.stringify(idx, null, 2), 'utf8');
  return idx;
}
exports.rebuildSearchIndex = rebuildSearchIndex;
