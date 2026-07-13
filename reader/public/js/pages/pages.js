/* ═══════════════════════════════════════════════════════════════════════
   library.js — Library Page
   novel.js — Novel Detail Page  
   search.js — Search Page
   history.js — History Page (fixed)
   settings.js — Settings Page
   profile.js — Profile Page
   ═══════════════════════════════════════════════════════════════════════ */

// ── LIBRARY ──────────────────────────────────────────────────────────────
const LibraryPage = {
  async render(params = {}) {
    const page = Ui.$('page-library');
    if (!page) return;
    Ui.showSkeleton('page-library');
    try {
      const novels = await Api.getNovels();
      const visibleNovels = novels.filter(Ui.isVisibleNovel).map(Ui.enrichNovel);
      if (!visibleNovels.length) {
        Ui.showEmpty(page, 'หอสมุดว่างเปล่า', 'ยังไม่มีนิยายในระบบ เริ่มเพิ่มกันเลย!');
        return;
      }
      const settings = Store.getSettings();
      const sortBy = params.sort || settings.librarySort || 'title';
      const requestedFilter = params.filter || settings.libraryFilter || 'all';
      const filterBy = ['all', 'readable', 'complete', 'untranslated'].includes(requestedFilter)
        ? requestedFilter : 'all';
      const query = (params.q || '').trim().toLowerCase();
      const counts = {
        total: visibleNovels.length,
        readable: visibleNovels.filter(n => n.translatedCount > 0).length,
        complete: visibleNovels.filter(n => n.totalCount > 0 && n.translatedCount >= n.totalCount).length,
        untranslated: visibleNovels.filter(n => n.translatedCount === 0).length,
      };
      const filtered = visibleNovels.filter(n => {
        if (filterBy === 'readable') return n.translatedCount > 0;
        if (filterBy === 'complete') return n.totalCount > 0 && n.translatedCount >= n.totalCount;
        if (filterBy === 'untranslated') return n.translatedCount === 0;
        return true;
      }).filter(n => {
        if (!query) return true;
        return [n.title, n.translatedTitle, n.slug, n.author].some(value => String(value || '').toLowerCase().includes(query));
      });
      const sorted = [...filtered].sort((a, b) => {
        if (sortBy === 'progress') return (b.translatedChapters || 0) - (a.translatedChapters || 0);
        if (sortBy === 'chapters') return (b.chapterCount || 0) - (a.chapterCount || 0);
        if (sortBy === 'last') return (b.lastRead || 0) - (a.lastRead || 0);
        return (Ui.displayTitle(a) || '').localeCompare(Ui.displayTitle(b) || '');
      });
      const resultHtml = sorted.length
        ? sorted.map(n => Ui.novelCard(n)).join('')
        : '<div class="c-empty c-empty--compact"><div class="c-empty__title">ไม่พบนิยายตามเงื่อนไข</div><div class="c-empty__desc">ลองเปลี่ยน filter หรือคำค้นหา</div></div>';
      let html = `<div class="c-container c-library-page">
        <header class="c-page-heading">
          <p class="c-page-heading__eyebrow">ห้องอ่าน</p>
          <h1 class="c-page-heading__title">คลังนิยาย</h1>
          <p class="c-page-heading__subtitle">เลือกเรื่องที่อยากอ่าน แล้วกลับมาต่อจากตำแหน่งเดิมได้ทุกอุปกรณ์ในวง LAN</p>
        </header>
        <section class="c-section">
          <div class="c-library-toolbar">
            <div class="c-search c-library-toolbar__search">
              ${Ui.icon('search', 'sm')}
              <input type="search" id="library-search" class="c-search__input" value="${Ui.esc(params.q || '')}" placeholder="ค้นหาชื่อเรื่อง ผู้แต่ง หรือ slug" />
            </div>
            <select id="library-filter" class="c-library-sort" aria-label="กรองนิยาย">
              <option value="all"${filterBy === 'all' ? ' selected' : ''}>ทั้งหมด</option>
              <option value="readable"${filterBy === 'readable' ? ' selected' : ''}>มีฉบับแปล (${counts.readable})</option>
              <option value="complete"${filterBy === 'complete' ? ' selected' : ''}>แปลครบ (${counts.complete})</option>
              <option value="untranslated"${filterBy === 'untranslated' ? ' selected' : ''}>ยังไม่มีฉบับแปล (${counts.untranslated})</option>
            </select>
            <select id="library-sort" class="c-library-sort" aria-label="เรียงนิยาย">
              <option value="title"${sortBy === 'title' ? ' selected' : ''}>ชื่อ</option>
              <option value="progress"${sortBy === 'progress' ? ' selected' : ''}>ความคืบหน้า</option>
              <option value="chapters"${sortBy === 'chapters' ? ' selected' : ''}>จำนวนตอน</option>
              <option value="last"${sortBy === 'last' ? ' selected' : ''}>อ่านล่าสุด</option>
            </select>
            <span class="c-section__count">${sorted.length}/${visibleNovels.length} เรื่อง</span>
          </div>
          <div class="c-card-grid c-library-grid">${resultHtml}</div>
        </section>
      </div>`;
      page.innerHTML = html;
      
      const sel = document.getElementById('library-sort');
      if (sel) {
        sel.addEventListener('change', () => {
          Store.setSetting('librarySort', sel.value);
          LibraryPage.render({ sort: sel.value, filter: filterBy, q: document.getElementById('library-search')?.value || '' });
        });
      }
      const filterSel = document.getElementById('library-filter');
      if (filterSel) {
        filterSel.addEventListener('change', () => {
          Store.setSetting('libraryFilter', filterSel.value);
          LibraryPage.render({ sort: sel?.value || sortBy, filter: filterSel.value, q: document.getElementById('library-search')?.value || '' });
        });
      }
      const searchInput = document.getElementById('library-search');
      if (searchInput) {
        searchInput.addEventListener('input', Ui.debounce(() => {
          LibraryPage.render({ sort: sel?.value || sortBy, filter: filterSel?.value || filterBy, q: searchInput.value || '' });
        }, 180));
      }
    } catch (err) { Ui.showError(page, 'โหลดไม่สำเร็จ', err.message); }
  }
};

