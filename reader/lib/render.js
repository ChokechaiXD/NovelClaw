/**
 * lib/render.js — Chapter JSON → HTML renderer.
 *
 * Converts a Chapter object (with blocks array) into HTML string.
 * Handles all block types: narration, dialogue, system, game_title, end.
 */
const { getBracketProfile } = require('./brackets');
const { esc } = require('./helpers');

function toCurly(s) {
  return s
    .replace(/\u300c/g, '\u201C')
    .replace(/\u300d/g, '\u201D')
    .replace(/\u300e/g, '\u2018')
    .replace(/\u300f/g, '\u2019')
    .replace(/^"(.*)"$/s, '\u201C$1\u201D')
    .replace(/^'(.*)'$/s, '\u2018$1\u2019');
}

function renderDialogue(text, brackets) {
  const dialogueOpen = brackets.dialogueOpen || '\u201C';
  const dialogueClose = brackets.dialogueClose || '\u201D';

  if (dialogueOpen === '\u300c' && text.startsWith('\u300c') && text.endsWith('\u300d')) {
    return `<p class="block-dialogue">${esc(text)}</p>`;
  }

  const normalized = toCurly(text);
  if (normalized.startsWith(dialogueOpen) && normalized.endsWith(dialogueClose)) {
    return `<p class="block-dialogue">${esc(normalized)}</p>`;
  }

  return `<p class="block-dialogue">${esc(dialogueOpen)}${esc(normalized)}${esc(dialogueClose)}</p>`;
}

function renderChapterJson(ch) {
  if (!ch || !Array.isArray(ch.blocks)) {
    return '<p class="error">Invalid chapter layout structure.</p>';
  }

  const brackets = getBracketProfile(ch);

  return ch.blocks.map(block => {
    const text = block.text || '';
    switch (block.type) {
      case 'end':
        return `<p class="end-marker">${esc(brackets.endMarker || '(จบบท)')}</p>`;
      case 'system':
        return `<p class="block-system">${esc(text).replace(/\u3010([^\u3011]+)\u3011/g, '<span class="inline-stat-badge">\u3010$1\u3011</span>')}</p>`;
      case 'game_title':
        return `<p class="block-gametitle">${esc(brackets.gameOpen || '\u300a')}${esc(text).replace(/\u3010([^\u3011]+)\u3011/g, '<span class="inline-stat-badge">\u3010$1\u3011</span>')}${esc(brackets.gameClose || '\u300b')}</p>`;
      case 'dialogue':
        return renderDialogue(text, brackets);
      case 'narration':
      default:
        return `<p class="block-narration">${esc(text).replace(/\u3010([^\u3011]+)\u3011/g, '<span class="inline-stat-badge">\u3010$1\u3011</span>').replace(/\u300c/g, '\u201C').replace(/\u300d/g, '\u201D').replace(/\u300e/g, '\u2018').replace(/\u300f/g, '\u2019')}</p>`;
    }
  }).join('\n');
}

module.exports = { renderChapterJson };
