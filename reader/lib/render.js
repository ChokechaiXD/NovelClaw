/**
 * lib/render.js — Chapter JSON → HTML renderer.
 *
 * Converts a Chapter object (with blocks array) into HTML string.
 * Handles all block types: narration, dialogue, system, game_title, end.
 * Converts CN/JP kagikakko to curly Thai/EN quotes.
 */
const { getBracketProfile } = require('./brackets');
const { esc } = require('./helpers');

function renderChapterJson(ch) {
  if (!ch || !Array.isArray(ch.blocks)) {
    return '<p class="error">Invalid chapter layout structure.</p>';
  }

  // Convert CN/JP kagikakko to curly Thai/EN quotes
  const toCurly = (s) => s
    .replace(/\u300c/g, '\u201C')
    .replace(/\u300d/g, '\u201D')
    .replace(/\u300e/g, '\u2018')
    .replace(/\u300f/g, '\u2019');

  // Wrap inline 【...】 inside narration/dialogue with badge span
  const parseInline = (t) => t ? t.replace(/\u3010([^\u3011]+)\u3011/g, '<span class="inline-stat-badge">\u3010$1\u3011</span>') : '';

  const brackets = getBracketProfile(ch);

  return ch.blocks.map(block => {
    const text = esc(block.text || '');
    switch (block.type) {
      case 'end':
        return `<p class="end-marker">${esc(brackets.endMarker || '(จบบท)')}</p>`;
      case 'system':
        return `<p class="block-system">${parseInline(text)}</p>`;
      case 'game_title':
        return `<p class="block-gametitle">${esc(brackets.gameOpen || '《')}${parseInline(text)}${esc(brackets.gameClose || '》')}</p>`;
      case 'dialogue':
        return `<p class="block-dialogue">${esc(brackets.dialogueOpen || '"')}${parseInline(toCurly(text))}${esc(brackets.dialogueClose || '"')}</p>`;
      case 'narration':
      default:
        return `<p class="block-narration">${parseInline(toCurly(text))}</p>`;
    }
  }).join('\n');
}

module.exports = { renderChapterJson };
