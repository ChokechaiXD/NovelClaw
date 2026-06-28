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
};

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
        '<span class="c-badge c-badge--teal">✅ ระบบปกติ</span>' +
        '<span class="c-badge' + (translatedChapters > 0 ? ' c-badge--teal' : ' c-badge--gray') + '">📖 แปลแล้ว ' + translatedChapters + ' ตอน</span>' +
        '<span class="c-badge' + (untranslated > 0 ? ' c-badge--amber' : ' c-badge--gray') + '">📄 รอแปล ' + untranslated + ' ตอน</span>' +
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
        '</div>' +
        '<div class="c-section__header c-admin-page__header c-admin-page__header--loose"><h3 class="c-section__title">เครื่องมือ</h3></div>' +
        '<div class="c-admin-dashboard__grid">' +
        '<a href="#admin/import" class="c-card c-admin-dashboard__tile" data-nav>' +
        '  <svg class="c-admin-dashboard__tile-icon"><use xlink:href="#icon-arrow-right"/></svg><div><div class="c-admin-dashboard__tile-title">นำเข้านิยาย</div><div class="c-admin-dashboard__tile-meta">เพิ่มเรื่องใหม่ / นำเข้าตอน</div></div></a>' +
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
      let html = '<div class="c-container">' + Ui.adminNav('novels') +
        '<div class="c-admin-page__toolbar"><h3 class="c-admin-page__title">📚 รายการนิยายทั้งหมด</h3><a href="#admin/import" class="c-btn c-btn--primary c-btn--sm c-admin-page__action" data-nav>📥 นำเข้านิยายใหม่</a></div>' +
        '<div class="c-table-wrap c-admin-table-wrap"><table class="c-table"><thead><tr><th>Slug</th><th>ชื่อเรื่อง</th><th>ภาษา</th><th>ตอน</th><th>แปลแล้ว</th><th>สถานะ</th><th class="c-admin-novels__actions-col">การจัดการ</th></tr></thead><tbody>';
      for (const n of novels) {
        const translated = n.translatedChapters || 0;
        const total = n.totalChapters || n.chapterCount || 0;
        const statusClass = n.status === 'complete' ? 'c-badge--purple' : n.status === 'ongoing' ? 'c-badge--teal' : 'c-badge--gray';
        html += '<tr><td class="c-admin-table__mono-strong">' + Ui.esc(n.slug) + '</td><td>' + Ui.esc(n.title||'') + '</td><td>' + (n.source_lang||'cn').toUpperCase() + ' → ' + (n.target_lang||'th').toUpperCase() + '</td><td class="c-admin-table__mono">' + total + '</td><td class="c-admin-table__mono-accent">' + translated + ' (' + Math.round(translated/total*100) + '%)</td><td><span class="c-badge ' + statusClass + '">' + Ui.esc(Ui.statusMap[n.status]||'ไม่ระบุ') + '</span></td><td class="c-admin-table__actions-cell"><button class="c-btn c-btn--danger c-btn--xs c-admin-novels__delete-btn delete-novel-btn" data-slug="' + Ui.esc(n.slug) + '">ลบ</button></td></tr>';
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
          '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">📖 ตอนทั้งหมด: ' + Ui.esc(slug) + '</h3><span class="c-admin-page__meta">' + totalFiltered + ' / ' + chapters.length + ' ตอน</span></div>' +

          // ── Search + Filter Controls ──
          '<div class="c-admin-chapters__filters">' +
          '<input id="ch-filter-search" type="text" placeholder="ค้นหาเลขตอน หรือชื่อ..." class="c-form__input c-admin-chapters__search" value="' + Ui.esc(searchQuery) + '" />' +
          '<select id="ch-filter-status" class="c-form__select c-admin-chapters__status-filter">' +
          '<option value="all"' + (filterStatus === 'all' ? ' selected' : '') + '>ทั้งหมด</option>' +
          '<option value="translated"' + (filterStatus === 'translated' ? ' selected' : '') + '>✅ แปลแล้ว</option>' +
          '<option value="source_only"' + (filterStatus === 'source_only' ? ' selected' : '') + '>📄 ต้นฉบับ</option>' +
          '<option value="read"' + (filterStatus === 'read' ? ' selected' : '') + '>📖 อ่านแล้ว</option>' +
          '<option value="unread"' + (filterStatus === 'unread' ? ' selected' : '') + '>📕 ยังไม่อ่าน</option>' +
          '</select>' +
          '<input id="ch-jump-num" type="number" min="1" max="' + chapters.length + '" placeholder="ไปตอน..." class="c-form__input c-admin-chapters__jump-input" />' +
          '<button id="ch-jump-btn" class="c-btn c-btn--sm">ไป</button>' +
          '</div>' +

          // ── Pagination ──
          '<div class="c-admin-chapters__pagination">' +
          '<button class="c-btn c-btn--xs" id="ch-page-prev"' + (currentPage <= 0 ? ' disabled' : '') + '>◀ ก่อนหน้า</button>' +
          '<span>หน้า ' + (currentPage + 1) + ' / ' + (maxPage + 1) + '</span>' +
          '<button class="c-btn c-btn--xs" id="ch-page-next"' + (currentPage >= maxPage ? ' disabled' : '') + '>ถัดไป ▶</button>' +
          '</div>' +

          // ── Table ──
          '<div class="c-table-wrap"><table class="c-table"><thead><tr><th>#</th><th>ชื่อตอน</th><th>สถานะ</th></tr></thead><tbody>';

        for (const ch of pageList) {
          const statusLabel = ch.status === 'translated' ? '✅ แปลแล้ว' : (ch.status === 'source_only' ? '📄 ต้นฉบับ' : '⬜');
          const statusClass = ch.status === 'translated' ? 'c-badge--teal' : (ch.status === 'source_only' ? 'c-badge--amber' : 'c-badge--gray');
          html += '<tr><td class="c-admin-table__mono-strong">' + ch.num + '</td>' +
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
              '<button class="c-btn c-btn--primary" id="glossary-save-btn">บันทึก</button>' +
              '<button class="c-btn c-btn--secondary" id="glossary-cancel-btn" hidden>ยกเลิก</button>' +
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
            '<button class="c-btn c-btn--secondary" id="ai-glossary-scan-btn">สแกน</button>' +
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
            '<button class="c-btn c-btn--xs c-btn--secondary glossary-edit-btn" data-index="' + index + '">แก้ไข</button>' +
            '<button class="c-btn c-btn--xs c-btn--danger glossary-del-btn" data-index="' + index + '">ลบ</button>' +
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
        saveBtn.textContent = 'กำลังบันทึก...';
        await this._saveTerms();
        Ui.showToast('บันทึกคำศัพท์แล้ว');
        this._renderUI(page);
      } catch (err) {
        this._setStatus('บันทึกไม่สำเร็จ: ' + err.message, 'error');
        Ui.showToast('บันทึกคำศัพท์ไม่สำเร็จ', 'error');
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'บันทึก';
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
          aiScanBtn.textContent = 'กำลังสแกน...';
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
            terms.forEach(term => {
              const item = document.createElement('div');
              item.className = 'c-glossary-admin__result-item';
              item.innerHTML = `
                <span class="c-glossary-admin__term">${Ui.esc(term)}</span>
                <div class="c-glossary-admin__result-actions">
                  <span id="ai-suggest-res-${term}" class="c-glossary-admin__suggestion"></span>
                  <button class="c-btn c-btn--xs c-btn--secondary ai-suggest-btn c-glossary-admin__mini-btn" data-term="${Ui.esc(term)}">ขอไอเดียแปล</button>
                  <button class="c-btn c-btn--xs c-btn--primary ai-add-btn c-glossary-admin__mini-btn" data-term="${Ui.esc(term)}" hidden>ย้ายเข้าฟอร์ม</button>
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
                  btn.textContent = 'กำลังแปล...';
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
                  btn.textContent = 'ขอไอเดียแปล';
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
          aiScanBtn.textContent = 'สแกน';
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
      page.innerHTML = '<div class="c-container"><div class="c-section__header c-admin-page__header"><h3 class="c-section__title">แก้ไขนิยาย: ' + Ui.esc(slug||'') + '</h3></div><div class="c-settings-form"><div class="c-form"><div class="c-form__group"><label class="c-form__label">ชื่อไทย</label><input class="c-form__input" id="edit-translated-title" value="' + Ui.esc(novel?.translatedTitle||'') + '" /></div><div class="c-form__group"><label class="c-form__label">ชื่อต้นฉบับ</label><input class="c-form__input" id="edit-title" value="' + Ui.esc(novel?.title||'') + '" /></div><div class="c-form__group"><label class="c-form__label">ผู้แต่ง</label><input class="c-form__input" id="edit-author" value="' + Ui.esc(novel?.author||'') + '" /></div><div class="c-form__group c-admin-edit__actions"><button class="c-btn c-btn--primary" id="edit-save">บันทึก</button><span id="edit-status" class="c-admin-edit__status"></span></div></div></div></div>';
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
            AdminUi.setStatus('edit-status', 'c-admin-edit__status', '✅ บันทึกสำเร็จ', 'success');
          } else {
            AdminUi.setStatus('edit-status', 'c-admin-edit__status', '❌ ' + (data.error || 'เกิดข้อผิดพลาด'), 'error');
          }
        } catch (e) {
          AdminUi.setStatus('edit-status', 'c-admin-edit__status', '❌ ' + e.message, 'error');
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
          '<button class="c-btn c-btn--primary c-admin-logs__submit" id="logs-query-btn">ตรวจสอบ Audit Log</button>' +
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
        '<a href="#admin/logs" class="c-btn c-btn--sm c-btn--secondary c-admin-logs__link" data-nav>ค้นหาใหม่</a>' +
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

// ── ADMIN TRANSLATE PAGE (Simplified) ⭐ ──────────────────────────
const AdminTranslatePage = {
  setConsole(state, title, message) {
    AdminUi.setConsole('translate', state, title, message);
  },

  async render(params) {
    const page = Ui.$('page-admin-translate');
    if (!page) return;
    Ui.showSkeleton('page-admin-translate');

    try {
      const novels = await Api.getNovels();

      const novelOptions = novels.map(n => 
        `<option value="${Ui.esc(n.slug)}">${Ui.esc(Ui.displayTitle(n) || n.slug)}</option>`
      ).join('');

      let html = `
      <div class="c-container">
        ${Ui.adminNav('translate')}
        
        <div class="c-admin-translate">
          <!-- INFO: setting up AI → go to Provider wizard -->
          <div class="c-card c-admin-translate__provider-note">
            <p class="c-admin-translate__provider-note-text">🤖 ตั้งค่า Provider / Model ที่ <a href="#admin/provider" data-nav><strong>หน้า Provider</strong></a></p>
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
              </div>
              <div class="c-admin-translate__actions">
                <button class="c-btn c-btn--primary" id="translate-batch-run-btn">🚀 เริ่มแปล</button>
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

      // ── Bind Batch Translation Event
      const runBtn = document.getElementById('translate-batch-run-btn');
      if (runBtn) {
        runBtn.addEventListener('click', async () => {
          const slugVal = document.getElementById('translate-batch-novel').value;
          const rangeVal = document.getElementById('translate-batch-range').value;
          const concurrentVal = parseInt(document.getElementById('translate-batch-concurrent').value, 10);

          if (!rangeVal.trim()) {
            AdminTranslatePage.setConsole('error', 'ยังไม่ได้ระบุช่วงตอน', 'กรุณากรอกช่วงตอนที่ต้องการสั่งแปล เช่น 5-10 หรือ 5');
            Ui.showToast('กรุณากรอกช่วงตอนที่ต้องการสั่งแปล', 'error');
            return;
          }

          AdminTranslatePage.setConsole(
            'running',
            `รันการแปลช่วงตอน: ${rangeVal}`,
            `กำลังส่งคำสั่งแปล\\nนิยาย: ${slugVal}`
          );

          try {
            runBtn.disabled = true;
            runBtn.textContent = 'กำลังดำเนินการแปล...';

            const res = await Api.translateBatch(slugVal, rangeVal, concurrentVal);
            const result = res.data || res;

            if (res.ok && result.success) {
              AdminTranslatePage.setConsole(
                'success',
                `แปลเสร็จสิ้น: ${rangeVal}`,
                `[SUCCESS] แปลภาษาสำเร็จเรียบร้อยแล้ว\\n\\nผลลัพธ์:\\n${result.stdout || '—'}`
              );
              Api.invalidateAll(slugVal);
              Ui.showToast('แปลกลุ่มช่วงตอนสำเร็จแล้ว');
            } else {
              throw new Error(res.error?.message || 'แปลไม่สำเร็จ');
            }
          } catch (err) {
            AdminTranslatePage.setConsole(
              'error',
              `แปลไม่สำเร็จ: ${rangeVal}`,
              `[ERROR] การแปลเกิดข้อผิดพลาด:\\n\\n${err.message}`
            );
            Ui.showToast('การแปลเกิดข้อผิดพลาด: ' + err.message, 'error');
          } finally {
            runBtn.disabled = false;
            runBtn.textContent = '🚀 เริ่มแปล';
          }
        });
      }

    } catch (err) {
      Ui.showError(page, 'โหลดหน้าแปลล้มเหลว', err.message);
    }
  }
};

// ── ADMIN PROVIDER CONFIG — Step Wizard ⭐ ────────────────────────────
const AdminProviderPage = {
  _state: {},

  async render(params) {
    const page = Ui.$('page-admin-provider');
    if (!page) { 
      const container = document.getElementById('page-admin');
      if (!container) return;
      container.innerHTML = '<div id="page-admin-provider"></div>';
      return this.render(params);
    }
    Ui.showSkeleton('page-admin-provider');
    try {
      const cfg = await Api.getProviderConfig();
      this._state = {
        providers: cfg.providers || [],
        active: cfg.active || '',
        default_model: cfg.default_model || '',
        discovery_model: cfg.discovery_model || '',
        step: 1,
        selected_provider: cfg.active || '',
        selected_model: cfg.default_model || '',
        selected_discovery: cfg.discovery_model || '',
      };
      this._renderStep(page);
    } catch (err) {
      Ui.showError(page, 'โหลดข้อมูลไม่สำเร็จ', err.message);
    }
  },

  _renderStep(page) {
    switch (this._state.step) {
      case 1: this._renderStep1(page); break;
      case 2: this._renderStep2(page); break;
      case 3: this._renderStep3(page); break;
      default: this._renderDone(page); break;
    }
  },

  _stepIndicator(page, current) {
    const steps = [
      { num: 1, label: 'เลือก Provider' },
      { num: 2, label: 'เลือกโมเดลแปล' },
      { num: 3, label: 'ตั้งค่า + บันทึก' },
    ];
    return '<div class="c-admin-wizard__steps">' +
      steps.map(s => {
        const cls = s.num === current ? 'c-admin-wizard__step--active' :
                    s.num < current ? 'c-admin-wizard__step--done' : '';
        return '<div class="c-admin-wizard__step ' + cls + '">' +
          '<span class="c-admin-wizard__step-num">' + (s.num < current ? '✓' : s.num) + '</span>' +
          '<span class="c-admin-wizard__step-label">' + s.label + '</span></div>';
      }).join(' → ') + '</div>';
  },

  // ── Step 1: เลือก Provider ──
  _renderStep1(page) {
    const { providers, selected_provider } = this._state;
    page.innerHTML = '<div class="c-container">' +
      Ui.adminNav('provider') +
      '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">🤖 ตั้งค่าระบบ AI</h3></div>' +
      this._stepIndicator(page, 1) +
      '<div class="c-admin-wizard__body">' +
      '<h4>ขั้นตอนที่ 1: เลือกผู้ให้บริการ AI</h4>' +
      '<p class="u-text-muted">เลือก Provider ที่ต้องการใช้ แล้วกด "ต่อไป"</p>' +
      '<div class="c-admin-provider__cards">' +
      providers.map(p => {
        const act = p.name === selected_provider ? ' c-admin-provider__card--active' : '';
        const modelCount = (p.models || []).length;
        return '<div class="c-card c-admin-provider__card' + act + '" data-provider="' + Ui.esc(p.name) + '">' +
          '<div class="c-admin-provider__card-name">' + Ui.esc(p.display_name || p.name) + '</div>' +
          '<div class="c-admin-provider__card-meta">' + modelCount + ' โมเดล</div>' +
          '</div>';
      }).join('') +
      '</div></div>' +
      '<div class="c-admin-wizard__actions">' +
      '<button class="c-btn c-btn--primary" id="wizard-next-1" disabled>ต่อไป →</button>' +
      '</div></div>';

    // Card click handler
    page.querySelectorAll('.c-admin-provider__card').forEach(card => {
      card.addEventListener('click', () => {
        page.querySelectorAll('.c-admin-provider__card').forEach(c => c.classList.remove('c-admin-provider__card--active'));
        card.classList.add('c-admin-provider__card--active');
        this._state.selected_provider = card.dataset.provider;
        document.getElementById('wizard-next-1').disabled = false;
      });
    });

    document.getElementById('wizard-next-1').addEventListener('click', () => {
      this._state.step = 2;
      this._renderStep(page);
    });
  },

  // ── Step 2: เลือก Translate Model + Discovery Model ──
  _renderStep2(page) {
    const { providers, selected_provider, selected_model, selected_discovery } = this._state;
    const activeProvider = providers.find(p => p.name === selected_provider) || {};
    const models = activeProvider.models || [];

    let translateOpts = models.map(m =>
      `<option value="${Ui.esc(m.id)}" ${m.id === selected_model ? 'selected' : ''}>${Ui.esc(m.name || m.id)}</option>`
    ).join('');
    if (!models.some(m => m.id === selected_model) && selected_model) {
      translateOpts = `<option value="${Ui.esc(selected_model)}" selected>${Ui.esc(selected_model)}</option>` + translateOpts;
    }

    let discOpts = models.map(m =>
      `<option value="${Ui.esc(m.id)}" ${m.id === selected_discovery ? 'selected' : ''}>${Ui.esc(m.name || m.id)}</option>`
    ).join('');
    discOpts += '<option value="openai/gpt-oss-120b:free"' + (selected_discovery === 'openai/gpt-oss-120b:free' ? ' selected' : '') + '>openai/gpt-oss-120b:free</option>';

    page.innerHTML = '<div class="c-container">' +
      Ui.adminNav('provider') +
      '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">🤖 ตั้งค่าระบบ AI</h3></div>' +
      this._stepIndicator(page, 2) +
      '<div class="c-admin-wizard__body">' +
      '<h4>ขั้นตอนที่ 2: เลือกโมเดล</h4>' +
      '<p class="u-text-muted">Provider: <strong>' + Ui.esc(activeProvider.display_name || selected_provider) + '</strong></p>' +
      '<div class="c-form__group">' +
      '<label class="c-form__label">โมเดลสำหรับแปล (Translate)</label>' +
      '<select class="c-form__select" id="wiz-model-select">' + translateOpts + '</select>' +
      '</div>' +
      '<div class="c-form__group">' +
      '<label class="c-form__label">โมเดลค้นหาคำศัพท์ (Discovery)</label>' +
      '<p class="c-form__help-text">ใช้ LLM อีกตัวเพื่อค้นหา + เสนอคำแปลคำศัพท์ใหม่</p>' +
      '<select class="c-form__select" id="wiz-discovery-select">' + discOpts + '</select>' +
      '</div>' +
      '</div>' +
      '<div class="c-admin-wizard__actions">' +
      '<button class="c-btn c-btn--ghost" id="wizard-prev-2">← ย้อนกลับ</button>' +
      '<button class="c-btn c-btn--primary" id="wizard-next-2">ต่อไป →</button>' +
      '</div></div>';

    document.getElementById('wizard-prev-2').addEventListener('click', () => {
      this._state.step = 1;
      this._renderStep(page);
    });
    document.getElementById('wizard-next-2').addEventListener('click', () => {
      this._state.selected_model = document.getElementById('wiz-model-select').value;
      this._state.selected_discovery = document.getElementById('wiz-discovery-select').value;
      this._state.step = 3;
      this._renderStep(page);
    });
  },

  // ── Step 3: Summary + Save ──
  _renderStep3(page) {
    const { selected_provider, selected_model, selected_discovery, providers } = this._state;
    const p = providers.find(x => x.name === selected_provider) || {};
    const pName = p.display_name || selected_provider;

    page.innerHTML = '<div class="c-container">' +
      Ui.adminNav('provider') +
      '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">🤖 ตั้งค่าระบบ AI</h3></div>' +
      this._stepIndicator(page, 3) +
      '<div class="c-admin-wizard__body">' +
      '<h4>ขั้นตอนที่ 3: ตรวจสอบและบันทึก</h4>' +
      '<div class="c-card c-admin-wizard__summary">' +
      '<table class="c-table"><tbody>' +
      '<tr><td>ผู้ให้บริการ</td><td><strong>' + Ui.esc(pName) + '</strong></td></tr>' +
      '<tr><td>โมเดลแปล</td><td><strong>' + Ui.esc(selected_model) + '</strong></td></tr>' +
      '<tr><td>โมเดลค้นหาคำศัพท์</td><td><strong>' + Ui.esc(selected_discovery) + '</strong></td></tr>' +
      '</tbody></table>' +
      '</div>' +
      '<div id="wizard-status"></div>' +
      '<div class="c-admin-wizard__actions">' +
      '<button class="c-btn c-btn--ghost" id="wizard-prev-3">← ย้อนกลับ</button>' +
      '<button class="c-btn c-btn--primary" id="wizard-save">💾 บันทึก</button>' +
      '</div></div></div>';

    document.getElementById('wizard-prev-3').addEventListener('click', () => {
      this._state.step = 2;
      this._renderStep(page);
    });

    document.getElementById('wizard-save').addEventListener('click', async () => {
      const btn = document.getElementById('wizard-save');
      const statusEl = document.getElementById('wizard-status');
      btn.disabled = true;
      btn.textContent = '⏳ กำลังบันทึก...';
      statusEl.innerHTML = '<span class="c-badge c-badge--amber">⏳ กำลังบันทึก...</span>';
      try {
        await Api.saveProviderConfig({
          active: this._state.selected_provider,
          default_model: this._state.selected_model,
          discovery_model: this._state.selected_discovery,
        });
        statusEl.innerHTML = '<span class="c-badge c-badge--teal">✅ บันทึกสำเร็จ!</span>';
        btn.textContent = '✅ บันทึกแล้ว';
        Ui.showToast('บันทึกการตั้งค่าเรียบร้อย');
        // Show done
        this._state.step = 4;
        setTimeout(() => this._renderStep(page), 1000);
      } catch (err) {
        statusEl.innerHTML = '<span class="c-badge c-badge--red">❌ ' + Ui.esc(err.message) + '</span>';
        btn.disabled = false;
        btn.textContent = '💾 ลองอีกครั้ง';
      }
    });
  },

  // ── Done ──
  _renderDone(page) {
    page.innerHTML = '<div class="c-container">' +
      Ui.adminNav('provider') +
      '<div class="c-section__header c-admin-page__header"><h3 class="c-section__title">🤖 ตั้งค่าระบบ AI</h3></div>' +
      '<div class="c-admin-wizard__body c-admin-wizard__done">' +
      '<div class="c-admin-wizard__done-icon">🎉</div>' +
      '<h4>ตั้งค่าเสร็จสมบูรณ์!</h4>' +
      '<p class="u-text-muted">ระบบ AI พร้อมทำงานแล้ว ต่อไปก็แค่กดแปล!</p>' +
      '<a href="#admin/translate" class="c-btn c-btn--primary c-btn--lg" data-nav>ไปหน้าแปล →</a>' +
      '</div></div>';
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
    'novel-edit': AdminNovelEditPage,
    'logs': AdminLogsPage,
    'translate': AdminTranslatePage,
    'provider': AdminProviderPage,
  };
  const handler = adminRoutes[sub] || AdminDashboardPage;
  handler.render(p);
});
