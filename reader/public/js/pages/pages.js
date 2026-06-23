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
  async render(params) {
    const page = Ui.$('page-library');
    if (!page) return;
    Ui.showSkeleton('page-library');
    try {
      const novels = await Api.getNovels();
      if (!novels.length) {
        Ui.showEmpty(page, 'หอสมุดว่างเปล่า', 'ยังไม่มีนิยายในระบบ เริ่มเพิ่มกันเลย!');
        return;
      }
      const sortBy = params.sort || Store.getSettings().librarySort || 'title';
      const sorted = [...novels].sort((a, b) => {
        if (sortBy === 'progress') return (b.translatedChapters || 0) - (a.translatedChapters || 0);
        if (sortBy === 'chapters') return (b.chapterCount || 0) - (a.chapterCount || 0);
        return (Ui.displayTitle(a) || '').localeCompare(Ui.displayTitle(b) || '');
      });
      let html = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title"><svg style="width:16px;height:16px;margin-right:6px;vertical-align:-2px;"><use xlink:href="#icon-library"/></svg>หอสมุด</h3><div class="u-flex u-gap-sm" style="align-items:center;"><span style="font-size:11px;color:var(--c-text-muted);">' + novels.length + ' เรื่อง</span><select id="library-sort" style="font-size:11px;background:var(--c-surface);border:1px solid var(--c-border);border-radius:var(--radius-sm);padding:4px 6px;color:var(--c-text-secondary);cursor:pointer;"><option value="title"' + (sortBy === 'title' ? ' selected' : '') + '>ชื่อ</option><option value="progress"' + (sortBy === 'progress' ? ' selected' : '') + '>ความคืบหน้า</option><option value="chapters"' + (sortBy === 'chapters' ? ' selected' : '') + '>ตอน</option></select></div></div><div class="c-card-grid">';
      for (const n of sorted) {
        const h = Ui.slugToHue(n.slug);
        const lr = Store.getLastPosition(n.slug);
        html += '<a href="#novel/' + n.slug + '" class="c-card" data-nav><div class="c-card__cover" style="background:linear-gradient(135deg,hsl(' + h + ',70%,40%),hsl(' + ((h + 40) % 360) + ',60%,30%));color:#000;">' + Ui.esc(Ui.displayTitle(n).charAt(0)) + '</div><div class="c-card__info"><span class="c-card__title">' + Ui.esc(Ui.displayTitle(n)) + '</span><span class="c-card__meta">' + (n.author || '') + ' • ' + (n.chapterCount || 0) + ' ตอน</span>' + (lr ? '<span style="font-size:10px;color:var(--c-accent);font-weight:600;">อ่านล่าสุด: ตอนที่ ' + lr + '</span>' : '') + '</div></a>';
      }
      html += '</div></section></div>';
      page.innerHTML = html;
      
      // Wire sort dropdown
      const sel = document.getElementById('library-sort');
      if (sel) {
        sel.addEventListener('change', () => {
          Store.setSetting('librarySort', sel.value);
          LibraryPage.render({ sort: sel.value });
        });
      }
    } catch (err) { Ui.showError(page, 'โหลดไม่สำเร็จ', err.message); }
  }
};

// ── SEARCH ───────────────────────────────────────────────────────────────
const SearchPage = {
  async render(params) {
    const page = Ui.$('page-search');
    if (!page) return;
    page.innerHTML = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title"><svg style="width:16px;height:16px;margin-right:6px;vertical-align:-2px;"><use xlink:href="#icon-search"/></svg>ค้นหานิยาย</h3></div><div class="c-search"><input type="text" id="search-input-field" placeholder="พิมพ์ชื่อ ภาษาไทย จีน อังกฤษ หรือ slug..." class="c-search__input" autofocus /><div id="search-results"></div></div></section></div>';
    Ui.$('search-input-field')?.addEventListener('input', async (e) => {
      const q = e.target.value.trim().toLowerCase();
      const results = Ui.$('search-results');
      if (!results) return;
      if (q.length < 2) { results.innerHTML = ''; return; }
      try {
        const novels = await Api.getNovels();
        const filtered = novels.filter(n =>
          (n.title || '').toLowerCase().includes(q) ||
          (n.translatedTitle || '').toLowerCase().includes(q) ||
          (n.slug || '').toLowerCase().includes(q) ||
          (n.author || '').toLowerCase().includes(q)
        );
        if (filtered.length === 0) {
          results.innerHTML = '<div class="c-empty" style="padding:32px 0;"><div class="c-empty__title">ไม่พบนิยาย</div><div class="c-empty__desc">ลองค้นด้วยชื่อเรื่อง ภาษาไทย จีน หรือ slug เช่น global-descent</div></div>';
          return;
        }
        let html = '<div class="c-card-grid" style="margin-top:16px;">';
        for (const n of filtered) {
          const h = Ui.slugToHue(n.slug);
          html += '<a href="#novel/' + n.slug + '" class="c-card" data-nav><div class="c-card__cover" style="background:linear-gradient(135deg,hsl(' + h + ',70%,40%),hsl(' + ((h + 40) % 360) + ',60%,30%));color:#000;">' + Ui.esc((n.title || n.slug).charAt(0)) + '</div><div class="c-card__info"><span class="c-card__title">' + Ui.esc(Ui.displayTitle(n)) + '</span><span class="c-card__meta">' + (n.author || '') + ' • ' + (n.chapterCount || 0) + ' ตอน</span></div></a>';
        }
        html += '</div>';
        results.innerHTML = html;
      } catch(_) { results.innerHTML = '<p class="u-text-center c-error__title">เกิดข้อผิดพลาด</p>'; }
    });
  }
};

