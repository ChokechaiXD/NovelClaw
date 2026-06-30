/* ═══════════════════════════════════════════════════════════════════════
   admin.js — Admin Dashboard, Novels, Chapters, Glossary Pages
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */


const AdminUi = {
  consoleBadges: {
    running: ['กำลังทำงาน', 'c-badge c-badge--amber'],
    success: ['สำเร็จ', 'c-badge c-badge--teal'],
    error: ['ขัดข้อง', 'c-badge c-badge--red'],
    idle: ['พร้อมใช้งาน', 'c-badge c-badge--gray'],
  },

  setConsole(prefix, state, title, message) {
    const consoleCard = document.getElementById(`${prefix}-console-card`);
    const consoleTitle = document.getElementById(`${prefix}-console-title`);
    const consoleBadge = document.getElementById(`${prefix}-console-badge`);
    const consoleOutput = document.getElementById(`${prefix}-console-output`);
    const badge = this.consoleBadges[state] || this.consoleBadges.idle;

    if (consoleCard) consoleCard.hidden = false;
    if (consoleTitle) consoleTitle.textContent = title || '';
    if (consoleBadge) {
      consoleBadge.textContent = badge[0];
      consoleBadge.className = badge[1];
    }
    if (consoleOutput) {
      consoleOutput.textContent = message || '';
    }
  },

  setStatus(id, baseClass, message, type = 'success') {
    const statusEl = document.getElementById(id);
    if (!statusEl) return;
    statusEl.textContent = message || '';
    statusEl.className = `${baseClass} ${baseClass}--${type}`;
  },

  setButton(btn, icon, label) {
    if (!btn) return;
    btn.innerHTML = (icon ? Ui.icon(icon, 'xs') : '') + '<span>' + Ui.esc(label || '') + '</span>';
  },
};

function formatImportRepairSummary(slug, repair = {}) {
  const sample = (repair.changes || []).slice(0, 5).map(item => {
    const before = item.titleBefore || '(missing)';
    const after = item.titleAfter || '(unchanged)';
    return '  - ' + item.filename + ': ' + before + ' -> ' + after +
      (item.noiseLinesRemoved ? ' | noise -' + item.noiseLinesRemoved : '');
  });
  return [
    'slug: ' + slug,
    'source files changed: ' + (repair.filesChanged || 0),
    'titles repaired: ' + (repair.titlesRepaired || 0),
    'noise lines removed: ' + (repair.noiseLinesRemoved || 0),
    'titles unchanged: ' + (repair.titlesUnchanged || 0),
    'index rebuild: ' + (repair.indexRebuilt ? 'yes' : 'no'),
    sample.length ? 'sample:' : '',
    ...sample,
  ].filter(Boolean).join('\n');
}

function formatTocRecoverySummary(slug, data = {}) {
  const sample = (data.sampleChapters || []).slice(0, 8).map(item =>
    '  - ' + item.num + ': ' + (item.title || '(untitled)')
  );
  return [
    'slug: ' + slug,
    'site: ' + (data.site || 'auto'),
    'url: ' + (data.url || '-'),
    'title: ' + (data.title || '-'),
    'chapters found: ' + (data.chapterCount || 0),
    'toc path: ' + (data.tocPath || '-'),
    sample.length ? 'sample:' : '',
    ...sample,
  ].filter(Boolean).join('\n');
}

