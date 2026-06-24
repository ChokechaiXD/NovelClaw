/* ═══════════════════════════════════════════════════════════════════════
   reader-renderer.js — Paragraph rendering for chapter reader
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const ReaderRenderer = {

  /**
   * Render chapter data to HTML.
   * @param {object} data — chapter JSON (paragraphs[] or blocks[])
   * @returns {string} rendered HTML
   */
  renderChapter(data) {
    if (window.__NC_PERF) performance.mark('render-start');
    let html;
    // New format: paragraphs (type-less, inline markers)
    if (data.paragraphs && data.paragraphs.length) {
      html = this._renderParagraphs(data.paragraphs);
    }
    // Legacy format: blocks with types
    else if (data.blocks && data.blocks.length) {
      html = this._renderBlocks(data.blocks);
    } else {
      html = '<p style="text-align:center;padding:2em;">ยังไม่มีเนื้อหา</p>';
    }
    if (window.__NC_PERF) {
      performance.mark('render-end');
      performance.measure('chapter-render', 'render-start', 'render-end');
      const entries = performance.getEntriesByName('chapter-render');
      const last = entries[entries.length - 1];
      if (last && last.duration > 50) console.debug(`[perf] renderChapter: ${last.duration.toFixed(1)}ms (${html.length} chars)`);
    }
    return html;
  },

  /* ── v3 paragraph render ─────────────────────────────────────────── */
  _renderParagraphs(paragraphs) {
    let html = '';
    for (const para of paragraphs) {
      if (!para || !para.trim()) continue;
      const t = this._esc(para.trim());

      // End marker
      if (t === '(จบบท)' || t === '(End)' || t === '（終）' || t === '(끝)' || /^\([\u0e00-\u0e7f]+\)$/.test(t)) {
        html += `<p class="end-marker">${t}</p>`;
        continue;
      }

      // Inline marker styling — single-pass approach
      html += '<p>' + this._applyMarkers(t) + '</p>';
    }
    return html;
  },

  /* ── Legacy v2 block render ──────────────────────────────────────── */
  _renderBlocks(blocks) {
    let html = '';
    for (const b of blocks) {
      const t = (b.text || '').trim();
      if (!t) continue;
      switch (b.type) {
        case 'dialogue': html += `<p class="dialogue">${this._esc(t)}</p>`; break;
        case 'system':   html += `<p class="system-msg">${this._esc(t)}</p>`; break;
        case 'game_title': html += `<p class="game-title">${this._esc(t)}</p>`; break;
        case 'end':      html += `<p class="end-marker">${this._esc(t)}</p>`; break;
        default:         html += `<p>${this._esc(t)}</p>`;
      }
    }
    return html;
  },

  /* ── Marker styling ──────────────────────────────────────────────── */
  _applyMarkers(text) {
    // Order: dialogue first (uses " in HTML), then system+thought (no " conflict)
    let html = this._replaceDialogue(text);
    html = this._replaceSystem(html);
    html = this._replaceThought(html);
    return html;
  },

  _replaceDialogue(s) {
    return s
      .replace(/\u201c([^\u201d\n]+)\u201d/g, '<span class="c-marker--dialogue">$&</span>')
      .replace(/「([^」]+)」/g, '<span class="c-marker--dialogue">$&</span>');
  },

  _replaceSystem(s) {
    return s.replace(/【([^】]+)】/g, '<span class="c-marker--system">$&</span>');
  },

  _replaceThought(s) {
    return s.replace(/『([^』]+)』/g, '<span class="c-marker--thought">$&</span>');
  },

  /* ── HTML escape ─────────────────────────────────────────────────── */
  _esc(str) {
    const el = document.createElement('div');
    el.textContent = str;
    return el.innerHTML;
  }
};
