/* ═══════════════════════════════════════════════════════════════════════
   admin.js — Admin Dashboard, Novels, Chapters, Glossary Pages
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */


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
        '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">ระบบหลังบ้าน</h3></div>' +
        // ── Stats ──
        '<div class="c-stats">' +
        '<div class="c-stat"><span class="c-stat__num">' + novels.length + '</span><span class="c-stat__label">นิยาย</span></div>' +
        '<div class="c-stat"><span class="c-stat__num">' + totalChapters + '</span><span class="c-stat__label">ตอนทั้งหมด</span></div>' +
        '<div class="c-stat"><span class="c-stat__num" style="color:var(--c-success);">' + translatedChapters + '</span><span class="c-stat__label">แปลแล้ว</span></div>' +
        '<div class="c-stat"><span class="c-stat__num" style="color:var(--c-warning);">' + untranslated + '</span><span class="c-stat__label">รอแปล</span></div>' +
        '</div>' +
        // ── Health Summary ──
        '<div class="c-health-row">' +
        '<span class="c-badge c-badge--teal">✅ ระบบปกติ</span>' +
        '<span class="c-badge' + (translatedChapters > 0 ? ' c-badge--teal' : ' c-badge--gray') + '">📖 แปลแล้ว ' + translatedChapters + ' ตอน</span>' +
        '<span class="c-badge' + (untranslated > 0 ? ' c-badge--amber' : ' c-badge--gray') + '">📄 รอแปล ' + untranslated + ' ตอน</span>' +
        '<a href="#admin/jobs" class="c-badge c-badge--gray" data-nav style="text-decoration:none;cursor:pointer;">📋 ดูคิวงาน →</a>' +
        '</div>' +
        '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">จัดการระบบ</h3></div>' +
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:var(--space-sm);">' +
        '<a href="#admin/novels" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <svg style="width:28px;height:28px;flex-shrink:0;color:var(--c-accent);"><use xlink:href="#icon-library"/></svg><div><div style="font-weight:600;color:var(--c-text-primary);">จัดการนิยาย</div><div style="font-size:12px;color:var(--c-text-muted);">' + Object.values(statusCounts).reduce((a,b)=>a+b,0) + ' เรื่อง</div></div></a>' +
        '<a href="#admin/chapters" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <svg style="width:28px;height:28px;flex-shrink:0;color:var(--c-accent);"><use xlink:href="#icon-book"/></svg><div><div style="font-weight:600;color:var(--c-text-primary);">จัดการตอน</div><div style="font-size:12px;color:var(--c-text-muted);">' + untranslated + ' ตอนที่ยังไม่แปล</div></div></a>' +
        '<a href="#admin/glossary" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <svg style="width:28px;height:28px;flex-shrink:0;color:var(--c-accent-2);"><use xlink:href="#icon-bookmarks"/></svg><div><div style="font-weight:600;color:var(--c-text-primary);">จัดการคำศัพท์</div><div style="font-size:12px;color:var(--c-text-muted);">Glossary / NPC names</div></div></a>' +
        '</div>' +
        '<div class="c-section__header" style="margin-top:var(--space-lg);"><h3 class="c-section__title">เครื่องมือ</h3></div>' +
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:var(--space-sm);">' +
        '<a href="#admin/import" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <svg style="width:28px;height:28px;flex-shrink:0;color:var(--c-accent);"><use xlink:href="#icon-arrow-right"/></svg><div><div style="font-weight:600;color:var(--c-text-primary);">นำเข้านิยาย</div><div style="font-size:12px;color:var(--c-text-muted);">เพิ่มเรื่องใหม่ / นำเข้าตอน</div></div></a>' +
        '<a href="#admin/jobs" class="c-card" style="display:flex;align-items:center;gap:12px;padding:16px;text-decoration:none;" data-nav>' +
        '  <svg style="width:28px;height:28px;flex-shrink:0;color:var(--c-accent);"><use xlink:href="#icon-shield"/></svg><div><div style="font-weight:600;color:var(--c-text-primary);">คิวแปล AI</div><div style="font-size:12px;color:var(--c-text-muted);">จัดการ queue การแปล</div></div></a>' +
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
      let html = '<div class="c-container">' + Ui.adminNav('novels') +
        '<div style="display:flex; justify-content:space-between; align-items:center; margin-top:var(--space-md);"><h3 style="margin:0; font-size:var(--text-md); font-weight:600; color:var(--c-text-primary);">📚 รายการนิยายทั้งหมด</h3><a href="#admin/import" class="c-btn c-btn--primary c-btn--sm" data-nav style="text-decoration:none; display:inline-flex; align-items:center; gap:6px; min-height:32px; font-size:12px; padding:4px 12px;">📥 นำเข้านิยายใหม่</a></div>' +
        '<div class="c-table-wrap" style="margin-top:var(--space-sm);"><table class="c-table"><thead><tr><th>Slug</th><th>ชื่อเรื่อง</th><th>ภาษา</th><th>ตอน</th><th>แปลแล้ว</th><th>สถานะ</th><th style="width: 80px; text-align: center;">การจัดการ</th></tr></thead><tbody>';
      for (const n of novels) {
        const translated = n.translatedChapters || 0;
        const total = n.totalChapters || n.chapterCount || 0;
        const statusClass = n.status === 'complete' ? 'c-badge--purple' : n.status === 'ongoing' ? 'c-badge--teal' : 'c-badge--gray';
        html += '<tr><td style="font-weight:600;font-family:var(--font-mono);">' + Ui.esc(n.slug) + '</td><td>' + Ui.esc(n.title||'') + '</td><td>' + (n.source_lang||'cn').toUpperCase() + ' → ' + (n.target_lang||'th').toUpperCase() + '</td><td style="font-family:var(--font-mono);">' + total + '</td><td style="font-family:var(--font-mono);color:var(--c-accent);">' + translated + ' (' + Math.round(translated/total*100) + '%)</td><td><span class="c-badge ' + statusClass + '">' + Ui.esc(Ui.statusMap[n.status]||'ไม่ระบุ') + '</span></td><td style="text-align: center;"><button class="c-btn c-btn--danger c-btn--xs delete-novel-btn" data-slug="' + Ui.esc(n.slug) + '" style="padding: 2px 8px; font-size: 11px; min-height: 24px;">ลบ</button></td></tr>';
      }
      html += '</tbody></table></div></div>';
      page.innerHTML = html;

      // Bind delete button events
      page.querySelectorAll('.delete-novel-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const slug = btn.dataset.slug;
          if (!slug) return;
          if (confirm('⚠️ คำเตือน: คุณต้องการลบนิยาย "' + slug + '" ใช่หรือไม่?\nการลบนี้จะทำลายโฟลเดอร์นิยาย บทแปล และศัพท์เฉพาะทั้งหมดอย่างถาวรและไม่สามารถเรียกคืนได้!')) {
            try {
              btn.disabled = true;
              btn.textContent = 'กำลังลบ...';
              await Api.deleteNovel(slug);
              Ui.showToast('ลบนิยาย "' + slug + '" เรียบร้อยแล้วค่ะ');
              // Reload page to refresh table
              await AdminNovelsPage.render(params);
            } catch (err) {
              Ui.showToast('ลบไม่สำเร็จ: ' + err.message, 'error');
              btn.disabled = false;
              btn.textContent = 'ลบ';
            }
          }
        });
      });
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
      const firstReal = novels.find(n => !n.slug?.startsWith('test-') && !n.slug?.startsWith('fixture-') && !n.slug?.startsWith('tmp-'));
      const slug = params.slug || firstReal?.slug || novels[0]?.slug;
      if (!slug) { page.innerHTML = '<div class="c-container">' + Ui.adminNav('chapters') + '<p class="u-text-muted u-p-lg">ไม่มีนิยายในระบบ</p></div>'; return; }
      const chapters = await Api.getChapters(slug);
      if (!chapters || chapters.length === 0) {
        page.innerHTML = '<div class="c-container">' + Ui.adminNav('chapters') + '<p class="u-text-muted u-p-lg">ไม่มีตอนในนิยายนี้</p></div>';
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

        let html = '<div class="c-container">' + Ui.adminNav('chapters') +
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
  _terms: [],
  _slug: '',
  _editingIndex: -1,

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
      '<div class="c-form__group" style="margin-top:var(--space-md); margin-bottom:var(--space-md); max-width:320px;">' +
        '<label class="c-form__label">เลือกนิยายเพื่อจัดการ Glossary</label>' +
        '<select class="c-form__select" id="glossary-novel-select" style="height:44px;padding:0 var(--space-sm);">' +
          novelOptions +
        '</select>' +
      '</div>' +
      '<div class="c-section__header"><h3 class="c-section__title">จัดการคลังคำศัพท์ (' + Ui.esc(this._slug) + ')</h3></div>' +
      
      // Two-column responsive layout for Forms
      '<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:var(--space-md); margin-bottom:var(--space-lg);">' +
        // Card 1: Add/Edit Term
        '<div class="c-settings-form" style="background:var(--c-bg-secondary);padding:var(--space-md);border-radius:var(--radius);">' +
          '<h4 id="glossary-form-title" class="u-mb-sm" style="font-weight:600;">เพิ่มคำศัพท์ใหม่</h4>' +
          '<div class="c-form" style="display:flex; flex-direction:column; gap:var(--space-sm);">' +
            '<div style="display:grid; grid-template-columns:1fr 1fr; gap:var(--space-sm);">' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">คำศัพท์เดิม (จีน)</label>' +
                '<input class="c-form__input" id="glossary-source" placeholder="เช่น 曹星" />' +
              '</div>' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">คำแปล (ไทย)</label>' +
                '<input class="c-form__input" id="glossary-thai" placeholder="เช่น เฉาซิง" />' +
              '</div>' +
            '</div>' +
            '<div style="display:grid; grid-template-columns:1fr 1fr; gap:var(--space-sm);">' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">ประเภท</label>' +
                '<select class="c-form__select" id="glossary-category" style="height:44px;padding:0 var(--space-sm);">' +
                  '<option value="คำศัพท์">คำศัพท์ทั่วไป</option>' +
                  '<option value="ตัวละคร">ตัวละคร</option>' +
                  '<option value="สถานที่">สถานที่</option>' +
                  '<option value="สกิล">สกิล/ทักษะ</option>' +
                  '<option value="ไอเทม">ไอเทม</option>' +
                '</select>' +
              '</div>' +
              '<div class="c-form__group">' +
                '<label class="c-form__label">การล็อก</label>' +
                '<select class="c-form__select" id="glossary-lock" style="height:44px;padding:0 var(--space-sm);">' +
                  '<option value="auto">Auto (ลื่นไหล)</option>' +
                  '<option value="locked">Locked (ห้ามเปลี่ยน)</option>' +
                  '<option value="reference">Reference (อ้างอิง)</option>' +
                '</select>' +
              '</div>' +
            '</div>' +
            '<div class="c-form__group" style="display:flex;gap:var(--space-xs); justify-content:flex-end; margin-top:var(--space-xs);">' +
              '<button class="c-btn c-btn--primary" id="glossary-save-btn" style="min-height:44px;">บันทึก</button>' +
              '<button class="c-btn c-btn--secondary" id="glossary-cancel-btn" style="min-height:44px;display:none;">ยกเลิก</button>' +
            '</div>' +
          '</div>' +
          '<div id="glossary-status" style="margin-top:var(--space-xs);font-size:var(--text-xs);color:var(--c-success);"></div>' +
        '</div>' +

        // Card 2: AI Glossary Suggestion
        '<div class="c-settings-form" style="background:var(--c-bg-secondary);padding:var(--space-md);border-radius:var(--radius); display:flex; flex-direction:column;">' +
          '<h4 class="u-mb-sm" style="font-weight:600; display:flex; align-items:center; gap:8px;">💡 แนะนำคำศัพท์ใหม่ด้วย AI</h4>' +
          '<div style="display:flex; gap:var(--space-sm); align-items:end; margin-bottom:var(--space-md);">' +
            '<div class="c-form__group" style="flex:1; max-width:180px;">' +
              '<label class="c-form__label">ตอนที่ต้องการสแกน</label>' +
              '<input type="number" min="1" class="c-form__input" id="ai-glossary-ch" placeholder="เช่น 1" />' +
            '</div>' +
            '<button class="c-btn c-btn--secondary" id="ai-glossary-scan-btn" style="min-height:44px;">🔍 สแกน</button>' +
          '</div>' +
          '<div id="ai-glossary-loading" style="display:none; color:var(--c-text-secondary); margin-bottom:var(--space-sm); font-size:var(--text-sm);">' +
            '⌛ กำลังสแกนหาศัพท์จีนที่ยังไม่ได้แปล...' +
          '</div>' +
          '<div id="ai-glossary-results-box" style="flex:1; max-height:220px; overflow-y:auto; border:1px solid var(--c-border); padding:var(--space-sm); border-radius:var(--radius-sm); background:var(--c-bg-tertiary); display:none;">' +
            '<div id="ai-glossary-results-list" style="display:flex; flex-direction:column; gap:var(--space-xs);"></div>' +
          '</div>' +
        '</div>' +
      '</div>';

    // Glossary Table
    html += '<div class="c-table-wrap"><table class="c-table"><thead><tr><th>จีน</th><th>ไทย</th><th>ประเภท</th><th>ระดับ</th><th>การตรวจสอบ</th><th style="width:140px;text-align:center;">การจัดการ</th></tr></thead><tbody>';
    
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
            '<span class="c-badge ' + verifyBadgeClass + ' glossary-verify-toggle" data-index="' + index + '" style="cursor:pointer; user-select:none;" title="คลิกเพื่อสลับสถานะการตรวจสอบ">' +
              verifyLabel +
            '</span>' +
          '</td>' +
          '<td style="text-align:center;display:flex;gap:var(--space-xs);justify-content:center;">' +
            '<button class="c-btn c-btn--xs c-btn--secondary glossary-edit-btn" data-index="' + index + '">แก้ไข</button>' +
            '<button class="c-btn c-btn--xs c-btn--danger glossary-del-btn" data-index="' + index + '" style="background:var(--c-error);color:white;border:none;">ลบ</button>' +
          '</td>' +
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
          alert('ไม่สามารถโหลด Glossary สำหรับนิยายเรื่องนี้ได้: ' + err.message);
        }
      };
    }

    const sourceInput = document.getElementById('glossary-source');
    const thaiInput = document.getElementById('glossary-thai');
    const categorySelect = document.getElementById('glossary-category');
    const lockSelect = document.getElementById('glossary-lock');
    const saveBtn = document.getElementById('glossary-save-btn');
    const cancelBtn = document.getElementById('glossary-cancel-btn');
    const statusEl = document.getElementById('glossary-status');
    const formTitle = document.getElementById('glossary-form-title');

    // Save click handler
    saveBtn.onclick = async () => {
      const source = sourceInput.value.trim();
      const thai = thaiInput.value.trim();
      const category = categorySelect.value;
      const lock = lockSelect.value;

      if (!source || !thai) {
        alert('กรุณากรอกทั้งคำศัพท์เดิม (จีน) และคำแปล (ไทย)');
        return;
      }

      if (this._editingIndex === -1) {
        // Add Mode: Check duplicate
        const exists = this._terms.some(t => t.source === source);
        if (exists) {
          alert('คำศัพท์ "' + source + '" มีอยู่แล้วในคลังศัพท์');
          return;
        }
        this._terms.push({ source, thai, category, priority: 3, lock, explanation: '', notes: '', verified: true });
        statusEl.textContent = 'เพิ่มคำศัพท์สำเร็จแล้ว';
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
        statusEl.textContent = 'แก้ไขคำศัพท์สำเร็จแล้ว';
        this._editingIndex = -1;
      }

      // Save to server
      try {
        const res = await fetch('/api/novel/' + this._slug + '/glossary/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ terms: this._terms })
        });
        if (res.ok) {
          this._renderUI(page);
        } else {
          alert('ไม่สามารถเซฟข้อมูลลง Server ได้');
        }
      } catch (err) {
        alert('เกิดข้อผิดพลาด: ' + err.message);
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

        cancelBtn.style.display = 'inline-block';
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
            const res = await fetch('/api/novel/' + this._slug + '/glossary/save', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ terms: this._terms })
            });
            if (res.ok) {
              this._renderUI(page);
            } else {
              alert('ไม่สามารถเซฟข้อมูลลง Server ได้');
            }
          } catch (err) {
            alert('เกิดข้อผิดพลาด: ' + err.message);
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
          badge.style.opacity = '0.5';
          const res = await Api.verifyGlossaryTerm(this._slug, index, newVerified);
          this._terms[index].verified = res.data.verified;
          this._renderUI(page);
        } catch (err) {
          alert('ไม่สามารถสลับสถานะการตรวจสอบได้ค่ะ: ' + err.message);
          badge.style.opacity = '1';
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
          alert('กรุณากรอกเลขตอนที่ถูกต้องค่ะ');
          return;
        }

        try {
          aiScanBtn.disabled = true;
          aiLoading.style.display = 'block';
          aiResultsBox.style.display = 'none';
          aiResultsList.innerHTML = '';

          const res = await Api.getUnknownTerms(this._slug, chNum);
          const terms = res.terms || [];

          aiLoading.style.display = 'none';
          aiResultsBox.style.display = 'block';

          if (terms.length === 0) {
            aiResultsList.innerHTML = '<div style="font-size:var(--text-sm);color:var(--c-text-muted);padding:var(--space-xs);text-align:center;">ไม่พบคำศัพท์ภาษาจีนใหม่ในตอนนี้นะคะ</div>';
          } else {
            terms.forEach(term => {
              const item = document.createElement('div');
              item.style.cssText = 'display:flex; align-items:center; justify-content:space-between; padding:var(--space-xs) 0; border-bottom:1px solid var(--c-border-subtle); gap:var(--space-sm); flex-wrap:wrap;';
              item.innerHTML = `
                <span style="font-weight:600; font-size:14px; color:var(--c-text-primary); font-family:var(--font-ui);">${Ui.esc(term)}</span>
                <div style="display:flex; gap:var(--space-xs); align-items:center;">
                  <span id="ai-suggest-res-${term}" style="font-size:12px; color:var(--c-text-muted); margin-right:4px;"></span>
                  <button class="c-btn c-btn--xs c-btn--secondary ai-suggest-btn" data-term="${Ui.esc(term)}" style="padding: 2px 8px; font-size: 11px;">💡 ขอไอเดียแปล</button>
                  <button class="c-btn c-btn--xs c-btn--primary ai-add-btn" data-term="${Ui.esc(term)}" style="display:none; padding: 2px 8px; font-size: 11px;">➕ ย้ายเข้าฟอร์ม</button>
                </div>
              `;
              aiResultsList.appendChild(item);
            });

            // Bind Suggest Idea Event
            aiResultsList.querySelectorAll('.ai-suggest-btn').forEach(btn => {
              btn.onclick = async () => {
                const term = btn.dataset.term;
                const resSpan = document.getElementById(`ai-suggest-res-${term}`);
                const addBtn = btn.nextElementSibling;

                try {
                  btn.disabled = true;
                  btn.textContent = '⌛...';
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
                  
                  resSpan.innerHTML = `<span class="c-badge c-badge--gray" style="font-size:10px;padding:2px 4px;margin-right:2px;">${Ui.esc(cat)}</span> <strong>${Ui.esc(thai)}</strong>`;
                  btn.style.display = 'none';
                  
                  addBtn.style.display = 'inline-block';
                  addBtn.dataset.thai = thai;
                  addBtn.dataset.category = cat;
                } catch (errSuggest) {
                  resSpan.textContent = 'ขัดข้อง';
                  btn.disabled = false;
                  btn.textContent = '💡 ขอไอเดียแปล';
                  alert('ไม่สามารถแนะนำคำศัพท์ได้: ' + errSuggest.message);
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

                statusEl.textContent = 'โหลดแนะนำจาก AI เข้าฟอร์มแล้ว กรุณากดบันทึกค่ะ';
                thaiInput.focus();
                
                // Smooth scroll to form
                formTitle.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              };
            });
          }
        } catch (errScan) {
          alert('เกิดข้อผิดพลาดในการสแกนคำศัพท์: ' + errScan.message);
        } finally {
          aiScanBtn.disabled = false;
          aiLoading.style.display = 'none';
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
      page.innerHTML = '<div class="c-container"><div class="c-section__header"><h3 class="c-section__title">แก้ไขนิยาย: ' + Ui.esc(slug||'') + '</h3></div><div class="c-settings-form"><div class="c-form"><div class="c-form__group"><label class="c-form__label">ชื่อไทย</label><input class="c-form__input" id="edit-translated-title" value="' + Ui.esc(novel?.translatedTitle||'') + '" /></div><div class="c-form__group"><label class="c-form__label">ชื่อต้นฉบับ</label><input class="c-form__input" id="edit-title" value="' + Ui.esc(novel?.title||'') + '" /></div><div class="c-form__group"><label class="c-form__label">ผู้แต่ง</label><input class="c-form__input" id="edit-author" value="' + Ui.esc(novel?.author||'') + '" /></div><div class="c-form__group" style="margin-top:var(--space-md);"><button class="c-btn c-btn--primary" id="edit-save">บันทึก</button><span id="edit-status" style="margin-left:var(--space-sm);"></span></div></div></div></div>';
    } catch(_) { Ui.showError(page, 'เกิดข้อผิดพลาด'); }

    // ── Save handler ────────────────────────────────────────────────
    const saveBtn = document.getElementById('edit-save');
    const statusEl = document.getElementById('edit-status');
    if (saveBtn) {
      saveBtn.onclick = async () => {
        const title = document.getElementById('edit-title')?.value?.trim() || '';
        const translatedTitle = document.getElementById('edit-translated-title')?.value?.trim() || '';
        const author = document.getElementById('edit-author')?.value?.trim() || '';
        statusEl.textContent = 'กำลังบันทึก...';
        statusEl.style.color = 'var(--c-text-muted)';
        try {
          const res = await fetch('/api/novel/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ slug, title, author, translatedTitle }),
          });
          const data = await res.json();
          if (res.ok) {
            statusEl.textContent = '✅ บันทึกสำเร็จ';
            statusEl.style.color = 'var(--c-success)';
          } else {
            statusEl.textContent = '❌ ' + (data.error || 'เกิดข้อผิดพลาด');
            statusEl.style.color = 'var(--c-error)';
          }
        } catch (e) {
          statusEl.textContent = '❌ ' + e.message;
          statusEl.style.color = 'var(--c-error)';
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

// ── ADMIN JOBS DASHBOARD ────────────────────────────────────────────────
const AdminJobsPage = {
  async render(params) {
    const page = Ui.$('page-admin-jobs');
    if (!page) return;
    Ui.showSkeleton('page-admin-jobs');
    try {
      const res = await fetch('/api/admin/jobs');
      const data = await res.json();

      let filter = 'needs_review';  // Default: only show pending items

      // Helper: format chapter list as ranges
      const fmtChapters = (ch) => {
        if (!ch || ch === '') return '';
        // Already a plain number string
        if (/^\d+$/.test(String(ch))) return String(ch);
        // Array of numbers — convert to ranges
        if (Array.isArray(ch)) {
          if (ch.length <= 3) return ch.join(', ');
          const sorted = [...ch].sort((a,b) => a-b);
          let ranges = [];
          let start = sorted[0], end = sorted[0];
          for (let i = 1; i < sorted.length; i++) {
            if (sorted[i] === end + 1) { end = sorted[i]; }
            else { ranges.push(start === end ? `${start}` : `${start}-${end}`); start = end = sorted[i]; }
          }
          ranges.push(start === end ? `${start}` : `${start}-${end}`);
          return ranges.join(', ');
        }
        return String(ch).slice(0, 30);
      };

      // Helper: clean error message
      const fmtError = (msg) => {
        if (!msg) return '';
        // Show only first meaningful line (not traceback)
        const lines = msg.split('\n');
        for (const line of lines) {
          const t = line.trim();
          if (t && !t.includes('Traceback') && !t.includes('File "') && !t.startsWith('^^')) {
            return t.slice(0, 80);
          }
        }
        return lines[0].slice(0, 80);
      };

      const renderJobs = () => {
        let allItems = [];
        const src = data || {};
        // Collect all items with type tag
        if (src.active) src.active.forEach(i => allItems.push({ ...i, _type: 'active' }));
        if (src.needsReview) src.needsReview.forEach(i => allItems.push({ ...i, _type: 'needs_review' }));
        if (src.failed) src.failed.forEach(i => allItems.push({ ...i, _type: 'failed' }));
        if (src.done) src.done.forEach(i => allItems.push({ ...i, _type: 'done' }));

        // Sort newest first by createdAt
        allItems.sort((a, b) => {
          const ta = a.data?.createdAt || '';
          const tb = b.data?.createdAt || '';
          return tb.localeCompare(ta);
        });

        // Filter
        let filtered = allItems;
        if (filter !== 'all') filtered = allItems.filter(i => i._type === filter);

        const counts = {
          all: allItems.length,
          active: (src.active||[]).length,
          needs_review: (src.needsReview||[]).length,
          failed: (src.failed||[]).length,
          done: (src.done||[]).length,
        };

        let html = '<div class="c-container">' + Ui.adminNav('jobs') +
          '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">📋 คิวงานแปล</h3></div>' +

          // ── Filter tabs ──
          '<div style="display:flex;gap:var(--space-xs);margin-bottom:var(--space-md);flex-wrap:wrap;font-size:var(--text-sm);">' +
          ['all','active','needs_review','failed','done'].map(t =>
            `<button class="c-btn c-btn--xs c-job-filter" data-filter="${t}" style="${filter === t ? 'background:var(--c-accent);color:#fff;' : ''}">${t === 'all' ? 'ทั้งหมด' : t === 'needs_review' ? 'รอตรวจ' : t === 'active' ? 'กำลังรัน' : t} (${counts[t]})</button>`
          ).join('') +
          '</div>' +

          // ── Compact list ──
          '<div class="c-table-wrap c-table-wrap--compact"><table class="c-table"><thead><tr><th>ตอน</th><th>ประเภท</th><th>สถานะ</th><th>คำสั่ง</th><th></th></tr></thead><tbody>';

        if (filtered.length === 0) {
          html += '<tr><td colspan="5" class="u-text-center u-text-muted u-p-md">ไม่มีรายการ</td></tr>';
        } else {
          for (const item of filtered) {
            const d = item.data || {};
            const ch = d.chapter || d.chapterNo || (d.chapters ? d.chapters : '');
            const reason = d.reason || d.error || d.state || '';
            const suggestion = d.suggestedCommand || '';
            const slug = d.slug || '';
            const mode = d.mode || '';
            const createdAt = d.createdAt ? new Date(d.createdAt).toLocaleString('th-TH', { day:'numeric', month:'short', hour:'2-digit', minute:'2-digit' }) : '';
            const fileId = 'cmd-' + Math.random().toString(36).slice(2, 7);

            let typeLabel = item._type;
            let badgeClass = 'c-badge--gray';
            if (item._type === 'active') { typeLabel = 'กำลังรัน'; badgeClass = 'c-badge--teal'; }
            else if (item._type === 'needs_review') { typeLabel = 'รอตรวจ'; badgeClass = 'c-badge--amber'; }
            else if (item._type === 'failed') { typeLabel = 'ล้มเหลว'; badgeClass = 'c-badge--red'; }
            else if (item._type === 'done') { typeLabel = 'เสร็จแล้ว'; badgeClass = 'c-badge--teal'; }

            html += '<tr>' +
              '<td style="font-family:var(--font-mono);font-weight:600;white-space:nowrap;">' + Ui.esc(fmtChapters(ch)) + '</td>' +
              '<td><span class="c-badge c-badge--gray" style="font-size:10px;">' + Ui.esc(mode || typeLabel) + '</span></td>' +
              '<td><span class="c-badge ' + badgeClass + '">' + typeLabel + '</span>' +
                (reason ? '<div style="font-size:10px;color:var(--c-text-muted);margin-top:2px;" title="' + Ui.esc(reason) + '">' + Ui.esc(fmtError(reason)) + '</div>' : '') +
                (createdAt ? '<div style="font-size:10px;color:var(--c-text-soft);margin-top:1px;">' + createdAt + '</div>' : '') +
              '</td>' +
              '<td>' +
                (suggestion ? '<code id="' + fileId + '" style="font-size:10px;white-space:pre-wrap;">' + Ui.esc(suggestion) + '</code>' : '') +
              '</td>' +
              '<td style="white-space:nowrap;">' +
                (suggestion ? '<button class="c-btn c-btn--xs" onclick="navigator.clipboard.writeText(document.getElementById(\'' + fileId + '\').textContent)" title="คัดลอกคำสั่ง">📋</button>' : '') +
                (slug && ch ? ' <a href="#admin/logs/' + Ui.esc(slug) + '/' + ch + '" class="c-btn c-btn--xs" data-nav title="ดู audit log">📂</a>' : '') +
              '</td>' +
            '</tr>';
          }
        }

        html += '</tbody></table></div></div>';
        page.innerHTML = html;

        // Bind filter clicks
        document.querySelectorAll('.c-job-filter').forEach(btn => {
          btn.addEventListener('click', () => {
            filter = btn.dataset.filter;
            renderJobs();
          });
        });
      };

      renderJobs();
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
        const novels = await Api.getNovels();
        const novelOptions = novels.map(n => 
          `<option value="${Ui.esc(n.slug)}">${Ui.esc(Ui.displayTitle(n) || n.slug)}</option>`
        ).join('');
        
        let selectHtml = '<div class="c-container">' + Ui.adminNav('logs') +
          '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">📂 ตรวจสอบ Audit Log รายตอน</h3></div>' +
          '<div class="c-settings-card" style="background:var(--c-surface); border:1px solid var(--c-border); border-radius:var(--radius); padding:var(--space-md);">' +
          '<div class="c-form">' +
          '<div class="c-form__row" style="display:grid; grid-template-columns:1fr 1fr; gap:var(--space-md);">' +
          '<div class="c-form__group">' +
          '<label class="c-form__label">เลือกนิยาย</label>' +
          '<select class="c-form__select c-form__select--compact" id="logs-novel-select" style="width:100% !important;">' +
          novelOptions +
          '</select>' +
          '</div>' +
          '<div class="c-form__group">' +
          '<label class="c-form__label">ตอนที่ต้องการตรวจ (Chapter Number)</label>' +
          '<input type="number" class="c-form__input c-form__input--compact" id="logs-chapter-num" value="1" min="1" style="width:100% !important;" />' +
          '</div>' +
          '</div>' +
          '<button class="c-btn c-btn--primary" id="logs-query-btn" style="margin-top:var(--space-md); min-height:38px;">📂 ตรวจสอบ Audit Log</button>' +
          '</div>' +
          '</div>' +
          '</div>';
          
        page.innerHTML = selectHtml;
        
        document.getElementById('logs-query-btn')?.addEventListener('click', () => {
          const selectedSlug = document.getElementById('logs-novel-select').value;
          const selectedNum = document.getElementById('logs-chapter-num').value.trim();
          if (!selectedSlug || !selectedNum) {
            alert('กรุณาเลือกนิยายและระบุเลขตอนด้วยค่ะ');
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
        '<div class="c-section__header" style="margin-top:var(--space-md);"><h3 class="c-section__title">📂 Audit Log: ' + Ui.esc(slug) + ' / ตอน ' + Ui.esc(num) + '</h3>' +
        '<div style="display:flex; gap:var(--space-xs);">' +
        '<a href="#admin/logs" class="c-btn c-btn--sm c-btn--secondary" data-nav style="text-decoration:none; display:inline-flex; align-items:center; min-height:32px;">🔍 ค้นหาใหม่</a>' +
        '<a href="#admin/jobs" class="c-btn c-btn--sm c-btn--ghost" data-nav style="text-decoration:none; display:inline-flex; align-items:center; min-height:32px;">← กลับคิวงาน</a>' +
        '</div></div>';

      const files = data.ok && data.data ? data.data.files : [];

      if (!data.ok || !files || files.length === 0) {
        const errorMsg = data.error?.message || data.data?.warning || 'ไม่มี log สำหรับตอนนี้';
        html += '<div class="c-settings-card" style="padding:var(--space-md); background:var(--c-surface); border:1px solid var(--c-border);"><p class="u-text-muted" style="margin:0;">' + Ui.esc(errorMsg) + '</p></div>';
      } else {
        for (const file of files) {
          html += '<div class="c-section" style="margin-top:var(--space-md);">' +
            '<div class="c-section__header"><h3 class="c-section__title" style="font-size:var(--text-sm); font-weight:600; color:var(--c-text-primary);">' + Ui.esc(file.name) + '</h3></div>' +
            '<pre style="background:var(--c-surface);border:1px solid var(--c-border);padding:var(--space-md);border-radius:var(--radius-sm);font-size:12px;overflow-x:auto;max-height:400px;color:var(--c-text);line-height:1.6;"><code>' + Ui.esc(file.content) + '</code></pre>' +
            '</div>';
        }
      }
      page.innerHTML = html;
    } catch (err) {
      Ui.showError(page, 'โหลดล็อกไม่สำเร็จ', err.message);
    }
  }
};

// ── ADMIN TRANSLATE & CONFIG PAGE ────────────────────────────────────────
const AdminTranslatePage = {
  async render(params) {
    const page = Ui.$('page-admin-translate');
    if (!page) return;
    Ui.showSkeleton('page-admin-translate');

    try {
      const novels = await Api.getNovels();
      const cfg = await Api.getLlmConfig();

      const novelOptions = novels.map(n => 
        `<option value="${Ui.esc(n.slug)}">${Ui.esc(Ui.displayTitle(n) || n.slug)}</option>`
      ).join('');

      let html = `
      <div class="c-container">
        ${Ui.adminNav('translate')}
        
        <div style="display:grid; grid-template-columns:1fr; gap:var(--space-md); margin-top:var(--space-md);">
          
          <!-- LLM CONFIG FORM -->
          <div class="c-card" style="padding:var(--space-md);">
            <h3 style="margin-top:0; margin-bottom:var(--space-sm); font-size:var(--text-md); font-weight:600; color:var(--c-text-primary);">⚙️ ตั้งค่าความเชื่อมต่อ AI และโมเดล</h3>
            <div class="c-form" style="display:flex; flex-direction:column; gap:var(--space-sm);">
              <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:var(--space-sm);">
                <div class="c-form__group">
                  <label class="c-form__label">ผู้ให้บริการ (Provider)</label>
                  <select class="c-form__select c-form__select--compact" id="translate-cfg-provider">
                    <option value="openrouter" ${cfg.default_provider === 'openrouter' ? 'selected' : ''}>OpenRouter (Gemma/GPT-OSS)</option>
                    <option value="openmodel" ${cfg.default_provider === 'openmodel' ? 'selected' : ''}>OpenModel (DeepSeek Flash)</option>
                  </select>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label" style="display:flex; justify-content:space-between; align-items:center;">
                    <span>รุ่นของ AI Model</span>
                    <button id="fetch-models-btn" class="c-btn c-btn--xs c-btn--secondary" style="padding:2px 8px; font-size:10px; min-height:auto; display:none;">🔍 ดึงโมเดลล่าสุด</button>
                  </label>
                  <input type="text" class="c-form__input c-form__input--compact" id="translate-cfg-model" list="model-datalist" placeholder="เช่น google/gemma-4-31b-it:free" value="${Ui.esc(cfg.default_model || '')}" />
                  <datalist id="model-datalist"></datalist>
                </div>
              </div>
              <div class="c-form__group">
                <label class="c-form__label">OpenRouter API Key (เว้นว่างไว้เพื่อไม่ให้เปลี่ยนแปลง)</label>
                <input type="password" class="c-form__input c-form__input--compact" id="translate-cfg-key" placeholder="${cfg.hasOpenRouterKey ? '●●●●●●●●●●●● (ตั้งค่าไว้เรียบร้อยแล้ว)' : 'กรอก API Key ใหม่ที่นี่...'}" />
              </div>
              <div style="display:flex; justify-content:flex-end;">
                <button class="c-btn c-btn--primary" id="translate-cfg-save-btn" style="min-height:36px; font-size:var(--text-sm);">💾 บันทึกการตั้งค่า</button>
              </div>
            </div>
          </div>
 
          <!-- BATCH TRANSLATION PANEL -->
          <div class="c-card" style="padding:var(--space-md);">
            <h3 style="margin-top:0; margin-bottom:var(--space-sm); font-size:var(--text-md); font-weight:600; color:var(--c-text-primary);">🚀 สั่งการแปลนิยายเป็นกลุ่ม (Batch Translation)</h3>
            <div class="c-form" style="display:flex; flex-direction:column; gap:var(--space-sm);">
              <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:var(--space-sm); align-items:end;">
                <div class="c-form__group">
                  <label class="c-form__label">เลือกนิยายที่ต้องการแปล</label>
                  <select class="c-form__select c-form__select--compact" id="translate-batch-novel">
                    ${novelOptions}
                  </select>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">ช่วงตอนที่จะแปล (เช่น 5-10 หรือ 5)</label>
                  <input type="text" class="c-form__input c-form__input--compact" id="translate-batch-range" placeholder="ระบุช่วง เช่น 1-10" />
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">ประเมินผลคะแนนคุณภาพ</label>
                  <select class="c-form__select c-form__select--compact" id="translate-batch-score">
                    <option value="true">ประเมินด้วย LLM-as-Judge</option>
                    <option value="false">ข้ามการประเมินคะแนน</option>
                  </select>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">แปลขนาน (Concurrent)</label>
                  <select class="c-form__select c-form__select--compact" id="translate-batch-concurrent">
                    <option value="1">1 ตอนพร้อมกัน</option>
                    <option value="2">2 ตอนพร้อมกัน</option>
                    <option value="3">3 ตอนพร้อมกัน</option>
                  </select>
                </div>
              </div>
              <div style="display:flex; justify-content:flex-end; gap:var(--space-xs); margin-top:var(--space-xs);">
                <button class="c-btn c-btn--primary" id="translate-batch-run-btn" style="min-height:38px; font-weight:600;">⚡ สั่งแปลตามช่วงที่เลือก</button>
              </div>
            </div>
          </div>

          <!-- TRANSLATION CONSOLE/PROGRESS -->
          <div class="c-card" id="translate-console-card" style="padding:var(--space-md); display:none;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:var(--space-sm);">
              <h4 style="margin:0; font-weight:600; color:var(--c-text-primary);" id="translate-console-title">กำลังรันคำสั่งแปลภาษา...</h4>
              <span id="translate-console-badge" class="c-badge c-badge--teal">กำลังประมวลผล</span>
            </div>
            <pre id="translate-console-output" style="background:var(--c-surface); color:var(--c-text-secondary); padding:var(--space-sm); border-radius:var(--radius-sm); font-size:var(--text-xs); overflow-x:auto; max-height:300px; font-family:var(--font-mono); margin:0;"><code>ระบบกำลังเริ่มต้น...</code></pre>
          </div>

        </div>
      </div>`;

      page.innerHTML = html;

      // ── Datalist Management
      const providerSelect = document.getElementById('translate-cfg-provider');
      const updateDatalist = (provider) => {
        const dl = document.getElementById('model-datalist');
        const fetchBtn = document.getElementById('fetch-models-btn');
        if (!dl) return;
        
        let options = [];
        if (provider === 'openrouter') {
          if (fetchBtn) fetchBtn.style.display = 'inline-block';
          options = [
            'google/gemma-4-26b-a4b-it:free',
            'google/gemma-2-9b-it:free',
            'google/gemma-2-27b-it:free',
            'meta-llama/llama-3.1-70b-instruct',
            'meta-llama/llama-3.1-405b-instruct',
            'deepseek/deepseek-chat'
          ];
        } else {
          if (fetchBtn) fetchBtn.style.display = 'none';
          options = [
            'deepseek-chat',
            'deepseek-coder',
            'gpt-4o-mini',
            'gpt-4o',
            'claude-3-5-sonnet'
          ];
        }
        dl.innerHTML = options.map(opt => `<option value="${opt}"></option>`).join('');
      };

      if (providerSelect) {
        providerSelect.addEventListener('change', (e) => {
          updateDatalist(e.target.value);
        });
        updateDatalist(providerSelect.value);
      }

      // ── Fetch Models Click Event
      const fetchBtn = document.getElementById('fetch-models-btn');
      if (fetchBtn) {
        fetchBtn.addEventListener('click', async (e) => {
          e.preventDefault();
          try {
            fetchBtn.disabled = true;
            fetchBtn.textContent = '⌛ กำลังดึง...';
            
            const response = await fetch('https://openrouter.ai/api/v1/models');
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            
            if (data && Array.isArray(data.data)) {
              const dl = document.getElementById('model-datalist');
              if (dl) {
                const opts = data.data.map(model => 
                  `<option value="${model.id}">${Ui.esc(model.name || model.id)}</option>`
                ).join('');
                dl.innerHTML = opts;
                alert('ดึงโมเดล OpenRouter สำเร็จเรียบร้อยแล้วค่ะ! เลือกรุ่นในช่องกรอกได้เลย');
              }
            }
          } catch (err) {
            alert('ไม่สามารถดึงข้อมูลโมเดลล่าสุดได้ค่ะ: ' + err.message);
          } finally {
            fetchBtn.disabled = false;
            fetchBtn.textContent = '🔍 ดึงโมเดลล่าสุด';
          }
        });
      }

      // ── Bind Settings Form Save Event
      const saveBtn = document.getElementById('translate-cfg-save-btn');
      if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
          const modelVal = document.getElementById('translate-cfg-model').value;
          const providerVal = document.getElementById('translate-cfg-provider').value;
          const keyVal = document.getElementById('translate-cfg-key').value;

          const payload = {
            default_model: modelVal,
            default_provider: providerVal
          };
          if (keyVal.trim()) {
            payload.openrouter_api_key = keyVal.trim();
          }

          try {
            saveBtn.disabled = true;
            saveBtn.textContent = '⌛ กำลังบันทึก...';
            await Api.saveLlmConfig(payload);
            alert('บันทึกการตั้งค่าลง llm.json สำเร็จเรียบร้อยแล้วค่ะ!');
            document.getElementById('translate-cfg-key').value = '';
            AdminTranslatePage.render(params);
          } catch (err) {
            alert('เกิดข้อผิดพลาดในการบันทึก: ' + err.message);
          } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = '💾 บันทึกการตั้งค่า';
          }
        });
      }

      // ── Bind Batch Translation Event
      const runBtn = document.getElementById('translate-batch-run-btn');
      if (runBtn) {
        runBtn.addEventListener('click', async () => {
          const slugVal = document.getElementById('translate-batch-novel').value;
          const rangeVal = document.getElementById('translate-batch-range').value;
          const scoreVal = document.getElementById('translate-batch-score').value === 'true';
          const concurrentVal = parseInt(document.getElementById('translate-batch-concurrent').value, 10);

          if (!rangeVal.trim()) {
            alert('กรุณากรอกช่วงตอนที่ต้องการสั่งแปล เช่น "5-10" หรือ "5"');
            return;
          }

          const consoleCard = document.getElementById('translate-console-card');
          const consoleTitle = document.getElementById('translate-console-title');
          const consoleBadge = document.getElementById('translate-console-badge');
          const consoleOutput = document.getElementById('translate-console-output');

          if (consoleCard) consoleCard.style.display = 'block';
          if (consoleTitle) consoleTitle.textContent = `รันการแปลช่วงตอน: ${rangeVal}`;
          if (consoleBadge) {
            consoleBadge.textContent = 'กำลังแปล...';
            consoleBadge.className = 'c-badge c-badge--amber';
          }
          if (consoleOutput) consoleOutput.innerHTML = `<code>กำลังส่ง Request และเรียกใช้ python tools/translate.py...</code>`;

          try {
            runBtn.disabled = true;
            runBtn.textContent = '⌛ กำลังดำเนินการแปล...';
            
            const res = await Api.translateBatch(slugVal, rangeVal, scoreVal, concurrentVal);
            
            if (res.success) {
              if (consoleBadge) {
                consoleBadge.textContent = 'แปลเสร็จสิ้น';
                consoleBadge.className = 'c-badge c-badge--teal';
              }
              if (consoleOutput) {
                consoleOutput.innerHTML = `<code>[SUCCESS] แปลภาษาสำเร็จเรียบร้อยแล้วค่ะ!\n\nผลลัพธ์:\n${Ui.esc(res.stdout || 'ไม่มีการส่งข้อมูลผลลัพธ์ออก')}\n\nล้างแคชบทเรียนและซิงค์เรียบร้อยแล้ว</code>`;
              }
              Api.invalidateAll(slugVal);
              alert('แปลกลุ่มช่วงตอนสำเร็จแล้วค่ะ!');
            } else {
              throw new Error(res.error?.message || 'แปลไม่สำเร็จ');
            }
          } catch (err) {
            if (consoleBadge) {
              consoleBadge.textContent = 'ขัดข้อง';
              consoleBadge.className = 'c-badge c-badge--red';
            }
            if (consoleOutput) {
              consoleOutput.innerHTML = `<code>[ERROR] การแปลเกิดข้อผิดพลาด:\n\n${Ui.esc(err.message)}</code>`;
            }
            alert('การแปลเกิดข้อผิดพลาด: ' + err.message);
          } finally {
            runBtn.disabled = false;
            runBtn.textContent = '⚡ สั่งแปลตามช่วงที่เลือก';
          }
        });
      }

    } catch (err) {
      Ui.showError(page, 'โหลดหน้าแปลล้มเหลว', err.message);
    }
  }
};

// ── ADMIN IMPORT NOVEL ───────────────────────────────────────────────────
const AdminImportPage = {
  async render(params) {
    const page = Ui.$('page-admin-import');
    if (!page) return;
    
    let html = '<div class="c-container">' + Ui.adminNav('import') +
      `<div class="c-section__header" style="margin-top:var(--space-md);">
        <h3 class="c-section__title">📥 นำเข้านิยาย (Import Novel)</h3>
        <span style="font-size:var(--text-sm);color:var(--c-text-muted);">สร้างและนำเข้านิยายเข้าสู่ฐานข้อมูลระบบ</span>
      </div>
      
      <!-- Tab Switches -->
      <div class="c-admin-tabs" style="display:flex;gap:var(--space-sm);margin-bottom:var(--space-md);border-bottom:2px solid var(--c-border);padding-bottom:var(--space-xs);">
        <button class="c-btn c-btn--primary tab-btn" data-tab="file" style="min-width:140px;">นำเข้าจากไฟล์ (.txt)</button>
        <button class="c-btn c-btn--ghost tab-btn" data-tab="web" style="min-width:140px;">ดึงข้อมูลจากเว็บ (URL Scraper)</button>
      </div>

      <!-- TAB 1: File Import -->
      <div id="import-tab-file" class="import-tab-content">
        <div class="c-settings-card" style="background:var(--c-surface); border:1px solid var(--c-border); border-radius:var(--radius); padding:var(--space-md);">
          <div class="c-settings-card__title" style="margin-bottom:var(--space-md); font-weight:var(--font-weight-semibold); font-size:var(--text-md); display:flex; align-items:center; gap:8px;">
            📁 นำเข้าจากไฟล์ข้อความ (.txt)
          </div>
          
          <div class="c-form">
            <div class="c-form__row" style="display:grid; grid-template-columns:1fr 1fr; gap:var(--space-md);">
              <div class="c-form__group">
                <label class="c-form__label">ชื่อภาษาไทย/แปล (Title Thai)</label>
                <input type="text" id="import-file-title" class="c-form__input" placeholder="เช่น ท่องยุทธภพด้วยระบบฟาร์ม" required />
              </div>
              <div class="c-form__group">
                <label class="c-form__label">Slug (สำหรับใช้เป็นชื่อโฟลเดอร์)</label>
                <input type="text" id="import-file-slug" class="c-form__input" placeholder="เช่น martial-farming (อักษรภาษาอังกฤษและขีดกลาง)" required />
              </div>
            </div>

            <div class="c-form__row" style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:var(--space-md); margin-top:var(--space-sm);">
              <div class="c-form__group">
                <label class="c-form__label">ผู้แต่ง (Author)</label>
                <input type="text" id="import-file-author" class="c-form__input" placeholder="เช่น ปาเต้าหู้" />
              </div>
              <div class="c-form__group">
                <label class="c-form__label">ภาษาต้นฉบับ</label>
                <select class="c-form__select" id="import-file-source-lang">
                  <option value="cn" selected>จีน (Chinese)</option>
                  <option value="en">อังกฤษ (English)</option>
                </select>
              </div>
              <div class="c-form__group">
                <label class="c-form__label">ตัวแบ่งบท/แบ่งตอน (Regex Rule)</label>
                <input type="text" id="import-file-split-rule" class="c-form__input" placeholder="เว้นว่างเพื่อใช้ค่าเริ่มต้น (ตอนที่/第...章)" />
              </div>
            </div>

            <div class="c-form__group" style="margin-top:var(--space-md);">
              <label class="c-form__label">เนื้อความไฟล์ดิบ (.txt)</label>
              <textarea id="import-file-content" class="c-form__input" style="min-height:220px; font-family:var(--font-mono); font-size:13px; line-height:1.6;" placeholder="คัดลอกเนื้อความนิยายภาษาจีน/อังกฤษ ที่มีคำระบุตอน เช่น ตอนที่ 1 ... หรือ 第1章 ... แล้วนำมาวางที่นี่..."></textarea>
            </div>

            <button class="c-btn c-btn--primary c-btn--full" id="import-file-submit-btn" style="margin-top:var(--space-md); min-height:44px;">🚀 นำเข้าไฟล์ข้อความและสร้างนิยาย</button>
          </div>
        </div>
      </div>

      <!-- TAB 2: Web Scraping -->
      <div id="import-tab-web" class="import-tab-content" style="display:none;">
        <div class="c-settings-card" style="background:var(--c-surface); border:1px solid var(--c-border); border-radius:var(--radius); padding:var(--space-md);">
          <div class="c-settings-card__title" style="margin-bottom:var(--space-md); font-weight:var(--font-weight-semibold); font-size:var(--text-md); display:flex; align-items:center; gap:8px;">
            🌐 ดึงข้อมูลนิยายจากเว็บภายนอก (Web URL Scraper)
          </div>
          
          <div class="c-form">
            <div class="c-form__group">
              <label class="c-form__label">URL เว็บนิยายต้นฉบับ</label>
              <input type="url" id="import-web-url" class="c-form__input" placeholder="เช่น https://www.uukanshu.com/b/12345/ หรือเว็บนิยายอื่นๆ..." required />
            </div>

            <div class="c-form__row" style="display:grid; grid-template-columns:1fr 1fr; gap:var(--space-md); margin-top:var(--space-sm);">
              <div class="c-form__group">
                <label class="c-form__label">ชื่อภาษาไทย/แปล (Title Thai)</label>
                <input type="text" id="import-web-title" class="c-form__input" placeholder="เช่น ท่องยุทธภพด้วยระบบฟาร์ม" required />
              </div>
              <div class="c-form__group">
                <label class="c-form__label">Slug (สำหรับใช้เป็นชื่อโฟลเดอร์)</label>
                <input type="text" id="import-web-slug" class="c-form__input" placeholder="เช่น martial-farming" required />
              </div>
            </div>

            <div class="c-form__row" style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:var(--space-sm); margin-top:var(--space-sm);">
              <div class="c-form__group">
                <label class="c-form__label">ผู้แต่ง (Author)</label>
                <input type="text" id="import-web-author" class="c-form__input" placeholder="ระบุเองหรือดึงออโต้" />
              </div>
              <div class="c-form__group">
                <label class="c-form__label">ช่วงตอนเริ่มต้น</label>
                <input type="number" id="import-web-start" class="c-form__input" value="1" min="1" />
              </div>
              <div class="c-form__group">
                <label class="c-form__label">ช่วงตอนสิ้นสุด</label>
                <input type="number" id="import-web-end" class="c-form__input" value="10" min="1" />
              </div>
              <div class="c-form__group">
                <label class="c-form__label">Scraper Engine</label>
                <select class="c-form__select" id="import-web-engine">
                  <option value="direct" selected>Direct Scraper API (รวดเร็ว, ไม่ผ่าน JS)</option>
                  <option value="playwright">Playwright Crawler (จำลองเบราว์เซอร์, แก้แคปช่า)</option>
                </select>
              </div>
            </div>

            <!-- Alert Warning -->
            <div class="c-settings-card" style="background:#2d1a10; border:1px solid #78350f; color:#fef3c7; border-radius:var(--radius-sm); margin-top:var(--space-md); padding:10px var(--space-md); font-size:12px; line-height:1.6;">
              ⚠️ <strong>ข้อควรระวัง:</strong> การดึงนิยายจาก URL เว็บภายนอกอาจติดปัญหาระบบป้องกันความปลอดภัย (เช่น Cloudflare WAF, Captcha, DDOS Protection) หรือโครงสร้างหน้าเว็บเปลี่ยนไป หากเกิดข้อผิดพลาด แนะนำให้ใช้ตัวเลือก <strong>Direct Scraper API</strong> หรือดาวน์โหลดมาเป็นไฟล์ <strong>.txt</strong> แล้วนำเข้ามาทางแท็บแรกแทนค่ะ
            </div>

            <button class="c-btn c-btn--primary c-btn--full" id="import-web-submit-btn" style="margin-top:var(--space-md); min-height:44px;">🌐 เริ่มรันคำสั่ง Scrape และสร้างนิยาย</button>
          </div>
        </div>
      </div>
      
      <!-- Console Output Area -->
      <div id="import-console-card" class="c-settings-card" style="display:none; background:#05070a; border:1px solid #1e293b; border-radius:var(--radius); padding:var(--space-md); margin-top:var(--space-lg);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-sm);">
          <div id="import-console-title" style="font-weight:600; color:#94a3b8; font-size:var(--text-sm);">ผลลัพธ์คำสั่งระบบ</div>
          <span id="import-console-badge" class="c-badge c-badge--amber">กำลังนำเข้า...</span>
        </div>
        <pre id="import-console-output" style="background:#090d16; border:1px solid #0f172a; padding:12px; border-radius:var(--radius-sm); overflow-x:auto; margin:0; font-family:var(--font-mono); font-size:12px; color:#38bdf8; line-height:1.5; white-space:pre-wrap; max-height:250px; overflow-y:auto;"><code>...</code></pre>
      </div>
    </div>`;
    
    page.innerHTML = html;

    // Tab switcher logic
    const tabBtns = page.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        page.querySelectorAll('.import-tab-content').forEach(c => c.style.display = 'none');
        page.querySelectorAll('.tab-btn').forEach(b => {
          b.className = 'c-btn c-btn--ghost tab-btn';
        });
        
        btn.className = 'c-btn c-btn--primary tab-btn';
        document.getElementById('import-tab-' + tab).style.display = 'block';
      });
    });

    // Submit handlers
    const fileSubmit = document.getElementById('import-file-submit-btn');
    if (fileSubmit) {
      fileSubmit.addEventListener('click', async () => {
        const title = document.getElementById('import-file-title').value.trim();
        const slug = document.getElementById('import-file-slug').value.trim();
        const author = document.getElementById('import-file-author').value.trim();
        const sourceLang = document.getElementById('import-file-source-lang').value;
        const splitRule = document.getElementById('import-file-split-rule').value.trim();
        const content = document.getElementById('import-file-content').value.trim();

        if (!title || !slug) {
          alert('กรุณากรอกชื่อเรื่องและ Slug สำหรับนิยายด้วยค่ะ');
          return;
        }
        if (!content) {
          alert('กรุณาป้อนเนื้อความนิยายดิบที่จะใช้นำเข้าด้วยค่ะ');
          return;
        }

        const consoleCard = document.getElementById('import-console-card');
        const consoleTitle = document.getElementById('import-console-title');
        const consoleBadge = document.getElementById('import-console-badge');
        const consoleOutput = document.getElementById('import-console-output');

        if (consoleCard) consoleCard.style.display = 'block';
        if (consoleTitle) consoleTitle.textContent = `รันการนำเข้าไฟล์นิยาย: ${title}`;
        if (consoleBadge) {
          consoleBadge.textContent = 'กำลังดำเนินการ...';
          consoleBadge.className = 'c-badge c-badge--amber';
        }
        if (consoleOutput) consoleOutput.innerHTML = `<code>กำลังประมวลผลการวิเคราะห์และแยกบทเรียน...</code>`;

        try {
          fileSubmit.disabled = true;
          fileSubmit.textContent = '⌛ กำลังรันระบบนำเข้า...';

          const res = await fetch('/api/novel/import-file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, slug, author, sourceLang, splitRule, content })
          });
          const data = await res.json();

          if (res.ok && data.success) {
            if (consoleBadge) {
              consoleBadge.textContent = 'นำเข้าสำเร็จ';
              consoleBadge.className = 'c-badge c-badge--teal';
            }
            if (consoleOutput) {
              consoleOutput.innerHTML = `<code>[SUCCESS] นำเข้านิยายสำเร็จเรียบร้อยแล้วค่ะ!\n\nข้อมูลนิยาย:\n- เรื่อง: ${Ui.esc(data.title)} (${Ui.esc(data.slug)})\n- จำนวนตอนที่นำเข้าได้: ${data.chaptersCount} ตอน\n- ภาษาต้นฉบับ: ${data.sourceLang.toUpperCase()}\n\nคุณสามารถเปิดหน้า Admin แปลนิยาย หรือเข้าไปดูหน้าหอสมุดได้ทันทีค่ะ</code>`;
            }
            Api.invalidateNovels();
            alert(`นำเข้านิยาย "${title}" สำเร็จแล้วค่ะ! (ทั้งหมด ${data.chaptersCount} ตอน)`);
          } else {
            throw new Error(data.error?.message || 'นำเข้าไม่สำเร็จ');
          }
        } catch (err) {
          if (consoleBadge) {
            consoleBadge.textContent = 'ขัดข้อง';
            consoleBadge.className = 'c-badge c-badge--red';
          }
          if (consoleOutput) {
            consoleOutput.innerHTML = `<code>[ERROR] การนำเข้าล้มเหลว:\n\n${Ui.esc(err.message)}</code>`;
          }
          alert('นำเข้าล้มเหลว: ' + err.message);
        } finally {
          fileSubmit.disabled = false;
          fileSubmit.textContent = '🚀 นำเข้าไฟล์ข้อความและสร้างนิยาย';
        }
      });
    }

    // Web Scrape Submit handler
    const webSubmit = document.getElementById('import-web-submit-btn');
    if (webSubmit) {
      webSubmit.addEventListener('click', async () => {
        const url = document.getElementById('import-web-url').value.trim();
        const title = document.getElementById('import-web-title').value.trim();
        const slug = document.getElementById('import-web-slug').value.trim();
        const author = document.getElementById('import-web-author').value.trim();
        const start = parseInt(document.getElementById('import-web-start').value, 10);
        const end = parseInt(document.getElementById('import-web-end').value, 10);
        const engine = document.getElementById('import-web-engine').value;

        if (!url || !title || !slug) {
          alert('กรุณากรอกข้อมูล URL, ชื่อเรื่อง และ Slug ให้ครบด้วยค่ะ');
          return;
        }

        const consoleCard = document.getElementById('import-console-card');
        const consoleTitle = document.getElementById('import-console-title');
        const consoleBadge = document.getElementById('import-console-badge');
        const consoleOutput = document.getElementById('import-console-output');

        if (consoleCard) consoleCard.style.display = 'block';
        if (consoleTitle) consoleTitle.textContent = `รัน Scraper ดึงข้อมูล: ${title}`;
        if (consoleBadge) {
          consoleBadge.textContent = 'กำลัง Scrape...';
          consoleBadge.className = 'c-badge c-badge--amber';
        }
        if (consoleOutput) consoleOutput.innerHTML = `<code>กำลังรัน Scraper Engine (${engine}) เพื่อเชื่อมต่อไปยัง ${Ui.esc(url)}...</code>`;

        try {
          webSubmit.disabled = true;
          webSubmit.textContent = '⌛ กำลังดึงข้อมูล...';

          const res = await fetch('/api/novel/import-web', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, title, slug, author, start, end, engine })
          });
          const data = await res.json();

          if (res.ok && data.success) {
            if (consoleBadge) {
              consoleBadge.textContent = 'ดึงสำเร็จ';
              consoleBadge.className = 'c-badge c-badge--teal';
            }
            if (consoleOutput) {
              consoleOutput.innerHTML = `<code>[SUCCESS] Scraped ดึงข้อมูลนิยายสำเร็จเรียบร้อยแล้วค่ะ!\n\nสถานะ:\n- เรื่อง: ${Ui.esc(data.title)} (${Ui.esc(data.slug)})\n- ช่วงตอนที่ดึง: ${data.start} ถึง ${data.end}\n- ดึงสำเร็จจริง: ${data.chaptersCount} ตอน\n- รายละเอียด: ${Ui.esc(data.message)}\n\nนิยายพร้อมสำหรับสั่งแปลด้วย AI หรือเข้าอ่านแล้วค่ะ!</code>`;
            }
            Api.invalidateNovels();
            alert(`ดึงข้อมูลและนำเข้านิยายสำเร็จแล้วค่ะ! (ดึงมาได้ทั้งหมด ${data.chaptersCount} ตอน)`);
          } else {
            throw new Error(data.error?.message || 'ดึงข้อมูลไม่สำเร็จ');
          }
        } catch (err) {
          if (consoleBadge) {
            consoleBadge.textContent = 'ขัดข้อง';
            consoleBadge.className = 'c-badge c-badge--red';
          }
          if (consoleOutput) {
            consoleOutput.innerHTML = `<code>[ERROR] Scraper เกิดข้อผิดพลาด:\n\n${Ui.esc(err.message)}</code>`;
          }
          alert('Scraper เกิดข้อผิดพลาด: ' + err.message);
        } finally {
          webSubmit.disabled = false;
          webSubmit.textContent = '🌐 เริ่มรันคำสั่ง Scrape และสร้างนิยาย';
        }
      });
    }
  }
};