// ── ADMIN DASHBOARD
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

      page.innerHTML = '<div class="c-container">' + Ui.adminNav('dashboard') +
        '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">ระบบหลังบ้าน</h3></div>' +
        // ── Stats ──
        '<div class="c-stats">' +
        '<div class="c-stat"><span class="c-stat__num">' + novels.length + '</span><span class="c-stat__label">นิยาย</span></div>' +
        '<div class="c-stat"><span class="c-stat__num">' + totalChapters + '</span><span class="c-stat__label">ตอนทั้งหมด</span></div>' +
        '<div class="c-stat"><span class="c-stat__num c-stat__num--success">' + translatedChapters + '</span><span class="c-stat__label">แปลแล้ว</span></div>' +
        '<div class="c-stat"><span class="c-stat__num c-stat__num--warning">' + untranslated + '</span><span class="c-stat__label">รอแปล</span></div>' +
        '</div>' +
        // ── Health Summary ──
        '<div class="c-health-row">' +
        '<span class="c-badge c-badge--teal">ระบบปกติ</span>' +
        '<span class="c-badge' + (translatedChapters > 0 ? ' c-badge--teal' : ' c-badge--gray') + '">แปลแล้ว ' + translatedChapters + ' ตอน</span>' +
        '<span class="c-badge' + (untranslated > 0 ? ' c-badge--amber' : ' c-badge--gray') + '">รอแปล ' + untranslated + ' ตอน</span>' +
        '' +
        '</div>' +
        '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">จัดการระบบ</h3></div>' +
        '<div class="c-admin-dashboard__grid">' +
        '<a href="#admin/novels" class="c-card c-admin-dashboard__tile" data-nav>' +
        '  <svg class="c-admin-dashboard__tile-icon"><use xlink:href="#icon-library"/></svg><div><div class="c-admin-dashboard__tile-title">จัดการนิยาย</div><div class="c-admin-dashboard__tile-meta">' + Object.values(statusCounts).reduce((a,b)=>a+b,0) + ' เรื่อง</div></div></a>' +
        '<a href="#admin/chapters" class="c-card c-admin-dashboard__tile" data-nav>' +
        '  <svg class="c-admin-dashboard__tile-icon"><use xlink:href="#icon-book"/></svg><div><div class="c-admin-dashboard__tile-title">จัดการตอน</div><div class="c-admin-dashboard__tile-meta">' + untranslated + ' ตอนที่ยังไม่แปล</div></div></a>' +
        '<a href="#admin/glossary" class="c-card c-admin-dashboard__tile" data-nav>' +
        '  <svg class="c-admin-dashboard__tile-icon c-admin-dashboard__tile-icon--accent-2"><use xlink:href="#icon-bookmarks"/></svg><div><div class="c-admin-dashboard__tile-title">จัดการคำศัพท์</div><div class="c-admin-dashboard__tile-meta">Glossary / NPC names</div></div></a>' +
        '<a href="#admin/import" class="c-card c-admin-dashboard__tile" data-nav>' +
        '  <svg class="c-admin-dashboard__tile-icon"><use xlink:href="#icon-library"/></svg><div><div class="c-admin-dashboard__tile-title">นำเข้าต้นฉบับ</div><div class="c-admin-dashboard__tile-meta">URL / Paste → Source</div></div></a>' +
        '</div>' +
        '<div class="c-section__header c-admin-page__header c-admin-page__header--loose"><h3 class="c-section__title">เครื่องมือ</h3></div>' +
        '<div class="c-admin-dashboard__grid">' +
        '<a href="#admin/provider" class="c-card c-admin-dashboard__tile" data-nav>' +
        '  <svg class="c-admin-dashboard__tile-icon c-admin-dashboard__tile-icon--accent-2"><use xlink:href="#icon-settings"/></svg><div><div class="c-admin-dashboard__tile-title">จัดการระบบ AI</div><div class="c-admin-dashboard__tile-meta">Provider / Model / Config</div></div></a>' +
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
      const healthPayload = (await Api.getImportHealth().catch(() => ({ data: { novels: [] } }))).data || { novels: [] };
      const healthBySlug = {};
      for (const h of healthPayload.novels || []) healthBySlug[h.slug] = h;
      let query = '';
      let filter = 'all';
      let sortBy = 'title';

      const healthBadge = (status) => {
        if (status === 'error') return ['ต้องตรวจ', 'c-badge c-badge--red'];
        if (status === 'warn') return ['ควรดู', 'c-badge c-badge--amber'];
        return ['พร้อม', 'c-badge c-badge--teal'];
      };

      const renderRows = () => {
        let list = novels.map(n => ({ ...n, health: healthBySlug[n.slug] || null }));
        const q = query.trim().toLowerCase();
        if (q) {
          list = list.filter(n =>
            (n.slug || '').toLowerCase().includes(q) ||
            (n.title || '').toLowerCase().includes(q) ||
            (n.translatedTitle || '').toLowerCase().includes(q) ||
            (n.author || '').toLowerCase().includes(q)
          );
        }
        if (filter === 'source') list = list.filter(n => (n.health?.sourceFileCount || 0) > 0);
        else if (filter === 'warn') list = list.filter(n => n.health && n.health.status !== 'ok');
        else if (filter === 'translated') list = list.filter(n => (n.translatedChapters || 0) > 0);
        else if (filter === 'empty-cover') list = list.filter(n => !n.coverImage);

        list.sort((a, b) => {
          if (sortBy === 'chapters') return (b.totalChapters || b.chapterCount || 0) - (a.totalChapters || a.chapterCount || 0);
          if (sortBy === 'progress') return (b.translatedChapters || 0) - (a.translatedChapters || 0);
          if (sortBy === 'health') return (a.health?.status || 'ok').localeCompare(b.health?.status || 'ok');
          return Ui.displayTitle(a).localeCompare(Ui.displayTitle(b));
        });

        const rows = list.map(n => {
          const translated = n.translatedChapters || 0;
          const total = n.totalChapters || n.chapterCount || 0;
          const pct = total > 0 ? Math.round((translated / total) * 100) : 0;
          const statusClass = n.status === 'complete' ? 'c-badge--purple' : n.status === 'ongoing' ? 'c-badge--teal' : 'c-badge--gray';
          const [healthText, healthClass] = healthBadge(n.health?.status || 'ok');
          const sourceMeta = n.health ? `${n.health.sourceFileCount || 0} source` : 'no scan';
          return '<tr>' +
            '<td><div class="c-admin-novel-cell"><div class="c-admin-novel-cover">' + Ui.coverHtml(n) + '</div><div><strong>' + Ui.esc(Ui.displayTitle(n)) + '</strong><div class="u-text-muted">' + Ui.esc(n.slug) + '</div></div></div></td>' +
            '<td>' + Ui.esc(n.author || '-') + '</td>' +
            '<td>' + Ui.esc((n.source_lang || 'cn').toUpperCase()) + ' → ' + Ui.esc((n.target_lang || 'th').toUpperCase()) + '<div class="u-text-muted">' + Ui.esc(n.health?.sourceSite || '') + '</div></td>' +
            '<td class="c-admin-table__mono">' + total + '<div class="u-text-muted">' + sourceMeta + '</div></td>' +
            '<td class="c-admin-table__mono-accent">' + translated + ' (' + pct + '%)</td>' +
            '<td><span class="c-badge ' + statusClass + '">' + Ui.esc(Ui.statusMap[n.status] || 'ไม่ระบุ') + '</span><div class="c-admin-novels__health"><span class="' + healthClass + '">' + healthText + '</span></div></td>' +
            '<td class="c-admin-table__actions-cell"><div class="c-admin-novels__actions">' +
            '<a class="c-btn c-btn--xs c-btn--ghost" href="#novel/' + Ui.esc(n.slug) + '" data-nav>' + Ui.icon('book', 'xs') + '<span>อ่าน</span></a>' +
            '<a class="c-btn c-btn--xs c-btn--secondary" href="#admin/novel-edit/' + Ui.esc(n.slug) + '" data-nav>' + Ui.icon('settings', 'xs') + '<span>แก้</span></a>' +
            '<button class="c-btn c-btn--xs c-btn--secondary repair-novel-btn" data-slug="' + Ui.esc(n.slug) + '" type="button">' + Ui.icon('settings', 'xs') + '<span>ซ่อม</span></button>' +
            '<button class="c-btn c-btn--danger c-btn--xs c-admin-novels__delete-btn delete-novel-btn" data-slug="' + Ui.esc(n.slug) + '" type="button">' + Ui.icon('close', 'xs') + '<span>ลบ</span></button>' +
            '</div></td>' +
            '</tr>';
        }).join('');

        const countEl = document.getElementById('admin-novel-count');
        if (countEl) countEl.textContent = list.length + ' / ' + novels.length + ' เรื่อง';
        const tbody = document.getElementById('admin-novels-tbody');
        if (tbody) tbody.innerHTML = rows || '<tr><td colspan="7" class="u-text-muted">ไม่พบนิยายตามเงื่อนไข</td></tr>';
        bindRowActions();
      };

      const bindRowActions = () => {
        page.querySelectorAll('.repair-novel-btn').forEach(btn => {
          btn.onclick = async () => {
            const slug = btn.dataset.slug;
            if (!slug) return;
            btn.disabled = true;
            AdminUi.setButton(btn, 'search', 'Checking...');
            try {
              const preview = await Api.repairImport(slug, 'all', { dryRun: true });
              const previewRepair = preview.data?.repair || {};
              const summary = formatImportRepairSummary(slug, previewRepair);
              if (!confirm('Repair preview\n\n' + summary + '\n\nApply these changes?')) {
                btn.disabled = false;
                AdminUi.setButton(btn, 'settings', 'ซ่อม');
                return;
              }
              AdminUi.setButton(btn, 'settings', 'Repairing...');
              const result = await Api.repairImport(slug, 'all');
              const repair = result.data?.repair || {};
              Ui.showToast('ซ่อมแล้ว: title ' + (repair.titlesRepaired || 0) + ', index rebuilt');
              AdminUi.setButton(btn, 'settings', 'Done');
              setTimeout(() => AdminNovelsPage.render(params), 900);
            } catch (err) {
              Ui.showToast('ซ่อมไม่สำเร็จ: ' + err.message, 'error');
              btn.disabled = false;
              AdminUi.setButton(btn, 'settings', 'ซ่อม');
            }
          };
        });
        page.querySelectorAll('.delete-novel-btn').forEach(btn => {
          btn.onclick = async () => {
            const slug = btn.dataset.slug;
          if (!slug) return;
          if (confirm('⚠️ คำเตือน: คุณต้องการลบนิยาย "' + slug + '" ใช่หรือไม่?\nการลบนี้จะทำลายโฟลเดอร์นิยาย บทแปล และศัพท์เฉพาะทั้งหมดอย่างถาวรและไม่สามารถเรียกคืนได้!')) {
            try {
              btn.disabled = true;
              AdminUi.setButton(btn, 'close', 'กำลังลบ...');
              await Api.deleteNovel(slug);
              Ui.showToast('ลบนิยาย "' + slug + '" เรียบร้อยแล้วค่ะ');
              // Reload page to refresh table
              await AdminNovelsPage.render(params);
            } catch (err) {
              Ui.showToast('ลบไม่สำเร็จ: ' + err.message, 'error');
              btn.disabled = false;
              AdminUi.setButton(btn, 'close', 'ลบ');
            }
          }
          };
        });
      };

      page.innerHTML = '<div class="c-container">' + Ui.adminNav('novels') +
        '<div class="c-admin-page__toolbar"><h3 class="c-admin-page__title">รายการนิยายทั้งหมด</h3><span id="admin-novel-count" class="c-admin-page__meta"></span></div>' +
        '<div class="c-admin-novels__filters">' +
        '<input id="admin-novel-search" class="c-form__input c-admin-novels__search" placeholder="ค้นหา title, slug, author..." />' +
        '<select id="admin-novel-filter" class="c-form__select c-admin-novels__select"><option value="all">ทั้งหมด</option><option value="source">มี source</option><option value="warn">ต้องตรวจ</option><option value="translated">มีแปลแล้ว</option><option value="empty-cover">ยังไม่มีปก</option></select>' +
        '<select id="admin-novel-sort" class="c-form__select c-admin-novels__select"><option value="title">เรียงตามชื่อ</option><option value="chapters">ตอนมากสุด</option><option value="progress">แปลมากสุด</option><option value="health">health</option></select>' +
        '</div>' +
        '<div class="c-table-wrap c-admin-table-wrap"><table class="c-table"><thead><tr><th>นิยาย</th><th>ผู้แต่ง</th><th>ภาษา</th><th>ตอน</th><th>แปลแล้ว</th><th>สถานะ</th><th class="c-admin-novels__actions-col">การจัดการ</th></tr></thead><tbody id="admin-novels-tbody"></tbody></table></div></div>';

      document.getElementById('admin-novel-search')?.addEventListener('input', (event) => {
        query = event.target.value || '';
        renderRows();
      });
      document.getElementById('admin-novel-filter')?.addEventListener('change', (event) => {
        filter = event.target.value || 'all';
        renderRows();
      });
      document.getElementById('admin-novel-sort')?.addEventListener('change', (event) => {
        sortBy = event.target.value || 'title';
        renderRows();
      });
      renderRows();
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
      const firstReal = novels.find(Ui.isVisibleNovel);
      const slug = params.slug || firstReal?.slug || novels[0]?.slug;
      if (!slug) { page.innerHTML = '<div class="c-container">' + Ui.adminNav('chapters') + '<p class="u-text-muted u-p-lg">ไม่มีนิยายในระบบ</p></div>'; return; }
      const [chapters, importHealthResp] = await Promise.all([
        Api.getChapters(slug),
        Api.getImportHealth(slug, { includeChapters: true }).catch(() => ({ data: { chapters: [] } })),
      ]);
      if (!chapters || chapters.length === 0) {
        page.innerHTML = '<div class="c-container">' + Ui.adminNav('chapters') + '<p class="u-text-muted u-p-lg">ไม่มีตอนในนิยายนี้</p></div>';
        return;
      }

      const importHealth = importHealthResp.data || {};
      const sourceIssueByNum = {};
      for (const item of importHealth.chapters || []) sourceIssueByNum[item.num] = item;
      const blockingNums = new Set(importHealth.blockingSourceNums || []);
      const selectedNums = new Set();
      let filterStatus = 'all';
      let searchQuery = '';
      let pageSize = 100;
      let currentPage = 0;

      const selectedRange = () => [...selectedNums].sort((a, b) => a - b).join(',');
      const issueBadgeHtml = (ch) => {
        const issue = sourceIssueByNum[ch.num];
        if (!issue) return '<span class="c-badge c-badge--teal">source ok</span>';
        const hasError = (issue.issues || []).some(item => item.severity === 'error');
        const codes = (issue.issues || []).map(item => item.code).slice(0, 2).join(', ');
        return '<span class="c-badge ' + (hasError ? 'c-badge--red' : 'c-badge--amber') + '">' + Ui.esc(codes || 'source issue') + '</span>';
      };

      const renderTable = (opts = {}) => {
        // Apply filters
        let list = [...chapters];
        if (filterStatus === 'translated') list = list.filter(c => c.status === 'translated');
        else if (filterStatus === 'source_only') list = list.filter(c => c.status === 'source_only');
        else if (filterStatus === 'source_dirty') list = list.filter(c => sourceIssueByNum[c.num]);
        else if (filterStatus === 'source_error') list = list.filter(c => blockingNums.has(c.num));
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
        const maxPage = Math.max(0, Math.ceil(totalFiltered / pageSize) - 1);
        if (currentPage > maxPage) currentPage = Math.max(0, maxPage);
        const start = currentPage * pageSize;
        const pageList = list.slice(start, start + pageSize);

        let html = '<div class="c-container">' + Ui.adminNav('chapters') +
          '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">📖 ตอนทั้งหมด: ' + Ui.esc(slug) + '</h3><span class="c-admin-page__meta">' + totalFiltered + ' / ' + chapters.length + ' ตอน</span></div>' +
          '<div class="c-admin-chapters__summary">' +
          Ui.stat('แปลแล้ว', chapters.filter(c => c.status === 'translated').length, { tone: 'success' }) +
          Ui.stat('ต้นฉบับ', chapters.filter(c => c.status === 'source_only').length, { tone: 'warn' }) +
          Ui.stat('source error', importHealth.blockingSourceCount || 0, { tone: importHealth.blockingSourceCount ? 'warn' : 'success' }) +
          Ui.stat('เลือกไว้', selectedNums.size, { tone: 'accent' }) +
          '</div>' +

          // ── Search + Filter Controls ──
          '<div class="c-admin-chapters__filters">' +
          '<input id="ch-filter-search" type="text" placeholder="ค้นหาเลขตอน หรือชื่อ..." class="c-form__input c-admin-chapters__search" value="' + Ui.esc(searchQuery) + '" />' +
          '<select id="ch-filter-status" class="c-form__select c-admin-chapters__status-filter">' +
          '<option value="all"' + (filterStatus === 'all' ? ' selected' : '') + '>ทั้งหมด</option>' +
          '<option value="translated"' + (filterStatus === 'translated' ? ' selected' : '') + '>แปลแล้ว</option>' +
          '<option value="source_only"' + (filterStatus === 'source_only' ? ' selected' : '') + '>📄 ต้นฉบับ</option>' +
          '<option value="source_error"' + (filterStatus === 'source_error' ? ' selected' : '') + '>⛔ source error</option>' +
          '<option value="source_dirty"' + (filterStatus === 'source_dirty' ? ' selected' : '') + '>⚠️ source issue</option>' +
          '<option value="read"' + (filterStatus === 'read' ? ' selected' : '') + '>📖 อ่านแล้ว</option>' +
          '<option value="unread"' + (filterStatus === 'unread' ? ' selected' : '') + '>📕 ยังไม่อ่าน</option>' +
          '</select>' +
          '<input id="ch-jump-num" type="number" min="1" max="' + chapters.length + '" placeholder="ไปตอน..." class="c-form__input c-admin-chapters__jump-input" />' +
          '<button id="ch-jump-btn" class="c-btn c-btn--sm" type="button">' + Ui.icon('search', 'xs') + '<span>ไป</span></button>' +
          '</div>' +

          '<div class="c-admin-chapters__bulk">' +
          '<button class="c-btn c-btn--xs c-btn--secondary" id="ch-select-visible" type="button">' + Ui.icon('bookmarks', 'xs') + '<span>เลือกหน้านี้</span></button>' +
          '<button class="c-btn c-btn--xs c-btn--ghost" id="ch-clear-selected" type="button">' + Ui.icon('close', 'xs') + '<span>ล้างเลือก</span></button>' +
          '<button class="c-btn c-btn--xs c-btn--primary" id="ch-translate-selected" type="button"' + (selectedNums.size ? '' : ' disabled') + '>' + Ui.icon('book', 'xs') + '<span>แปลที่เลือก</span></button>' +
          '<button class="c-btn c-btn--xs c-btn--secondary" id="ch-reimport-selected" type="button"' + (selectedNums.size ? '' : ' disabled') + '>' + Ui.icon('library', 'xs') + '<span>นำเข้าใหม่</span></button>' +
          '<button class="c-btn c-btn--xs c-btn--ghost" id="ch-inspect-first" type="button"' + (selectedNums.size ? '' : ' disabled') + '>' + Ui.icon('search', 'xs') + '<span>ตรวจตอนแรก</span></button>' +
          '<span class="c-admin-chapters__selected-range">' + Ui.esc(selectedRange() || 'ยังไม่ได้เลือกตอน') + '</span>' +
          '</div>' +

          // ── Pagination ──
          '<div class="c-admin-chapters__pagination">' +
          '<button class="c-btn c-btn--xs" id="ch-page-prev" type="button"' + (currentPage <= 0 ? ' disabled' : '') + '>' + Ui.icon('arrow-left', 'xs') + '<span>ก่อนหน้า</span></button>' +
          '<span>หน้า ' + (currentPage + 1) + ' / ' + (maxPage + 1) + '</span>' +
          '<button class="c-btn c-btn--xs" id="ch-page-next" type="button"' + (currentPage >= maxPage ? ' disabled' : '') + '><span>ถัดไป</span>' + Ui.icon('arrow-right', 'xs') + '</button>' +
          '</div>' +

          // ── Table ──
          '<div class="c-table-wrap"><table class="c-table"><thead><tr><th><span class="u-sr-only">เลือก</span></th><th>#</th><th>ชื่อตอน</th><th>แปล</th><th>source</th><th>คำสั่ง</th></tr></thead><tbody>';

        for (const ch of pageList) {
          const statusLabel = ch.status === 'translated' ? 'แปลแล้ว' : (ch.status === 'source_only' ? 'ต้นฉบับ' : 'รอจัดการ');
          const statusClass = ch.status === 'translated' ? 'c-badge--teal' : (ch.status === 'source_only' ? 'c-badge--amber' : 'c-badge--gray');
          html += '<tr><td><input class="ch-row-check" type="checkbox" data-num="' + Ui.esc(ch.num) + '"' + (selectedNums.has(ch.num) ? ' checked' : '') + '></td>' +
            '<td class="c-admin-table__mono-strong">' + ch.num + '</td>' +
            '<td><a href="#novel/' + Ui.esc(slug) + '/' + Ui.esc(ch.num) + '" class="c-link" data-nav>' + Ui.esc(ch.title || '') + '</a></td>' +
            '<td><span class="c-badge ' + statusClass + '">' + statusLabel + '</span></td>' +
            '<td>' + issueBadgeHtml(ch) + '</td>' +
            '<td><div class="c-admin-chapters__row-actions">' +
            '<button class="c-btn c-btn--xs c-btn--ghost ch-inspect-one" data-num="' + Ui.esc(ch.num) + '" type="button">' + Ui.icon('search', 'xs') + '<span>ตรวจ</span></button>' +
            '<button class="c-btn c-btn--xs c-btn--secondary ch-translate-one" data-num="' + Ui.esc(ch.num) + '" type="button">' + Ui.icon('book', 'xs') + '<span>แปล</span></button>' +
            '</div></td></tr>';
        }

        html += '</tbody></table></div></div>';
        page.innerHTML = html;

        // Bind filter events
        Ui.$('ch-filter-search').oninput = () => {
          const input = Ui.$('ch-filter-search');
          searchQuery = input.value;
          currentPage = 0;
          renderTable({ focusSearch: true, cursor: input.selectionStart });
        };
        Ui.$('ch-filter-status').onchange = () => {
          filterStatus = Ui.$('ch-filter-status').value;
          currentPage = 0;
          renderTable();
        };
        Ui.$('ch-page-prev').onclick = () => { if (currentPage > 0) { currentPage--; renderTable(); } };
        Ui.$('ch-page-next').onclick = () => { if (currentPage < maxPage) { currentPage++; renderTable(); } };
        page.querySelectorAll('.ch-row-check').forEach(input => {
          input.onchange = () => {
            const num = parseInt(input.dataset.num, 10);
            if (!Number.isNaN(num)) {
              if (input.checked) selectedNums.add(num);
              else selectedNums.delete(num);
              renderTable();
            }
          };
        });
        Ui.$('ch-select-visible').onclick = () => {
          for (const ch of pageList) selectedNums.add(ch.num);
          renderTable();
        };
        Ui.$('ch-clear-selected').onclick = () => {
          selectedNums.clear();
          renderTable();
        };
        Ui.$('ch-reimport-selected').onclick = () => {
          const range = selectedRange();
          if (range) window.location.hash = '#admin/import/' + encodeURIComponent(slug) + '/' + encodeURIComponent(range);
        };
        Ui.$('ch-inspect-first').onclick = () => {
          const first = [...selectedNums].sort((a, b) => a - b)[0];
          if (first) window.location.hash = '#admin/import/' + encodeURIComponent(slug) + '/' + encodeURIComponent(first);
        };
        Ui.$('ch-translate-selected').onclick = async () => {
          const range = selectedRange();
          if (!range) return;
          if (!confirm('เริ่มแปลตอนที่เลือก?\n\n' + range)) return;
          try {
            await Api.translateBatch(slug, range, 1);
            Api.invalidateAll(slug);
            Ui.showToast('ส่งงานแปลแล้ว');
            selectedNums.clear();
            await AdminChaptersPage.render({ slug });
          } catch (err) {
            Ui.showToast(err.message, 'error');
          }
        };
        page.querySelectorAll('.ch-inspect-one').forEach(btn => {
          btn.onclick = () => {
            window.location.hash = '#admin/import/' + encodeURIComponent(slug) + '/' + encodeURIComponent(btn.dataset.num || '1');
          };
        });
        page.querySelectorAll('.ch-translate-one').forEach(btn => {
          btn.onclick = async () => {
            const num = parseInt(btn.dataset.num, 10);
            if (!num) return;
            btn.disabled = true;
            AdminUi.setButton(btn, 'book', 'กำลังแปล...');
            try {
              await Api.translateSingle(slug, num, true);
              Api.invalidateAll(slug);
              Ui.showToast('แปลตอน ' + num + ' สำเร็จ');
              await AdminChaptersPage.render({ slug });
            } catch (err) {
              Ui.showToast(err.message, 'error');
              btn.disabled = false;
              AdminUi.setButton(btn, 'book', 'แปล');
            }
          };
        });
        Ui.$('ch-jump-btn').onclick = () => {
          const num = parseInt(Ui.$('ch-jump-num').value, 10);
          if (num) {
            window.location.hash = '#novel/' + slug + '/' + num;
          }
        };
        Ui.$('ch-jump-num').onkeydown = (e) => { if (e.key === 'Enter') Ui.$('ch-jump-btn').click(); };

        if (opts.focusSearch) {
          const input = Ui.$('ch-filter-search');
          input?.focus();
          input?.setSelectionRange?.(opts.cursor ?? searchQuery.length, opts.cursor ?? searchQuery.length);
        }
      };

      renderTable();
    } catch (err) { Ui.showError(page, 'โหลดไม่สำเร็จ', err.message); }
  }
};

