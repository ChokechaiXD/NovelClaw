/* ═══════════════════════════════════════════════════════════════════════
   reader-renderer.js — Thai Style Paragraph Renderer
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const ReaderRenderer = {

  /**
   * Render chapter data to HTML.
   * Supports both new format (paragraphs with type) and legacy.
   */
  renderChapter(data) {
    let html;
    // New format: paragraphs with type
    if (data.paragraphs && data.paragraphs.length && typeof data.paragraphs[0] === 'object') {
      html = this._renderTypedParagraphs(data.paragraphs);
    }
    // New format v2: paragraphs as strings (fallback via classify)
    else if (data.paragraphs && data.paragraphs.length && typeof data.paragraphs[0] === 'string') {
      html = this._renderClassifiedParagraphs(data.paragraphs);
    }
    // Legacy blocks
    else if (data.blocks && data.blocks.length) {
      html = this._renderBlocks(data.blocks);
    } else {
      html = '<p class="c-reader-empty-content">ยังไม่มีเนื้อหา</p>';
    }
    return html;
  },

  /* ── New format: type-based rendering ───────────────────────────── */

  _renderTypedParagraphs(paragraphs) {
    let html = '';
    for (const para of paragraphs) {
      if (!para || !para.text || !para.text.trim()) continue;
      const type = para.type || 'narration';
      const text = this._esc(para.text.trim());

      switch (type) {
        case 'dialogue':
          html += `<p class="c-para c-para--dialogue">${text}</p>`;
          break;
        case 'system':
          html += `<p class="c-para c-para--system">${text}</p>`;
          break;
        case 'thought':
          // text may already have <em> tags from classifier
          html += `<p class="c-para c-para--thought">${text}</p>`;
          break;
        case 'action':
          html += `<p class="c-para c-para--action">${text}</p>`;
          break;
        case 'end':
          html += `<p class="end-marker">${text}</p>`;
          break;
        case 'narration':
        default:
          html += `<p class="c-para c-para--narration">${text}</p>`;
          break;
      }
    }
    return html;
  },

  /* ── Classify string paragraphs on-the-fly (for legacy JSON) ──── */

  _renderClassifiedParagraphs(paragraphs) {
    const classified = this._classifyParagraphs(paragraphs);
    return this._renderTypedParagraphs(classified);
  },

  _classifyParagraphs(paragraphs) {
    const result = [];
    for (const text of paragraphs) {
      if (!text || !text.trim()) continue;
      const t = text.trim();
      // End markers
      if (t === '(จบบท)' || t === '(End)' || t === '（終）' || t === '(끝)') {
        result.push({ type: 'end', text: t });
        continue;
      }
      // Dialogue
      if (/["\u201c\u201d\u300c\u300d]/.test(t)) {
        result.push({ type: 'dialogue', text: t });
        continue;
      }
      // System
      if (/【[^】]*】/.test(t)) {
        result.push({ type: 'system', text: t });
        continue;
      }
      // Thought (CN brackets)
      if (/『[^』]+』/.test(t)) {
        result.push({ type: 'thought', text: t.replace(/『([^』]+)』/g, '<em>$1</em>') });
        continue;
      }
      // Thought (Thai indicators)
      const thoughtWords = ['รู้สึก', 'คิด', 'นึก', 'สงสัย', 'ครุ่นคิด', 'นึกในใจ', 'ในใจ'];
      if (thoughtWords.some(w => t.slice(0, 40).includes(w))) {
        result.push({ type: 'thought', text: `<em>${t}</em>` });
        continue;
      }
      // Action verbs
      const actionVerbs = ['หัน', 'เดิน', 'วิ่ง', 'กระโดด', 'ยก', 'วาง', 'ดึง', 'ก้ม', 'เงย',
                           'ก้าว', 'ลุก', 'ทรุด', 'เปิด', 'ปิด', 'หยิบ', 'คว้า'];
      if (actionVerbs.some(v => t.startsWith(v))) {
        result.push({ type: 'action', text: t });
        continue;
      }
      // Default: narration
      result.push({ type: 'narration', text: t });
    }
    return result;
  },

  /* ── Legacy v2 block render ────────────────────────────────────── */

  _renderBlocks(blocks) {
    let html = '';
    for (const b of blocks) {
      const t = (b.text || '').trim();
      if (!t) continue;
      const esc = this._esc(t);
      switch (b.type) {
        case 'dialogue':
          html += `<p class="c-para c-para--dialogue">${esc}</p>`;
          break;
        case 'system':
          html += `<p class="c-para c-para--system">${esc}</p>`;
          break;
        case 'game_title':
          html += `<p class="c-para c-para--system">${esc}</p>`;
          break;
        case 'end':
          html += `<p class="end-marker">${esc}</p>`;
          break;
        default:
          html += `<p class="c-para c-para--narration">${esc}</p>`;
      }
    }
    return html;
  },

  /* ── HTML escape ─────────────────────────────────────────────────── */

  _esc(str) {
    const el = document.createElement('div');
    el.textContent = str;
    return el.innerHTML;
  },
};