// ── HISTORY ──────────────────────────────────────────────────────────────
const HistoryPage = {
  async render(params) {
    const page = Ui.$('page-history');
    if (!page) return;
    const recent = Store.getHistory();
    const novels = await Api.getNovels();
    let html = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title">ประวัติการอ่าน</h3></div><div class="c-list">';
    if (recent.length === 0) {
      html += '<div class="c-empty" style="padding:40px 0;"><svg class="c-empty__mascot"><use xlink:href="#mascot-crab-reading"/></svg><div class="c-empty__title">ยังไม่มีประวัติ</div><div class="c-empty__desc">เมื่ออ่านนิยายจะปรากฏที่นี่</div></div>';
    } else {
      for (const e of recent) {
        const n = novels.find(x => x.slug === e.slug);
        const title = Ui.displayTitle(n) || e.slug;
        const dateStr = (e.ts && !isNaN(new Date(e.ts)))
          ? new Date(e.ts).toLocaleString('th-TH', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })
          : 'ไม่ระบุวันที่';
        html += '<a href="#novel/' + e.slug + '/' + e.num + '" class="c-list__item" data-nav><div class="c-list__info"><span class="c-list__title">' + Ui.esc(title) + '</span><span class="c-list__meta">ตอนที่ ' + e.num + ' · ' + dateStr + '</span></div><span style="color:var(--c-accent);font-weight:600;font-size:12px;">อ่านต่อ →</span></a>';
      }
    }
    html += '</div></section></div>';
    page.innerHTML = html;
  }
};

// ── RANKING ──────────────────────────────────────────────────────────────
const RankingPage = {
  async render(params) {
    const page = Ui.$('page-ranking');
    if (!page) return;
    try {
      const novels = await Api.getNovels();
      if (!novels.length) {
        Ui.showEmpty(page.querySelector('.c-container') || page, 'ไม่มีข้อมูลอันดับ', 'เริ่มอ่านนิยายเพื่อสะสมสถิติ');
        return;
      }
      const sorted = [...novels].sort((a, b) => (b.translatedChapters || 0) - (a.translatedChapters || 0));
      let html = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title"><svg style="width:16px;height:16px;margin-right:6px;"><use xlink:href="#icon-ranking"/></svg>อันดับนิยาย</h3><span style="font-size:11px;color:var(--c-text-muted);">เรียงตามจำนวนตอนที่แปล</span></div><div class="c-popular">';
      for (let i = 0; i < Math.min(10, sorted.length); i++) {
        const n = sorted[i];
        const h = Ui.slugToHue(n.slug);
        const rankClass = 'c-popular__rank--' + (i + 1);
        html += '<a href="#novel/' + n.slug + '" class="c-popular__item" data-nav><span class="c-popular__rank ' + rankClass + '">' + (i + 1) + '</span><div class="c-popular__cover" style="background:linear-gradient(135deg,hsl(' + h + ',70%,40%),hsl(' + ((h + 40) % 360) + ',60%,30%));">' + (n.title ? n.title.charAt(0) : '?') + '</div><div class="c-popular__info"><span class="c-popular__title">' + Ui.displayTitle(n) + '</span><span class="c-popular__meta">' + (n.author || '') + '</span><span class="c-popular__views">' + (n.translatedChapters || 0) + '/' + (n.totalChapters || n.chapterCount || 0) + ' ตอนที่แปลแล้ว</span></div></a>';
      }
      html += '</div></section></div>';
      page.innerHTML = html;
    } catch (err) { Ui.showError(page, 'โหลดไม่สำเร็จ', err.message); }
  }
};