// ── SEARCH ───────────────────────────────────────────────────────────────
const SearchPage = {
  async render(params = {}) {
    const page = Ui.$('page-search');
    if (!page) return;
    
    page.innerHTML = `<div class="c-container c-search-page">
      <header class="c-page-heading">
        <p class="c-page-heading__eyebrow">ห้องอ่าน</p>
        <h1 class="c-page-heading__title">ค้นหานิยาย</h1>
        <p class="c-page-heading__subtitle">ค้นจากชื่อเรื่อง ชื่อแปล ผู้แต่ง หรือรหัสเรื่อง</p>
      </header>
      <section class="c-section">
        <div class="c-search c-search-page__input-wrap">
          ${Ui.icon('search', 'sm')}
          <input type="search" id="search-input-field" placeholder="พิมพ์ชื่อเรื่อง ผู้แต่ง หรือรหัสเรื่อง..." class="c-search__input" />
        </div>
        <div id="search-summary" class="c-search-page__summary"></div>
        <div id="search-results"></div>
      </section>
    </div>`;
    
    const results = Ui.$('search-results');
    const input = Ui.$('search-input-field');
    if (!results) return;

    // Helper function to render a list of novels
    const renderNovelsList = (filteredList) => {
      if (filteredList.length === 0) {
        Ui.$('search-summary').textContent = 'ไม่พบผลลัพธ์';
        results.innerHTML = '<div class="c-empty c-empty--compact"><div class="c-empty__title">ไม่พบนิยาย</div><div class="c-empty__desc">ลองค้นด้วยชื่อเรื่อง ภาษาไทย จีน ผู้แต่ง หรือ slug เช่น global-descent</div></div>';
        return;
      }
      Ui.$('search-summary').textContent = filteredList.length + ' เรื่อง';
      results.innerHTML = '<div class="c-card-grid c-search-results-grid">' + filteredList.map(n => Ui.novelCard(n, { compact: true })).join('') + '</div>';
    };

    // Load initial list (all novels)
    try {
      const allNovels = (await Api.getNovels()).filter(Ui.isVisibleNovel).map(Ui.enrichNovel);
      renderNovelsList(allNovels);

      // Handle search input events
      input?.addEventListener('input', async (e) => {
        const q = e.target.value.trim().toLowerCase();
        if (q.length < 2) {
          renderNovelsList(allNovels);
          return;
        }
        const filtered = allNovels.filter(n =>
          (n.title || '').toLowerCase().includes(q) ||
          (n.translatedTitle || '').toLowerCase().includes(q) ||
          (n.slug || '').toLowerCase().includes(q) ||
          (n.author || '').toLowerCase().includes(q) ||
          (n.source_lang || '').toLowerCase().includes(q)
        );
        renderNovelsList(filtered);
      });
    } catch (_) {
      results.innerHTML = '<p class="u-text-center c-error__title">เกิดข้อผิดพลาด</p>';
    }
  }
};

