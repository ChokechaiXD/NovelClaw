/**
 * routes/chapters-admin.js — Admin-only chapter endpoints.
 * Mounted at /api/v1/admin by routes/index.js.
 *
 * POST   /novels/:slug/chapters/:num          — save chapter
 * DELETE /novels/:slug/chapters/:num          — delete chapter
 * POST   /novels/:slug/chapters/:num/translate — auto-translate
 */
const express = require('express');
const router = express.Router();
const path = require('node:path');
const fs = require('node:fs/promises');
const zlib = require('node:zlib');
const multer = require('multer');
const { assertValidSlug } = require('../lib/helpers');
const { NOVELS_DIR, invalidateCache, chapterHtmlCache, novelMetaCache } = require('../config');
const { renderChapterJson } = require('../lib/render');
const { validateChapterJs } = require('../services/validation');
const { safeWriteJson, safeWriteText } = require('../lib/safe-write');
const { runTool } = require('../services/python');
const { recordSearchIndexFailure } = require('../services/search-index');
const { marked } = require('marked');

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } });

function readUInt32(buf, offset) {
  return buf.readUInt32LE(offset);
}

function parseZipEntries(buffer) {
  const entries = new Map();
  let offset = 0;
  while (offset + 30 <= buffer.length) {
    if (offset + 30 > buffer.length) break;
    const sig = readUInt32(buffer, offset);
    if (sig !== 0x04034b50) break;
    const method = buffer.readUInt16LE(offset + 8);
    const compressedSize = readUInt32(buffer, offset + 18);
    const uncompressedSize = readUInt32(buffer, offset + 22);
    const nameLen = buffer.readUInt16LE(offset + 26);
    const extraLen = buffer.readUInt16LE(offset + 28);
    const nameStart = offset + 30;
    const dataStart = nameStart + nameLen + extraLen;
    if (nameStart + nameLen > buffer.length || dataStart + compressedSize > buffer.length) {
      throw new Error('EPUB มีโครงสร้าง ZIP ไม่สมบูรณ์');
    }
    const name = buffer.slice(nameStart, nameStart + nameLen).toString('utf8').replace(/^\/+/, '');
    const compressed = buffer.slice(dataStart, dataStart + compressedSize);
    let data;
    if (method === 0) data = compressed;
    else if (method === 8) data = zlib.inflateRawSync(compressed, { maxOutputLength: Math.max(uncompressedSize, 25 * 1024 * 1024) });
    else throw new Error(`Unsupported ZIP method ${method} in ${name}`);
    if (name) entries.set(name, data);
    offset = dataStart + compressedSize;
  }
  if (!entries.size) throw new Error('ไม่พบไฟล์ EPUB ที่อ่านได้');
  return entries;
}

function xmlText(xml, tag) {
  const match = String(xml || '').match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i'));
  return match ? match[1].trim() : '';
}

