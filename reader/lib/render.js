/**
 * lib/render.js — Chapter JSON → HTML renderer.
 *
 * ⚠️  TEST SUPPORT ONLY — Not used in production.
 *     Frontend rendering is handled by js/pages/reader.js + js/reader-renderer.js.
 *     This file exists only for server-side Node tests.
 *     Consider using reader/tests/stub-renderer.js for future tests.
 *
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

/**
 * renderParagraphs — New universal renderer.
 *
 * Takes an array of paragraph strings, applies inline marker styling.
 * No block types needed — markers in text drive the styling via regex.
 * Supports: dialogue "" / 「」, system 【】, thought 『』, end markers.
 * Universal across all novel languages and genres.
 */
function renderParagraphs(paragraphs, lang) {
  if (!paragraphs || !paragraphs.length) return '';
  return paragraphs.map(text => {
    if (!text) return '<p></p>';
    const escaped = esc(text);

    // End marker paragraph (full line only)
    if (/^\([\u0e00-\u0e7f]+\)$/.test(escaped) ||
        /^[\u3000-\u30ff\u4e00-\u9fff\uff01-\uff5e\(\)]+$/.test(escaped)) {
      return `<p class="end-marker">${escaped}</p>`;
    }

    // Apply inline marker styling
    const html = escaped
      // System 【...】
      .replace(/【([^】]+)】/g, '<span class="c-marker--system">【$1】</span>')
      // Inner thought 『...』 (JP/CN)
      .replace(/『([^』]+)』/g, '<span class="c-marker--thought">『$1』</span>')
      // Dialogue "..." (straight quotes — easiest for LLM)
      .replace(/"([^"\n]+)"/g, '<span class="c-marker--dialogue">"$1"</span>')
      // Dialogue 「...」 (CJK brackets)
      .replace(/「([^」]+)」/g, '<span class="c-marker--dialogue">「$1」</span>')
      // Dialogue "" (curly quotes)
      .replace(/\u201c([^\u201d\n]+)\u201d/g, '<span class="c-marker--dialogue">\u201c$1\u201d</span>');

    return `<p>${html}</p>`;
  }).join('\n') + '\n';
}

module.exports = { renderChapterJson, renderParagraphs };