// ── HISTORY ──────────────────────────────────────────────────────────────
const HistoryPage = {
  async render(params = {}) {
    const page = Ui.$('page-history');
    if (!page) return;
    const recent = Store.getHistory();
    const novels = await Api.getNovels();
    let html = `<div class="c-container c-history-page">
      <header class="c-page-heading">
        <p class="c-page-heading__eyebrow">ห้องอ่าน</p>
        <h1 class="c-page-heading__title">อ่านล่าสุด</h1>
        <p class="c-page-heading__subtitle">กลับไปยังตอนที่เคยอ่าน โดยเรียงจากรายการล่าสุด</p>
      </header>
      <section class="c-section"><div class="c-list c-history-list">`;
    if (recent.length === 0) {
      html += '<div class="c-empty c-empty--roomy"><svg class="c-empty__mascot" aria-hidden="true"><use href="#brand-mark"/></svg><div class="c-empty__title">ยังไม่มีประวัติ</div><div class="c-empty__desc">เมื่ออ่านนิยายจะปรากฏที่นี่</div></div>';
    } else {
      for (const e of recent) {
        const n = novels.find(x => x.slug === e.slug);
        const title = Ui.displayTitle(n) || e.slug;
        const dateStr = (e.ts && !isNaN(new Date(e.ts)))
          ? new Date(e.ts).toLocaleString('th-TH', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })
          : 'ไม่ระบุวันที่';
        html += '<a href="#novel/' + Ui.esc(e.slug) + '/' + Ui.esc(e.num) + '" class="c-list__item c-history-item" data-nav>' +
          '<div class="c-history-item__cover">' + Ui.coverHtml(n || { slug: e.slug, title }) + '</div>' +
          '<div class="c-list__info"><span class="c-list__title">' + Ui.esc(title) + '</span><span class="c-list__meta">ตอนที่ ' + Ui.esc(e.num) + ' · ' + Ui.esc(dateStr) + '</span></div>' +
          '<span class="c-list__action">อ่านต่อ ' + Ui.icon('arrow-right', 'xs') + '</span></a>';
      }
    }
    html += '</div></section></div>';
    page.innerHTML = html;
  }
};

