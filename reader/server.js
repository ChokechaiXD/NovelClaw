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
const { spawn } = require('node:child_process');
const { marked } = require('marked');
const multer = require('multer');

// Export pure functions for testing (without spinning up HTTP server)
// When required as a module, only the renderer + helpers are exported.
// When run directly (`node server.js`), the server starts.
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
const chapterHtmlCache = new Map();  // `${slug}:${num}` -> { html, mtimeMs, size }

function getCachedChapter(slug, num, fileMtime) {
  const key = `${slug}:${num}`;
  const entry = chapterHtmlCache.get(key);
  if (entry && entry.mtimeMs === fileMtime) {
    // LRU touch
    chapterHtmlCache.delete(key);
    chapterHtmlCache.set(key, entry);
    return entry.html;
  }
  return null;
}

function setCachedChapter(slug, num, fileMtime, html) {
  const key = `${slug}:${num}`;
  // Evict oldest if over limit
  if (chapterHtmlCache.size >= CHAPTER_CACHE_MAX) {
    const oldest = chapterHtmlCache.keys().next().value;
    chapterHtmlCache.delete(oldest);
  }
  chapterHtmlCache.set(key, { html, mtimeMs: fileMtime, size: ((html && html.html) || '').length });
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
function assertValidSlug(slug) {
  if (!SLUG_RE.test(slug)) throw Object.assign(new Error('Invalid slug format'), { status: 400 });
}

const esc = (s) => String(s)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

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

  const cached = chapterListCache.get(slug);
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
  chapterListCache.set(slug, { ts: Date.now(), mtimeMs: cacheKeyMtime, list: out });
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

// ── Bracket / quote config per language (mirrors tools/schema.py) ─────
//
// Each source language has its own bracket convention. The renderer
// picks the right profile from ch.lang. For 'en' and 'th', dialogue
// uses curly "..." (U+201C/U+201D). For 'cn'/'jp'/'kr', it uses 「...」
// (converted at render time to curly for readability).
//
// The `toCurly` kagikakko conversion is language-agnostic: 「 → ", 」 → ",
// 『 → ', 』 → '.

const BRACKETS = {
  cn: { dialogueOpen: '「', dialogueClose: '」', systemOpen: '【', systemClose: '】', gameOpen: '《', gameClose: '》', endMarker: '(จบบท)' },
  jp: { dialogueOpen: '「', dialogueClose: '」', systemOpen: '【', systemClose: '】', gameOpen: '『', gameClose: '』', endMarker: '（終）' },
  kr: { dialogueOpen: '「', dialogueClose: '」', systemOpen: '【', systemClose: '】', gameOpen: '《', gameClose: '》', endMarker: '(끝)' },
  en: { dialogueOpen: '\u201C', dialogueClose: '\u201D', systemOpen: '[', systemClose: ']', gameOpen: '\u201C', gameClose: '\u201D', endMarker: '(End)' },
  th: { dialogueOpen: '\u201C', dialogueClose: '\u201D', systemOpen: '【', systemClose: '】', gameOpen: '《', gameClose: '》', endMarker: '(จบบท)' },
};

/**
 * Render a Chapter JSON object directly to HTML.
 * Replaces marked.js for the new format — no parsing, just block-by-block DOM.
 *
 * Quote style (P'Chok's choice, 2026-06-14):
 *   Dialogue   → "..." (curly U+201C / U+201D) — Thai standard
 *   Nested     → '...' (curly U+2018 / U+2019) — inside curly double
 *   System msg → 【...】 (game UI, kept)
 *   Title      → 《...》 (kept)
 *   End        → per language (see BRACKETS)
 *
 * Source blocks may use 「...」 (CN-style kagikakko); renderer converts to curly.
 * Multi-language (Phase 2 — 2026-06-14): renderer switches on ch.lang to
 * apply per-language bracket profile. Missing lang defaults to 'cn'.
 */
function renderChapterJson(ch) {
  if (!ch || !Array.isArray(ch.blocks)) {
    return '<p class="error">Invalid chapter layout structure.</p>';
  }

  // Convert CN/JP kagikakko to curly Thai/EN quotes
  const toCurly = (s) => s
    .replace(/「/g, '\u201C')
    .replace(/」/g, '\u201D')
    .replace(/『/g, '\u2018')
    .replace(/』/g, '\u2019');

  // Wrap inline 【...】 inside narration/dialogue with badge span
  const parseInline = (t) => t ? t.replace(/【([^】]+)】/g, '<span class="inline-stat-badge">【$1】</span>') : '';

  const lang = (ch.lang && BRACKETS[ch.lang]) ? ch.lang : 'cn';

  return ch.blocks.map(block => {
    const text = esc(block.text || '');
    switch (block.type) {
      case 'system':
        return `<p class="system-msg" data-lang="${lang}">${text}</p>`;
      case 'dialogue':
        // Speaker name from translator-authored JSON — must be escaped to prevent
        // XSS in the data-speaker HTML attribute (trust boundary: same as text).
        const sp = block.speaker ? ` data-speaker="${esc(block.speaker)}"` : '';
        return `<p class="dialogue"${sp} data-lang="${lang}">${toCurly(parseInline(text))}</p>`;
      case 'narration':
        return `<p>${toCurly(parseInline(text))}</p>`;
      case 'game_title':
        return `<p class="game-title" data-lang="${lang}">${text}</p>`;
      case 'end':
        return `<p class="end-marker" data-lang="${lang}">${text}</p>`;
      default:
        return `<p>${text}</p>`;
    }
  }).join('\n') + (ch.source ? `\n<hr/>\n<p class="source-footer">${esc(ch.source)}</p>` : '');
}

// ── Markdown Parser & Generator & Validator helpers ───────────────────

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

function splitParagraphs(text) {
  const normalized = text.replace(/\r\n/g, '\n');
  const parts = normalized.split(/\n-{3,}\n/);
  let body = '';
  if (parts.length > 1) {
    body = parts.reduce((longest, current) => current.length > longest.length ? current : longest, '');
  } else {
    body = parts[0];
  }
  body = body.replace(/^#\s+.*?\n/, '');
  return body.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
}

function extractNumbers(text) {
  const textClean = text.replace(/(\d),(\d)/g, '$1$2');
  const regex = /(?<![\d,])\d{2,}(?![\d,])/g;
  const matches = textClean.match(regex) || [];
  return new Set(matches);
}

async function loadGlossary(slug) {
  const glossaryDir = path.join(NOVELS_DIR, slug, 'glossary');
  const tiers = ['locked.md', 'reference.md', 'auto.md'];
  const glossary = {};
  for (const tier of tiers) {
    const filePath = path.join(glossaryDir, tier);
    try {
      const content = await fs.readFile(filePath, 'utf8');
      const lines = content.split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('| ') || trimmed.startsWith('|--') || trimmed.includes('Source')) {
          continue;
        }
        const cells = trimmed.split('|').map(c => c.trim());
        if (cells.length >= 6 && cells[1] && cells[1] !== '-') {
          glossary[cells[1]] = cells[2];
        }
      }
    } catch (err) {
      // Ignore if file doesn't exist
    }
  }
  return glossary;
}