function htmlToText(html) {
  return decodeHtmlEntities(String(html || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim());
}

function blockType(text) {
  if (/^\s*【/.test(text) || /^\s*\[System\]/i.test(text)) return 'system';
  if (/^\s*[「\"“]/.test(text)) return 'dialogue';
  if (/^\s*《/.test(text) || /《[\s\S]+》/.test(text)) return 'title';
  return 'narration';
}

function htmlBlocks(html) {
  const bodyMatch = String(html || '').match(/<body[\s\S]*?<\/body>/i);
  const body = bodyMatch ? bodyMatch[0] : String(html || '');
  const chunks = body
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .split(/<\/?(?:p|div|br|h\d)[^>]*>/i)
    .map(htmlToText)
    .filter(Boolean);
  if (!chunks.length) {
    const text = htmlToText(body);
    return text ? [{ type: 'narration', text }] : [];
  }
  return chunks.map(text => ({ type: blockType(text), text }));
}

function parseEpub(buffer) {
  const entries = parseZipEntries(buffer);
  const container = entries.get('META-INF/container.xml');
  if (!container) throw new Error('EPUB ไม่พบ META-INF/container.xml');
  const containerXml = container.toString('utf8');
  const rootfileMatch = containerXml.match(/<rootfile\s+([^>]*)>/i);
  const rootfile = rootfileMatch ? rootfileMatch[1].match(/full-path="([^"]+)"/) : null;
  const opfPath = rootfile ? rootfile[1] : 'content.opf';
  const opfData = entries.get(opfPath);
  if (!opfData) throw new Error(`ไม่พบไฟล์ OPF: ${opfPath}`);
  const opf = opfData.toString('utf8');
  const baseDir = path.posix.dirname(opfPath);
  const manifest = [...opf.matchAll(/<item\s+([^>]*?)\s*\/?>/gi)].map((m) => {
    const attrs = {};
    for (const part of m[1].matchAll(/([a-zA-Z-]+)="([^"]*)"/g)) attrs[part[1]] = part[2];
    return attrs;
  });
  const htmlItems = new Map(manifest.filter(item => /xhtml|html/.test(item['media-type'] || '')).map(item => [item.id, item.href]));
  const spine = [...opf.matchAll(/<itemref\s+([^>]*?)\s*\/?>/gi)].map((m) => {
    const attrs = {};
    for (const part of m[1].matchAll(/([a-zA-Z-]+)="([^"]*)"/g)) attrs[part[1]] = part[2];
    return attrs.idref || attrs.itemref;
  }).filter(Boolean);
  const chapters = spine.map((id, idx) => {
    const href = htmlItems.get(id);
    if (!href) return null;
    const filePath = path.posix.normalize(path.posix.join(baseDir, href));
    const html = entries.get(filePath);
    if (!html) return null;
    const text = html.toString('utf8');
    return {
      id,
      href,
      title: xmlText(text, 'title') || `Chapter ${idx + 1}`,
      blocks: htmlBlocks(text),
    };
  }).filter(Boolean);
  return chapters;
}

function chapterFromImport(item, num) {
  return {
    schema_version: 2,
    num,
    title: item.title || `ตอนที่ ${num}`,
    lang: 'cn',
    output_lang: 'th',
    profile_lang: null,
    blocks: item.blocks || [],
    source: `Imported from EPUB: ${item.href}`,
    notes: [],
  };
}

function renderEpubStatusHtml(result) {
  const label = result.dryRun ? 'Preview' : 'Import';
  return `<div><strong>${label}: ${result.imported.length} ตอน</strong> (${result.skipped.length} ตอนข้ามเพราะมีไฟล์อยู่แล้ว)</div>`;
}

function warningFromSearchToolOutput({ action, slug, chapter, novelRoot, output }) {
  const text = String(output || '').trim();
  if (!text || text.startsWith('✅')) return null;
  return recordSearchIndexFailure({
    action,
    slug,
    chapter,
    novelRoot,
    message: 'Search index operation reported a warning',
    details: { toolOutput: text.slice(0, 4000) },
  });
}

async function updateChapterSearchIndex(slug, num) {
  const novelRoot = path.join(NOVELS_DIR, slug);
  const warnings = [];
  try {
    const result = await runTool('tools/chapter_search.py', ['--novel-root', novelRoot, 'update-one', String(num)]);
    const warning = warningFromSearchToolOutput({ action: 'update-one', slug, chapter: num, novelRoot, output: result });
    if (warning) warnings.push(warning);
  } catch (searchErr) {
    warnings.push(recordSearchIndexFailure({
      action: 'update-one',
      slug,
      chapter: num,
      novelRoot,
      message: 'Search index update failed',
      error: searchErr,
    }));
  }
  return warnings;
}

async function deleteChapterSearchIndex(slug, num) {
  const novelRoot = path.join(NOVELS_DIR, slug);
  const warnings = [];
  try {
    const result = await runTool('tools/chapter_search.py', ['--novel-root', novelRoot, 'delete-one', String(num)]);
    const warning = warningFromSearchToolOutput({ action: 'delete-one', slug, chapter: num, novelRoot, output: result });
    if (warning) warnings.push(warning);
  } catch (searchErr) {
    warnings.push(recordSearchIndexFailure({
      action: 'delete-one',
      slug,
      chapter: num,
      novelRoot,
      message: 'Search index delete failed',
      error: searchErr,
    }));
  }
  return warnings;
}

function decodeHtmlEntities(text) {
  return String(text || '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&');
}

function getTranslationCapability() {
  const provider = process.env.NOVELCLAW_AI_PROVIDER || (process.env.NOVELCLAW_AI_API_KEY ? 'openai-compatible' : null);
  const apiKey = process.env.NOVELCLAW_AI_API_KEY;
  if (!provider || !apiKey || provider === 'none' || provider === 'local') {
    return {
      enabled: false,
      provider: null,
      model: null,
      reason: 'Configure NOVELCLAW_AI_API_KEY to enable automatic translation.',
    };
  }
  return {
    enabled: true,
    provider,
    model: process.env.NOVELCLAW_AI_MODEL || 'gpt-4o-mini',
    reason: null,
  };
}

async function translateWithConfiguredProvider(chapterData) {
  const capability = getTranslationCapability();
  if (!capability.enabled) {
    const err = new Error(capability.reason);
    err.status = 503;
    throw err;
  }

  const sourceText = chapterData.blocks.map(block => `[${block.type}] ${block.text || ''}`).join('\n\n');
  const payload = {
    model: capability.model,
    messages: [
      { role: 'system', content: 'Translate the provided source chapter blocks into natural Thai. Preserve dialogue, system text, title markers, and canonical block meaning. Return only the translated Thai text blocks in order.' },
      { role: 'user', content: sourceText },
    ],
    temperature: 0.3,
  };
  const base = process.env.NOVELCLAW_AI_BASE_URL || 'https://api.openai.com/v1/chat/completions';
  const res = await fetch(base, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`AI provider request failed: ${res.status} ${body.slice(0, 300)}`);
  }
  const data = await res.json();
  const translatedText = data.choices?.[0]?.message?.content || '';
  if (!translatedText.trim()) throw new Error('AI provider returned empty translation');
  const lines = translatedText.split(/\n+/).map(line => line.trim()).filter(Boolean);
  const translatedBlocks = lines.map((line, idx) => {
    const original = chapterData.blocks[idx] || { type: 'narration', text: '' };
    return { ...original, text: line };
  });
  return { mode: 'ai-provider', chapterData: { ...chapterData, blocks: translatedBlocks, output_lang: chapterData.output_lang, profile_lang: chapterData.profile_lang } };
}

router.get('/translation-capability', (req, res) => {
  res.json(getTranslationCapability());
});

// ── Admin: EPUB import ─────────────────────────────────────────────
router.post('/:slug/chapters/import-epub', upload.single('file'), async (req, res) => {
  try {
    assertValidSlug(req.params.slug);
    if (!req.file) return res.status(400).json({ error: 'กรุณาเลือกไฟล์ EPUB' });
    const startNum = Math.max(1, parseInt(req.body.startNum || req.query.startNum || '1', 10));
    const dryRun = req.body.dryRun === 'true' || req.query.dryRun === 'true';
    const chapters = parseEpub(req.file.buffer);
    if (!chapters.length) return res.status(400).json({ error: 'ไม่พบเนื้อหาบทใน EPUB' });
    const chapterDir = path.join(NOVELS_DIR, req.params.slug, 'chapters');
    if (!dryRun) await fs.mkdir(chapterDir, { recursive: true });
    const imported = [];
    const skipped = [];
    for (const [idx, item] of chapters.entries()) {
      const num = startNum + idx;
      const jsonPath = path.join(chapterDir, `${String(num).padStart(4, '0')}.json`);
      const exists = await fs.access(jsonPath).then(() => true).catch(() => false);
      if (exists) { skipped.push(num); continue; }
      const data = chapterFromImport(item, num);
      if (!dryRun) await safeWriteJson(jsonPath, data);
      imported.push({ num, title: data.title, blocks: data.blocks.length });
    }
    if (!dryRun) {
      invalidateCache(req.params.slug);
      novelMetaCache.delete(req.params.slug);
    }
    const result = { ok: true, dryRun, imported, skipped };
    res.json(result);
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message });
  }
});