// ── SETTINGS ─────────────────────────────────────────────────────────────
const SettingsPage = {
  render(params = {}) {
    const page = Ui.$('page-settings');
    if (!page) return;
    const settings = Store.getSettings();
    const fontSize = parseInt(settings.fontSize, 10) || 18;
    const lineHeight = parseFloat(settings.lineHeight) || 1.8;
    page.innerHTML = `<div class="c-container c-settings-page">
      <header class="c-page-heading">
        <p class="c-page-heading__eyebrow">เฉพาะอุปกรณ์นี้</p>
        <h1 class="c-page-heading__title">ตั้งค่าการอ่าน</h1>
        <p class="c-page-heading__subtitle">ปรับธีม ตัวอักษร และเครื่องมือที่ใช้บนเครื่องนี้</p>
      </header>
      <section class="c-settings-grid">
        <div class="c-settings-card">
          <div class="c-settings-card__title">${Ui.icon('moon', 'sm')}รูปลักษณ์</div>
          <div class="c-form__group">
            <label class="c-form__label" for="settings-theme">ธีมเริ่มต้น</label>
            <select class="c-form__select" id="settings-theme">
              <option value="sepia"${settings.theme === 'sepia' ? ' selected' : ''}>Sepia - อ่านสบาย</option>
              <option value="night"${settings.theme === 'night' ? ' selected' : ''}>Night - กลางคืน</option>
              <option value="paper"${settings.theme === 'paper' ? ' selected' : ''}>Paper - สว่าง</option>
              <option value="amoled"${settings.theme === 'amoled' ? ' selected' : ''}>AMOLED Black</option>
            </select>
          </div>
        </div>
        <div class="c-settings-card">
          <div class="c-settings-card__title">${Ui.icon('book', 'sm')}การอ่าน</div>
          <div class="c-form__group">
            <label class="c-form__label" for="settings-reader-lang">ภาษาที่ใช้ในหน้าอ่าน</label>
            <select class="c-form__select" id="settings-reader-lang">
              <option value="th"${settings.readerLang === 'th' ? ' selected' : ''}>ไทย - แปลแล้ว</option>
              <option value="cn"${settings.readerLang === 'cn' ? ' selected' : ''}>ต้นฉบับ</option>
            </select>
          </div>
          <div class="c-form__group">
            <span class="c-form__label">ขนาดตัวอักษร</span>
            <div class="c-settings-stepper">
              <button class="c-btn c-btn--ghost c-settings-font-btn" id="settings-font-sm" type="button" aria-label="ลดขนาดตัวอักษร"><span>A-</span></button>
              <span id="settings-font-label" class="c-settings-font-label">${fontSize}px</span>
              <button class="c-btn c-btn--ghost c-settings-font-btn" id="settings-font-lg" type="button" aria-label="เพิ่มขนาดตัวอักษร"><span>A+</span></button>
            </div>
          </div>
          <div class="c-form__group">
            <span class="c-form__label">ระยะบรรทัด</span>
            <div class="c-settings-stepper">
              <button class="c-btn c-btn--ghost c-settings-font-btn" id="settings-leading-tight" type="button" aria-label="ลดระยะบรรทัด"><span>-</span></button>
              <span id="settings-leading-label" class="c-settings-font-label">${lineHeight.toFixed(2)}</span>
              <button class="c-btn c-btn--ghost c-settings-font-btn" id="settings-leading-loose" type="button" aria-label="เพิ่มระยะบรรทัด"><span>+</span></button>
            </div>
          </div>
        </div>
        <div class="c-settings-card">
          <div class="c-settings-card__title">${Ui.icon('settings', 'sm')}เครื่องมือในเครื่อง</div>
          <div class="c-form__group">
            <label class="c-form__label" for="settings-editor-type">โปรแกรมแก้ไขไฟล์บทแปล</label>
            <select class="c-form__select" id="settings-editor-type">
              <option value="notepad"${settings.editorType === 'notepad' ? ' selected' : ''}>Notepad - มีทุกเครื่อง</option>
              <option value="vscode"${settings.editorType === 'vscode' ? ' selected' : ''}>VS Code - ถ้าติดตั้งไว้</option>
              <option value="system_default"${settings.editorType === 'system_default' ? ' selected' : ''}>System Default</option>
            </select>
          </div>
          <p class="c-form__help-text">การตั้งค่านี้เก็บ local เท่านั้น ใช้กับปุ่มแก้ไขจากหน้าอ่านและหน้าแอดมิน</p>
        </div>
        <div class="c-settings-card">
          <div class="c-settings-card__title">${Ui.icon('info', 'sm')}เกี่ยวกับระบบ</div>
          <div class="c-settings-about">
            <strong>NovelClaw</strong>
            <span>ระบบนำเข้า แปล และอ่านนิยายแบบ local-first</span>
            <span>Foundation Release: stable-novelctl-foundation-v1</span>
          </div>
        </div>
      </section>
    </div>`;

    // Font label fix — use the new ID
    const fontLabel = document.getElementById('settings-font-label');
    if (fontLabel) fontLabel.textContent = (parseInt(Store.getSettings().fontSize, 10) || 18) + 'px';

    const sel = document.getElementById('settings-theme');
    if (sel) {
      sel.addEventListener('change', () => { Store.setSetting('theme', sel.value); });
      Store.on('setting:theme', (t) => { sel.value = t; });
    }

    const langSel = document.getElementById('settings-reader-lang');
    if (langSel) {
      langSel.addEventListener('change', () => { Store.setSetting('readerLang', langSel.value); });
      Store.on('setting:readerLang', (l) => { langSel.value = l; });
    }

    const editorSel = document.getElementById('settings-editor-type');
    if (editorSel) {
      editorSel.addEventListener('change', () => { Store.setSetting('editorType', editorSel.value); });
      Store.on('setting:editorType', (e) => { editorSel.value = e; });
    }

    // Font size controls
    const savedFontSize = parseInt(Store.getSettings().fontSize, 10) || 18;
    let fontStep = Math.round((savedFontSize - 18) / 2);
    const applyFont = (step) => {
      const px = Math.max(14, Math.min(28, 18 + step * 2));
      document.documentElement.style.setProperty('--reader-font-size', `${px}px`);
      Store.setSetting('fontSize', px);
      const lbl = Ui.$('settings-font-label');
      if (lbl) lbl.textContent = `${px}px`;
    };
    applyFont(fontStep);
    document.getElementById('settings-font-sm')?.addEventListener('click', () => {
      fontStep = Math.max(-1, fontStep - 1);
      applyFont(fontStep);
    });
    document.getElementById('settings-font-lg')?.addEventListener('click', () => {
      fontStep = Math.min(2, fontStep + 1);
      applyFont(fontStep);
    });

    let leading = parseFloat(Store.getSettings().lineHeight) || 1.8;
    const applyLeading = (value) => {
      leading = Math.max(1.5, Math.min(2.1, value));
      document.documentElement.style.setProperty('--reader-line-height', String(leading));
      Store.setSetting('lineHeight', leading);
      const lbl = Ui.$('settings-leading-label');
      if (lbl) lbl.textContent = leading.toFixed(2);
    };
    applyLeading(leading);
    document.getElementById('settings-leading-tight')?.addEventListener('click', () => applyLeading(leading - 0.05));
    document.getElementById('settings-leading-loose')?.addEventListener('click', () => applyLeading(leading + 0.05));
  }
};