// ── ADMIN GLOSSARY ───────────────────────────────────────────────────────
const AdminGlossaryPage = {
  _terms: [],
  _slug: '',
  _editingIndex: -1,

  _setStatus(message, type = 'success') {
    AdminUi.setStatus('glossary-status', 'c-glossary-admin__status', message, type);
  },

  async _saveTerms() {
    const res = await fetch('/api/novel/' + this._slug + '/glossary/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ terms: this._terms })
    });
    if (!res.ok) throw new Error('ไม่สามารถเซฟข้อมูลลง Server ได้');
    return res.json();
  },

  async render(params) {
    const page = Ui.$('page-admin-glossary');
    if (!page) return;
    
    try {
      const res = await fetch('/api/novels');
      const novels = await res.json();
      this._novels = novels || [];
      
      if (!this._slug && this._novels.length > 0) {
        const firstReal = this._novels.find(n => !n.slug?.startsWith('test-') && !n.slug?.startsWith('fixture-') && !n.slug?.startsWith('tmp-'));
        this._slug = firstReal?.slug || this._novels[0]?.slug;
      }
      
      if (!this._slug) {
        page.innerHTML = '<div class="c-container">' + Ui.adminNav('glossary') + '<p class="u-text-center u-text-muted">ไม่พบนิยายที่จะแก้ไข Glossary</p></div>';
        return;
      }

      // Load terms
      const glossRes = await fetch(`/api/novel/${this._slug}/glossary/data`);
      if (glossRes.ok) {
        const data = await glossRes.json();
        this._terms = data.terms || data || [];
      } else {
        this._terms = [];
      }

      this._editingIndex = -1;
      this._renderUI(page);
    } catch (err) {
      page.innerHTML = '<div class="c-container">' + Ui.adminNav('glossary') + '<p class="u-text-center c-error__title">เกิดข้อผิดพลาด</p><p class="u-text-center u-text-muted">' + Ui.esc(err.message) + '</p></div>';
    }
  },

  _renderUI(page) {
    const novelOptions = (this._novels || []).map(n =>
      `<option value="${Ui.esc(n.slug)}" ${n.slug === this._slug ? 'selected' : ''}>${Ui.esc(Ui.displayTitle(n) || n.slug)}</option>`
    ).join('');

    let html = '<div class="c-container">' + Ui.adminNav('glossary') +
      '<div class="c-form__group c-glossary-admin__novel-select">' +
        '<label class="c-form__label">เลือกนิยายเพื่อจัดการ Glossary</label>' +
        '<select class="c-form__select" id="glossary-novel-select">' +
          novelOptions +
        '</select>' +
      '</div>' +
      '<div class="c-section__header"><h3 class="c-section__title">จัดการคลังคำศัพท์ (' + Ui.esc(this._slug) + ')</h3></div>' +
      
      // Two-column responsive layout for Forms
      '<div class="c-glossary-admin__grid">' +
        // Card 1: Add/Edit Term
        '<div class="c-settings-form c-glossary-admin__panel">' +
          '<h4 id="glossary-form-title" class="c-glossary-admin__title">เพิ่มคำศัพท์ใหม่</h4>' +
          '<div class="c-form c-glossary-admin__form">' +
            '<div class="c-glossary-admin__fields">' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">คำศัพท์เดิม (จีน)</label>' +
                '<input class="c-form__input" id="glossary-source" placeholder="เช่น 曹星" />' +
              '</div>' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">คำแปล (ไทย)</label>' +
                '<input class="c-form__input" id="glossary-thai" placeholder="เช่น เฉาซิง" />' +
              '</div>' +
            '</div>' +
            '<div class="c-glossary-admin__fields">' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">ประเภท</label>' +
                '<select class="c-form__select" id="glossary-category">' +
                  '<option value="คำศัพท์">คำศัพท์ทั่วไป</option>' +
                  '<option value="ตัวละคร">ตัวละคร</option>' +
                  '<option value="สถานที่">สถานที่</option>' +
                  '<option value="สกิล">สกิล/ทักษะ</option>' +
                  '<option value="ไอเทม">ไอเทม</option>' +
                '</select>' +
              '</div>' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">การล็อก</label>' +
                '<select class="c-form__select" id="glossary-lock">' +
                  '<option value="auto">Auto (ลื่นไหล)</option>' +
                  '<option value="locked">Locked (ห้ามเปลี่ยน)</option>' +
                  '<option value="reference">Reference (อ้างอิง)</option>' +
                '</select>' +
              '</div>' +
            '</div>' +
            '<div class="c-glossary-admin__actions">' +
              '<button class="c-btn c-btn--primary" id="glossary-save-btn" type="button">' + Ui.icon('bookmarks', 'xs') + '<span>บันทึกคำศัพท์</span></button>' +
              '<button class="c-btn c-btn--secondary" id="glossary-cancel-btn" type="button" hidden>' + Ui.icon('close', 'xs') + '<span>ยกเลิก</span></button>' +
            '</div>' +
          '</div>' +
          '<div id="glossary-status" class="c-glossary-admin__status" aria-live="polite"></div>' +
        '</div>' +

        // Card 2: AI Glossary Suggestion
        '<div class="c-settings-form c-glossary-admin__panel c-glossary-admin__panel--ai">' +
          '<h4 class="c-glossary-admin__title">แนะนำคำศัพท์ใหม่ด้วย AI</h4>' +
          '<div class="c-glossary-admin__scan-row">' +
            '<div class="c-form__group c-glossary-admin__scan-input">' +
              '<label class="c-form__label">ตอนที่ต้องการสแกน</label>' +
              '<input type="number" min="1" class="c-form__input" id="ai-glossary-ch" placeholder="เช่น 1" />' +
            '</div>' +
            '<button class="c-btn c-btn--secondary" id="ai-glossary-scan-btn" type="button">' + Ui.icon('search', 'xs') + '<span>สแกน</span></button>' +
          '</div>' +
          '<div id="ai-glossary-loading" class="c-glossary-admin__loading" hidden>' +
            'กำลังสแกนหาศัพท์จีนที่ยังไม่ได้แปล...' +
          '</div>' +
          '<div id="ai-glossary-results-box" class="c-glossary-admin__results" hidden>' +
            '<div id="ai-glossary-results-list" class="c-glossary-admin__results-list"></div>' +
          '</div>' +
        '</div>' +
      '</div>';

    // Glossary Table
    html += '<div class="c-table-wrap"><table class="c-table"><thead><tr><th>จีน</th><th>ไทย</th><th>ประเภท</th><th>ระดับ</th><th>การตรวจสอบ</th><th class="c-glossary-admin__actions-col">การจัดการ</th></tr></thead><tbody>';
    
    if (this._terms.length === 0) {
      html += '<tr><td colspan="6" class="u-text-center u-text-muted">ไม่มีคำศัพท์ในคลัง</td></tr>';
    } else {
      this._terms.forEach((t, index) => {
        const lockClass = t.lock === 'locked' ? 'c-badge--teal' : t.lock === 'reference' ? 'c-badge--purple' : 'c-badge--gray';
        const isVerified = t.verified !== false;
        const verifyBadgeClass = isVerified ? 'c-badge--teal' : 'c-badge--amber';
        const verifyLabel = isVerified ? '✔ ยืนยันแล้ว' : '⏳ แนะนำโดย AI';
        
        html += '<tr>' +
          '<td><strong>' + Ui.esc(t.source || '') + '</strong></td>' +
          '<td>' + Ui.esc(t.thai || '') + '</td>' +
          '<td>' + Ui.esc(t.category || 'คำศัพท์') + '</td>' +
          '<td><span class="c-badge ' + lockClass + '">' + Ui.esc(t.lock || 'auto') + '</span></td>' +
          '<td>' +
            '<span class="c-badge ' + verifyBadgeClass + ' glossary-verify-toggle c-glossary-admin__verify" data-index="' + index + '" title="คลิกเพื่อสลับสถานะการตรวจสอบ">' +
              verifyLabel +
            '</span>' +
          '</td>' +
          '<td><div class="c-glossary-admin__table-actions">' +
            '<button class="c-btn c-btn--xs c-btn--secondary glossary-edit-btn" data-index="' + index + '" type="button">' + Ui.icon('settings', 'xs') + '<span>แก้ไข</span></button>' +
            '<button class="c-btn c-btn--xs c-btn--danger glossary-del-btn" data-index="' + index + '" type="button">' + Ui.icon('close', 'xs') + '<span>ลบ</span></button>' +
          '</div></td>' +
        '</tr>';
      });
    }

    html += '</tbody></table></div></div>';
    page.innerHTML = html;

    this._bindEvents(page);
  },

  _bindEvents(page) {
    const novelSelect = document.getElementById('glossary-novel-select');
    if (novelSelect) {
      novelSelect.onchange = async () => {
        this._slug = novelSelect.value;
        try {
          const glossRes = await fetch(`/api/novel/${this._slug}/glossary/data`);
          if (glossRes.ok) {
            const data = await glossRes.json();
            this._terms = data.terms || data || [];
          } else {
            this._terms = [];
          }
          this._editingIndex = -1;
          this._renderUI(page);
        } catch (err) {
          Ui.showToast('โหลด Glossary ไม่สำเร็จ: ' + err.message, 'error');
        }
      };
    }

    const sourceInput = document.getElementById('glossary-source');
    const thaiInput = document.getElementById('glossary-thai');
    const categorySelect = document.getElementById('glossary-category');
    const lockSelect = document.getElementById('glossary-lock');
    const saveBtn = document.getElementById('glossary-save-btn');
    const cancelBtn = document.getElementById('glossary-cancel-btn');
    const formTitle = document.getElementById('glossary-form-title');

    // Save click handler
    saveBtn.onclick = async () => {
      const source = sourceInput.value.trim();
      const thai = thaiInput.value.trim();
      const category = categorySelect.value;
      const lock = lockSelect.value;

      if (!source || !thai) {
        this._setStatus('กรุณากรอกทั้งคำศัพท์เดิม (จีน) และคำแปล (ไทย)', 'error');
        Ui.showToast('กรุณากรอกข้อมูลคำศัพท์ให้ครบ', 'error');
        return;
      }

      if (this._editingIndex === -1) {
        // Add Mode: Check duplicate
        const exists = this._terms.some(t => t.source === source);
        if (exists) {
          this._setStatus('คำศัพท์ "' + source + '" มีอยู่แล้วในคลังศัพท์', 'error');
          Ui.showToast('คำศัพท์นี้มีอยู่แล้ว', 'error');
          return;
        }
        this._terms.push({ source, thai, category, priority: 3, lock, explanation: '', notes: '', verified: true });
        this._setStatus('เพิ่มคำศัพท์สำเร็จแล้ว');
      } else {
        // Edit Mode
        this._terms[this._editingIndex] = {
          ...this._terms[this._editingIndex],
          source,
          thai,
          category,
          lock,
          verified: true
        };
        this._setStatus('แก้ไขคำศัพท์สำเร็จแล้ว');
        this._editingIndex = -1;
      }

      // Save to server
      try {
        saveBtn.disabled = true;
        AdminUi.setButton(saveBtn, 'bookmarks', 'กำลังบันทึก...');
        await this._saveTerms();
        Ui.showToast('บันทึกคำศัพท์แล้ว');
        this._renderUI(page);
      } catch (err) {
        this._setStatus('บันทึกไม่สำเร็จ: ' + err.message, 'error');
        Ui.showToast('บันทึกคำศัพท์ไม่สำเร็จ', 'error');
      } finally {
        saveBtn.disabled = false;
        AdminUi.setButton(saveBtn, 'bookmarks', 'บันทึกคำศัพท์');
      }
    };

    // Cancel click handler
    cancelBtn.onclick = () => {
      this._editingIndex = -1;
      this._renderUI(page);
    };

    // Edit click handlers
    page.querySelectorAll('.glossary-edit-btn').forEach(btn => {
      btn.onclick = () => {
        const index = parseInt(btn.dataset.index, 10);
        const t = this._terms[index];
        if (!t) return;

        this._editingIndex = index;
        formTitle.textContent = 'แก้ไขคำศัพท์: ' + t.source;
        sourceInput.value = t.source;
        thaiInput.value = t.thai;
        categorySelect.value = t.category || 'คำศัพท์';
        lockSelect.value = t.lock || 'auto';

        cancelBtn.hidden = false;
        sourceInput.focus();
      };
    });

    // Delete click handlers
    page.querySelectorAll('.glossary-del-btn').forEach(btn => {
      btn.onclick = async () => {
        const index = parseInt(btn.dataset.index, 10);
        const t = this._terms[index];
        if (!t) return;

        if (confirm('คุณแน่ใจว่าต้องการลบคำศัพท์ "' + t.source + '" ใช่หรือไม่?')) {
          this._terms.splice(index, 1);
          try {
            await this._saveTerms();
            Ui.showToast('ลบคำศัพท์แล้ว');
            this._renderUI(page);
          } catch (err) {
            Ui.showToast('ลบไม่สำเร็จ: ' + err.message, 'error');
          }
        }
      };
    });

    // Toggle Verification Badge Handler
    page.querySelectorAll('.glossary-verify-toggle').forEach(badge => {
      badge.onclick = async () => {
        const index = parseInt(badge.dataset.index, 10);
        const currentVerified = this._terms[index].verified !== false;
        const newVerified = !currentVerified;
        
        try {
          badge.classList.add('is-busy');
          const res = await Api.verifyGlossaryTerm(this._slug, index, newVerified);
          this._terms[index].verified = res.data.verified;
          Ui.showToast(newVerified ? 'ยืนยันคำศัพท์แล้ว' : 'ตั้งเป็นรอตรวจแล้ว');
          this._renderUI(page);
        } catch (err) {
          Ui.showToast('สลับสถานะไม่สำเร็จ: ' + err.message, 'error');
          badge.classList.remove('is-busy');
        }
      };
    });

    // AI Glossary Suggestion Handlers
    const aiScanBtn = document.getElementById('ai-glossary-scan-btn');
    const aiChInput = document.getElementById('ai-glossary-ch');
    const aiLoading = document.getElementById('ai-glossary-loading');
    const aiResultsBox = document.getElementById('ai-glossary-results-box');
    const aiResultsList = document.getElementById('ai-glossary-results-list');

    if (aiScanBtn && aiChInput) {
      aiScanBtn.onclick = async () => {
        const chNum = parseInt(aiChInput.value, 10);
        if (isNaN(chNum) || chNum < 1) {
          this._setStatus('กรุณากรอกเลขตอนที่ถูกต้อง', 'error');
          Ui.showToast('กรุณากรอกเลขตอนที่ถูกต้อง', 'error');
          return;
        }

        try {
          aiScanBtn.disabled = true;
          AdminUi.setButton(aiScanBtn, 'search', 'กำลังสแกน...');
          aiLoading.hidden = false;
          aiResultsBox.hidden = true;
          aiResultsList.innerHTML = '';

          const res = await Api.getUnknownTerms(this._slug, chNum);
          const terms = res.terms || [];

          aiLoading.hidden = true;
          aiResultsBox.hidden = false;

          if (terms.length === 0) {
            aiResultsList.innerHTML = '<div class="c-glossary-admin__empty">ไม่พบคำศัพท์ภาษาจีนใหม่ในตอนนี้นะคะ</div>';
          } else {
            terms.forEach((term, termIdx) => {
              const resultId = `ai-suggest-res-${termIdx}`;
              const item = document.createElement('div');
              item.className = 'c-glossary-admin__result-item';
              item.innerHTML = `
                <span class="c-glossary-admin__term">${Ui.esc(term)}</span>
                <div class="c-glossary-admin__result-actions">
                  <span id="${resultId}" class="c-glossary-admin__suggestion"></span>
                  <button class="c-btn c-btn--xs c-btn--secondary ai-suggest-btn c-glossary-admin__mini-btn" data-term="${Ui.esc(term)}" data-result-id="${resultId}" type="button">${Ui.icon('search', 'xs')}<span>ขอไอเดีย</span></button>
                  <button class="c-btn c-btn--xs c-btn--primary ai-add-btn c-glossary-admin__mini-btn" data-term="${Ui.esc(term)}" type="button" hidden>${Ui.icon('arrow-right', 'xs')}<span>ย้ายเข้าฟอร์ม</span></button>
                </div>
              `;
              aiResultsList.appendChild(item);
            });

            // Bind Suggest Idea Event
            aiResultsList.querySelectorAll('.ai-suggest-btn').forEach(btn => {
              btn.onclick = async () => {
                const term = btn.dataset.term;
                const resSpan = document.getElementById(btn.dataset.resultId);
                const addBtn = btn.nextElementSibling;
                if (!resSpan || !addBtn) return;

                try {
                  btn.disabled = true;
                  AdminUi.setButton(btn, 'search', 'กำลังแปล...');
                  resSpan.textContent = 'กำลังแปล...';

                  // Fetch context from source chapter
                  let context = '';
                  try {
                    const sourceRes = await fetch(`/api/novel/${this._slug}/source/${chNum}`);
                    if (sourceRes.ok) {
                      const sourceText = await sourceRes.text();
                      const idx = sourceText.indexOf(term);
                      if (idx !== -1) {
                        const start = Math.max(0, idx - 100);
                        const end = Math.min(sourceText.length, idx + term.length + 100);
                        context = sourceText.substring(start, end).replace(/\n+/g, ' ').trim();
                      }
                    }
                  } catch (errContext) {
                    console.warn('Could not grab context from source:', errContext);
                  }

                  // Call API
                  const suggestRes = await Api.translateTerm(term, context);
                  const thai = suggestRes.data.thai || '';
                  const cat = suggestRes.data.category || 'คำศัพท์';
                  
                  resSpan.innerHTML = `<span class="c-badge c-badge--gray c-glossary-admin__mini-badge">${Ui.esc(cat)}</span> <strong>${Ui.esc(thai)}</strong>`;
                  btn.hidden = true;
                  
                  addBtn.hidden = false;
                  addBtn.dataset.thai = thai;
                  addBtn.dataset.category = cat;
                } catch (errSuggest) {
                  resSpan.textContent = 'ขัดข้อง';
                  btn.disabled = false;
                  AdminUi.setButton(btn, 'search', 'ขอไอเดีย');
                  Ui.showToast('แนะนำคำศัพท์ไม่สำเร็จ: ' + errSuggest.message, 'error');
                }
              };
            });

            // Bind Add to Form Event
            aiResultsList.querySelectorAll('.ai-add-btn').forEach(btn => {
              btn.onclick = () => {
                const term = btn.dataset.term;
                const thai = btn.dataset.thai;
                const cat = btn.dataset.category;

                sourceInput.value = term;
                thaiInput.value = thai;
                categorySelect.value = cat;
                lockSelect.value = 'auto';

                this._setStatus('โหลดแนะนำจาก AI เข้าฟอร์มแล้ว กรุณากดบันทึกค่ะ');
                Ui.showToast('ย้ายคำแนะนำเข้าฟอร์มแล้ว');
                thaiInput.focus();
                
                // Smooth scroll to form
                formTitle.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              };
            });
          }
        } catch (errScan) {
          Ui.showToast('สแกนคำศัพท์ไม่สำเร็จ: ' + errScan.message, 'error');
        } finally {
          aiScanBtn.disabled = false;
          AdminUi.setButton(aiScanBtn, 'search', 'สแกน');
          aiLoading.hidden = true;
        }
      };
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
      page.innerHTML =
        '<div class="c-container">' + Ui.adminNav('novels') +
        '<div class="c-section__header c-admin-page__header c-admin-edit__header">' +
        '<div><h3 class="c-section__title">แก้ไขนิยาย: ' + Ui.esc(slug || '') + '</h3><p class="u-text-muted">แก้ metadata และปก จากนั้นไปจัดตอนหรือนำเข้าต้นฉบับต่อได้ทันที</p></div>' +
        '<div class="c-admin-edit__quick-actions">' +
        '<a class="c-btn c-btn--sm c-btn--ghost" href="#admin/novels" data-nav>' + Ui.icon('library', 'xs') + '<span>รายการนิยาย</span></a>' +
        '<a class="c-btn c-btn--sm c-btn--secondary" href="#novel/' + Ui.esc(slug || '') + '" data-nav>' + Ui.icon('book', 'xs') + '<span>อ่าน</span></a>' +
        '<a class="c-btn c-btn--sm c-btn--secondary" href="#admin/chapters/' + Ui.esc(slug || '') + '" data-nav>' + Ui.icon('bookmarks', 'xs') + '<span>จัดตอน</span></a>' +
        '<a class="c-btn c-btn--sm c-btn--secondary" href="#admin/import/' + Ui.esc(slug || '') + '" data-nav>' + Ui.icon('info', 'xs') + '<span>สุขภาพนำเข้า</span></a>' +
        '</div></div>' +
        '<div class="c-admin-edit-layout">' +
        '<div class="c-admin-cover-panel"><div class="c-admin-cover-preview" id="edit-cover-preview">' + Ui.coverHtml(novel || { slug }) + '</div>' +
        '<input class="c-admin-cover-input" id="edit-cover-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif">' +
        '<div class="c-admin-cover-actions"><button class="c-btn c-btn--primary" id="edit-cover-save" type="button">' + Ui.icon('book', 'xs') + '<span>บันทึกปก</span></button><button class="c-btn c-btn--ghost" id="edit-cover-delete" type="button">' + Ui.icon('close', 'xs') + '<span>ลบปก</span></button></div>' +
        '<span id="edit-cover-status" class="c-admin-edit__status"></span></div>' +
        '<div class="c-settings-form c-admin-edit-form"><div class="c-form">' +
        '<div class="c-form__group"><label class="c-form__label" for="edit-translated-title">ชื่อไทย</label><input class="c-form__input" id="edit-translated-title" value="' + Ui.esc(novel?.translatedTitle || '') + '" /></div>' +
        '<div class="c-form__group"><label class="c-form__label" for="edit-title">ชื่อต้นฉบับ</label><input class="c-form__input" id="edit-title" value="' + Ui.esc(novel?.title || '') + '" /></div>' +
        '<div class="c-form__group"><label class="c-form__label" for="edit-author">ผู้แต่ง</label><input class="c-form__input" id="edit-author" value="' + Ui.esc(novel?.author || '') + '" /></div>' +
        '<div class="c-form__group c-admin-edit__actions"><button class="c-btn c-btn--primary" id="edit-save" type="button">' + Ui.icon('settings', 'xs') + '<span>บันทึก metadata</span></button><span id="edit-status" class="c-admin-edit__status"></span></div>' +
        '</div></div></div></div>';
    } catch(_) { Ui.showError(page, 'เกิดข้อผิดพลาด'); }

    // ── Save handler ────────────────────────────────────────────────
    const saveBtn = document.getElementById('edit-save');
    const statusEl = document.getElementById('edit-status');
    if (saveBtn && statusEl) {
      saveBtn.onclick = async () => {
        const title = document.getElementById('edit-title')?.value?.trim() || '';
        const translatedTitle = document.getElementById('edit-translated-title')?.value?.trim() || '';
        const author = document.getElementById('edit-author')?.value?.trim() || '';
        AdminUi.setStatus('edit-status', 'c-admin-edit__status', 'กำลังบันทึก...', 'muted');
        try {
          const res = await fetch('/api/novel/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ slug, title, author, translatedTitle }),
          });
          const data = await res.json();
          if (res.ok) {
            Api.invalidateAll(slug);
            AdminUi.setStatus('edit-status', 'c-admin-edit__status', 'บันทึกสำเร็จ', 'success');
            Ui.showToast('บันทึกข้อมูลนิยายแล้ว');
          } else {
            AdminUi.setStatus('edit-status', 'c-admin-edit__status', data.error?.message || 'เกิดข้อผิดพลาด', 'error');
          }
        } catch (e) {
          AdminUi.setStatus('edit-status', 'c-admin-edit__status', e.message, 'error');
        }
      };
    }

    const coverInput = document.getElementById('edit-cover-file');
    const coverSaveBtn = document.getElementById('edit-cover-save');
    const coverDeleteBtn = document.getElementById('edit-cover-delete');
    const coverPreview = document.getElementById('edit-cover-preview');
    const coverPanel = coverPreview?.closest('.c-admin-cover-panel');
    let selectedCoverData = '';

    const resizeCoverImage = (file) => new Promise((resolve, reject) => {
      if (!file.type.startsWith('image/')) {
        reject(new Error('ไฟล์นี้ไม่ใช่รูปภาพ'));
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          const maxW = 900;
          const scale = Math.min(1, maxW / Math.max(1, img.naturalWidth));
          const canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
          canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            resolve(String(reader.result || ''));
            return;
          }
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          resolve(canvas.toDataURL('image/webp', 0.86));
        };
        img.onerror = () => reject(new Error('อ่านรูปไม่สำเร็จ'));
        img.src = String(reader.result || '');
      };
      reader.onerror = () => reject(new Error('อ่านไฟล์รูปไม่สำเร็จ'));
      reader.readAsDataURL(file);
    });

    const readSelectedCover = () => new Promise((resolve, reject) => {
      const file = coverInput?.files?.[0];
      if (!file) {
        reject(new Error('กรุณาเลือกรูปปกก่อนค่ะ'));
        return;
      }
      if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type)) {
        reject(new Error('รองรับเฉพาะ PNG, JPEG, WebP หรือ GIF'));
        return;
      }
      if (file.size > 4 * 1024 * 1024) {
        reject(new Error('รูปปกต้องไม่เกิน 4 MB'));
        return;
      }
      resizeCoverImage(file).then(resolve).catch(reject);
    });

    if (coverInput && coverPreview) {
      coverInput.addEventListener('change', async () => {
        try {
          selectedCoverData = await readSelectedCover();
          coverPreview.innerHTML = '<img class="c-cover-img" src="' + Ui.esc(selectedCoverData) + '" alt="Cover preview">';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'พร้อมบันทึกปกใหม่', 'muted');
        } catch (err) {
          selectedCoverData = '';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', err.message, 'error');
        }
      });
    }

    if (coverPanel && coverInput && coverPreview) {
      ['dragenter', 'dragover'].forEach(type => {
        coverPanel.addEventListener(type, (event) => {
          event.preventDefault();
          coverPanel.classList.add('is-dragging');
        });
      });
      ['dragleave', 'drop'].forEach(type => {
        coverPanel.addEventListener(type, (event) => {
          event.preventDefault();
          coverPanel.classList.remove('is-dragging');
        });
      });
      coverPanel.addEventListener('drop', async (event) => {
        const file = event.dataTransfer?.files?.[0];
        if (!file) return;
        try {
          if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type)) {
            throw new Error('รองรับเฉพาะ PNG, JPEG, WebP หรือ GIF');
          }
          if (file.size > 4 * 1024 * 1024) throw new Error('รูปปกต้องไม่เกิน 4 MB');
          selectedCoverData = await resizeCoverImage(file);
          coverPreview.innerHTML = '<img class="c-cover-img" src="' + Ui.esc(selectedCoverData) + '" alt="Cover preview">';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'พร้อมบันทึกปกใหม่', 'muted');
        } catch (err) {
          selectedCoverData = '';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', err.message, 'error');
        }
      });
    }

    if (coverSaveBtn) {
      coverSaveBtn.onclick = async () => {
        try {
          coverSaveBtn.disabled = true;
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'กำลังบันทึกปก...', 'muted');
          const imageData = selectedCoverData || await readSelectedCover();
          const res = await Api.saveNovelCover(slug, imageData);
          selectedCoverData = '';
          if (coverPreview) {
            coverPreview.innerHTML = '<img class="c-cover-img" src="' + Ui.esc(res.data.coverImage) + '" alt="Cover preview">';
          }
          if (coverInput) coverInput.value = '';
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'บันทึกปกสำเร็จ', 'success');
        } catch (err) {
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', err.message, 'error');
        } finally {
          coverSaveBtn.disabled = false;
        }
      };
    }

    if (coverDeleteBtn) {
      coverDeleteBtn.onclick = async () => {
        try {
          coverDeleteBtn.disabled = true;
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'กำลังลบปก...', 'muted');
          await Api.deleteNovelCover(slug);
          selectedCoverData = '';
          if (coverInput) coverInput.value = '';
          if (coverPreview) coverPreview.innerHTML = Ui.coverHtml({ slug, title: novel?.title || slug });
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', 'ลบปกแล้ว', 'success');
        } catch (err) {
          AdminUi.setStatus('edit-cover-status', 'c-admin-edit__status', err.message, 'error');
        } finally {
          coverDeleteBtn.disabled = false;
        }
      };
    }
  }
};

