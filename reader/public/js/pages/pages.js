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
      const library = novels.filter(n => Store.getLastPosition(n.slug) !== null);
      if (library.length === 0) {
        Ui.showEmpty(page, 'หอสมุดว่างเปล่า', 'เริ่มอ่านนิยายกันเลย!');
        return;
      }
      let html = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title"><svg style="width:16px;height:16px;margin-right:6px;vertical-align:-2px;"><use xlink:href="#icon-library"/></svg>หอสมุด</h3><span style="font-size:11px;color:var(--c-text-muted);">' + library.length + ' เรื่อง</span></div><div class="c-card-grid">';
      for (const n of library) {
        const h = Ui.slugToHue(n.slug);
        const lr = Store.getLastPosition(n.slug);
        html += '<a href="#novel/' + n.slug + '" class="c-card" data-nav><div class="c-card__cover" style="background:linear-gradient(135deg,hsl(' + h + ',70%,40%),hsl(' + ((h + 40) % 360) + ',60%,30%));color:#000;">' + (n.title || n.slug).charAt(0) + '</div><div class="c-card__info"><span class="c-card__title">' + Ui.esc(n.title || n.slug) + '</span><span class="c-card__meta">อ่านล่าสุด: ตอนที่ ' + (lr || '—') + '</span><span style="font-size:10px;color:var(--c-accent);font-weight:600;">' + (n.chapterCount || 0) + ' ตอน</span></div></a>';
      }
      html += '</div></section></div>';
      page.innerHTML = html;
    } catch (err) { Ui.showError(page, 'โหลดไม่สำเร็จ', err.message); }
  }
};

// ── SEARCH ───────────────────────────────────────────────────────────────
const SearchPage = {
  async render(params) {
    const page = Ui.$('page-search');
    if (!page) return;
    page.innerHTML = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title"><svg style="width:16px;height:16px;margin-right:6px;vertical-align:-2px;"><use xlink:href="#icon-search"/></svg>ค้นหานิยาย</h3></div><div class="c-search"><input type="text" id="search-input-field" placeholder="พิมพ์ชื่อนิยาย ผู้แต่ง หรือคีย์เวิร์ด..." class="c-search__input" /><div class="c-search__tags"><span class="c-tag c-tag--active" data-genre="all">ทั้งหมด</span><span class="c-tag" data-genre="fantasy">แฟนตาซี</span><span class="c-tag" data-genre="action">แอคชัน</span><span class="c-tag" data-genre="sci-fi">ไซไฟ</span><span class="c-tag" data-genre="romance">โรแมนติก</span></div><div id="search-results"></div></div></section></div>';
    Ui.$('search-input-field')?.addEventListener('input', async (e) => {
      const q = e.target.value.trim().toLowerCase();
      const results = Ui.$('search-results');
      if (!results) return;
      if (q.length < 2) { results.innerHTML = ''; return; }
      try {
        const novels = await Api.getNovels();
        const filtered = novels.filter(n => (n.title || n.slug).toLowerCase().includes(q) || (n.author || '').toLowerCase().includes(q));
        if (filtered.length === 0) { results.innerHTML = '<p class="u-text-center u-text-muted u-p-lg">ไม่พบนิยายที่ค้นหา</p>'; return; }
        let html = '<div class="c-card-grid" style="margin-top:16px;">';
        for (const n of filtered) {
          const h = Ui.slugToHue(n.slug);
          html += '<a href="#novel/' + n.slug + '" class="c-card" data-nav><div class="c-card__cover" style="background:linear-gradient(135deg,hsl(' + h + ',70%,40%),hsl(' + ((h + 40) % 360) + ',60%,30%));color:#000;">' + (n.title || n.slug).charAt(0) + '</div><div class="c-card__info"><span class="c-card__title">' + Ui.esc(n.title || n.slug) + '</span><span class="c-card__meta">' + (n.author || '') + ' • ' + (n.chapterCount || 0) + ' ตอน</span></div></a>';
        }
        html += '</div>';
        results.innerHTML = html;
      } catch(_) { results.innerHTML = '<p class="u-text-center c-error__title">เกิดข้อผิดพลาด</p>'; }
    });
  }
};

