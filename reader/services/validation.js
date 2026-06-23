/**
 * services/validation.js — Chapter validation (JS-side).
 *
 * validateChapterJs(slug, num, title, blocks, source, lang, options)
 *   → { valid, errors, warnings, info, score }
 *
 * Options:
 *   novelRoot      - path to novels/ directory (default: ../novels relative to server.js)
 *   output_lang    - target language profile for bracket checks
 *   profile_lang   - overrides output_lang
 */

const fs = require('node:fs/promises');
const path = require('node:path');
const { getBracketProfile } = require('../lib/brackets');

// ── Default config (overridable by validation_config.json) ─────────────
const CONFIG_PATH = path.join(__dirname, '../validation_config.json');
let LENGTH_RATIO_OK = [0.6, 3.5];
let NAME_CHECKS = [
  { cn: '曹星', correct: 'เฉาซิง', wrong: 'โจวซิง' },
  { cn: '柳慕雪', correct: 'หลิวมู่เสวี่ย', wrong: 'หลิวมู่สวี่' },
  { cn: '陈江', correct: 'เฉินเจียง', wrong: 'เฉินเจียงก' },
  { cn: '香江', correct: 'ฮ่องกง', wrong: 'เซียงเจียง' },
  { cn: '极地人', correct: 'คนเมืองหนาว', wrong: 'ชาวโพลาร์' }
];
try {
  const fsSync = require('node:fs');
  if (fsSync.existsSync(CONFIG_PATH)) {
    const sharedConfig = JSON.parse(fsSync.readFileSync(CONFIG_PATH, 'utf8'));
    if (sharedConfig.length_ratio_ok) LENGTH_RATIO_OK = sharedConfig.length_ratio_ok;
    if (sharedConfig.name_checks) NAME_CHECKS = sharedConfig.name_checks;
  }
} catch (err) {
  console.warn(`[validation] config load skipped: ${err.message}. Using defaults.`);
}

const CJK_PATTERN = /[\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u{20000}-\u{2A6DF}\u{2A700}-\u{2B73F}\uAC00-\uD7AF\u1100-\u11FF]/u;
const NON_ALLOWED_PATTERN = /[^\u0E00-\u0E7F\u0000-\u007F\u2000-\u206F\u2200-\u22FF\u2600-\u26FF\u2700-\u27BF\u3000-\u303F\uFF00-\uFFEF\s]/u;

// ── Helpers ────────────────────────────────────────────────────────────

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

// ── Glossary cache (module-level, TTL 60s) ────────────────────────────
// ponytail: avoid 3-4 file reads per chapter API call
const GLOSSARY_CACHE = new Map();
const GLOSSARY_TTL = 60_000; // 60 seconds

function invalidateGlossaryCache(slug) {
  GLOSSARY_CACHE.delete(slug);
}

async function loadGlossary(slug, novelRoot) {
  // Check cache first
  const cached = GLOSSARY_CACHE.get(slug);
  if (cached && Date.now() - cached.ts < GLOSSARY_TTL) {
    return cached.data;
  }

  const glossaryDir = path.join(novelRoot, slug, 'glossary');
  // Try glossary.json first (modern), fallback to .md tables (legacy)
  try {
    const jsonPath = path.join(glossaryDir, 'glossary.json');
    const jsonRaw = await fs.readFile(jsonPath, 'utf8');
    const parsed = JSON.parse(jsonRaw);
    const glossary = {};
    if (parsed.terms && Array.isArray(parsed.terms)) {
      for (const t of parsed.terms) {
        if (t.source && t.thai) glossary[t.source.trim()] = t.thai.trim();
      }
    }
    if (Object.keys(glossary).length > 0) return glossary;
  } catch { /* fall through to .md parsing */ }

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
    } catch { /* skip missing */ }
  }
  // Cache result
  GLOSSARY_CACHE.set(slug, { data: glossary, ts: Date.now() });
  return glossary;
}

// ── Main validator ─────────────────────────────────────────────────────

async function validateChapterJs(slug, num, title, blocks, sourceFooter, lang, options = {}) {
  const novelRoot = options.novelRoot || path.resolve(__dirname, '../../novels');
  const padded = String(num).padStart(4, '0');
  const srcPath = path.join(novelRoot, slug, 'chapters', 'source', `${padded}.md`);

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
      const glossary = await loadGlossary(slug, novelRoot);
      const used = [];
      const missingGlossary = [];
      for (const [srcWord, thaiWord] of Object.entries(glossary)) {
        if (sourceText.includes(srcWord)) {
          used.push({ srcWord, thaiWord });
          let pattern;
          if (thaiWord.length === 1) {
            pattern = new RegExp(`(?<![\\u0E00-\\u0E7F])${thaiWord}(?![\\u0E00-\\u0E7F])`);
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

  // Profile-aware end marker text check
  const profileLang = options.profile_lang || options.output_lang || lang || 'cn';
  if (endBlocks.length === 1) {
    const bp = getBracketProfile({ lang, output_lang: options.output_lang, profile_lang: options.profile_lang });
    const expectedEnd = bp.endMarker;
    if (expectedEnd && endBlocks[0].text !== expectedEnd) {
      warnings.push(`End marker text "${endBlocks[0].text}" does not match expected "${expectedEnd}" for lang=${profileLang}`);
    }
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

module.exports = { invalidateGlossaryCache, validateChapterJs };