// ── BOOKMARKS ────────────────────────────────────────────────────────────
const BookmarksPage = {
  async render(params) {
    const page = Ui.$('page-bookmarks');
    if (!page) return;
    try {
      const list = JSON.parse(localStorage.getItem('novelclaw-bookmarks')) || [];
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
        const novels = await Api.getNovels();
        const novelOptions = novels.map(n => 
          `<option value="${Ui.esc(n.slug)}">${Ui.esc(Ui.displayTitle(n) || n.slug)}</option>`
        ).join('');
        
        let selectHtml = '<div class="c-container">' + Ui.adminNav('logs') +
          '<div class="c-section__header c-admin-logs__header"><h3 class="c-section__title">📂 ตรวจสอบ Audit Log รายตอน</h3></div>' +
          '<div class="c-settings-card c-admin-logs__panel">' +
          '<div class="c-form">' +
          '<div class="c-admin-logs__form-grid">' +
          '<div class="c-form__group">' +
          '<label class="c-form__label">เลือกนิยาย</label>' +
          '<select class="c-form__select c-form__select--compact" id="logs-novel-select">' +
          novelOptions +
          '</select>' +
          '</div>' +
          '<div class="c-form__group">' +
          '<label class="c-form__label">ตอนที่ต้องการตรวจ (Chapter Number)</label>' +
          '<input type="number" class="c-form__input c-form__input--compact" id="logs-chapter-num" value="1" min="1" />' +
          '</div>' +
          '</div>' +
          '<div id="logs-query-status" class="c-admin-logs__status" aria-live="polite"></div>' +
          '<button class="c-btn c-btn--primary c-admin-logs__submit" id="logs-query-btn" type="button">' + Ui.icon('search', 'xs') + '<span>ตรวจ Audit Log</span></button>' +
          '</div>' +
          '</div>' +
          '</div>';
          
        page.innerHTML = selectHtml;
        
        document.getElementById('logs-query-btn')?.addEventListener('click', () => {
          const selectedSlug = document.getElementById('logs-novel-select').value;
          const selectedNum = document.getElementById('logs-chapter-num').value.trim();
          if (!selectedSlug || !selectedNum) {
            const statusEl = document.getElementById('logs-query-status');
            if (statusEl) statusEl.textContent = 'กรุณาเลือกนิยายและระบุเลขตอน';
            Ui.showToast('กรุณาเลือกนิยายและระบุเลขตอน', 'error');
            return;
          }
          window.location.hash = `#admin/logs/${selectedSlug}/${selectedNum}`;
        });
        return;
      }
      
      const res = await fetch('/api/admin/logs/' + encodeURIComponent(slug) + '/' + num);
      const data = await res.json();
      let html = '<div class="c-container">' +
        Ui.adminNav('logs') +
        '<div class="c-section__header c-admin-logs__header"><h3 class="c-section__title">📂 Audit Log: ' + Ui.esc(slug) + ' / ตอน ' + Ui.esc(num) + '</h3>' +
        '<div class="c-admin-logs__actions">' +
        '<a href="#admin/logs" class="c-btn c-btn--sm c-btn--secondary c-admin-logs__link" data-nav>' + Ui.icon('search', 'xs') + '<span>ค้นหาใหม่</span></a>' +
        '' +
        '</div></div>';

      const files = data.ok && data.data ? data.data.files : [];

      if (!data.ok || !files || files.length === 0) {
        const errorMsg = data.error?.message || data.data?.warning || 'ไม่มี log สำหรับตอนนี้';
        html += '<div class="c-settings-card c-admin-logs__panel"><p class="u-text-muted c-admin-logs__empty">' + Ui.esc(errorMsg) + '</p></div>';
      } else {
        for (const file of files) {
          html += '<div class="c-section c-admin-logs__file">' +
            '<div class="c-section__header"><h3 class="c-section__title c-admin-logs__file-title">' + Ui.esc(file.name) + '</h3></div>' +
            '<pre class="c-admin-logs__pre"><code>' + Ui.esc(file.content) + '</code></pre>' +
            '</div>';
        }
      }
      page.innerHTML = html;
    } catch (err) {
      Ui.showError(page, 'โหลดล็อกไม่สำเร็จ', err.message);
    }
  }
};