// ── SETTINGS ─────────────────────────────────────────────────────────────
const SettingsPage = {
  render(params) {
    const page = Ui.$('page-settings');
    if (!page) return;
    const settings = Store.getSettings();
    page.innerHTML = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title">ตั้งค่า</h3></div><div class="c-settings-form"><div class="c-settings__group"><div class="c-form__group"><label class="c-form__label" for="settings-theme">ธีม</label><select class="c-form__select" id="settings-theme"><option value="sepia"' + (settings.theme === 'sepia' ? ' selected' : '') + '>คลาสสิก (Sepia) ★</option><option value="night"' + (settings.theme === 'night' ? ' selected' : '') + '>กลางคืน (Night)</option><option value="paper"' + (settings.theme === 'paper' ? ' selected' : '') + '>สว่าง (Paper)</option><option value="amoled"' + (settings.theme === 'amoled' ? ' selected' : '') + '>AMOLED Black</option></select></div><div class="c-form__group"><label class="c-form__label">ขนาดตัวอักษร</label><div class="u-flex u-gap-sm" style="align-items:center;"><button class="c-btn c-btn--ghost" id="settings-font-sm" style="font-size:var(--text-lg);padding:8px 16px;">A−</button><span id="settings-font-label" style="font-size:var(--text-base);color:var(--c-text);min-width:40px;text-align:center;">18px</span><button class="c-btn c-btn--ghost" id="settings-font-lg" style="font-size:var(--text-lg);padding:8px 16px;">A+</button></div></div></div></div></section></div>';

    const sel = document.getElementById('settings-theme');
    if (sel) {
      sel.addEventListener('change', () => { Store.setSetting('theme', sel.value); });
      Store.on('setting:theme', (t) => { sel.value = t; });
    }

    // Font size controls (persisted)
    const savedFontSize = parseInt(Store.getSettings().fontSize, 10) || 18;
    let fontStep = Math.round((savedFontSize - 18) / 2);
    const BASE_FONT = 18;
    const applyFont = (step) => {
      const px = BASE_FONT + step * 2;
      document.documentElement.style.setProperty('--text-base', px + 'px');
      Store.setSetting('fontSize', px);
      const lbl = document.getElementById('settings-font-label');
      if (lbl) lbl.textContent = px + 'px';
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
  }
};

// ── PROFILE ──────────────────────────────────────────────────────────────
const ProfilePage = {
  render(params) {
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

    let html = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title">โปรไฟล์</h3></div><div class="c-profile-card"><div class="c-avatar" style="background:' + GRADIENTS[prof.avatarColorIndex || 0].value + ';width:48px;height:48px;font-size:var(--text-lg);">' + prof.name.charAt(0).toUpperCase() + '</div><div><div style="font-size:var(--text-lg);font-weight:var(--font-weight-bold);color:var(--c-text-primary);">' + Ui.esc(prof.name) + '</div><div style="font-size:var(--text-sm);color:var(--c-text-muted);">' + Ui.esc(prof.email) + ' • ' + Ui.esc(prof.role) + '</div></div></div></section>';

    html += '<section class="c-section"><div class="c-section__header"><h3 class="c-section__title">แก้ไขข้อมูลโปรไฟล์</h3></div><div class="c-profile-form"><div class="c-form"><div class="c-form__group"><label class="c-form__label">ชื่อ</label><input class="c-form__input" id="profile-name" value="' + Ui.esc(prof.name) + '" /></div><div class="c-form__group"><label class="c-form__label">อีเมล</label><input class="c-form__input" id="profile-email" value="' + Ui.esc(prof.email) + '" /></div><div class="c-form__group"><label class="c-form__label">บทบาท</label><select class="c-form__select" id="profile-role"><option value="admin"' + (prof.role === 'admin' ? ' selected' : '') + '>ผู้ดูแลระบบ</option><option value="paid"' + (prof.role === 'paid' ? ' selected' : '') + '>สมาชิกพิเศษ</option><option value="user"' + (prof.role === 'user' ? ' selected' : '') + '>สมาชิกทั่วไป</option><option value="bot"' + (prof.role === 'bot' ? ' selected' : '') + '>บอท</option></select></div><div class="c-form__group"><label class="c-form__label">Avatar Gradient</label><div class="u-flex u-gap-sm" style="flex-wrap:wrap;">';

    GRADIENTS.forEach((g, idx) => {
      html += '<button class="c-btn profile-gradient-btn" data-idx="' + idx + '" style="background:' + g.value + ';width:40px;height:40px;border-radius:50%;border:2px solid ' + (idx === (prof.avatarColorIndex || 0) ? 'var(--c-accent)' : 'transparent') + ';" title="' + g.name + '"></button>';
    });

    html += '</div></div><button class="c-btn c-btn--primary c-btn--full" id="profile-save-btn">บันทึกโปรไฟล์</button></div></div></section></div>';
    page.innerHTML = html;

    document.getElementById('profile-save-btn')?.addEventListener('click', () => {
      const newProf = {
        name: Ui.$('profile-name')?.value || prof.name,
        email: Ui.$('profile-email')?.value || prof.email,
        role: Ui.$('profile-role')?.value || prof.role,
        avatarColorIndex: prof.avatarColorIndex
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
        page.querySelectorAll('.profile-gradient-btn').forEach(b => b.style.borderColor = 'transparent');
        btn.style.borderColor = 'var(--c-accent)';
      });
    });
  }
};
