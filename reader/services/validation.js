/**
 * services/validation.js — Chapter validation (JS-side).
 *
 * validateChapterJs(slug, num, title, blocks, source, lang) → { valid, errors, warnings, info, score }
 */
const { getBracketProfile } = require('../lib/brackets');

async function validateChapterJs(slug, num, title, blocks, source, lang, options = {}) {
  const errors = [];
  const warnings = [];
  const info = [];
  const score = { total: 0, pass: 0, warn: 0, fail: 0 };

  if (!Array.isArray(blocks) || blocks.length === 0) {
    errors.push('Chapter has no blocks');
    score.fail++;
    return { valid: false, errors, warnings, info, score };
  }

  // Title check
  if (!title || title.trim() === '') {
    errors.push('Missing chapter title');
    score.fail++;
  } else {
    score.pass++;
    if (!title.includes(String(num))) {
      warnings.push(`Title may be missing chapter number: "${title}"`);
      score.warn++;
    }
  }

  // End marker check
  const endBlocks = blocks.filter(b => b.type === 'end');
  const bracketProfile = getBracketProfile({
    lang,
    output_lang: options.output_lang,
    profile_lang: options.profile_lang,
  });
  const activeLang = options.profile_lang || options.output_lang || lang || 'cn';
  if (endBlocks.length === 0) {
    errors.push('Missing end marker block');
    score.fail++;
  } else if (endBlocks.length > 1) {
    warnings.push(`Multiple end markers: ${endBlocks.length}`);
    score.warn++;
    score.pass++;
  } else {
    score.pass++;
    if (bracketProfile.endMarker && !endBlocks[0].text?.includes(bracketProfile.endMarker.replace(/[()]/g, ''))) {
      warnings.push(`End marker text may not match expected for lang=${activeLang}`);
      score.warn++;
    }
  }

  // Block type validation
  const validTypes = ['narration', 'dialogue', 'system', 'game_title', 'end'];
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    if (!validTypes.includes(b.type)) {
      warnings.push(`L${i + 1}: Unknown block type: ${b.type}`);
      score.warn++;
    }
    if (!b.text || b.text.trim() === '') {
      warnings.push(`L${i + 1}: Empty text in ${b.type} block`);
      score.warn++;
    }
  }

  // Dialogue quote check
  const dialogueBlocks = blocks.filter(b => b.type === 'dialogue');
  for (const db of dialogueBlocks) {
    const expectedOpen = bracketProfile.dialogueOpen || '"';
    const expectedClose = bracketProfile.dialogueClose || '"';
    if (!db.text?.includes(expectedOpen) && !db.text?.includes(expectedClose)) {
      warnings.push(`Dialogue block missing ${activeLang} quote markers`);
      score.warn++;
    }
  }

  // Consecutive narration merge suggestion
  let consecNarration = 0;
  for (const b of blocks) {
    if (b.type === 'narration') {
      consecNarration++;
      if (consecNarration > 5) {
        info.push('Consider breaking long narration into smaller paragraphs');
        break;
      }
    } else {
      consecNarration = 0;
    }
  }

  score.total = score.pass + score.warn + score.fail;
  return { valid: errors.length === 0, errors, warnings, info, score };
}

module.exports = { validateChapterJs };