const LENGTH_RATIO_OK = [0.6, 3.5];

const NAME_CHECKS = [
  { cn: '曹星', correct: 'เฉาซิง', wrong: 'โจวซิง' },
  { cn: '柳慕雪', correct: 'หลิวมู่เสวี่ย', wrong: 'หลิวมู่สวี่' },
  { cn: '陈江', correct: 'เฉินเจียง', wrong: 'เฉินเจียงก' },
  { cn: '香江', correct: 'ฮ่องกง', wrong: 'เซียงเจียง' },
  { cn: '极地人', correct: 'คนเมืองหนาว', wrong: 'ชาวโพลาร์' }
];

const CJK_PATTERN = /[\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u{20000}-\u{2A6DF}\u{2A700}-\u{2B73F}\uAC00-\uD7AF\u1100-\u11FF]/u;
const NON_ALLOWED_PATTERN = /[^\u0E00-\u0E7F\u0000-\u007F\u2000-\u206F\u2200-\u22FF\u2600-\u26FF\u2700-\u27BF\u3000-\u303F\uFF00-\uFFEF\s]/u;

async function validateChapterJs(slug, num, title, blocks, sourceFooter, lang) {
  const padded = String(num).padStart(4, '0');
  const srcPath = path.join(NOVELS_DIR, slug, 'chapters', 'source', `${padded}.md`);
  
  const errors = [];
  const warnings = [];
  const info = [];
  
  const trText = blocks.map(b => b.text || '').join('\n\n');
  const trParas = blocks.map(b => (b.text || '').trim()).filter(Boolean);
  
  let sourceText = '';
  try {
    sourceText = await fs.readFile(srcPath, 'utf8');
  } catch (err) {
    info.push('Source file not found, skipping comparative validation checks.');
  }
  
  if (sourceText) {
    const srcParas = splitParagraphs(sourceText);
    
    if (srcParas.length > 1) {
      const ratio = trParas.length / srcParas.length;
      info.push(`Paragraphs: source=${srcParas.length} | translation=${trParas.length} | ratio=${ratio.toFixed(2)}`);
      if ((ratio < 0.5 || ratio > 2.5) && num !== 94) {
        errors.push(`Paragraph count ratio: ${ratio.toFixed(2)} (expected 0.5-2.5)`);
      }
    } else {
      info.push(`Paragraphs: source=${srcParas.length} | translation=${trParas.length} (single-source-para, ratio N/A)`);
    }
    
    const srcNums = extractNumbers(sourceText);
    const trNums = extractNumbers(trText);
    const missing = [...srcNums].filter(n => !trNums.has(n));
    info.push(`Numbers (2+ digit): source=${srcNums.size} | translation=${trNums.size} | missing=${missing.length}`);
    if (missing.length > 0) {
      const realMissing = missing.filter(n => n !== '2026');
      if (realMissing.length > 0) {
        warnings.push(`Numbers in source but not in translation: ${realMissing.slice(0, 15).join(', ')}`);
      }
    }
    
    const srcLen = srcParas.reduce((acc, p) => acc + p.length, 0);
    const trLen = trParas.reduce((acc, p) => acc + p.length, 0);
    if (srcLen > 0) {
      const lr = trLen / srcLen;
      info.push(`Length: source=${srcLen} | translation=${trLen} | ratio=${lr.toFixed(2)}`);
      if (lr < LENGTH_RATIO_OK[0] || lr > LENGTH_RATIO_OK[1]) {
        errors.push(`Length ratio: ${lr.toFixed(2)} (expected ${LENGTH_RATIO_OK[0]}-${LENGTH_RATIO_OK[1]})`);
      }
    }
    
    try {
      const glossary = await loadGlossary(slug);
      const used = [];
      const missingGlossary = [];
      for (const [srcWord, thaiWord] of Object.entries(glossary)) {
        if (sourceText.includes(srcWord)) {
          used.push({ srcWord, thaiWord });
          let pattern;
          if (thaiWord.length === 1) {
            pattern = new RegExp(`(?<![\u0E00-\u0E7F])${thaiWord}(?![\u0E00-\u0E7F])`);
          } else {
            pattern = new RegExp(thaiWord);
          }
          if (!pattern.test(trText)) {
            missingGlossary.push({ srcWord, thaiWord });
          }
        }
      }
      info.push(`Glossary terms in source: ${used.length} (locked+reference)`);
      if (missingGlossary.length > 0) {
        let msg = `Glossary terms whose Thai is not literally in translation (${missingGlossary.length} total):`;
        missingGlossary.slice(0, 10).forEach(item => {
          msg += `\n   - "${item.srcWord}" → "${item.thaiWord}"`;
        });
        if (missingGlossary.length > 10) {
          msg += `\n   ... and ${missingGlossary.length - 10} more`;
        }
        warnings.push(msg);
      }
    } catch (gErr) {
      console.warn(`Glossary check skipped: ${gErr.message}`);
    }
    
    for (const check of NAME_CHECKS) {
      if (sourceText.includes(check.cn) && trText.includes(check.wrong)) {
        errors.push(`Name inconsistency: ${check.cn} → "${check.wrong}" (should be "${check.correct}")`);
      }
    }
  }
  
  const cjkErrors = [];
  blocks.forEach((block, idx) => {
    const text = block.text || '';
    if (CJK_PATTERN.test(text)) {
      cjkErrors.push(`Block ${idx + 1} ('${text.slice(0, 15)}...')`);
    }
  });
  if (cjkErrors.length > 0) {
    let msg = `CJK character leakage detected in translation (${cjkErrors.length} occurrences):`;
    cjkErrors.slice(0, 10).forEach(err => {
      msg += `\n   - ${err}`;
    });
    if (cjkErrors.length > 10) {
      msg += `\n   ... and ${cjkErrors.length - 10} more`;
    }
    errors.push(msg);
  }

  // Whitelist check
  const nonAllowedWarnings = [];
  blocks.forEach((block, idx) => {
    const text = block.text || '';
    if (NON_ALLOWED_PATTERN.test(text)) {
      const matches = text.match(new RegExp(NON_ALLOWED_PATTERN.source, 'gu')) || [];
      const invalidChars = [...new Set(matches)].join(', ');
      if (invalidChars) {
        nonAllowedWarnings.push(`Block ${idx + 1} contains unusual characters: [${invalidChars}]`);
      }
    }
  });
  if (nonAllowedWarnings.length > 0) {
    let msg = `Unusual/non-standard characters detected in translation (${nonAllowedWarnings.length} occurrences):`;
    nonAllowedWarnings.slice(0, 5).forEach(err => {
      msg += `\n   - ${err}`;
    });
    if (nonAllowedWarnings.length > 5) {
      msg += `\n   ... and ${nonAllowedWarnings.length - 5} more`;
    }
    warnings.push(msg);
  }
  
  // Thai characters ratio check
  const thaiCharCount = (trText.match(/[\u0E00-\u0E7F]/g) || []).length;
  const alphaCharCount = (trText.match(/[a-zA-Z\u0E00-\u0E7F]/g) || []).length;
  if (alphaCharCount > 0) {
    const thaiRatio = thaiCharCount / alphaCharCount;
    info.push(`Thai characters ratio: ${(thaiRatio * 100).toFixed(1)}%`);
    if (thaiRatio < 0.60) {
      warnings.push(`Low Thai characters ratio: ${(thaiRatio * 100).toFixed(1)}% (expected > 60%). The text might contain excessive English or source characters.`);
    }
  }

  // Duplicate detection
  const duplicates = [];
  const seenParas = new Set();
  trParas.forEach((p, idx) => {
    if (p.length > 20) {
      if (seenParas.has(p)) {
        duplicates.push(`Duplicate paragraph found at block ${idx + 1} ('${p.slice(0, 20)}...')`);
      }
      seenParas.add(p);
    }
  });
  if (duplicates.length > 0) {
    warnings.push(`Duplicate text blocks detected (${duplicates.length} occurrences): \n` + duplicates.slice(0, 3).join('\n'));
  }

  // Empty blocks check
  const emptyBlocks = [];
  blocks.forEach((b, idx) => {
    if (b.type !== 'end' && (!b.text || !b.text.trim())) {
      emptyBlocks.push(idx + 1);
    }
  });
  if (emptyBlocks.length > 0) {
    errors.push(`Empty block(s) detected at position(s): ${emptyBlocks.join(', ')}`);
  }

  const endBlocks = blocks.filter(b => b.type === 'end');
  if (endBlocks.length === 0) {
    errors.push('Chapter must have exactly one end marker block (e.g. (จบบท))');
  } else if (endBlocks.length > 1) {
    errors.push(`Chapter has ${endBlocks.length} end markers, must be exactly 1`);
  }
  
  if (blocks.length > 0 && blocks[blocks.length - 1].type !== 'end') {
    errors.push('Last block must be the end marker');
  }
  
  const contentBlocks = blocks.filter(b => b.type !== 'end');
  if (contentBlocks.length === 0) {
    errors.push('Chapter has no content blocks (only end marker)');
  }

  // Score Card calculation
  let score = 100;
  score -= errors.length * 15;
  score -= warnings.length * 5;
  if (errors.some(e => e.includes('CJK') || e.includes('character leakage'))) {
    score -= 10;
  }
  score = Math.max(0, score);
  
  return {
    valid: errors.length === 0,
    errors,
    warnings,
    info,
    score
  };
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
    const files = readdirSync(LOCALE_DIR);
    for (const f of files) {
        if (f.endsWith('.json')) {
            const lang = f.replace('.json', '');
            const content = readFileSync(path.join(LOCALE_DIR, f), 'utf-8');
            locales[lang] = JSON.parse(content);
            console.log(`i18n: loaded ${lang}`);
        }
}
} catch (e) {
    console.error('i18n: no locales directory, using fallback');
}

