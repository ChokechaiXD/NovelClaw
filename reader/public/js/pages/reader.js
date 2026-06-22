/* ═══════════════════════════════════════════════════════════════════════
   reader.js — Chapter Reader Page
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const ReaderPage = {
  _readerKeyHandler: null,

  async render(params) {
    const page = Ui.$('page-reader');
    if (!page) return;
    const slug = params.slug;
    const num = parseInt(params.num, 10);
    if (!slug || isNaN(num)) { Ui.showError(page, 'ไม่พบตอน'); return; }

    try {
      const chapters = await Api.getChapters(slug);
      const novels = await Api.getNovels();
      const novel = novels.find(n => n.slug === slug);

      let idx = chapters.findIndex(c => c.num === num);
      if (idx === -1) idx = 0;

      let html = `
      <div class="c-container" style="max-width:760px;">
        <div class="c-toolbar">
          <a href="#novel/${slug}" class="c-toolbar__back" data-nav>
            <svg style="width:16px;height:16px;"><use xlink:href="#icon-arrow-left"/></svg>
            <span>กลับ</span>
          </a>
          <span class="c-toolbar__title">${novel ? Ui.esc(novel.title) : slug}</span>
          <span class="c-toolbar__divider"></span>
          <button class="c-btn c-btn--icon" id="reader-theme-toggle" title="เปลี่ยนธีม"></button>
          <button class="c-btn c-btn--icon" id="reader-distraction-toggle" title="โหมดอ่านหนังสือ">
            <svg style="width:16px;height:16px;"><use xlink:href="#icon-fullscreen"/></svg>
          </button>
        </div>
        <div class="c-reader__nav">
          <button class="c-reader__nav-btn" id="reader-prev">◀ ก่อนหน้า</button>
          <span class="c-reader__position" id="reader-position"></span>
          <button class="c-reader__nav-btn" id="reader-next">ถัดไป ▶</button>
        </div>
        <div class="c-reader">
          <h1 class="c-reader__title" id="reader-title"></h1>
          <div class="c-reader__meta">
            <button class="c-btn c-btn--icon" id="reader-font-sm" title="ลดขนาดอักษร">A−</button>
            <span style="font-size:var(--text-sm);color:var(--c-text-muted);">16px</span>
            <button class="c-btn c-btn--icon" id="reader-font-lg" title="เพิ่มขนาดอักษร">A+</button>
          </div>
          <div class="c-reader__content" id="reader-content"></div>
        </div>
        <div class="c-reader__nav">
          <button class="c-reader__nav-btn" id="reader-prev-2">◀ ก่อนหน้า</button>
          <button class="c-reader__nav-btn" id="reader-back-top">↑ กลับบน</button>
          <button class="c-reader__nav-btn" id="reader-next-2">ถัดไป ▶</button>
        </div>
      </div>`;

      page.innerHTML = html;

      // ── Load chapter ─────────────────────────────────────────────────
      const loadChapter = async (chIdx) => {
        const ch = chapters[chIdx];
        if (!ch) return;
        try {
          const data = await Api.getChapterContent(slug, ch.num);

          Ui.$('reader-title').textContent = `ตอนที่ ${ch.num}${ch.title ? ' — ' + ch.title : ''}`;
          Ui.$('reader-position').textContent = `${chIdx + 1} / ${chapters.length}`;

          let contentHtml = '';
          // New format: paragraphs (type-less, inline markers)
          if (data.paragraphs && data.paragraphs.length) {
            for (const para of data.paragraphs) {
              if (!para || !para.trim()) continue;
              const t = Ui.esc(para.trim());
              // End marker paragraph
              if (t === '(จบบท)' || t === '(End)' || t === '（終）' || t === '(끝)' || /^\([\u0e00-\u0e7f]+\)$/.test(t)) {
                contentHtml += `<p class="end-marker">${t}</p>`;
                continue;
              }
              // Inline marker styling
              const html = t
                .replace(/【([^】]+)】/g, '<span class="c-marker--system">【$1】</span>')
                .replace(/『([^』]+)』/g, '<span class="c-marker--thought">『$1』</span>')
                .replace(/"([^"\n]+)"/g, '<span class="c-marker--dialogue">"$1"</span>')
                .replace(/「([^」]+)」/g, '<span class="c-marker--dialogue">「$1」</span>')
                .replace(/\u201c([^\u201d\n]+)\u201d/g, '<span class="c-marker--dialogue">\u201c$1\u201d</span>');
              contentHtml += `<p>${html}</p>`;
            }
          }
          // Legacy format: blocks with types (backward compat)
          else {
            const blocks = data.blocks || data.chapter?.blocks || [];
            for (const b of blocks) {
              const t = (b.text || '').trim();
              if (!t) continue;
              if (b.type === 'dialogue') contentHtml += `<p class="dialogue">${Ui.esc(t)}</p>`;
              else if (b.type === 'system') contentHtml += `<p class="system-msg">${Ui.esc(t)}</p>`;
              else if (b.type === 'game_title') contentHtml += `<p class="game-title">${Ui.esc(t)}</p>`;
              else if (b.type === 'end') contentHtml += `<p class="end-marker">${Ui.esc(t)}</p>`;
              else contentHtml += `<p>${Ui.esc(t)}</p>`;
            }
          }
          Ui.$('reader-content').innerHTML = contentHtml;

          // Mark as read
          Store.markRead(slug, ch.num);
          Store.setLastPosition(slug, ch.num);

          // Update nav buttons
          Ui.$('reader-prev').disabled = chIdx <= 0;
          Ui.$('reader-prev-2').disabled = chIdx <= 0;
          Ui.$('reader-next').disabled = chIdx >= chapters.length - 1;
          Ui.$('reader-next-2').disabled = chIdx >= chapters.length - 1;

          // Scroll top
          const scrollContainer = document.querySelector('.c-content');
          if (scrollContainer) scrollContainer.scrollTop = 0;
        } catch (err) {
          Ui.$('reader-title').textContent = 'เกิดข้อผิดพลาด';
          Ui.$('reader-content').innerHTML = `<p style="text-align:center;padding:2em;color:var(--c-error);">โหลดไม่สำเร็จ: ${err.message}</p>`;
        }
      };

      await loadChapter(idx);
      currentReaderIdx = idx;
      currentReaderChapters = chapters;
      currentReaderSlug = slug;

      // ── Wire Nav Events ──────────────────────────────────────────────
      Ui.$('reader-prev').onclick = () => { if (currentReaderIdx > 0) loadChapter(--currentReaderIdx); };
      Ui.$('reader-next').onclick = () => { if (currentReaderIdx < currentReaderChapters.length - 1) loadChapter(++currentReaderIdx); };
      Ui.$('reader-prev-2').onclick = () => { if (currentReaderIdx > 0) loadChapter(--currentReaderIdx); };
      Ui.$('reader-next-2').onclick = () => { if (currentReaderIdx < currentReaderChapters.length - 1) loadChapter(++currentReaderIdx); };
      Ui.$('reader-back-top').onclick = () => {
        const sc = document.querySelector('.c-content');
        if (sc) sc.scrollTo({ top: 0, behavior: 'smooth' });
      };

      // ── Font size ───────────────────────────────────────────────────
      let fontStep = 0;
      Ui.$('reader-font-sm').onclick = () => {
        fontStep = Math.max(-2, fontStep - 1);
        document.documentElement.style.setProperty('--text-base', `${15 + fontStep * 2}px`);
      };
      Ui.$('reader-font-lg').onclick = () => {
        fontStep = Math.min(3, fontStep + 1);
        document.documentElement.style.setProperty('--text-base', `${15 + fontStep * 2}px`);
      };

      // ── Theme toggle ─────────────────────────────────────────────────
      const THEMES = ['dark', 'amoled', 'light', 'sepia'];
      const THEME_ICONS = { light: '#icon-sun', dark: '#icon-moon', amoled: '#icon-moon', sepia: '#icon-book' };
      let currentTheme = Store.getSettings().theme || 'dark';

      const updateIcon = (t) => {
        const btn = Ui.$('reader-theme-toggle');
        if (btn) btn.innerHTML = `<svg style="width:16px;height:16px;"><use xlink:href="${THEME_ICONS[t] || '#icon-moon'}"/></svg>`;
      };
      updateIcon(currentTheme);

      Ui.$('reader-theme-toggle').onclick = () => {
        currentTheme = THEMES[(THEMES.indexOf(currentTheme) + 1) % THEMES.length];
        Store.setSetting('theme', currentTheme);
        updateIcon(currentTheme);
      };

      // ── Distraction-free mode ────────────────────────────────────────
      Ui.$('reader-distraction-toggle').onclick = () => {
        const app = document.getElementById('app-layout');
        if (!app) return;
        const isCollapsed = app.classList.contains('c-app__sidebar--collapsed');
        app.classList.toggle('c-app__sidebar--collapsed');
        app.classList.toggle('c-app__rightbar--collapsed');
        Ui.showToast(isCollapsed ? 'เปิดแถบเมนูแล้ว' : 'โหมดอ่านหนังสือ');
      };

      // ── Keyboard shortcuts ──────────────────────────────────────────
      if (this._readerKeyHandler) document.removeEventListener('keydown', this._readerKeyHandler);
      this._readerKeyHandler = (e) => {
        if (e.target.matches('input, textarea')) return;
        if (e.key === 'ArrowLeft') Ui.$('reader-prev')?.click();
        if (e.key === 'ArrowRight') Ui.$('reader-next')?.click();
      };
      document.addEventListener('keydown', this._readerKeyHandler);

    } catch (err) {
      Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
    }
  }
};

// Global state for reader nav
let currentReaderIdx = 0;
let currentReaderChapters = [];
let currentReaderSlug = '';
