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
      const filterBy = params.filter || settings.libraryFilter || 'all';
      const query = (params.q || '').trim().toLowerCase();
      const counts = {
        total: visibleNovels.length,
        ready: visibleNovels.filter(n => n.totalCount > n.translatedCount).length,
        active: visibleNovels.filter(n => n.translatedCount > 0 && n.translatedCount < n.totalCount).length,
        complete: visibleNovels.filter(n => n.totalCount > 0 && n.translatedCount >= n.totalCount).length,
        noCover: visibleNovels.filter(n => !n.coverImage).length,
      };
      const filtered = visibleNovels.filter(n => {
        if (filterBy === 'ready') return n.totalCount > n.translatedCount;
        if (filterBy === 'active') return n.translatedCount > 0 && n.translatedCount < n.totalCount;
        if (filterBy === 'complete') return n.totalCount > 0 && n.translatedCount >= n.totalCount;
        if (filterBy === 'no-cover') return !n.coverImage;
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
      const lastReadNovel = visibleNovels.find(n => n.lastRead) || visibleNovels[0];
      const resultHtml = sorted.length
        ? sorted.map(n => Ui.novelCard(n)).join('')
        : '<div class="c-empty c-empty--compact"><div class="c-empty__title">ไม่พบนิยายตามเงื่อนไข</div><div class="c-empty__desc">ลองเปลี่ยน filter หรือคำค้นหา</div></div>';
      let html = `<div class="c-container c-library-page">
        <section class="c-control-center c-library-cockpit">
          <div class="c-control-center__head">
            <div>
              <h2 class="c-control-center__title">${Ui.icon('library', 'sm')}Library</h2>
              <p class="c-control-center__subtitle">เลือกอ่านต่อ แปลต่อ หรือจัดการเรื่องที่ต้องดูแลจากหน้าเดียว</p>
            </div>
            <a href="${lastReadNovel ? '#novel/' + Ui.esc(lastReadNovel.slug) + (lastReadNovel.lastRead ? '/' + Ui.esc(lastReadNovel.lastRead) : '') : '#library'}" class="c-btn c-btn--primary" data-nav>${Ui.icon('book', 'xs')}<span>อ่านต่อ</span></a>
          </div>
          <div class="c-control-center__stats">
            ${Ui.stat('นิยาย', counts.total)}
            ${Ui.stat('พร้อมแปล', counts.ready, { tone: 'warn' })}
            ${Ui.stat('กำลังทำ', counts.active)}
            ${Ui.stat('แปลครบ', counts.complete, { tone: 'success' })}
          </div>
          <div class="c-control-center__actions">
            <a class="c-btn c-btn--secondary" href="#admin/import" data-nav>${Ui.icon('library', 'xs')}<span>Import Novel</span></a>
            <a class="c-btn c-btn--secondary" href="#admin/translate" data-nav>${Ui.icon('settings', 'xs')}<span>Translate Queue</span></a>
            <a class="c-btn c-btn--ghost" href="#admin/novels" data-nav>${Ui.icon('info', 'xs')}<span>Edit Library</span></a>
          </div>
        </section>
        <section class="c-section">
          <div class="c-library-toolbar">
            <div class="c-search c-library-toolbar__search">
              ${Ui.icon('search', 'sm')}
              <input type="search" id="library-search" class="c-search__input" value="${Ui.esc(params.q || '')}" placeholder="ค้นหาชื่อเรื่อง ผู้แต่ง หรือ slug" />
            </div>
            <select id="library-filter" class="c-library-sort" aria-label="กรองนิยาย">
              <option value="all"${filterBy === 'all' ? ' selected' : ''}>ทั้งหมด</option>
              <option value="ready"${filterBy === 'ready' ? ' selected' : ''}>พร้อมแปล</option>
              <option value="active"${filterBy === 'active' ? ' selected' : ''}>กำลังทำ</option>
              <option value="complete"${filterBy === 'complete' ? ' selected' : ''}>แปลครบ</option>
              <option value="no-cover"${filterBy === 'no-cover' ? ' selected' : ''}>ยังไม่มีปก (${counts.noCover})</option>
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
      <section class="c-control-center c-search-cockpit">
        <div class="c-control-center__head">
          <div>
            <h2 class="c-control-center__title">${Ui.icon('search', 'sm')}Search</h2>
            <p class="c-control-center__subtitle">ค้นหาเรื่องจากชื่อ ผู้แต่ง หรือ slug แล้วไปอ่าน/แปล/แก้ไขได้ทันที</p>
          </div>
          <a class="c-btn c-btn--secondary" href="#library" data-nav>${Ui.icon('library', 'xs')}<span>เปิดคลัง</span></a>
        </div>
      </section>
      <section class="c-section">
        <div class="c-search c-search-page__input-wrap">
          ${Ui.icon('search', 'sm')}
          <input type="search" id="search-input-field" placeholder="พิมพ์ชื่อ ภาษาไทย จีน อังกฤษ ผู้แต่ง หรือ slug..." class="c-search__input" autofocus />
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
        Ui.$('search-summary').textContent = '0 results';
        results.innerHTML = '<div class="c-empty c-empty--compact"><div class="c-empty__title">ไม่พบนิยาย</div><div class="c-empty__desc">ลองค้นด้วยชื่อเรื่อง ภาษาไทย จีน ผู้แต่ง หรือ slug เช่น global-descent</div></div>';
        return;
      }
      Ui.$('search-summary').textContent = filteredList.length + ' results';
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
      <section class="c-control-center c-history-cockpit">
        <div class="c-control-center__head">
          <div>
            <h2 class="c-control-center__title">${Ui.icon('book', 'sm')}Reading History</h2>
            <p class="c-control-center__subtitle">กลับไปยังตอนที่เคยอ่านล่าสุดแบบไม่ต้องไล่หาในคลัง</p>
          </div>
          <a class="c-btn c-btn--secondary" href="#library" data-nav>${Ui.icon('library', 'xs')}<span>เปิดคลัง</span></a>
        </div>
      </section>
      <section class="c-section"><div class="c-list c-history-list">`;
    if (recent.length === 0) {
      html += '<div class="c-empty c-empty--roomy"><svg class="c-empty__mascot"><use xlink:href="#mascot-crab-reading"/></svg><div class="c-empty__title">ยังไม่มีประวัติ</div><div class="c-empty__desc">เมื่ออ่านนิยายจะปรากฏที่นี่</div></div>';
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

// ── RANKING ──────────────────────────────────────────────────────────────
const RankingPage = {
  async render(params = {}) {
    const page = Ui.$('page-ranking');
    if (!page) return;
    try {
      const novels = (await Api.getNovels()).filter(Ui.isVisibleNovel).map(Ui.enrichNovel);
      if (!novels.length) {
        Ui.showEmpty(page.querySelector('.c-container') || page, 'ไม่มีข้อมูลอันดับ', 'เริ่มอ่านนิยายเพื่อสะสมสถิติ');
        return;
      }
      const sorted = [...novels].sort((a, b) => (b.translatedChapters || 0) - (a.translatedChapters || 0));
      let html = `<div class="c-container c-ranking-page">
        <section class="c-control-center c-ranking-cockpit">
          <div class="c-control-center__head">
            <div>
              <h2 class="c-control-center__title">${Ui.icon('ranking', 'sm')}Progress Ranking</h2>
              <p class="c-control-center__subtitle">ดูเรื่องที่คืบหน้ามากสุด และเปิดไปจัดการงานต่อได้ทันที</p>
            </div>
            <a class="c-btn c-btn--secondary" href="#admin/translate" data-nav>${Ui.icon('settings', 'xs')}<span>Translate Queue</span></a>
          </div>
        </section>
        <section class="c-section"><div class="c-popular c-ranking-list">`;
      for (let i = 0; i < Math.min(10, sorted.length); i++) {
        const n = sorted[i];
        const rankClass = 'c-popular__rank--' + (i + 1);
        html += '<a href="#novel/' + Ui.esc(n.slug) + '" class="c-popular__item c-ranking-item" data-nav>' +
          '<span class="c-popular__rank ' + rankClass + '">' + (i + 1) + '</span>' +
          '<div class="c-popular__cover">' + Ui.coverHtml(n) + '</div>' +
          '<div class="c-popular__info"><span class="c-popular__title">' + Ui.esc(Ui.displayTitle(n)) + '</span>' +
          '<span class="c-popular__meta">' + Ui.esc(n.source_lang || 'auto') + ' -> ' + Ui.esc(n.target_lang || 'th') + ' · ' + Ui.esc(n.author || 'ไม่ระบุ') + '</span>' +
          '<div class="c-card__progress c-ranking-item__progress"><span class="c-card__progress-bar"><span class="c-card__progress-fill ' + Ui.progressClass(n.translationPct) + '"></span></span><span class="c-card__progress-pct">' + Ui.esc(n.translationPct) + '%</span></div></div>' +
          '<span class="c-popular__views">' + (n.translatedChapters || 0) + '/' + (n.totalChapters || n.chapterCount || 0) + ' ตอน</span></a>';
      }
      html += '</div></section></div>';
      page.innerHTML = html;
    } catch (err) { Ui.showError(page, 'โหลดไม่สำเร็จ', err.message); }
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
      <section class="c-control-center c-settings-cockpit">
        <div class="c-control-center__head">
          <div>
            <h2 class="c-control-center__title">${Ui.icon('settings', 'sm')}Settings</h2>
            <p class="c-control-center__subtitle">ตั้งค่าเฉพาะเครื่องนี้สำหรับการอ่าน การแก้ไข และ workflow local-first</p>
          </div>
          <a class="c-btn c-btn--primary" href="#admin/provider" data-nav>${Ui.icon('settings', 'xs')}<span>AI Settings</span></a>
        </div>
        <div class="c-settings-summary">
          ${Ui.stat('Theme', settings.theme || 'sepia')}
          ${Ui.stat('Reader', (settings.readerLang || 'th').toUpperCase())}
          ${Ui.stat('Font', fontSize + 'px')}
          ${Ui.stat('Line', lineHeight.toFixed(2))}
        </div>
      </section>
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
          <div class="c-settings-card__title">${Ui.icon('book', 'sm')}Reader</div>
          <div class="c-form__group">
            <label class="c-form__label" for="settings-reader-lang">ภาษาใน Reader</label>
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
          <div class="c-settings-card__title">${Ui.icon('settings', 'sm')}Local tools</div>
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
          <div class="c-settings-card__title">${Ui.icon('info', 'sm')}About</div>
          <div class="c-settings-about">
            <strong>NovelClaw</strong>
            <span>Local-first novel import, translate, and reading cockpit.</span>
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

// ── PROFILE ──────────────────────────────────────────────────────────────
const ProfilePage = {
  render(params = {}) {
    const page = Ui.$('page-profile');
    if (!page) return;
    const prof = Store.getProfile();
    const GRADIENTS = [
      { name: 'Flame', value: 'linear-gradient(135deg,#f59e0b,#ef4444)' },
      { name: 'Neon', value: 'linear-gradient(135deg,#00f5d4,#38bdf8)' },
      { name: 'Forest', value: 'linear-gradient(135deg,#10b981,#059669)' },
      { name: 'Twilight', value: 'linear-gradient(135deg,#a78bfa,#ec4899)' },
      { name: 'Obsidian', value: 'linear-gradient(135deg,#64748b,#1e293b)' }
    ];

    let html = `<div class="c-container c-profile-page">
      <section class="c-control-center c-profile-cockpit">
        <div class="c-control-center__head">
          <div class="c-profile-card c-profile-card--flat">
            <div class="c-avatar c-profile-avatar u-avatar-gradient-${prof.avatarColorIndex || 0}">${Ui.esc(prof.name.charAt(0).toUpperCase())}</div>
            <div>
              <h2 class="c-control-center__title">Profile</h2>
              <div class="c-profile-summary__name">${Ui.esc(prof.name)}</div>
              <div class="c-profile-summary__meta">${Ui.esc(prof.email)} · ${Ui.esc(prof.role)}</div>
            </div>
          </div>
          <a class="c-btn c-btn--secondary" href="#settings" data-nav>${Ui.icon('settings', 'xs')}<span>Settings</span></a>
        </div>
      </section>
      <section class="c-settings-grid">
        <div class="c-settings-card c-profile-form">
          <div class="c-settings-card__title">${Ui.icon('info', 'sm')}ข้อมูลผู้ใช้ local</div>
          <div class="c-form">
            <div class="c-form__group"><label class="c-form__label" for="profile-name">ชื่อ</label><input class="c-form__input" id="profile-name" value="${Ui.esc(prof.name)}" /></div>
            <div class="c-form__group"><label class="c-form__label" for="profile-email">อีเมล</label><input class="c-form__input" id="profile-email" value="${Ui.esc(prof.email)}" /></div>
            <div class="c-form__group"><label class="c-form__label" for="profile-role">บทบาท</label><select class="c-form__select" id="profile-role"><option value="admin"${prof.role === 'admin' ? ' selected' : ''}>ผู้ดูแลระบบ</option><option value="paid"${prof.role === 'paid' ? ' selected' : ''}>สมาชิกพิเศษ</option><option value="user"${prof.role === 'user' ? ' selected' : ''}>สมาชิกทั่วไป</option><option value="bot"${prof.role === 'bot' ? ' selected' : ''}>บอท</option></select></div>
          </div>
        </div>
        <div class="c-settings-card">
          <div class="c-settings-card__title">${Ui.icon('moon', 'sm')}Avatar</div>
          <div class="c-form__group"><span class="c-form__label" id="profile-gradient-label">สี Avatar</span><div class="c-profile-gradient-row" role="group" aria-labelledby="profile-gradient-label">`;

    GRADIENTS.forEach((g, idx) => {
      html += '<button class="c-btn profile-gradient-btn u-avatar-gradient-' + idx + (idx === (prof.avatarColorIndex || 0) ? ' is-active' : '') + '" data-idx="' + idx + '" type="button" title="' + g.name + '" aria-label="เลือกสี Avatar ' + Ui.esc(g.name) + '"></button>';
    });

    html += '</div></div><button class="c-btn c-btn--primary c-btn--full" id="profile-save-btn" type="button">' + Ui.icon('settings', 'xs') + '<span>บันทึกโปรไฟล์</span></button></div></section></div>';
    page.innerHTML = html;

    document.getElementById('profile-save-btn')?.addEventListener('click', () => {
      const currentProf = Store.getProfile();
      const newProf = {
        name: Ui.$('profile-name')?.value || prof.name,
        email: Ui.$('profile-email')?.value || prof.email,
        role: Ui.$('profile-role')?.value || prof.role,
        avatarColorIndex: currentProf.avatarColorIndex
      };
      Store.saveProfile(newProf);
      Ui.updateAvatar();
      Ui.showToast('บันทึกโปรไฟล์แล้ว');
    });

    page.querySelectorAll('.profile-gradient-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.idx, 10);
        const prof2 = Store.getProfile();
        prof2.avatarColorIndex = idx;
        Store.saveProfile(prof2);
        Ui.updateAvatar();
        page.querySelectorAll('.profile-gradient-btn').forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
      });
    });
  }
};