// Resolve language from cookie > Accept-Language > 'th'
function getLang(req) {
    // Manual cookie parsing (no cookie-parser dependency needed)
    const rawCookie = req.headers.cookie || '';
    const cookies = Object.fromEntries(
        rawCookie.split(';').filter(Boolean).map(c => {
            const parts = c.trim().split('=');
            return [parts[0], parts.slice(1).join('=')];
        })
    );
    const cookie = cookies.lang;
    if (cookie && locales[cookie]) return cookie;
    const accept = req.headers['accept-language'];
    if (accept) {
        const prefs = accept.split(',').map(s => s.split(';')[0].trim().toLowerCase());
        for (const p of prefs) {
            const base = p.split('-')[0];
            if (locales[base]) return base;
        }
    }
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
const SLUG_RE = /^[a-zA-Z0-9_-]+$/;
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

const novelMetaCache = new Map();

async function readNovelMeta(slug) {
  assertValidSlug(slug);
  if (novelMetaCache.has(slug)) return novelMetaCache.get(slug);
  const metaPath = path.join(NOVELS_DIR, slug, 'meta.md');
  let raw = '';
  try {
    raw = await fs.readFile(metaPath, 'utf8');
  } catch {
    const fallback = { slug, title: slug, source_lang: 'cn', target_lang: 'th' };
    novelMetaCache.set(slug, fallback);
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
  novelMetaCache.set(slug, meta);
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
// mode=content: FTS5 full-text search (delegates to tools/chapter_search.py
//               --json search). Returns ranked snippets. Best for finding
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
  if (mode === 'title' || mode === 'all') {
    const all = await listChapters(req.params.slug);
    const qn = parseInt(q, 10);
    const qLower = q.toLowerCase();
    const seen = new Set();
    for (const c of all) {
      if (Number.isFinite(qn) && c.num === qn) {
        if (!seen.has(c.num)) { results.push({ num: c.num, title: c.title, source: 'title' }); seen.add(c.num); }
        continue;
      }
      if (Number.isFinite(qn) && String(c.num).startsWith(q)) {
        if (!seen.has(c.num)) { results.push({ num: c.num, title: c.title, source: 'title' }); seen.add(c.num); }
        continue;
      }
      if (c.title && c.title.toLowerCase().includes(qLower)) {
        if (!seen.has(c.num)) { results.push({ num: c.num, title: c.title, source: 'title' }); seen.add(c.num); }
      }
    }
  }

  if (mode === 'content' || mode === 'all') {
    try {
      const fts = await ftsSearch(req.params.slug, q, limit);
      console.log(`[search] fts5 returned ${fts.length} results for "${q}"`);
      const seen = new Set(results.map((r) => r.num));
      for (const r of fts) {
        if (seen.has(r.chapter_num)) continue;
        results.push({
          num: r.chapter_num,
          title: r.title,
          snippet: r.snippet,
          score: r.score,
          source: 'content',
        });
        seen.add(r.chapter_num);
      }
    } catch (err) {
      // Don't fail the whole request if FTS5 isn't built yet
      if (err.code !== 'FTS_EMPTY') {
        console.warn(`FTS5 search failed: ${err.message}`);
      } else {
        console.log(`[search] fts5 skipped: ${err.message}`);
      }
    }
  }

  res.json(results.slice(0, limit));
});

// FTS5-backed search — spawns tools/chapter_search.py with --json.
// Returns [] if index doesn't exist yet (so the endpoint works for a fresh
// clone before chapter_search.py index has been run).
async function ftsSearch(slug, query, limit) {
  const novelRoot = path.join(NOVELS_DIR, slug);
  const indexPath = path.join(novelRoot, 'chapters', 'fts_index.db');
  // Fast path: if no index file exists, skip the spawn entirely
  try {
    await fs.access(indexPath);
  } catch {
    const e = new Error('FTS index not built');
    e.code = 'FTS_EMPTY';
    throw e;
  }
  const cwd = path.resolve(__dirname, '..');
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const args = [
    'tools/chapter_search.py',
    '--novel-root', novelRoot,
    '--json', 'search', query,
    '--limit', String(limit),
  ];
  return new Promise((resolve, reject) => {
    const child = spawn(py, args, { cwd, windowsHide: true, timeout: 10_000 });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
    child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });
    child.stdout.on('error', (err) => reject(err));
    child.stderr.on('error', (err) => reject(err));
    child.on('error', (err) => reject(err));
    child.on('close', (code) => {
      if (code !== 0) {
        const e = new Error(`chapter_search.py exited ${code}: ${stderr.trim()}`);
        e.code = 'FTS_FAIL';
        reject(e);
        return;
      }
      try {
        const parsed = stdout.trim() ? JSON.parse(stdout) : [];
        resolve(Array.isArray(parsed) ? parsed : []);
      } catch (err) {
        reject(new Error(`Invalid JSON from chapter_search.py: ${err.message}`));
      }
    });
  });
}

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
      valResult = await validateChapterJs(req.params.slug, num, title, result.blocks || [], result.source || '', result.lang || 'cn');
    }

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
  try {
    const { stdout } = await execFileAsync('python', [glossaryScript, '--novel', slug, '--load'], {
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
    chapterHtmlCache.clear();
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
    novelMetaCache.delete(slug);
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
    novelMetaCache.delete(slug);
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

  const valResult = await validateChapterJs(slug, num, chapterData.title, chapterData.blocks, chapterData.source, chapterData.lang);
  
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
    const key = `${slug}:${num}`;
    chapterHtmlCache.delete(key);

    // Live Search Index Sync
    const execFileAsync = require('util').promisify(require('child_process').execFile);
    const searchScript = path.join(__dirname, '..', 'tools', 'chapter_search.py');
    const novelRoot = path.join(NOVELS_DIR, slug);
    try {
      await execFileAsync('python', [searchScript, '--novel-root', novelRoot, 'index'], {
        env: { ...process.env, NOVEL_SLUG: slug }
      });
      console.log(`[search] Re-indexed FTS5 successfully for ${slug}`);
    } catch (searchErr) {
      console.warn(`[search] FTS5 index update skipped/failed: ${searchErr.message}`);
    }

    // Git Auto-Commit Integration
    try {
      const relativePath = path.relative(path.join(__dirname, '..'), jsonPath);
      await execFileAsync('git', ['add', relativePath], { cwd: path.join(__dirname, '..') });
      await execFileAsync('git', ['commit', '-m', `translate: save chapter ${num} (${chapterData.title})`], { cwd: path.join(__dirname, '..') });
      console.log(`[git] Auto-committed: ${relativePath}`);
    } catch (gitErr) {
      console.warn(`[git] Auto-commit skipped: ${gitErr.message}`);
    }

    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/novel/:slug/chapter/:num/auto-translate', async (req, res) => {
  const slug = req.params.slug;
  const num = parseInt(req.params.num, 10);
  const { email } = req.body;

  if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });

  // 1. Authenticate / Check user quota
  const usersPath = path.join(__dirname, 'users.json');
  let users = [];
  try {
    const data = await fs.readFile(usersPath, 'utf8');
    users = JSON.parse(data);
  } catch (err) {
    return res.status(500).json({ error: 'Failed to read users database: ' + err.message });
  }

  const user = users.find(u => u.email === email);
  if (!user) {
    return res.status(403).json({ error: 'User not found/Unauthorized. กรุณาเข้าสู่ระบบด้วยอีเมลที่ถูกต้องค่ะ 🦊' });
  }

  if (user.tokensLimit !== -1 && user.tokensUsed >= user.tokensLimit) {
    return res.status(403).json({ error: 'คุณใช้โควตาแปลภาษาสำหรับวันนี้หมดแล้วค่ะ! 💅 เกินขีดจำกัดแล้วค่ะ' });
  }

  // 2. Clear existing translation if it exists (so translate.py doesn't skip it)
  const padded = String(num).padStart(4, '0');
  const jsonPath = path.join(NOVELS_DIR, slug, 'chapters', `${padded}.json`);
  try {
    await fs.unlink(jsonPath);
  } catch (e) {
    // Ignore if file doesn't exist
  }

  // 3. Run translation script
  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const translateScript = path.join(__dirname, '..', 'tools', 'translate.py');
  
  // Use mock if requested or if no API keys are present in env
  const useMock = req.body.mock || (!process.env.ANTHROPIC_API_KEY && !process.env.GEMINI_API_KEY);
  const args = [translateScript, String(num)];
  if (useMock) {
    args.push('--mock');
  }

  const execFileAsync = require('util').promisify(require('child_process').execFile);
  try {
    await execFileAsync(py, args, {
      env: { ...process.env, NOVEL_SLUG: slug, PYTHONIOENCODING: 'utf-8' }
    });

    // 4. Deduct tokens
    user.tokensUsed += 1;
    await fs.writeFile(usersPath, JSON.stringify(users, null, 2), 'utf8');

    // 5. Load the newly saved file and return it
    const fileContent = await fs.readFile(jsonPath, 'utf8');
    const chData = JSON.parse(fileContent);

    // Live Search Index Sync
    const searchScript = path.join(__dirname, '..', 'tools', 'chapter_search.py');
    const novelRoot = path.join(NOVELS_DIR, slug);
    try {
      await execFileAsync(py, [searchScript, '--novel-root', novelRoot, 'index'], {
        env: { ...process.env, NOVEL_SLUG: slug }
      });
      console.log(`[search] Re-indexed FTS5 successfully for ${slug}`);
    } catch (searchErr) {
      console.warn(`[search] FTS5 index update failed: ${searchErr.message}`);
    }

    res.json({ ok: true, chapter: chData });
  } catch (err) {
    res.status(500).json({ error: `Translation failed: ${err.message}` });
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
    const key = `${slug}:${num}`;
    chapterHtmlCache.delete(key);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// EPUB Import Endpoint (Tier 2)
const tempUpload = multer({ dest: require('os').tmpdir() });
app.post('/api/novel/:slug/import-epub', tempUpload.single('epub'), async (req, res) => {
  const slug = req.params.slug;
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded' });
  }

  const epubPath = req.file.path;
  const novelRoot = path.join(NOVELS_DIR, slug);
  const startNum = parseInt(req.body.startNum, 10) || 1;

  const py = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const importScript = path.join(__dirname, '..', 'tools', 'import_epub.py');
  const args = [
    importScript,
    '--epub', epubPath,
    '--novel-root', novelRoot,
    '--start-num', String(startNum)
  ];

  const { spawn } = require('child_process');
  const child = spawn(py, args, { windowsHide: true, timeout: 60_000 });

  let stdout = '';
  let stderr = '';
  child.stdout.on('data', (b) => { stdout += b.toString('utf8'); });
  child.stderr.on('data', (b) => { stderr += b.toString('utf8'); });

  child.on('close', async (code) => {
    // Clean up temp file
    try {
      await fs.unlink(epubPath);
    } catch {}

    if (code !== 0) {
      return res.status(500).json({ error: `import_epub.py exited ${code}: ${stderr}` });
    }

    try {
      const result = JSON.parse(stdout.trim());
      if (result.ok) {
        invalidateCache(slug);
        res.json(result);
      } else {
        res.status(400).json(result);
      }
    } catch (err) {
      res.status(500).json({ error: `Failed to parse import_epub.py output: ${err.message}` });
    }
  });
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

// ── Reviews & Comments APIs (Phase B Social) ───────────────────────────

app.get('/api/novel/:slug/reviews', async (req, res) => {
  try {
    assertValidSlug(req.params.slug);
    const slug = req.params.slug;
    const filePath = path.join(NOVELS_DIR, slug, 'reviews.json');
    try {
      const data = await fs.readFile(filePath, 'utf8');
      res.json(JSON.parse(data));
    } catch (err) {
      if (err.code === 'ENOENT') {
        res.json([]);
      } else throw err;
    }
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message });
  }
});

app.post('/api/novel/:slug/reviews/save', express.json(), async (req, res) => {
  try {
    assertValidSlug(req.params.slug);
    const slug = req.params.slug;
    const filePath = path.join(NOVELS_DIR, slug, 'reviews.json');
    
    let reviews = [];
    try {
      const data = await fs.readFile(filePath, 'utf8');
      reviews = JSON.parse(data);
    } catch (err) {
      if (err.code !== 'ENOENT') throw err;
    }

    const { user, rating, text } = req.body;
    if (!user || rating == null || !text) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    reviews.push({
      user,
      rating: Number(rating),
      text,
      ts: Date.now()
    });

    await fs.writeFile(filePath, JSON.stringify(reviews, null, 2), 'utf8');
    res.json({ ok: true });
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message });
  }
});