// ── Admin: save chapter ───────────────────────────────────────────────
router.post('/:slug/chapters/:num', async (req, res) => {
  try {
    assertValidSlug(req.params.slug);
    const num = parseInt(req.params.num, 10);
    if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
    const padded = String(num).padStart(4, '0');
    let { title, blocks, source, lang, output_lang, profile_lang, markdownText } = req.body;
    let notes = [];
    if (markdownText) {
      const { parseMarkdownToBlocks } = require('../lib/markdown');
      const parsed = parseMarkdownToBlocks(markdownText, num);
      blocks = parsed.blocks;
      if (!title) title = parsed.title;
      notes = parsed.notes;
    }
    const chapterData = {
      schema_version: 2, num,
      title: title || `ตอนที่ ${num}`,
      lang: lang || 'cn',
      output_lang: output_lang || undefined,
      profile_lang: profile_lang || null,
      blocks: blocks || [],
      source: source || '',
      notes: notes || [],
    };
    const valResult = await validateChapterJs(req.params.slug, num, chapterData.title, chapterData.blocks, chapterData.source, chapterData.lang, {
      output_lang: chapterData.output_lang,
      profile_lang: chapterData.profile_lang,
    });
    if (!valResult.valid) {
      return res.status(422).json({ error: 'Validation Error', details: valResult });
    }
    const jsonPath = path.join(NOVELS_DIR, req.params.slug, 'chapters', `${padded}.json`);
    await fs.mkdir(path.dirname(jsonPath), { recursive: true });
    // Use safeWriteJson for atomic write (prevents corruption on concurrent saves)
    await safeWriteJson(jsonPath, chapterData);
    invalidateCache(req.params.slug);
    chapterHtmlCache.delete(`${req.params.slug}:${num}`);
    const warnings = await updateChapterSearchIndex(req.params.slug, num);
    res.json({ ok: true, chapter: chapterData, ...(warnings.length ? { warnings } : {}) });
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message });
  }
});

