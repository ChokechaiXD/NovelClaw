/* ═══════════════════════════════════════════════════════════════════════
   admin.js — Admin Dashboard, Novels, Chapters, Glossary Pages
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

// ── Shared Admin Nav ─────────────────────────────────────────────────────
function renderAdminNav(active) {
  const links = [
    { name: 'dashboard', label: 'ภาพรวม', page: 'admin' },
    { name: 'jobs', label: 'งานแปล', page: 'admin/jobs' },
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
      const slug = params.slug || novels[0]?.slug;
      if (!slug) { page.innerHTML = '<div class="c-container">' + renderAdminNav('chapters') + '<p class="u-text-muted u-p-lg">ไม่มีนิยายในระบบ</p></div>'; return; }
      const chapters = await Api.getChapters(slug);
      if (!chapters || chapters.length === 0) {
        page.innerHTML = '<div class="c-container">' + renderAdminNav('chapters') + '<p class="u-text-muted u-p-lg">ไม่มีตอนในนิยายนี้</p></div>';
        return;
      }

      let filtered = [...chapters];
      let filterStatus = 'all';
      let searchQuery = '';
      let pageSize = 100;
      let currentPage = 0;

      const renderTable = () => {
        // Apply filters
        let list = [...chapters];
        if (filterStatus === 'translated') list = list.filter(c => c.status === 'translated');
        else if (filterStatus === 'source_only') list = list.filter(c => c.status === 'source_only');
        else if (filterStatus === 'read') list = list.filter(c => Store.isRead(slug, c.num));
        else if (filterStatus === 'unread') list = list.filter(c => !Store.isRead(slug, c.num));

        if (searchQuery) {
          const q = searchQuery.toLowerCase();
          list = list.filter(c =>
            c.num.toString().includes(q) ||
            (c.title && c.title.toLowerCase().includes(q))
          );
        }

        const totalFiltered = list.length;
        const maxPage = Math.ceil(totalFiltered / pageSize) - 1;
        if (currentPage > maxPage) currentPage = Math.max(0, maxPage);
        const start = currentPage * pageSize;
        const pageList = list.slice(start, start + pageSize);

        let html = '<div class="c-container">' + renderAdminNav('chapters') +
          '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">📖 ตอนทั้งหมด: ' + Ui.esc(slug) + '</h3><span style="font-size:var(--text-sm);color:var(--c-text-muted);">' + totalFiltered + ' / ' + chapters.length + ' ตอน</span></div>' +

          // ── Search + Filter Controls ──
          '<div class="c-form__row" style="display:flex;gap:var(--space-sm);margin-bottom:var(--space-md);flex-wrap:wrap;">' +
          '<input id="ch-filter-search" type="text" placeholder="ค้นหาเลขตอน หรือชื่อ..." class="c-form__input" style="flex:1;min-width:160px;" value="' + Ui.esc(searchQuery) + '" />' +
          '<select id="ch-filter-status" class="c-form__select" style="min-width:140px;">' +
          '<option value="all"' + (filterStatus === 'all' ? ' selected' : '') + '>ทั้งหมด</option>' +
          '<option value="translated"' + (filterStatus === 'translated' ? ' selected' : '') + '>✅ แปลแล้ว</option>' +
          '<option value="source_only"' + (filterStatus === 'source_only' ? ' selected' : '') + '>📄 ต้นฉบับ</option>' +
          '<option value="read"' + (filterStatus === 'read' ? ' selected' : '') + '>📖 อ่านแล้ว</option>' +
          '<option value="unread"' + (filterStatus === 'unread' ? ' selected' : '') + '>📕 ยังไม่อ่าน</option>' +
          '</select>' +
          '<input id="ch-jump-num" type="number" min="1" max="' + chapters.length + '" placeholder="ไปตอน..." class="c-form__input" style="width:100px;" />' +
          '<button id="ch-jump-btn" class="c-btn c-btn--sm">ไป</button>' +
          '</div>' +

          // ── Pagination ──
          '<div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:var(--space-sm);font-size:var(--text-sm);color:var(--c-text-muted);">' +
          '<button class="c-btn c-btn--xs" id="ch-page-prev"' + (currentPage <= 0 ? ' disabled' : '') + '>◀ ก่อนหน้า</button>' +
          '<span>หน้า ' + (currentPage + 1) + ' / ' + (maxPage + 1) + '</span>' +
          '<button class="c-btn c-btn--xs" id="ch-page-next"' + (currentPage >= maxPage ? ' disabled' : '') + '>ถัดไป ▶</button>' +
          '</div>' +

          // ── Table ──
          '<div class="c-table-wrap"><table class="c-table"><thead><tr><th>#</th><th>ชื่อตอน</th><th>สถานะ</th></tr></thead><tbody>';

        for (const ch of pageList) {
          const read = Store.isRead(slug, ch.num);
          const statusLabel = ch.status === 'translated' ? '✅ แปลแล้ว' : (ch.status === 'source_only' ? '📄 ต้นฉบับ' : '⬜');
          const statusClass = ch.status === 'translated' ? 'c-badge--teal' : (ch.status === 'source_only' ? 'c-badge--amber' : 'c-badge--gray');
          html += '<tr><td style="font-family:var(--font-mono);font-weight:600;">' + ch.num + '</td>' +
            '<td><a href="#novel/' + slug + '/' + ch.num + '" class="c-link" data-nav>' + Ui.esc(ch.title || '') + '</a></td>' +
            '<td><span class="c-badge ' + statusClass + '">' + statusLabel + '</span></td></tr>';
        }

        html += '</tbody></table></div></div>';
        page.innerHTML = html;

        // Bind filter events
        Ui.$('ch-filter-search').oninput = () => {
          searchQuery = Ui.$('ch-filter-search').value;
          currentPage = 0;
          renderTable();
        };
        Ui.$('ch-filter-status').onchange = () => {
          filterStatus = Ui.$('ch-filter-status').value;
          currentPage = 0;
          renderTable();
        };
        Ui.$('ch-page-prev').onclick = () => { if (currentPage > 0) { currentPage--; renderTable(); } };
        Ui.$('ch-page-next').onclick = () => { if (currentPage < maxPage) { currentPage++; renderTable(); } };
        Ui.$('ch-jump-btn').onclick = () => {
          const num = parseInt(Ui.$('ch-jump-num').value, 10);
          if (num) {
            window.location.hash = '#novel/' + slug + '/' + num;
          }
        };
        Ui.$('ch-jump-num').onkeydown = (e) => { if (e.key === 'Enter') Ui.$('ch-jump-btn').click(); };
      };

      renderTable();
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
        '<p class="u-text-muted u-mb-md">ดูคำศัพท์จาก glossary.json</p>';
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

// ── BOOKMARKS ────────────────────────────────────────────────────────────
const BookmarksPage = {
  async render(params) {
    const page = Ui.$('page-bookmarks');
    if (!page) return;
    try {
      const list = JSON.parse(localStorage.getItem('nc-bookmarks')) || [];
      if (list.length === 0) {
        Ui.showEmpty(page, 'ยังไม่มีบุ๊กมาร์ก', 'เมื่อบุ๊กมาร์กตอนที่ชอบจะปรากฏที่นี่');
        return;
      }
      const novels = await Api.getNovels();
      let html = '<div class="c-container"><section class="c-section"><div class="c-section__header"><h3 class="c-section__title">บุ๊กมาร์ก</h3></div><div class="c-list">';
      for (const b of list) {
        const n = novels.find(x => x.slug === b.novel);
        const title = Ui.displayTitle(n) || b.novel;
        html += '<a href="#novel/' + b.novel + '/' + b.num + '" class="c-list__item" data-nav><div class="c-list__info"><span class="c-list__title">' + Ui.esc(title) + '</span><span class="c-list__meta">ตอนที่ ' + b.num + '</span></div></a>';
      }
      html += '</div></section></div>';
      page.innerHTML = html;
    } catch(_) { Ui.showEmpty(page, 'เกิดข้อผิดพลาด', 'ไม่สามารถโหลดบุ๊กมาร์กได้'); }
  }
};

// ── ADMIN JOBS DASHBOARD ────────────────────────────────────────────────
const AdminJobsPage = {
  async render(params) {
    const page = Ui.$('page-admin-jobs');
    if (!page) return;
    Ui.showSkeleton('page-admin-jobs');
    try {
      const res = await fetch('/api/admin/jobs');
      const data = await res.json();

      // Helper: render a section (always show, even if empty)
      const makeSection = (title, items, icon, emptyText) => {
        const count = items ? items.length : 0;
        let html = '<div class="c-section" style="margin-top:var(--space-md);">' +
          '<div class="c-section__header"><h3 class="c-section__title">' + icon + ' ' + title + ' (' + count + ')</h3></div>';

        if (count === 0) {
          html += '<p class="u-text-muted u-p-md">' + Ui.esc(emptyText || 'ไม่มีรายการ') + '</p>';
        } else {
          html += '<div class="c-table-wrap"><table class="c-table"><thead><tr><th>ไฟล์</th><th>รายละเอียด</th><th>คำสั่ง</th><th></th></tr></thead><tbody>';
          for (const item of items) {
            const d = item.data || {};
            const ch = d.chapter || d.chapterNo || '';
            const reason = d.reason || d.error || d.state || '';
            const suggestion = d.suggestedCommand || '';
            const slug = d.slug || '';
            const createdAt = d.createdAt ? new Date(d.createdAt).toLocaleString('th-TH') : '';
            const fileId = 'cmd-' + Math.random().toString(36).slice(2, 7);

            html += '<tr>' +
              '<td style="font-family:var(--font-mono);font-size:12px;white-space:nowrap;">' + Ui.esc(item.file) + '</td>' +
              '<td>' +
                '<div style="font-weight:600;">ตอนที่ ' + Ui.esc(String(ch)) + '</div>' +
                (reason ? '<div style="font-size:11px;color:var(--c-text-muted);">' + Ui.esc(reason.slice(0, 100)) + '</div>' : '') +
                (createdAt ? '<div style="font-size:10px;color:var(--c-text-soft);">' + createdAt + '</div>' : '') +
              '</td>' +
              '<td>' +
                (suggestion ? '<code id="' + fileId + '" style="font-size:11px;white-space:pre-wrap;">' + Ui.esc(suggestion) + '</code>' : '') +
              '</td>' +
              '<td style="white-space:nowrap;">' +
                (suggestion ? '<button class="c-btn c-btn--xs" onclick="navigator.clipboard.writeText(document.getElementById(\'' + fileId + '\').textContent)">📋</button>' : '') +
                (slug && ch ? ' <a href="#admin/logs/' + Ui.esc(slug) + '/' + ch + '" class="c-btn c-btn--xs" data-nav>📂</a>' : '') +
              '</td>' +
            '</tr>';
          }
          html += '</tbody></table></div>';
        }
        html += '</div>';
        return html;
      };

      const jobsData = data || {};
      let html = '<div class="c-container">' +
        renderAdminNav('jobs') +
        '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">📋 คิวงานแปล</h3></div>';

      html += makeSection('กำลังทำงาน', jobsData.active, '🔄', 'ไม่มี job ที่กำลังรัน');
      html += makeSection('รอตรวจสอบ', jobsData.needsReview, '⚠️', 'ไม่มีตอนที่รอตรวจสอบ');
      html += makeSection('ล้มเหลว', jobsData.failed, '❌', 'ไม่มีตอนที่ล้มเหลว');
      html += makeSection('เสร็จแล้ว', jobsData.done, '✅', 'ไม่มี job ที่เสร็จ');

      html += '</div>';
      page.innerHTML = html;
    } catch (err) {
      Ui.showError(page, 'โหลดคิวงานไม่สำเร็จ', err.message);
    }
  }
};

// ── ADMIN LOGS VIEWER ────────────────────────────────────────────────────
const AdminLogsPage = {
  async render(params) {
    const page = Ui.$('page-admin-logs');
    if (!page) return;
    Ui.showSkeleton('page-admin-logs');
    try {
      const slug = params.slug;
      const num = params.num;
      if (!slug || !num) {
        page.innerHTML = '<div class="c-container"><p class="u-text-muted u-p-lg">ไม่ระบุ slug หรือตอน</p></div>';
        return;
      }
      const res = await fetch('/api/admin/logs/' + encodeURIComponent(slug) + '/' + num);
      const data = await res.json();
      let html = '<div class="c-container">' +
        renderAdminNav('logs') +
        '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">📂 Audit Log: ' + Ui.esc(slug) + ' / ตอน ' + Ui.esc(num) + '</h3>' +
        '<a href="#admin/jobs" class="c-btn c-btn--sm" data-nav style="margin-left:var(--space-sm);">← กลับ</a></div>';

      if (!data.ok || !data.files || data.files.length === 0) {
        html += '<p class="u-text-muted u-p-lg">' + Ui.esc(data.error || 'ไม่มี log สำหรับตอนนี้') + '</p>';
      } else {
        for (const file of data.files) {
          html += '<div class="c-section" style="margin-top:var(--space-md);">' +
            '<div class="c-section__header"><h3 class="c-section__title">' + Ui.esc(file.name) + '</h3></div>';
          if (file.isJson) {
            html += '<pre style="background:var(--c-surface);padding:var(--space-md);border-radius:var(--radius-sm);font-size:12px;overflow-x:auto;max-height:400px;"><code>' + Ui.esc(JSON.stringify(file.content, null, 2)) + '</code></pre>';
          } else {
            html += '<pre style="background:var(--c-surface);padding:var(--space-md);border-radius:var(--radius-sm);font-size:12px;overflow-x:auto;max-height:400px;"><code>' + Ui.esc(file.content) + '</code></pre>';
          }
          html += '</div>';
        }
      }
      html += '</div>';
      page.innerHTML = html;
    } catch (err) {
      Ui.showError(page, 'โหลด log ไม่สำเร็จ', err.message);
    }
  }
};