// ── HISTORY ──────────────────────────────────────────────────────────────
const HistoryPage = {
  render(params) {
    const page = Ui.$('page-history');
    if (!page) return;
    const recent = Store.getHistory();
    let html = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title">ประวัติการอ่าน</h3></div><div class="c-list">';
    if (recent.length === 0) {
      html += '<p class="u-text-center c-empty__desc u-p-lg">ไม่มีประวัติการอ่าน</p>';
    } else {
      for (const e of recent) {
        const dateStr = (e.ts && !isNaN(new Date(e.ts)))
          ? new Date(e.ts).toLocaleString('th-TH', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })
          : 'ไม่ระบุวันที่';
        html += '<a href="#novel/' + e.slug + '/' + e.num + '" class="c-list__item" data-nav><div class="c-list__info"><span class="c-list__title">' + e.slug + ' — ตอนที่ ' + e.num + '</span><span class="c-list__meta">' + dateStr + '</span></div><span style="color:var(--c-accent);font-weight:600;font-size:12px;">อ่านต่อ →</span></a>';
      }
    }
    html += '</div></section></div>';
    page.innerHTML = html;
  }
};

// ── SETTINGS ─────────────────────────────────────────────────────────────
const SettingsPage = {
  render(params) {
    const page = Ui.$('page-settings');
    if (!page) return;
    const settings = Store.getSettings();
    page.innerHTML = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title">ตั้งค่า</h3></div><div class="c-settings-form"><div class="c-settings__group"><div class="c-form__group"><label class="c-form__label" for="settings-theme">ธีม</label><select class="c-form__select" id="settings-theme"><option value="dark"' + (settings.theme === 'dark' ? ' selected' : '') + '>มืด (Dark)</option><option value="light"' + (settings.theme === 'light' ? ' selected' : '') + '>สว่าง (Light)</option><option value="sepia"' + (settings.theme === 'sepia' ? ' selected' : '') + '>คลาสสิก (Sepia)</option><option value="amoled"' + (settings.theme === 'amoled' ? ' selected' : '') + '>AMOLED</option></select></div><div class="c-form__group"><label class="c-form__label">ขนาดตัวอักษร</label><div class="u-flex u-gap-sm" style="align-items:center;"><button class="c-btn c-btn--ghost" id="settings-font-sm" style="font-size:var(--text-lg);padding:8px 16px;">A−</button><span id="settings-font-label" style="font-size:var(--text-base);color:var(--c-text);min-width:40px;text-align:center;">15px</span><button class="c-btn c-btn--ghost" id="settings-font-lg" style="font-size:var(--text-lg);padding:8px 16px;">A+</button></div></div></div></div></section></div>';

    const sel = document.getElementById('settings-theme');
    if (sel) {
      sel.addEventListener('change', () => { Store.setSetting('theme', sel.value); });
      Store.on('setting:theme', (t) => { sel.value = t; });
    }

    let fontStep = 0;
    document.getElementById('settings-font-sm')?.addEventListener('click', () => {
      fontStep = Math.max(-2, fontStep - 1);
      const px = 15 + fontStep * 2;
      document.documentElement.style.setProperty('--text-base', px + 'px');
      const lbl = document.getElementById('settings-font-label');
      if (lbl) lbl.textContent = px + 'px';
    });
    document.getElementById('settings-font-lg')?.addEventListener('click', () => {
      fontStep = Math.min(3, fontStep + 1);
      const px = 15 + fontStep * 2;
      document.documentElement.style.setProperty('--text-base', px + 'px');
      const lbl = document.getElementById('settings-font-label');
      if (lbl) lbl.textContent = px + 'px';
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