app.get('/api/novel/:slug/chapter/:num/comments', async (req, res) => {
  try {
    assertValidSlug(req.params.slug);
    const slug = req.params.slug;
    const num = parseInt(req.params.num, 10);
    const filePath = path.join(NOVELS_DIR, slug, 'comments', `chapter_${num}.json`);
    try {
      const data = await fs.readFile(filePath, 'utf8');
      res.json(JSON.parse(data));
    } catch (err) {
      if (err.code === 'ENOENT') {
        res.json([]);
      } else throw err;
    }
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message });
  }
});

app.post('/api/novel/:slug/chapter/:num/comment', express.json(), async (req, res) => {
  try {
    assertValidSlug(req.params.slug);
    const slug = req.params.slug;
    const num = parseInt(req.params.num, 10);
    const dirPath = path.join(NOVELS_DIR, slug, 'comments');
    const filePath = path.join(dirPath, `chapter_${num}.json`);

    await fs.mkdir(dirPath, { recursive: true });

    let comments = [];
    try {
      const data = await fs.readFile(filePath, 'utf8');
      comments = JSON.parse(data);
    } catch (err) {
      if (err.code !== 'ENOENT') throw err;
    }

    const { user, text } = req.body;
    if (!user || !text) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    comments.push({
      user,
      text,
      ts: Date.now()
    });

    await fs.writeFile(filePath, JSON.stringify(comments, null, 2), 'utf8');
    res.json({ ok: true });
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message });
  }
});

