/**
 * lib/render.js — Chapter JSON → HTML renderer.
 *
 * Converts a Chapter object (with blocks array) into HTML string.
 * Uses the active language profile (output_lang / profile_lang / lang)
 * for bracket styling and end-marker display.
 *
 * CSS classes match design-system.css:
 *   narration  → <p> (no class)
 *   dialogue   → class="dialogue"  data-lang, data-speaker
 *   system     → class="system-msg"  data-lang
 *   game_title → class="game-title"  data-lang
 *   end        → class="end-marker"  data-lang
 */
const { getBracketProfile, resolveProfileLang } = require('./brackets');
const { esc } = require('./helpers');

// Convert CN/JP kagikakko to curly Thai/EN quotes
function toCurly(s) {
  return s
    .replace(/\u300c/g, '\u201C')
    .replace(/\u300d/g, '\u201D')
    .replace(/\u300e/g, '\u2018')
    .replace(/\u300f/g, '\u2019');
}

// Wrap inline 【...】 inside narration/dialogue with badge span
function parseInline(t) {
  return t ? t.replace(/【([^】]+)】/g, '<span class="inline-stat-badge">【$1】</span>') : '';
}

function renderChapterJson(ch) {
  if (!ch || !Array.isArray(ch.blocks)) {
    return '<p class="error">Invalid chapter layout structure.</p>';
  }

  const activeLang = resolveProfileLang(ch);

  const html = ch.blocks.map(block => {
    const text = esc(block.text || '');
    switch (block.type) {
      case 'system':
        return '<p class="system-msg" data-lang="' + activeLang + '">' + parseInline(text) + '</p>';
      case 'dialogue': {
        const sp = block.speaker ? ' data-speaker="' + esc(block.speaker) + '"' : '';
        return '<p class="dialogue"' + sp + ' data-lang="' + activeLang + '">' + toCurly(parseInline(text)) + '</p>';
      }
      case 'narration':
        return '<p>' + toCurly(parseInline(text)) + '</p>';
      case 'game_title':
        return '<p class="game-title" data-lang="' + activeLang + '">' + text + '</p>';
      case 'end':
        return '<p class="end-marker" data-lang="' + activeLang + '">' + text + '</p>';
      default:
        return '<p>' + text + '</p>';
    }
  }).join('\n') + (ch.source ? '\n<hr/>\n<p class="source-footer">' + esc(ch.source) + '</p>' : '');

  return html;
}

module.exports = { renderChapterJson };