// ── Admin: delete chapter ─────────────────────────────────────────────
router.delete('/:slug/chapters/:num', async (req, res) => {
  try {
    assertValidSlug(req.params.slug);
    const num = parseInt(req.params.num, 10);
    if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
    const padded = String(num).padStart(4, '0');
    const jsonPath = path.join(NOVELS_DIR, req.params.slug, 'chapters', `${padded}.json`);
    const mdPath = path.join(NOVELS_DIR, req.params.slug, 'chapters', `${padded}.md`);
    await fs.rm(jsonPath, { force: true });
    await fs.rm(mdPath, { force: true });
    invalidateCache(req.params.slug);
    chapterHtmlCache.delete(`${req.params.slug}:${num}`);
    const warnings = await deleteChapterSearchIndex(req.params.slug, num);
    res.json({ ok: true, ...(warnings.length ? { warnings } : {}) });
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message });
  }
});

// ── Admin: auto-translate ─────────────────────────────────────────────
router.post('/:slug/chapters/:num/translate', async (req, res) => {
  try {
    assertValidSlug(req.params.slug);
    const num = parseInt(req.params.num, 10);
    if (Number.isNaN(num)) return res.status(400).json({ error: 'Invalid chapter number' });
    const user = req.authUser;
    if (!user) return res.status(403).json({ error: 'Unauthorized' });
    if (user.tokensLimit !== -1 && user.tokensUsed >= user.tokensLimit) {
      return res.status(403).json({ error: 'คุณใช้โควตาหมดแล้วค่ะ' });
    }
    const capability = getTranslationCapability();
    if (!capability.enabled) return res.status(503).json({ error: capability.reason });
    const padded = String(num).padStart(4, '0');
    const jsonPath = path.join(NOVELS_DIR, req.params.slug, 'chapters', `${padded}.json`);
    const fileContent = await fs.readFile(jsonPath, 'utf8');
    const chData = JSON.parse(fileContent);
    const providerResult = await translateWithConfiguredProvider(chData);
    await safeWriteJson(jsonPath, providerResult.chapterData);

    const usersPath = path.join(__dirname, '..', 'users.json');
    const usersData = await fs.readFile(usersPath, 'utf8');
    const allUsers = JSON.parse(usersData);
    const targetUser = allUsers.find((entry) => entry.email === user.email);
    if (targetUser) {
      targetUser.tokensUsed += 1;
      await safeWriteJson(usersPath, allUsers);
    }
    const warnings = await updateChapterSearchIndex(req.params.slug, num);
    res.json({ ok: true, mode: providerResult.mode, chapter: providerResult.chapterData, ...(warnings.length ? { warnings } : {}) });
  } catch (err) {
    res.status(err.status || 500).json({ error: `Translation failed: ${err.message}` });
  }
});

module.exports = router;
module.exports.getTranslationCapability = getTranslationCapability;
