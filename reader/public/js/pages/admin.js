/* ═══════════════════════════════════════════════════════════════════════
   admin.js — Admin Dashboard, Novels, Chapters, Glossary Pages
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

// ── Shared Admin Nav ─────────────────────────────────────────────────────
function renderAdminNav(active) {
  const links = [
    { name: 'dashboard', label: 'ภาพรวม', page: 'admin' },
    { name: 'novels', label: 'นิยาย', page: 'admin/novels' },
    { name: 'chapters', label: 'ตอน', page: 'admin/chapters' },
    { name: 'glossary', label: 'คำศัพท์', page: 'admin/glossary' },
  ];
  return '<div class="c-admin-nav">' + links.map(l =>
    '<a href="#' + l.page + '" class="c-admin-nav__link' + (l.name === active ? ' c-admin-nav__link--active' : '') + '" data-nav>' + l.label + '</a>'
  ).join('') + '</div>';
}

// ── ADMIN DASHBOARD ──────────────────────────────────────────────────────
const AdminDashboardPage = {
  async render(params) {
    const page = Ui.$('page-admin');
    if (!page) return;
    Ui.showSkeleton('page-admin');
    try {
      const novels = await Api.getNovels();
      const totalChapters = novels.reduce((a, n) => a + (n.chapterCount || 0), 0);
      const translatedChapters = novels.reduce((a, n) => a + (n.translatedChapters || 0), 0);
      const untranslated = totalChapters - translatedChapters;
      const statusCounts = { complete: 0, ongoing: 0 };
      for (const n of novels) { statusCounts[n.status] = (statusCounts[n.status] || 0) + 1; }

      page.innerHTML = '<div class="c-container">' + renderAdminNav('dashboard') +
        '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">ระบบหลังบ้าน</h3></div>' +
        '<div class="c-stats" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:var(--space-sm);margin-bottom:var(--space-lg);">' +
        '<div class="c-stat"><span class="c-stat__num">' + novels.length + '</span><span class="c-stat__label">นิยาย</span></div>' +
        '<div class="c-stat"><span class="c-stat__num">' + totalChapters + '</span><span class="c-stat__label">ตอนทั้งหมด</span></div>' +
        '<div class="c-stat"><span class="c-stat__num" style="color:var(--c-success);">' + translatedChapters + '</span><span class="c-stat__label">แปลแล้ว</span></div>' +
        '<div class="c-stat"><span class="c-stat__num" style="color:var(--c-warning);">' + untranslated + '</span><span class="c-stat__label">รอแปล</span></div>' +
        '</div>' +
        '<div class="c-section__header"><h3 class="c-section__title">จัดการระบบ</h3></div>' +
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:var(--space-sm);">' +
        '<a href="#admin/novels" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <span style="font-size:24px;">📚</span><div><div style="font-weight:600;color:var(--c-text-primary);">จัดการนิยาย</div><div style="font-size:12px;color:var(--c-text-muted);">' + Object.values(statusCounts).reduce((a,b)=>a+b,0) + ' เรื่อง</div></div></a>' +
        '<a href="#admin/chapters" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <span style="font-size:24px;">📖</span><div><div style="font-weight:600;color:var(--c-text-primary);">จัดการตอน</div><div style="font-size:12px;color:var(--c-text-muted);">' + untranslated + ' ตอนที่ยังไม่แปล</div></div></a>' +
        '<a href="#admin/glossary" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <span style="font-size:24px;">📝</span><div><div style="font-weight:600;color:var(--c-text-primary);">จัดการคำศัพท์</div><div style="font-size:12px;color:var(--c-text-muted);">Glossary / NPC names</div></div></a>' +
        '</div>' +
        '<div class="c-section__header" style="margin-top:var(--space-lg);"><h3 class="c-section__title">เครื่องมือ</h3></div>' +
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:var(--space-sm);">' +
        '<a href="#admin/novels" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <span style="font-size:24px;">➕</span><div><div style="font-weight:600;color:var(--c-text-primary);">นำเข้านิยาย</div><div style="font-size:12px;color:var(--c-text-muted);">เพิ่มเรื่องใหม่ / นำเข้าตอน</div></div></a>' +
        '<a href="#admin/chapters" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <span style="font-size:24px;">🔄</span><div><div style="font-weight:600;color:var(--c-text-primary);">คิวแปล AI</div><div style="font-size:12px;color:var(--c-text-muted);">จัดการ queue การแปล</div></div></a>' +
        '</div></div>';
    } catch (err) { Ui.showError(page, 'โหลดไม่สำเร็จ', err.message); }
  }
};

// ── ADMIN NOVELS ─────────────────────────────────────────────────────────
const AdminNovelsPage = {
  async render(params) {
    const page = Ui.$('page-admin-novels');
    if (!page) return;
    Ui.showSkeleton('page-admin-novels');
    try {
      const novels = await Api.getNovels();
      let html = '<div class="c-container">' + renderAdminNav('novels') +
        '<div class="c-table-wrap" style="margin-top:var(--space-md);"><table class="c-table"><thead><tr><th>Slug</th><th>ชื่อเรื่อง</th><th>ภาษา</th><th>ตอน</th><th>แปลแล้ว</th><th>สถานะ</th></tr></thead><tbody>';
      for (const n of novels) {
        const translated = n.translatedChapters || 0;
        const total = n.totalChapters || n.chapterCount || 0;
        const statusClass = n.status === 'complete' ? 'c-badge--purple' : n.status === 'ongoing' ? 'c-badge--teal' : 'c-badge--gray';
        html += '<tr><td style="font-weight:600;font-family:var(--font-mono);">' + Ui.esc(n.slug) + '</td><td>' + Ui.esc(n.title||'') + '</td><td>' + (n.source_lang||'cn').toUpperCase() + ' → ' + (n.target_lang||'th').toUpperCase() + '</td><td style="font-family:var(--font-mono);">' + total + '</td><td style="font-family:var(--font-mono);color:var(--c-accent);">' + translated + ' (' + Math.round(translated/total*100) + '%)</td><td><span class="c-badge ' + statusClass + '">' + Ui.esc(Ui.statusMap[n.status]||'ไม่ระบุ') + '</span></td></tr>';
      }
      html += '</tbody></table></div></div>';
      page.innerHTML = html;
    } catch (err) { Ui.showError(page, 'โหลดไม่สำเร็จ', err.message); }
  }
};

// ── ADMIN CHAPTERS ───────────────────────────────────────────────────────
const AdminChaptersPage = {
  async render(params) {
    const page = Ui.$('page-admin-chapters');
    if (!page) return;
    try {
      const novels = await Api.getNovels();
      const slug = novels[0]?.slug;
      if (!slug) { page.innerHTML = '<div class="c-container">' + renderAdminNav('chapters') + '<p class="u-text-muted u-p-lg">ไม่มีนิยายในระบบ</p></div>'; return; }
      const chapters = await Api.getChapters(slug);
      page.innerHTML = '<div class="c-container">' + renderAdminNav('chapters') +
        '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">ตอนทั้งหมด: ' + Ui.esc(slug) + '</h3><span style="font-size:var(--text-sm);color:var(--c-text-muted);">' + chapters.length + ' ตอน</span></div>' +
        '<div class="c-table-wrap"><table class="c-table"><thead><tr><th>#</th><th>ชื่อตอน</th><th>สถานะ</th></tr></thead><tbody>';
      for (const ch of chapters.slice(-100)) {
        const read = Store.isRead(slug, ch.num);
        html += '<tr><td style="font-family:var(--font-mono);">' + ch.num + '</td><td>' + Ui.esc(ch.title||'') + '</td><td>' + (read ? '<span class="c-badge c-badge--teal">อ่านแล้ว</span>' : '<span class="c-badge c-badge--gray">ยังไม่ได้อ่าน</span>') + '</td></tr>';
      }
      html += '</tbody></table></div></div>';
      page.innerHTML = html;
    } catch (err) { Ui.showError(page, 'โหลดไม่สำเร็จ', err.message); }
  }
};

// ── ADMIN GLOSSARY ───────────────────────────────────────────────────────
const AdminGlossaryPage = {
  async render(params) {
    const page = Ui.$('page-admin-glossary');
    if (!page) return;
    try {
      const res = await fetch('/api/novels');
      const novels = await res.json();
      const slug = novels[0]?.slug;
      let html = '<div class="c-container">' + renderAdminNav('glossary') +
        '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">คลังคำศัพท์</h3></div>' +
        '<p class="u-text-muted u-mb-md">ดูคำศัพท์จาก glossary.yml</p>';
      if (slug) {
        html += '<div class="c-table-wrap"><table class="c-table"><thead><tr><th>จีน</th><th>ไทย</th><th>ประเภท</th><th>ระดับ</th></tr></thead><tbody>';
        try {
          const glossRes = await fetch('/api/novel/' + slug + '/glossary/data');
          if (!glossRes.ok) {
            html += '<tr><td colspan="4" class="u-text-center u-text-muted">ไม่สามารถโหลดคำศัพท์ (API: ' + glossRes.status + ')</td></tr>';
          } else {
            const data = await glossRes.json();
            const terms = data.terms || data || [];
            if (terms.length === 0) {
            html += '<tr><td colspan="4" class="u-text-center u-text-muted">ไม่มีคำศัพท์</td></tr>';
          } else {
            for (const t of terms) {
              const lockClass = t.lock === 'locked' ? 'c-badge--teal' : t.lock === 'reference' ? 'c-badge--purple' : 'c-badge--gray';
              html += '<tr><td>' + Ui.esc(t.source||'') + '</td><td>' + Ui.esc(t.thai||'') + '</td><td>' + Ui.esc(t.category||'') + '</td><td><span class="c-badge ' + lockClass + '">' + Ui.esc(t.lock||'') + '</span></td></tr>';
            }
          }
        }
        } catch(_) { html += '<tr><td colspan="4" class="u-text-center u-text-muted">ไม่สามารถโหลดคำศัพท์ได้</td></tr>'; }
        html += '</tbody></table></div>';
      }
      html += '</div>';
      page.innerHTML = html;
    } catch (err) { 
      page.innerHTML = '<div class="c-container">' + renderAdminNav('glossary') + '<p class="u-text-center c-error__title">เกิดข้อผิดพลาด</p><p class="u-text-center u-text-muted">' + Ui.esc(err.message) + '</p></div>';
    }
  }
};

// ── ADMIN NOVEL EDIT ─────────────────────────────────────────────────────
const AdminNovelEditPage = {
  async render(params) {
    const page = Ui.$('page-admin-novel-edit');
    if (!page) return;
    const slug = params.slug;
    try {
      const novels = await Api.getNovels();
      const novel = novels.find(n => n.slug === slug);
      page.innerHTML = '<div class="c-container"><div class="c-section__header"><h3 class="c-section__title">แก้ไขนิยาย: ' + Ui.esc(slug||'') + '</h3></div><div class="c-settings-form"><div class="c-form"><div class="c-form__group"><label class="c-form__label">ชื่อเรื่อง</label><input class="c-form__input" id="edit-title" value="' + Ui.esc(novel?.title||'') + '" /></div><div class="c-form__group"><label class="c-form__label">ผู้แต่ง</label><input class="c-form__input" id="edit-author" value="' + Ui.esc(novel?.author||'') + '" /></div></div></div></div>';
    } catch(_) { Ui.showError(page, 'เกิดข้อผิดพลาด'); }
  }
};

// ── ADMIN TRANSLATE ──────────────────────────────────────────────────────
const AdminTranslatePage = {
  render(params) {
    const page = Ui.$('page-admin-translate');
    if (!page) return;
    page.innerHTML = '<div class="c-container"><p class="u-text-muted u-text-center u-p-lg">หน้ากำลังแปล (Translate) — กำลังพัฒนา</p></div>';
  }
};

const AdminTranslateJobPage = {
  render(params) {
    const page = Ui.$('page-admin-translate-job');
    if (!page) return;
    page.innerHTML = '<div class="c-container"><p class="u-text-muted u-text-center u-p-lg">งานแปล (Translate Job) — กำลังพัฒนา</p></div>';
  }
};

// ── ADMIN USERS ──────────────────────────────────────────────────────────
const AdminUsersPage = {
  async render(params) {
    const page = Ui.$('page-admin-users');
    if (!page) return;
    try {
      const res = await fetch('/api/admin/users');
      const users = res.ok ? await res.json() : [];
      let html = '<div class="c-container"><div class="c-section__header"><h3 class="c-section__title">ผู้ใช้</h3></div><div class="c-table-wrap"><table class="c-table"><thead><tr><th>ชื่อ</th><th>บทบาท</th></tr></thead><tbody>';
      if (users.length === 0) html += '<tr><td colspan="2" class="u-text-center u-text-muted">ไม่มีผู้ใช้</td></tr>';
      else for (const u of users) html += '<tr><td>' + Ui.esc(u.username||'') + '</td><td>' + Ui.esc(u.role||'') + '</td></tr>';
      html += '</tbody></table></div></div>';
      page.innerHTML = html;
    } catch(_) { page.innerHTML = '<div class="c-container"><p class="u-text-muted u-text-center u-p-lg">ไม่สามารถโหลดข้อมูลผู้ใช้</p></div>'; }
  }
};

// ── Other pages (dummies) ────────────────────────────────────────────────
const RankingPage = {
  render(params) {
    const page = Ui.$('page-ranking');
    if (!page) return;
    page.innerHTML = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title"><svg style="width:16px;height:16px;margin-right:6px;vertical-align:-2px;"><use xlink:href="#icon-ranking"/></svg>อันดับ</h3></div><p class="u-text-muted">หน้านี้กำลังพัฒนา</p></section></div>';
  }
};

const BookmarksPage = {
  render(params) {
    const page = Ui.$('page-bookmarks');
    if (!page) return;
    try {
      const list = JSON.parse(localStorage.getItem('nc-bookmarks')) || [];
      let html = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title">บุ๊กมาร์ก</h3></div><div class="c-list">';
      if (list.length === 0) html += '<p class="u-text-center u-text-muted u-p-lg">ไม่มีบุ๊กมาร์ก</p>';
      else for (const b of list) html += '<a href="#novel/' + b.novel + '/' + b.num + '" class="c-list__item" data-nav><div class="c-list__info"><span class="c-list__title">' + (b.novel||'') + ' — ตอนที่ ' + b.num + '</span></div></a>';
      html += '</div></section></div>';
      page.innerHTML = html;
    } catch(_) { page.innerHTML = '<div class="c-container"><p class="u-text-muted u-text-center u-p-lg">ไม่มีบุ๊กมาร์ก</p></div>'; }
  }
};