// ── ADMIN IMPORT SOURCE ──────────────────────────────────────────────────
const AdminImportPage = {
  _preview: null,
  _sites: [],
  _health: null,

  setConsole(state, title, message) {
    AdminUi.setConsole('import', state, title, message);
  },

  _data(resp) {
    return resp && resp.data ? resp.data : (resp || {});
  },

  _slugFromTitle(title) {
    return String(title || 'imported-novel')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'imported-novel';
  },

  _summary(data) {
    const results = data.results || [];
    const warningCount = results.reduce((sum, item) => sum + ((item.warnings || []).length > 0 ? 1 : 0), 0);
    return [
      'imported: ' + (data.imported || 0),
      'skipped: ' + (data.skipped || 0),
      'failed: ' + (data.failed || 0),
      'warnings: ' + warningCount,
    ].join('\n');
  },

  _siteOptions() {
    const sites = this._sites || [];
    return '<option value="auto">auto</option>' + sites.map(site => {
      const label = `${site.displayName || site.id} (${site.sourceLang || '?'}, ${site.quality || 'beta'})`;
      return '<option value="' + Ui.esc(site.id) + '">' + Ui.esc(label) + '</option>';
    }).join('');
  },

  _siteCatalogHtml() {
    const sites = this._sites || [];
    if (!sites.length) return '';
    const rows = sites.map(site =>
      '<tr>' +
      '<td><strong>' + Ui.esc(site.displayName || site.id) + '</strong><div class="u-text-muted">' + Ui.esc((site.domains || []).join(', ')) + '</div></td>' +
      '<td>' + Ui.esc(site.sourceLang || '') + '</td>' +
      '<td>' + Ui.esc(site.adapterType || '') + '</td>' +
      '<td><span class="c-badge c-badge--gray">' + Ui.esc(site.quality || '') + '</span></td>' +
      '<td>' + (site.access?.requiresJs ? '<span class="c-badge c-badge--amber">JS</span>' : '<span class="c-badge c-badge--teal">HTML</span>') + '</td>' +
      '</tr>'
    ).join('');
    return '<div class="c-table-wrap c-admin-import__sites"><table class="c-table"><thead><tr><th>เว็บ</th><th>ภาษา</th><th>ชนิด</th><th>คุณภาพ</th><th>โหมด</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
  },

  _healthBadge(status) {
    if (status === 'error') return 'c-badge c-badge--red';
    if (status === 'warn') return 'c-badge c-badge--amber';
    return 'c-badge c-badge--teal';
  },

  _issueText(issueSummary = {}) {
    const byCode = issueSummary.byCode || {};
    const entries = Object.entries(byCode).filter(([, count]) => count > 0);
    if (!entries.length) return 'ปกติ';
    return entries.slice(0, 3).map(([code, count]) => code + ' × ' + count).join(', ');
  },

  _issueRange(n = {}) {
    const nums = n.blockingSourceNums || [];
    if (nums.length) return nums.join(',');
    const firstIssue = n.sampleIssues?.[0]?.num;
    return firstIssue ? String(firstIssue) : '';
  },

  _renderHealthPanel() {
    const health = this._health || { summary: {}, novels: [] };
    const summary = health.summary || {};
    const novels = health.novels || [];
    const risky = novels.filter(n => n.status !== 'ok' || n.staleIndexTitleCount > 0);
    const rows = (risky.length ? risky : novels.slice(0, 5)).map(n => {
      const badgeText = n.status === 'error' ? 'ต้องตรวจ' : (n.status === 'warn' ? 'ควรดู' : 'พร้อม');
      const genericCount = n.issueSummary?.byCode?.generic_title || 0;
      const toc = n.sourceToc || {};
      const tocText = toc.exists
        ? 'toc: ' + (toc.chapterCount || 0) + (toc.site ? ' · ' + toc.site : '')
        : 'toc: missing';
      const recoverButton = genericCount > 0
        ? '<button class="c-btn c-btn--sm c-btn--ghost import-recover-toc-btn" data-slug="' + Ui.esc(n.slug) + '" type="button">' + Ui.icon('library', 'xs') + '<span>กู้ TOC</span></button>'
        : '';
      const issueRange = this._issueRange(n);
      return '<tr>' +
        '<td><strong>' + Ui.esc(n.title || n.slug) + '</strong><div class="u-text-muted">' + Ui.esc(n.slug) + '</div></td>' +
        '<td>' + Ui.esc(n.sourceSite || '-') + '<div class="u-text-muted">' + Ui.esc(tocText) + '</div></td>' +
        '<td class="c-admin-table__mono">' + (n.sourceFileCount || 0) + '</td>' +
        '<td><span class="' + this._healthBadge(n.status) + '">' + badgeText + '</span></td>' +
        '<td>' + Ui.esc(this._issueText(n.issueSummary)) + (n.staleIndexTitleCount ? '<div class="u-text-muted">stale title × ' + n.staleIndexTitleCount + '</div>' : '') + (n.blockingSourceCount ? '<div class="u-text-muted">blocked × ' + n.blockingSourceCount + '</div>' : '') + '</td>' +
        '<td><div class="c-admin-import__row-actions">' +
        '<button class="c-btn c-btn--sm c-btn--secondary import-repair-btn" data-slug="' + Ui.esc(n.slug) + '" type="button">' + Ui.icon('settings', 'xs') + '<span>ซ่อม</span></button>' +
        '<button class="c-btn c-btn--sm c-btn--ghost import-view-issues-btn" data-slug="' + Ui.esc(n.slug) + '" type="button">' + Ui.icon('info', 'xs') + '<span>ปัญหา</span></button>' +
        '<button class="c-btn c-btn--sm c-btn--ghost import-inspect-btn" data-slug="' + Ui.esc(n.slug) + '" data-num="' + Ui.esc(issueRange.split(',')[0] || '1') + '" type="button">' + Ui.icon('search', 'xs') + '<span>ตรวจ</span></button>' +
        '<button class="c-btn c-btn--sm c-btn--secondary import-reimport-range-btn" data-slug="' + Ui.esc(n.slug) + '" data-range="' + Ui.esc(issueRange) + '" type="button">' + Ui.icon('library', 'xs') + '<span>นำเข้าใหม่</span></button>' +
        recoverButton + '</div></td>' +
        '</tr>';
    }).join('');

    return '<div class="c-card c-admin-import__panel c-admin-import__health">' +
      '<div class="c-admin-import__health-head"><h3 class="c-admin-import__title">Import Health</h3><button class="c-btn c-btn--sm c-btn--ghost" id="import-health-refresh" type="button">' + Ui.icon('search', 'xs') + '<span>รีเฟรช</span></button></div>' +
      '<div class="c-admin-import__health-stats">' +
      Ui.stat('นิยาย', summary.novels || 0, { tone: 'accent' }) +
      Ui.stat('source files', summary.sourceFiles || 0, { tone: 'accent' }) +
      Ui.stat('errors', summary.errors || 0, { tone: summary.errors ? 'warn' : 'success' }) +
      Ui.stat('warnings', summary.warnings || 0, { tone: summary.warnings ? 'warn' : 'success' }) +
      '</div>' +
      '<div class="c-table-wrap c-admin-import__health-table"><table class="c-table"><thead><tr><th>นิยาย</th><th>เว็บ</th><th>source</th><th>สถานะ</th><th>ปัญหา</th><th>ซ่อม</th></tr></thead><tbody>' +
      (rows || '<tr><td colspan="6" class="u-text-muted">ยังไม่มีข้อมูล import source</td></tr>') +
      '</tbody></table></div>' +
      '</div>';
  },

  _previewDiagnosticsHtml(data) {
    const diag = data.diagnostics || {};
    const sample = data.sampleChapter;
    const statusClass = diag.recommendImport ? 'c-badge c-badge--teal' : 'c-badge c-badge--amber';
    let html = '<div class="c-admin-import__diagnostics">' +
      '<span class="' + statusClass + '">' + (diag.recommendImport ? 'sample พร้อม import' : 'ควรตรวจ sample') + '</span>' +
      '<span class="c-badge ' + (diag.hasSampleContent ? 'c-badge--teal' : 'c-badge--red') + '">' + (diag.hasSampleContent ? 'มีเนื้อหา' : 'ไม่พบเนื้อหา') + '</span>';
    if (diag.sampleError) html += '<span class="c-badge c-badge--red">' + Ui.esc(diag.sampleError) + '</span>';
    html += '</div>';
    if (sample) {
      const warningHtml = (sample.warnings || []).map(w => '<span class="c-badge c-badge--amber">' + Ui.esc(w) + '</span>').join('');
      html += '<div class="c-admin-import__sample-card">' +
        '<div class="c-admin-import__sample-meta"><strong>' + Ui.esc(sample.title || '') + '</strong><span>' + (sample.paragraphCount || 0) + ' paragraphs · ' + (sample.charCount || 0) + ' chars</span></div>' +
        (warningHtml ? '<div class="c-admin-import__diagnostics">' + warningHtml + '</div>' : '') +
        '<div class="c-admin-import__sample-text">' + (sample.paragraphs || []).map(p => '<p>' + Ui.esc(p) + '</p>').join('') + '</div>' +
        '</div>';
    }
    return html;
  },

  _renderSourceInspector() {
    const novels = this._health?.novels || [];
    const options = novels
      .filter(n => (n.sourceFileCount || 0) > 0)
      .map(n => '<option value="' + Ui.esc(n.slug) + '">' + Ui.esc(n.title || n.slug) + '</option>')
      .join('');
    return '<div class="c-card c-admin-import__panel c-admin-source-inspector">' +
      '<h3 class="c-admin-import__title">Source Inspector</h3>' +
      '<div class="c-admin-source-inspector__form">' +
      '<div class="c-form__group"><label class="c-form__label" for="inspect-slug">นิยาย</label><select class="c-form__select" id="inspect-slug">' + options + '</select></div>' +
      '<div class="c-form__group"><label class="c-form__label" for="inspect-num">ตอน</label><input class="c-form__input" id="inspect-num" type="number" min="1" value="1"></div>' +
      '<button class="c-btn c-btn--secondary" id="inspect-run" type="button">' + Ui.icon('search', 'xs') + '<span>ตรวจ source</span></button>' +
      '</div>' +
      '<div id="inspect-output" class="c-admin-source-inspector__output" hidden></div>' +
      '</div>';
  },

  _renderInspection(data) {
    const out = document.getElementById('inspect-output');
    if (!out) return;
    const diagnostic = data.diagnostic || {};
    const issues = diagnostic.issues || [];
    const issueHtml = issues.length
      ? issues.map(issue => '<span class="c-badge ' + (issue.severity === 'error' ? 'c-badge--red' : 'c-badge--amber') + '">' + Ui.esc(issue.code) + '</span>').join('')
      : '<span class="c-badge c-badge--teal">clean</span>';
    out.hidden = false;
    out.innerHTML = '<div class="c-admin-source-inspector__summary">' +
      '<strong>' + Ui.esc(data.title || 'Untitled') + '</strong>' +
      '<span>' + (diagnostic.paragraphCount || 0) + ' paragraphs · ' + (diagnostic.charCount || 0) + ' chars</span>' +
      '<div class="c-admin-import__diagnostics">' + issueHtml + '</div>' +
      '</div>' +
      '<div class="c-admin-source-inspector__grid">' +
      '<div><div class="c-form__label">Raw source</div><pre class="c-admin-source-inspector__pre"><code>' + Ui.esc(data.raw || '') + '</code></pre></div>' +
      '<div><div class="c-form__label">Parsed clean text</div><pre class="c-admin-source-inspector__pre"><code>' + Ui.esc(data.cleanedText || '') + '</code></pre></div>' +
      '</div>';
  },

  _renderPreview(data) {
    const box = document.getElementById('import-preview');
    if (!box) return;
    const chapters = data.chapters || [];
    const sampleRows = chapters.slice(0, 8).map(ch =>
      '<tr><td class="c-admin-table__mono">' + Ui.esc(ch.num) + '</td><td>' + Ui.esc(ch.title || '') + '</td></tr>'
    ).join('');
    box.hidden = false;
    box.innerHTML =
      '<div class="c-card c-admin-import__preview">' +
      '<div class="c-admin-import__preview-grid">' +
      '<div><span class="c-form__label">ชื่อเรื่อง</span><strong>' + Ui.esc(data.title || '') + '</strong></div>' +
      '<div><span class="c-form__label">เว็บ</span><strong>' + Ui.esc(data.displayName || data.site || '') + '</strong></div>' +
      '<div><span class="c-form__label">ภาษา</span><strong>' + Ui.esc(data.sourceLang || '') + '</strong></div>' +
      '<div><span class="c-form__label">จำนวนตอน</span><strong>' + Ui.esc(data.chapterCount || 0) + '</strong></div>' +
      '</div>' +
      this._previewDiagnosticsHtml(data) +
      '<div class="c-admin-import__run-grid">' +
      '<div class="c-form__group"><label class="c-form__label" for="import-slug">Slug</label><input class="c-form__input" id="import-slug" value="' + Ui.esc(document.getElementById('import-target-slug')?.value || this._slugFromTitle(data.title)) + '" /></div>' +
      '<div class="c-form__group"><label class="c-form__label" for="import-range">ช่วงตอน</label><input class="c-form__input" id="import-range" placeholder="1-20" value="' + Ui.esc(document.getElementById('import-target-range')?.value || '') + '" /></div>' +
      '<label class="c-admin-import__check"><input type="checkbox" id="import-force" /> overwrite</label>' +
      '<button class="c-btn c-btn--primary" id="import-run" type="button">' + Ui.icon('library', 'xs') + '<span>นำเข้า source</span></button>' +
      '</div>' +
      '<div class="c-table-wrap c-admin-import__sample"><table class="c-table"><thead><tr><th>ตอน</th><th>ชื่อ</th></tr></thead><tbody>' + sampleRows + '</tbody></table></div>' +
      '</div>';

    document.getElementById('import-run')?.addEventListener('click', async () => {
      const btn = document.getElementById('import-run');
      const slug = document.getElementById('import-slug')?.value.trim();
      const range = document.getElementById('import-range')?.value.trim();
      const force = document.getElementById('import-force')?.checked;
      if (!slug) {
        Ui.showToast('กรุณาระบุ slug', 'error');
        return;
      }
      btn.disabled = true;
      AdminUi.setButton(btn, 'library', 'กำลังนำเข้า...');
      this.setConsole('running', 'Import running', 'Fetching and cleaning source chapters...');
      try {
        const result = this._data(await Api.importRun({
          url: data.url,
          site: data.site || 'auto',
          slug,
          range,
          force,
        }));
        this.setConsole('success', 'Import complete', this._summary(result));
        Ui.showToast('นำเข้า source สำเร็จ');
      } catch (err) {
        this.setConsole('error', 'Import failed', err.message);
        Ui.showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
        AdminUi.setButton(btn, 'library', 'นำเข้า source');
      }
    });
  },

  async render(params) {
    const page = Ui.$('page-admin-import');
    if (!page) return;
    let sitesPayload = {};
    try {
      sitesPayload = this._data(await Api.getImportSites());
      this._sites = sitesPayload.sites || [];
    } catch (err) {
      this._sites = [];
    }
    try {
      this._health = this._data(await Api.getImportHealth());
    } catch (err) {
      this._health = { summary: {}, novels: [] };
    }

    page.innerHTML = `
      <div class="c-container">
        ${Ui.adminNav('import')}
        <div class="c-section__header c-admin-page__header"><h3 class="c-section__title">นำเข้าต้นฉบับ</h3></div>
        <div class="c-admin-import">
          ${this._renderHealthPanel()}
          <div class="c-card c-admin-import__panel">
            <h3 class="c-admin-import__title">URL</h3>
            <div class="c-form c-admin-import__form">
              <div class="c-form__group c-admin-import__url-group">
                <label class="c-form__label" for="import-url">URL สารบัญ</label>
                <input class="c-form__input" id="import-url" placeholder="https://..." />
              </div>
              <div class="c-form__group">
                <label class="c-form__label" for="import-site">Adapter</label>
                <select class="c-form__select" id="import-site">
                  ${this._siteOptions()}
                </select>
              </div>
              <div class="c-form__group">
                <label class="c-form__label" for="import-target-slug">Target slug</label>
                <input class="c-form__input" id="import-target-slug" value="${Ui.esc(params?.slug || '')}" />
              </div>
              <div class="c-form__group">
                <label class="c-form__label" for="import-target-range">ช่วง</label>
                <input class="c-form__input" id="import-target-range" value="${Ui.esc(params?.num || '')}" placeholder="เช่น 563,598 หรือ 800-900" />
              </div>
              <button class="c-btn c-btn--secondary c-admin-import__preview-btn" id="import-preview-btn" type="button">${Ui.icon('search', 'xs')}<span>ดูตัวอย่าง</span></button>
            </div>
            ${this._siteCatalogHtml()}
            <div id="import-preview" hidden></div>
          </div>

          <div class="c-card c-admin-import__panel">
            <h3 class="c-admin-import__title">Paste</h3>
            <div class="c-form c-admin-import__paste-form">
              <div class="c-form__group"><label class="c-form__label" for="paste-slug">Slug</label><input class="c-form__input" id="paste-slug" /></div>
              <div class="c-form__group"><label class="c-form__label" for="paste-title">ชื่อเรื่อง</label><input class="c-form__input" id="paste-title" /></div>
              <div class="c-form__group"><label class="c-form__label" for="paste-lang">ภาษา source</label><input class="c-form__input" id="paste-lang" value="cn" /></div>
              <div class="c-form__group"><label class="c-form__label" for="paste-rule">Split rule</label><input class="c-form__input" id="paste-rule" placeholder="(?:ตอนที่|第|Chapter)\\s*(\\d+)" /></div>
              <div class="c-form__group c-admin-import__textarea-group"><label class="c-form__label" for="paste-content">ข้อความ</label><textarea class="c-form__textarea" id="paste-content"></textarea></div>
              <label class="c-admin-import__check"><input type="checkbox" id="paste-force" /> overwrite</label>
              <button class="c-btn c-btn--primary" id="paste-run" type="button">${Ui.icon('library', 'xs')}<span>บันทึก source</span></button>
            </div>
          </div>

          ${this._renderSourceInspector()}

          <div class="c-card c-admin-translate__panel" id="import-console-card" hidden>
            <div class="c-admin-translate__console-head">
              <h4 id="import-console-title">Import</h4>
              <span id="import-console-badge" class="c-badge c-badge--gray">พร้อมใช้งาน</span>
            </div>
            <pre class="c-admin-translate__console" id="import-console-output"></pre>
          </div>
        </div>
      </div>`;

    if (params?.slug) {
      const range = params.num || '';
      const importSlugInput = document.getElementById('import-target-slug');
      const importRangeInput = document.getElementById('import-target-range');
      const inspectSlugSelect = document.getElementById('inspect-slug');
      const inspectNumInput = document.getElementById('inspect-num');
      if (importSlugInput) importSlugInput.value = params.slug;
      if (importRangeInput) importRangeInput.value = range;
      if (inspectSlugSelect) inspectSlugSelect.value = params.slug;
      if (inspectNumInput && range) inspectNumInput.value = String(range).split(',')[0] || '1';
      if (range) {
        this.setConsole('idle', 'Re-import range ready', 'slug: ' + params.slug + '\nrange: ' + range + '\nใส่ URL สารบัญหรือ URL source แล้วกด Preview/Import เพื่อดึงช่วงนี้ใหม่');
      }
    }

    document.getElementById('import-health-refresh')?.addEventListener('click', async () => {
      await this.render(params);
    });

    page.querySelectorAll('.import-view-issues-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const slug = btn.dataset.slug;
        if (!slug) return;
        btn.disabled = true;
        AdminUi.setButton(btn, 'search', 'Loading...');
        try {
          const health = this._data(await Api.getImportHealth(slug, { includeChapters: true }));
          const lines = (health.chapters || []).slice(0, 80).map(ch => {
            const codes = (ch.issues || []).map(issue => issue.code + ':' + issue.severity).join(', ');
            return String(ch.num).padStart(4, '0') + '  ' + codes + '  ' + (ch.title || '');
          });
          this.setConsole(
            health.status === 'error' ? 'error' : 'idle',
            'Source issues: ' + slug,
            [
              'status: ' + health.status,
              'blocking: ' + (health.blockingSourceCount || 0),
              'warnings: ' + (health.issueSummary?.warningCount || 0),
              '',
              ...(lines.length ? lines : ['ไม่มี source issue']),
            ].join('\n')
          );
        } catch (err) {
          this.setConsole('error', 'Issue load failed', err.message);
        } finally {
          btn.disabled = false;
          AdminUi.setButton(btn, 'info', 'ปัญหา');
        }
      });
    });

    page.querySelectorAll('.import-inspect-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const slug = btn.dataset.slug || '';
        const num = btn.dataset.num || '1';
        const slugEl = document.getElementById('inspect-slug');
        const numEl = document.getElementById('inspect-num');
        if (slugEl) slugEl.value = slug;
        if (numEl) numEl.value = num;
        document.getElementById('inspect-run')?.click();
      });
    });

    page.querySelectorAll('.import-reimport-range-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const slug = btn.dataset.slug || '';
        const range = btn.dataset.range || '';
        const importSlugInput = document.getElementById('import-target-slug');
        const importRangeInput = document.getElementById('import-target-range');
        if (importSlugInput) importSlugInput.value = slug;
        if (importRangeInput) importRangeInput.value = range;
        this.setConsole('idle', 'Re-import range ready', 'slug: ' + slug + '\nrange: ' + (range || '-') + '\nใส่ URL แล้วกด Preview เพื่อดึง source ใหม่เฉพาะช่วงนี้');
        document.getElementById('import-url')?.focus();
      });
    });

    page.querySelectorAll('.import-repair-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const slug = btn.dataset.slug;
        if (!slug) return;
        btn.disabled = true;
        AdminUi.setButton(btn, 'search', 'Checking...');
        this.setConsole('running', 'Repair preview', 'Checking source titles, noise lines, and chapter index for ' + slug + '...');
        try {
          const preview = await Api.repairImport(slug, 'all', { dryRun: true });
          const previewRepair = preview.data?.repair || {};
          const previewMessage = formatImportRepairSummary(slug, previewRepair);
          this.setConsole('idle', 'Repair preview', previewMessage);
          if (!confirm('Repair preview\n\n' + previewMessage + '\n\nApply these changes?')) {
            btn.disabled = false;
            AdminUi.setButton(btn, 'settings', 'ซ่อม');
            return;
          }

          AdminUi.setButton(btn, 'settings', 'Repairing...');
          this.setConsole('running', 'Repair running', 'Applying source title/noise repairs and rebuilding chapter index for ' + slug + '...');
          const result = await Api.repairImport(slug, 'all');
          const repair = result.data?.repair || {};
          const message = formatImportRepairSummary(slug, repair);
          this.setConsole('success', 'Repair complete', message);
          Ui.showToast('ซ่อมแล้ว: title ' + (repair.titlesRepaired || 0) + ', index rebuilt');
          btn.disabled = false;
          AdminUi.setButton(btn, 'settings', 'Done');
        } catch (err) {
          this.setConsole('error', 'Repair failed', err.message);
          Ui.showToast(err.message, 'error');
          btn.disabled = false;
          AdminUi.setButton(btn, 'settings', 'ซ่อม');
        }
      });
    });

    page.querySelectorAll('.import-recover-toc-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const slug = btn.dataset.slug;
        if (!slug) return;
        btn.disabled = true;
        AdminUi.setButton(btn, 'search', 'Checking...');
        this.setConsole('running', 'TOC recovery preview', 'Fetching source table of contents for ' + slug + '...');
        try {
          const preview = this._data(await Api.recoverImportToc(slug, { dryRun: true }));
          const previewMessage = formatTocRecoverySummary(slug, preview);
          this.setConsole('idle', 'TOC recovery preview', previewMessage);
          if (!preview.chapterCount) {
            Ui.showToast('ไม่พบตอนจากสารบัญต้นทาง', 'error');
            btn.disabled = false;
            AdminUi.setButton(btn, 'library', 'กู้ TOC');
            return;
          }
          if (!confirm('TOC recovery preview\n\n' + previewMessage + '\n\nSave this toc.json?')) {
            btn.disabled = false;
            AdminUi.setButton(btn, 'library', 'กู้ TOC');
            return;
          }

          AdminUi.setButton(btn, 'library', 'Saving...');
          this.setConsole('running', 'TOC recovery running', 'Saving toc.json for ' + slug + '...');
          const result = this._data(await Api.recoverImportToc(slug, { dryRun: false }));
          this.setConsole('success', 'TOC recovery complete', formatTocRecoverySummary(slug, result));
          Ui.showToast('สร้าง toc.json แล้ว กด Repair เพื่อซ่อม generic title ต่อ');
          btn.disabled = false;
          AdminUi.setButton(btn, 'library', 'Done');
        } catch (err) {
          this.setConsole('error', 'TOC recovery failed', err.message);
          Ui.showToast(err.message, 'error');
          btn.disabled = false;
          AdminUi.setButton(btn, 'library', 'กู้ TOC');
        }
      });
    });

    document.getElementById('inspect-run')?.addEventListener('click', async () => {
      const btn = document.getElementById('inspect-run');
      const slug = document.getElementById('inspect-slug')?.value || '';
      const num = document.getElementById('inspect-num')?.value || '1';
      if (!slug) {
        Ui.showToast('ยังไม่มี source ให้ inspect', 'error');
        return;
      }
      btn.disabled = true;
      AdminUi.setButton(btn, 'search', 'Inspecting...');
      try {
        const data = this._data(await Api.inspectSource(slug, num));
        this._renderInspection(data);
      } catch (err) {
        Ui.showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
        AdminUi.setButton(btn, 'search', 'ตรวจ source');
      }
    });

    document.getElementById('import-preview-btn')?.addEventListener('click', async () => {
      const btn = document.getElementById('import-preview-btn');
      const url = document.getElementById('import-url')?.value.trim();
      const site = document.getElementById('import-site')?.value || 'auto';
      if (!url) {
        Ui.showToast('กรุณาระบุ URL', 'error');
        return;
      }
      btn.disabled = true;
      AdminUi.setButton(btn, 'search', 'Loading...');
      this.setConsole('running', 'Preview running', 'Fetching table of contents and sample chapter...');
      try {
        const data = this._data(await Api.importPreview({ url, site }));
        this._preview = data;
        this._renderPreview(data);
        const diag = data.diagnostics || {};
        this.setConsole('success', 'Preview ready', `${data.chapterCount || 0} chapters found\nsample content: ${diag.hasSampleContent ? 'yes' : 'no'}\nrecommend import: ${diag.recommendImport ? 'yes' : 'review first'}`);
      } catch (err) {
        this.setConsole('error', 'Preview failed', err.message);
        Ui.showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
        AdminUi.setButton(btn, 'search', 'ดูตัวอย่าง');
      }
    });

    document.getElementById('paste-run')?.addEventListener('click', async () => {
      const btn = document.getElementById('paste-run');
      const slug = document.getElementById('paste-slug')?.value.trim();
      const title = document.getElementById('paste-title')?.value.trim();
      const sourceLang = document.getElementById('paste-lang')?.value.trim() || 'cn';
      const splitRule = document.getElementById('paste-rule')?.value.trim();
      const content = document.getElementById('paste-content')?.value || '';
      const force = document.getElementById('paste-force')?.checked;
      if (!slug || !content.trim()) {
        Ui.showToast('กรุณาระบุ slug และข้อความ', 'error');
        return;
      }
      btn.disabled = true;
      AdminUi.setButton(btn, 'library', 'กำลังบันทึก...');
      this.setConsole('running', 'Paste import running', 'Cleaning pasted source...');
      try {
        const result = this._data(await Api.importPaste({ slug, title, sourceLang, splitRule, content, force }));
        this.setConsole('success', 'Paste import complete', this._summary(result));
        Ui.showToast('บันทึก source สำเร็จ');
      } catch (err) {
        this.setConsole('error', 'Paste import failed', err.message);
        Ui.showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
        AdminUi.setButton(btn, 'library', 'บันทึก source');
      }
    });
  }
};

