/* ═══════════════════════════════════════════════════════════════════════
   reader.js — Chapter Reader Page
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const ReaderPage = {
  _readerAbortController: null,

  async render(params) {
    // ── Cleanup previous events before re-render ─────────────────────
    this._cleanupEvents();

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
      <div class="reader-page">
        <!-- Progress bar -->
        <div class="reader-progress" id="reader-progress"><div class="reader-progress__fill" id="reader-progress-fill"></div></div>

        <!-- Floating exit button (visible in book mode) -->
        <button class="reader-exit-btn" id="reader-exit-btn" title="ออกจากโหมดอ่าน">
          <svg style="width:18px;height:18px;"><use xlink:href="#icon-arrow-left"/></svg>
        </button>

        <div class="c-toolbar reader-toolbar">
          <a href="#novel/${slug}" class="c-toolbar__back" data-nav>
            <svg style="width:16px;height:16px;"><use xlink:href="#icon-arrow-left"/></svg>
            <span>กลับ</span>
          </a>
          <span class="c-toolbar__title">${novel ? Ui.esc(Ui.displayTitle(novel)) : slug}</span>
          <span class="c-toolbar__divider"></span>
          <button class="c-btn c-btn--icon" id="reader-theme-toggle" title="เปลี่ยนธีม"></button>
          <button class="c-btn c-btn--icon" id="reader-distraction-toggle" title="โหมดอ่านหนังสือ">
            <svg style="width:16px;height:16px;"><use xlink:href="#icon-fullscreen"/></svg>
          </button>
        </div>

        <div class="reader-shell">
          <div class="c-reader__nav">
            <button class="c-reader__nav-btn" id="reader-prev">◀ ก่อนหน้า</button>
            <span class="c-reader__position" id="reader-position"></span>
            <button class="c-reader__nav-btn" id="reader-next">ถัดไป ▶</button>
          </div>
          <div class="reader-body">
            <h1 class="reader-title" id="reader-title"></h1>
            <div class="c-reader__meta">
              <button class="c-btn c-btn--icon" id="reader-font-sm" title="ลดขนาดอักษร">A−</button>
              <span style="font-size:var(--text-sm);color:var(--c-text-muted);" id="reader-font-label">18px</span>
              <button class="c-btn c-btn--icon" id="reader-font-lg" title="เพิ่มขนาดอักษร">A+</button>
              <span class="c-toolbar__divider"></span>
              <button class="c-btn c-btn--icon" id="reader-leading-sm" title="ลดช่องว่าง">↑↓</button>
              <span style="font-size:var(--text-sm);color:var(--c-text-muted);" id="reader-leading-label">1.8</span>
              <button class="c-btn c-btn--icon" id="reader-leading-lg" title="เพิ่มช่องว่าง">↑↑</button>
            </div>
            <div id="reader-content"></div>
          </div>
          <div class="c-reader__nav">
            <button class="c-reader__nav-btn" id="reader-prev-2">◀ ก่อนหน้า</button>
            <button class="c-reader__nav-btn" id="reader-back-top">↑ กลับบน</button>
            <button class="c-reader__nav-btn" id="reader-next-2">ถัดไป ▶</button>
          </div>
        </div>
      </div>`;

      page.innerHTML = html;

      // Show loading state while chapter loads
      Ui.$('reader-content').innerHTML = '<div class="c-skel c-skel--block" style="height:200px;"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line" style="width:75%;"></div><div class="c-skel c-skel--line"></div><div class="c-skel c-skel--line" style="width:60%;"></div>';

      // ── Load chapter ─────────────────────────────────────────────────
      const loadChapter = async (chIdx) => {
        const ch = chapters[chIdx];
        if (!ch) return;
        try {
          const data = await Api.getChapterContent(slug, ch.num, Store.getSettings().readerLang || 'th');

          Ui.$('reader-title').textContent = data.title || ch.title || `ตอนที่ ${ch.num}`;
          Ui.$('reader-position').textContent = `${chIdx + 1} / ${chapters.length}`;

          // Update topbar title with novel + chapter info
          const titleEl = document.getElementById('page-title');
          if (titleEl) titleEl.textContent = Ui.esc(Ui.displayTitle(novel) || slug) + ' — ตอนที่ ' + ch.num;

          let contentHtml = ReaderRenderer.renderChapter(data);
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

      // ── Wire Nav Events (navigate via hash — Router handles rendering) ─
      Ui.$('reader-prev').onclick = () => {
        if (currentReaderIdx > 0) {
          const prev = chapters[currentReaderIdx - 1];
          if (prev) window.location.hash = `#novel/${slug}/${prev.num}`;
        }
      };
      Ui.$('reader-next').onclick = () => {
        if (currentReaderIdx < chapters.length - 1) {
          const next = chapters[currentReaderIdx + 1];
          if (next) window.location.hash = `#novel/${slug}/${next.num}`;
        }
      };
      Ui.$('reader-prev-2').onclick = () => {
        if (currentReaderIdx > 0) {
          const prev = chapters[currentReaderIdx - 1];
          if (prev) window.location.hash = `#novel/${slug}/${prev.num}`;
        }
      };
      Ui.$('reader-next-2').onclick = () => {
        if (currentReaderIdx < chapters.length - 1) {
          const next = chapters[currentReaderIdx + 1];
          if (next) window.location.hash = `#novel/${slug}/${next.num}`;
        }
      };
      Ui.$('reader-back-top').onclick = () => {
        const sc = document.querySelector('.c-content');
        if (sc) sc.scrollTo({ top: 0, behavior: 'smooth' });
      };

      // ── Font size controls (persisted) ──────────────────────────────────
      const savedFontSize = parseInt(Store.getSettings().fontSize, 10) || 18;
      let fontStep = Math.round((savedFontSize - 18) / 2);
      const applyFont = (step) => {
        const px = Math.max(14, Math.min(28, 18 + step * 2));
        document.documentElement.style.setProperty('--reader-font-size', `${px}px`);
        Store.setSetting('fontSize', px);
        const lbl = Ui.$('reader-font-label');
        if (lbl) lbl.textContent = `${px}px`;
      };
      applyFont(fontStep);
      Ui.$('reader-font-sm').onclick = () => { fontStep = Math.max(-1, fontStep - 1); applyFont(fontStep); };
      Ui.$('reader-font-lg').onclick = () => { fontStep = Math.min(2, fontStep + 1); applyFont(fontStep); };

      // ── Line-height controls (persisted) ────────────────────────────────
      const LEADINGS = [1.6, 1.8, 2.0, 2.2];
      const savedLeading = parseFloat(Store.getSettings().lineHeight) || 1.8;
      let leadingIdx = LEADINGS.indexOf(savedLeading);
      if (leadingIdx === -1) leadingIdx = 1;
      const applyLeading = (idx) => {
        const val = LEADINGS[idx];
        document.documentElement.style.setProperty('--leading-reader', `${val}`);
        document.documentElement.style.setProperty('--reader-line-height', `${val}`);
        Store.setSetting('lineHeight', val);
        const lbl = Ui.$('reader-leading-label');
        if (lbl) lbl.textContent = `${val}`;
      };
      applyLeading(leadingIdx);
      Ui.$('reader-leading-sm').onclick = () => { leadingIdx = Math.max(0, leadingIdx - 1); applyLeading(leadingIdx); };
      Ui.$('reader-leading-lg').onclick = () => { leadingIdx = Math.min(LEADINGS.length - 1, leadingIdx + 1); applyLeading(leadingIdx); };

      // ── Theme toggle ─────────────────────────────────────────────────
      const THEMES = ['sepia', 'night', 'amoled', 'paper'];
      const THEME_ICONS = { sepia: '#icon-book', night: '#icon-moon', amoled: '#icon-moon', paper: '#icon-sun' };
      let currentTheme = Store.getSettings().theme || 'sepia';
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

      // ── Distraction-free / book mode ───────────────────────────────
      Ui.$('reader-distraction-toggle').onclick = () => {
        const app = document.querySelector('.c-app');
        if (!app) return;
        app.classList.toggle('c-app--book-mode');
        const isActive = app.classList.contains('c-app--book-mode');
        Ui.showToast(isActive ? 'โหมดอ่านหนังสือ' : 'ออกจากโหมดอ่านหนังสือ');
      };

      // ── Exit book mode button ──────────────────────────────────────
      Ui.$('reader-exit-btn').onclick = () => {
        const app = document.querySelector('.c-app');
        app?.classList.remove('c-app--book-mode');
        Ui.showToast('ออกจากโหมดอ่านหนังสือ');
      };

      // ── Bind events with AbortController for cleanup ──────────────────
      this._bindReaderEvents();

      // ── Scroll progress initial ────────────────────────────────────
      const doUpdateProgress = () => {
        const sc = document.querySelector('.c-content');
        if (!sc) return;
        const pct = (sc.scrollTop / (sc.scrollHeight - sc.clientHeight)) * 100;
        const fill = Ui.$('reader-progress-fill');
        if (fill) fill.style.width = Math.min(100, Math.max(0, pct)) + '%';
      };
      doUpdateProgress(); // initial

    } catch (err) {
      Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
    }
  },

  /* ── Bind persistent events with AbortController cleanup ────────── */
  _bindReaderEvents() {
    this._cleanupEvents();
    this._readerAbortController = new AbortController();
    const { signal } = this._readerAbortController;

    // Scroll progress bar (debounced)
    const updateProgress = () => {
      const sc = document.querySelector('.c-content');
      if (!sc) return;
      const pct = (sc.scrollTop / (sc.scrollHeight - sc.clientHeight)) * 100;
      const fill = Ui.$('reader-progress-fill');
      if (fill) fill.style.width = Math.min(100, Math.max(0, pct)) + '%';
    };
    const debouncedProgress = Ui.debounce(updateProgress, 100);
    document.querySelector('.c-content')?.addEventListener('scroll', debouncedProgress, { signal });

    // Keyboard shortcuts
    const keyHandler = (e) => {
      if (e.target.matches('input, textarea')) return;
      if (e.key === 'ArrowLeft') Ui.$('reader-prev')?.click();
      if (e.key === 'ArrowRight') Ui.$('reader-next')?.click();
    };
    document.addEventListener('keydown', keyHandler, { signal });
  },

  /* ── Cleanup all AbortController-bound events ──────────────────── */
  _cleanupEvents() {
    if (this._readerAbortController) {
      this._readerAbortController.abort();
      this._readerAbortController = null;
    }
  }
};

// Global state for reader nav
let currentReaderIdx = 0;
let currentReaderChapters = [];
let currentReaderSlug = '';