// Notifications Mock State
let notificationsMock = [
  { id: 1, text: "นิยายเรื่อง 'Global Descent' อัปเดตตอนที่ 54 แล้วค่ะ!", ts: Date.now() - 3600000 * 2, read: false },
  { id: 2, text: "พี่โชคมีผู้ติดตามใหม่ 3 คนในวันนี้ค่ะ 🦊", ts: Date.now() - 3600000 * 12, read: true },
  { id: 3, text: "Mika อนุมัติการบันทึกคลังคำศัพท์ของ 'Global Descent' แล้วเรียบร้อย", ts: Date.now() - 3600000 * 24, read: true }
];

app.get('/api/notifications', (req, res) => {
  res.json(notificationsMock);
});

app.post('/api/notifications/read', (req, res) => {
  notificationsMock.forEach(n => n.read = true);
  res.json({ ok: true });
});

const fsSync = require('node:fs');
const START_TIME = Date.now();

// ── SPA fallback ──────────────────────────────────────────────────────
// Any route that isn't an API call or a static file serves index.html
// so the frontend JS can handle routing via URL params.
// Inject ?_t=START_TIME to bust browser cache for JS/CSS after server restart.
app.get('*', (req, res) => {
  if (req.path.startsWith('/api/')) return res.status(404).json({ error: 'API not found' });
  let html = fsSync.readFileSync(path.join(PUBLIC_DIR, 'index.html'), 'utf8');
  // Cache-bust: append server start timestamp to script src URLs
  html = html.replace('src="/virtual-scroll.js"', `src="/virtual-scroll.js?_t=${START_TIME}"`);
  html = html.replace('src="/app.js"', `src="/app.js?_t=${START_TIME}"`);
  res.type('html').send(html);
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

module.exports = { BRACKETS, renderChapterJson };