// ── ADMIN TRANSLATE PAGE (Simplified) ⭐ ──────────────────────────
const AdminTranslatePage = {
  setConsole(state, title, message) {
    AdminUi.setConsole('translate', state, title, message);
  },

  _formatBatchResult(result = {}) {
    const summary = result.summary || {};
    const chapters = result.chapters || summary.chapters || [];
    const lines = [
      `[SUMMARY] translated=${summary.passed || 0} needs_review/failed=${summary.failed || 0} total=${summary.total || 0}`,
    ];
    for (const ch of chapters.slice(0, 80)) {
      const label = ch.status === 'ok' ? 'translated' : ch.status;
      const score = ch.score != null ? ` score=${ch.score}` : '';
      const issues = (ch.hardFailures || []).slice(0, 2).join('; ');
      const reason = ch.reason || issues || 'ok';
      lines.push(`- ch ${ch.ch || '-'}: ${label}${score} · ${reason}`);
    }
    if (chapters.length > 80) lines.push(`...and ${chapters.length - 80} more chapter results`);
    return lines.join('\n');
  },

  _rangeFromNums(nums = []) {
    const sorted = [...new Set(nums.map(n => parseInt(n, 10)).filter(Number.isFinite))].sort((a, b) => a - b);
    const ranges = [];
    for (let i = 0; i < sorted.length; i++) {
      const start = sorted[i];
      let end = start;
      while (i + 1 < sorted.length && sorted[i + 1] === end + 1) {
        end = sorted[++i];
      }
      ranges.push(start === end ? String(start) : `${start}-${end}`);
    }
    return ranges.join(',');
  },

  _chapterStatus(ch = {}, sourceIssue = null, resultIssue = null) {
    const resultStatus = resultIssue?.status;
    if (resultStatus && resultStatus !== 'ok') return resultStatus === 'failed' ? 'failed' : 'needs_review';
    const blockingIssue = sourceIssue?.issues?.some(issue => issue.severity === 'error');
    if (blockingIssue) return 'source_not_ready';
    const quality = ch.qualityRecord || ch.quality;
    if (quality && quality.passed === false) return 'needs_review';
    if (ch.isTranslated || ch.status === 'translated') return 'translated';
    return 'untranslated';
  },

  _statusBadge(status) {
    const map = {
      translated: ['แปลแล้ว', 'c-badge c-badge--teal'],
      untranslated: ['ยังไม่แปล', 'c-badge c-badge--gray'],
      needs_review: ['ควรดู', 'c-badge c-badge--amber'],
      failed: ['ล้มเหลว', 'c-badge c-badge--red'],
      source_not_ready: ['source error', 'c-badge c-badge--red'],
    };
    return map[status] || [status || '-', 'c-badge c-badge--gray'];
  },

  _qualityText(ch = {}, resultIssue = null) {
    const quality = ch.qualityRecord || ch.quality || {};
    const hardFailures = resultIssue?.hardFailures || quality.hardFailures || [];
    const warnings = resultIssue?.warnings || quality.warnings || [];
    const score = resultIssue?.score ?? quality.score ?? ch.score;
    const parts = [];
    if (score !== null && score !== undefined) parts.push(`score ${score}`);
    if (quality.lengthRatio) parts.push(`len ${Math.round(quality.lengthRatio * 100)}%`);
    if (hardFailures.length) parts.push(hardFailures.slice(0, 2).join(', '));
    else if (warnings.length) parts.push('warn: ' + warnings.slice(0, 2).join(', '));
    return parts.join(' · ') || '-';
  },

  async render(params) {
    const page = Ui.$('page-admin-translate');
    if (!page) return;
    Ui.showSkeleton('page-admin-translate');

    try {
      const [novels, translationHealth, importHealth, llmConfig] = await Promise.all([
        Api.getNovels(),
        Api.getTranslationHealth().catch(() => ({ data: { buckets: {} } })),
        Api.getImportHealth().catch(() => ({ data: { novels: [] } })),
        Api.getLlmConfig().catch(() => ({ providers: [] })),
      ]);
      const buckets = translationHealth.data?.buckets || {};
      const importHealthBySlug = {};
      for (const item of importHealth.data?.novels || []) importHealthBySlug[item.slug] = item;
      const bucketStat = (name) => buckets[name]?.count || 0;
      const batchLogs = translationHealth.data?.batchLogs || [];
      const activeBatch = batchLogs[0] || null;
      const latestFailed = (buckets.failed?.latest || buckets.needs_review?.latest || [])
        .slice(0, 3)
        .map(item => Ui.esc(item.name))
        .join(', ');
      const batchFailures = activeBatch?.failures?.slice(0, 5).map(item =>
        '<li><span class="c-admin-translate__chapter">ตอน ' + Ui.esc(item.chapter || '-') + '</span>' +
        '<span>' + Ui.esc(item.reason || '-') + '</span></li>'
      ).join('') || '';
      const batchRecent = activeBatch?.recentLines?.map(line => Ui.esc(line)).join('\n') || '';
      const modelProviderById = {};
      const modelOptions = (llmConfig.providers || []).flatMap(provider =>
        (provider.models || []).map(model => {
          modelProviderById[model.id] = provider.id;
          return '<option value="' + Ui.esc(model.id) + '" label="' + Ui.esc((provider.label || provider.id) + ' · ' + (model.label || model.id)) + '"></option>';
        })
      ).join('');

      const novelOptions = novels.map(n => {
        const h = importHealthBySlug[n.slug] || {};
        const label = h.status === 'error' ? 'source error' : (h.status === 'warn' ? 'source warn' : 'ready');
        return `<option value="${Ui.esc(n.slug)}" data-source-status="${Ui.esc(h.status || 'ok')}">${Ui.esc(Ui.displayTitle(n) || n.slug)} · ${Ui.esc(label)}</option>`;
      }
      ).join('');

      let html = `
      <div class="c-container">
        ${Ui.adminNav('translate')}
        
        <div class="c-admin-translate">
          <!-- INFO: setting up AI → go to Provider wizard -->
          <div class="c-card c-admin-translate__provider-note">
            <p class="c-admin-translate__provider-note-text">🤖 ตั้งค่า Provider / Model ที่ <a href="#admin/provider" data-nav><strong>หน้า Provider</strong></a></p>
          </div>

          <div class="c-card c-admin-translate__panel">
            <div class="c-admin-translate__console-head">
              <h3 class="c-admin-translate__title">Translation Health</h3>
              <button class="c-btn c-btn--xs c-btn--secondary" id="translate-health-refresh" type="button">${Ui.icon('search', 'xs')}<span>รีเฟรช</span></button>
            </div>
            <div class="c-stats c-admin-translate__health-stats">
              <div class="c-stat"><span class="c-stat__num">${bucketStat('active')}</span><span class="c-stat__label">active</span></div>
              <div class="c-stat"><span class="c-stat__num c-stat__num--success">${bucketStat('done')}</span><span class="c-stat__label">done</span></div>
              <div class="c-stat"><span class="c-stat__num c-stat__num--warning">${bucketStat('needs_review')}</span><span class="c-stat__label">needs review</span></div>
              <div class="c-stat"><span class="c-stat__num">${bucketStat('failed')}</span><span class="c-stat__label">failed</span></div>
            </div>
            <p class="u-text-muted">${latestFailed ? 'ล่าสุดที่ต้องดู: ' + latestFailed : 'ยังไม่มีรายการ failed/needs_review ล่าสุด'}</p>
            ${activeBatch ? `
            <div class="c-admin-translate__batch">
              <div class="c-admin-translate__batch-head">
                <div>
                  <strong>${Ui.esc(activeBatch.name)}</strong>
                  <p class="u-text-muted">ตอน ${Ui.esc(activeBatch.current || 0)} / ${Ui.esc(activeBatch.total || 0)} · active chapter ${Ui.esc(activeBatch.activeChapter || '-')}</p>
                </div>
                <span class="c-badge c-badge--amber">${Ui.esc(activeBatch.percent || 0)}%</span>
              </div>
              <progress class="c-admin-translate__progress" value="${Ui.esc(activeBatch.percent || 0)}" max="100"></progress>
              <div class="c-admin-translate__batch-metrics">
                <span>ผ่าน ${Ui.esc(activeBatch.passed || 0)}</span>
                <span>ล้มเหลว ${Ui.esc(activeBatch.failed || 0)}</span>
                <span>timeout ${Ui.esc(activeBatch.timeout || 0)}</span>
              </div>
              <div class="c-admin-translate__batch-grid">
                <div>
                  <h4 class="c-admin-translate__subhead">ปัญหาล่าสุด</h4>
                  <ul class="c-admin-translate__failure-list">${batchFailures || '<li class="u-text-muted">ยังไม่มีปัญหาใน log นี้</li>'}</ul>
                </div>
                <div>
                  <h4 class="c-admin-translate__subhead">Recent log</h4>
                  <pre class="c-admin-translate__mini-log">${batchRecent || '—'}</pre>
                </div>
              </div>
            </div>` : '<p class="u-text-muted">ยังไม่พบ batch log</p>'}
          </div>

          <!-- BATCH TRANSLATION PANEL (simplified) -->
          <div class="c-card c-admin-translate__panel">
            <h3 class="c-admin-translate__title">สั่งการแปลนิยาย</h3>
            <div class="c-form c-admin-translate__form">
              <div class="c-admin-translate__grid">
                <div class="c-form__group">
                  <label class="c-form__label">เลือกนิยาย</label>
                  <select class="c-form__select c-form__select--compact" id="translate-batch-novel">
                    ${novelOptions}
                  </select>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">ช่วงตอน (เช่น 5-10 หรือ 5)</label>
                  <input type="text" class="c-form__input c-form__input--compact" id="translate-batch-range" placeholder="เช่น 1-10" />
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">แปลพร้อมกัน</label>
                  <select class="c-form__select c-form__select--compact" id="translate-batch-concurrent">
                    <option value="1">1 ตอน (default)</option>
                    <option value="2">2 ตอน</option>
                    <option value="3">3 ตอน</option>
                  </select>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">Prompt preset</label>
                  <select class="c-form__select c-form__select--compact" id="translate-prompt-profile">
                    <option value="faithful_default">Faithful default</option>
                    <option value="flowing_thai">Flowing Thai</option>
                    <option value="strict_literal">Strict literal</option>
                  </select>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">Model override</label>
                  <input type="text" class="c-form__input c-form__input--compact" id="translate-model-override" list="translate-model-list" placeholder="ค้นหา model หรือเว้นว่างเพื่อใช้ Provider default" />
                  <datalist id="translate-model-list">${modelOptions}</datalist>
                </div>
              </div>
              <div id="translate-source-health" class="c-admin-translate__source-health"></div>
              <div class="c-admin-translate__actions">
                <button class="c-btn c-btn--primary" id="translate-batch-run-btn" type="button">${Ui.icon('book', 'xs')}<span>เริ่มแปล</span></button>
                <label class="c-admin-import__check"><input id="translate-force-source" type="checkbox"> force แปลแม้ source error</label>
              </div>
              <div class="c-admin-translate__chapter-panel">
                <div class="c-admin-translate__chapter-head">
                  <div>
                    <h4 class="c-admin-translate__subhead">เลือกตอนที่จะแปล</h4>
                    <p class="u-text-muted" id="translate-chapter-summary">กำลังโหลดรายการตอน...</p>
                  </div>
                  <div class="c-admin-translate__chapter-actions">
                    <button class="c-btn c-btn--xs c-btn--secondary" id="translate-select-untranslated" type="button">${Ui.icon('search', 'xs')}<span>ยังไม่แปล</span></button>
                    <button class="c-btn c-btn--xs c-btn--secondary" id="translate-select-review" type="button">${Ui.icon('search', 'xs')}<span>ควรดู/ล้มเหลว</span></button>
                    <button class="c-btn c-btn--xs c-btn--ghost" id="translate-clear-selection" type="button">${Ui.icon('info', 'xs')}<span>ล้าง</span></button>
                    <button class="c-btn c-btn--xs c-btn--primary" id="translate-run-selected" type="button">${Ui.icon('book', 'xs')}<span>แปลที่เลือก</span></button>
                  </div>
                </div>
                <div id="translate-chapter-table" class="c-admin-translate__chapter-table" aria-live="polite">
                  <div class="c-admin-translate__chapter-empty">กำลังโหลด...</div>
                </div>
              </div>
            </div>
          </div>

          <!-- TRANSLATION CONSOLE -->
          <div class="c-card c-admin-translate__panel" id="translate-console-card" hidden>
            <div class="c-admin-translate__console-head">
              <h4 class="c-admin-translate__console-title" id="translate-console-title">พร้อมแปล</h4>
              <span id="translate-console-badge" class="c-badge c-badge--teal">กำลังประมวลผล</span>
            </div>
            <pre id="translate-console-output" class="c-admin-translate__console" aria-live="polite">ระบบพร้อมทำงาน</pre>
          </div>

        </div>
      </div>`;

      page.innerHTML = html;
      document.getElementById('translate-health-refresh')?.addEventListener('click', () => this.render(params));

      const updateSourceHealth = () => {
        const slugVal = document.getElementById('translate-batch-novel')?.value || '';
        const h = importHealthBySlug[slugVal] || {};
        const box = document.getElementById('translate-source-health');
        if (!box) return;
        const status = h.status || 'ok';
        const cls = status === 'error' ? 'c-badge c-badge--red' : (status === 'warn' ? 'c-badge c-badge--amber' : 'c-badge c-badge--teal');
        const issueText = this._sourceIssueText ? this._sourceIssueText(h) : '';
        box.innerHTML = '<span class="' + cls + '">' + Ui.esc(status === 'error' ? 'source error' : (status === 'warn' ? 'source warning' : 'source ready')) + '</span>' +
          '<span>' + Ui.esc(issueText || 'พร้อมแปล') + '</span>' +
          (status !== 'ok' ? '<a class="c-btn c-btn--xs c-btn--ghost" href="#admin/import/' + Ui.esc(slugVal) + '" data-nav>' + Ui.icon('info', 'xs') + '<span>ดูสุขภาพนำเข้า</span></a>' : '');
      };
      this._sourceIssueText = (h = {}) => {
        const byCode = h.issueSummary?.byCode || {};
        return Object.entries(byCode).filter(([, count]) => count > 0).slice(0, 3).map(([code, count]) => code + ' × ' + count).join(', ');
      };
      document.getElementById('translate-batch-novel')?.addEventListener('change', updateSourceHealth);
      updateSourceHealth();

      let tableChapters = [];
      let sourceIssueByNum = {};
      let lastResultByNum = {};
      const selectedNums = new Set();

      const renderChapterTable = () => {
        const table = document.getElementById('translate-chapter-table');
        const summaryEl = document.getElementById('translate-chapter-summary');
        if (!table || !summaryEl) return;
        if (!tableChapters.length) {
          summaryEl.textContent = 'ยังไม่มีตอนในนิยายนี้';
          table.innerHTML = '<div class="c-admin-translate__chapter-empty">ไม่มีตอนให้แสดง</div>';
          return;
        }
        const counts = { translated: 0, untranslated: 0, needs_review: 0, failed: 0, source_not_ready: 0 };
        for (const ch of tableChapters) {
          const status = AdminTranslatePage._chapterStatus(ch, sourceIssueByNum[ch.num], lastResultByNum[ch.num]);
          counts[status] = (counts[status] || 0) + 1;
        }
        summaryEl.textContent = `ทั้งหมด ${tableChapters.length} ตอน · แปลแล้ว ${counts.translated || 0} · ยังไม่แปล ${counts.untranslated || 0} · ควรดู ${counts.needs_review || 0} · source error ${counts.source_not_ready || 0} · เลือก ${selectedNums.size}`;

        const rows = tableChapters.map(ch => {
          const resultIssue = lastResultByNum[ch.num];
          const status = AdminTranslatePage._chapterStatus(ch, sourceIssueByNum[ch.num], resultIssue);
          const [label, badgeClass] = AdminTranslatePage._statusBadge(status);
          const checked = selectedNums.has(ch.num) ? ' checked' : '';
          const sourceIssue = sourceIssueByNum[ch.num];
          const issueText = resultIssue?.reason
            || (sourceIssue?.issues || []).map(issue => issue.code).slice(0, 2).join(', ');
          const qualityText = AdminTranslatePage._qualityText(ch, resultIssue);
          const modelText = ch.model && ch.model !== 'unknown' ? ch.model : '';
          return `<tr data-status="${Ui.esc(status)}">
            <td><input class="translate-chapter-check" type="checkbox" data-num="${Ui.esc(ch.num)}"${checked} aria-label="เลือกตอน ${Ui.esc(ch.num)}"></td>
            <td class="c-admin-translate__chapter-num">${Ui.esc(ch.num)}</td>
            <td class="c-admin-translate__chapter-title">${Ui.esc(ch.title || ('ตอนที่ ' + ch.num))}</td>
            <td><span class="${badgeClass}">${Ui.esc(label)}</span></td>
            <td class="c-admin-translate__quality">${Ui.esc(qualityText)}</td>
            <td class="c-admin-translate__model">${Ui.esc(modelText || '-')}</td>
            <td class="c-admin-translate__issue">${Ui.esc(issueText || '-')}</td>
          </tr>`;
        }).join('');
        const allChecked = tableChapters.length > 0 && tableChapters.every(ch => selectedNums.has(ch.num)) ? ' checked' : '';
        table.innerHTML = `<div class="c-admin-translate__table-wrap">
          <table class="c-table c-admin-translate__table">
            <thead>
              <tr>
                <th><input id="translate-select-all" type="checkbox"${allChecked} aria-label="เลือกทุกตอน"></th>
                <th>ตอน</th>
                <th>ชื่อ</th>
                <th>สถานะ</th>
                <th>คุณภาพ</th>
                <th>model</th>
                <th>ปัญหา</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
      };

      const syncRangeFromSelection = () => {
        const range = AdminTranslatePage._rangeFromNums([...selectedNums]);
        const input = document.getElementById('translate-batch-range');
        if (input) input.value = range;
        renderChapterTable();
        return range;
      };

      const loadChapterTable = async (preserveResults = false) => {
        const slugVal = document.getElementById('translate-batch-novel')?.value || '';
        const table = document.getElementById('translate-chapter-table');
        const summaryEl = document.getElementById('translate-chapter-summary');
        if (!slugVal || !table || !summaryEl) return;
        summaryEl.textContent = 'กำลังโหลดรายการตอน...';
        table.innerHTML = '<div class="c-admin-translate__chapter-empty">กำลังโหลด...</div>';
        try {
          const [chapters, healthResp] = await Promise.all([
            Api.getChapters(slugVal, { withQuality: true }),
            Api.getImportHealth(slugVal, { includeChapters: true }).catch(() => ({ data: { chapters: [] } })),
          ]);
          tableChapters = chapters || [];
          sourceIssueByNum = {};
          for (const ch of healthResp.data?.chapters || []) sourceIssueByNum[ch.num] = ch;
          selectedNums.clear();
          if (!preserveResults) lastResultByNum = {};
          renderChapterTable();
        } catch (err) {
          summaryEl.textContent = 'โหลดรายการตอนไม่สำเร็จ';
          table.innerHTML = '<div class="c-admin-translate__chapter-empty">โหลดไม่สำเร็จ: ' + Ui.esc(err.message) + '</div>';
        }
      };

      const selectMatching = (predicate) => {
        selectedNums.clear();
        for (const ch of tableChapters) {
          const status = AdminTranslatePage._chapterStatus(ch, sourceIssueByNum[ch.num], lastResultByNum[ch.num]);
          if (predicate(status, ch)) selectedNums.add(ch.num);
        }
        syncRangeFromSelection();
      };

      document.getElementById('translate-chapter-table')?.addEventListener('change', (event) => {
        const checkbox = event.target.closest('input[type="checkbox"]');
        if (!checkbox) return;
        if (checkbox.id === 'translate-select-all') {
          selectedNums.clear();
          if (checkbox.checked) for (const ch of tableChapters) selectedNums.add(ch.num);
        } else if (checkbox.classList.contains('translate-chapter-check')) {
          const num = parseInt(checkbox.dataset.num, 10);
          if (Number.isFinite(num)) {
            if (checkbox.checked) selectedNums.add(num);
            else selectedNums.delete(num);
          }
        }
        syncRangeFromSelection();
      });

      document.getElementById('translate-select-untranslated')?.addEventListener('click', () => {
        selectMatching(status => status === 'untranslated');
      });
      document.getElementById('translate-select-review')?.addEventListener('click', () => {
        selectMatching(status => status === 'needs_review' || status === 'failed');
      });
      document.getElementById('translate-clear-selection')?.addEventListener('click', () => {
        selectedNums.clear();
        syncRangeFromSelection();
      });

      document.getElementById('translate-batch-novel')?.addEventListener('change', () => {
        updateSourceHealth();
        loadChapterTable();
      });
      loadChapterTable();

      // ── Bind Batch Translation Event
      const runBtn = document.getElementById('translate-batch-run-btn');
      const runBatch = async (rangeOverride = '') => {
          const slugVal = document.getElementById('translate-batch-novel').value;
          const rangeVal = rangeOverride || document.getElementById('translate-batch-range').value;
          const concurrentVal = parseInt(document.getElementById('translate-batch-concurrent').value, 10);
          const promptProfile = document.getElementById('translate-prompt-profile')?.value || 'faithful_default';
          const modelOverride = document.getElementById('translate-model-override')?.value.trim() || '';
          const forceSource = document.getElementById('translate-force-source')?.checked === true;
          const selectedHealth = importHealthBySlug[slugVal] || {};

          if (!rangeVal.trim()) {
            AdminTranslatePage.setConsole('error', 'ยังไม่ได้ระบุช่วงตอน', 'กรุณากรอกช่วงตอนที่ต้องการสั่งแปล เช่น 5-10 หรือ 5');
            Ui.showToast('กรุณากรอกช่วงตอนที่ต้องการสั่งแปล', 'error');
            return;
          }
          if (selectedHealth.status === 'error' && !forceSource) {
            const issueText = this._sourceIssueText(selectedHealth);
            AdminTranslatePage.setConsole('error', 'Source ยังไม่พร้อมแปล', issueText || 'พบ source error ในเรื่องนี้');
            Ui.showToast('Source มี error ต้องซ่อมหรือกด force ก่อนแปล', 'error');
            return;
          }

          AdminTranslatePage.setConsole(
            'running',
            `รันการแปลช่วงตอน: ${rangeVal}`,
            `กำลังส่งคำสั่งแปล\\nนิยาย: ${slugVal}`
          );

          try {
            if (runBtn) {
              runBtn.disabled = true;
              AdminUi.setButton(runBtn, 'book', 'กำลังดำเนินการแปล...');
            }

            const options = { force: forceSource, promptProfile };
            if (modelOverride) {
              options.model = modelOverride;
              if (modelProviderById[modelOverride]) options.provider = modelProviderById[modelOverride];
            }
            const res = await Api.translateBatch(slugVal, rangeVal, concurrentVal, options);
            const result = res.data || res;

            if (res.ok && result.success) {
              const batchResult = result.result || result;
              for (const ch of batchResult.chapters || []) {
                const num = parseInt(ch.ch || ch.num, 10);
                if (Number.isFinite(num)) lastResultByNum[num] = ch;
              }
              AdminTranslatePage.setConsole(
                'success',
                `แปลเสร็จสิ้น: ${rangeVal}`,
                AdminTranslatePage._formatBatchResult(batchResult)
              );
              Api.invalidateAll(slugVal);
              await loadChapterTable(true);
              Ui.showToast('แปลกลุ่มช่วงตอนสำเร็จแล้ว');
            } else {
              throw new Error(res.error?.message || 'แปลไม่สำเร็จ');
            }
          } catch (err) {
            const failedSummary = err.details?.summary || err.payload?.error?.details?.summary || {};
            const failedChapters = failedSummary.chapters || err.details?.chapters || [];
            for (const ch of failedChapters) {
              const num = parseInt(ch.ch || ch.num, 10);
              if (Number.isFinite(num)) lastResultByNum[num] = ch;
            }
            if (failedChapters.length) renderChapterTable();
            AdminTranslatePage.setConsole(
              'error',
              `แปลไม่สำเร็จ: ${rangeVal}`,
              failedChapters.length
                ? AdminTranslatePage._formatBatchResult({ summary: failedSummary, chapters: failedChapters })
                : `[ERROR] การแปลเกิดข้อผิดพลาด:\\n\\n${err.message}`
            );
            Ui.showToast('การแปลเกิดข้อผิดพลาด: ' + err.message, 'error');
          } finally {
            if (runBtn) {
              runBtn.disabled = false;
              AdminUi.setButton(runBtn, 'book', 'เริ่มแปล');
            }
          }
      };
      if (runBtn) runBtn.addEventListener('click', () => runBatch());
      document.getElementById('translate-run-selected')?.addEventListener('click', () => {
        const range = AdminTranslatePage._rangeFromNums([...selectedNums]);
        if (!range) {
          Ui.showToast('เลือกตอนก่อนสั่งแปล', 'error');
          return;
        }
        runBatch(range);
      });

    } catch (err) {
      Ui.showError(page, 'โหลดหน้าแปลล้มเหลว', err.message);
    }
  }
};

const AdminProviderPage = {
  _promise: null,
  async render(params) {
    if (!window.AdminProviderPage) {
      if (!this._promise) {
        this._promise = new Promise((resolve, reject) => {
          const script = document.createElement('script');
          script.src = '/js/pages/admin-provider.js?_v=20260629_provider_split';
          script.async = false;
          script.onload = resolve;
          script.onerror = () => reject(new Error('Failed to load admin-provider.js'));
          document.head.appendChild(script);
        });
      }
      await this._promise;
    }
    return window.AdminProviderPage.render(params);
  },
};

// ── Lazy-load registration ─────────────────────────────────────────
// admin.js is loaded on demand by app.js Router (see ensureAdminLoaded()).
// Register the real 'admin' route handler at module load so the router
// can resolve #admin/* URLs without re-loading a second copy of admin.js.
Router.register('admin', (p) => {
  const sub = p && p.page ? p.page : 'dash';
  const adminRoutes = {
    'dash': AdminDashboardPage,
    'novels': AdminNovelsPage,
    'chapters': AdminChaptersPage,
    'glossary': AdminGlossaryPage,
    'import': AdminImportPage,
    'novel-edit': AdminNovelEditPage,
    'logs': AdminLogsPage,
    'translate': AdminTranslatePage,
    'provider': AdminProviderPage,
  };
  const handler = adminRoutes[sub] || AdminDashboardPage;
  handler.render(p);
});
