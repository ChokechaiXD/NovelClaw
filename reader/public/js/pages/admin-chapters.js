/* Admin chapters page. Loaded lazily from admin.js. */

window.AdminChaptersPage = {
  async render(params) {
    const page = Ui.$('page-admin-chapters');
    if (!page) return;
    try {
      const novels = await Api.getNovels();
      const firstReal = novels.find(Ui.isVisibleNovel);
      const slug = params.slug || firstReal?.slug || novels[0]?.slug;
      if (!slug) {
        page.innerHTML = '<div class="c-container">' + Ui.adminNav('chapters') +
          '<header class="c-page-heading c-page-heading--studio"><div><span class="c-page-heading__eyebrow">Chapter library</span><h1>จัดการตอนทั้งหมด</h1><p>เพิ่มนิยายหรือนำเข้าต้นฉบับก่อนเริ่มจัดการตอน</p></div></header>' +
          '<div class="c-empty c-empty--compact"><div class="c-empty__title">ยังไม่มีนิยายในระบบ</div><div class="c-empty__desc">สร้างคลังเรื่องแรกจากไฟล์ URL หรือข้อความ</div><div class="c-page-heading__actions"><a class="c-btn c-btn--primary" href="#admin/import" data-nav>นำเข้าต้นฉบับ</a></div></div></div>';
        return;
      }
      const [chapters, importHealthResp] = await Promise.all([
        Api.getChapters(slug),
        Api.getImportHealth(slug, { includeChapters: true }).catch(() => ({ data: { chapters: [] } })),
      ]);
      if (!chapters || chapters.length === 0) {
        page.innerHTML = '<div class="c-container">' + Ui.adminNav('chapters') +
          '<header class="c-page-heading c-page-heading--studio"><div><span class="c-page-heading__eyebrow">Chapter library</span><h1>จัดการตอนทั้งหมด</h1><p>' + Ui.esc(slug) + ' · ยังไม่มีตอนที่พร้อมจัดการ</p></div></header>' +
          '<div class="c-empty c-empty--compact"><div class="c-empty__title">ยังไม่มีตอนในเรื่องนี้</div><div class="c-empty__desc">นำเข้าต้นฉบับเพื่อสร้างรายการตอน</div><div class="c-page-heading__actions"><a class="c-btn c-btn--primary" href="#admin/import/' + Ui.esc(slug) + '" data-nav>นำเข้าต้นฉบับ</a></div></div></div>';
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
          '<header class="c-page-heading c-page-heading--studio"><div><span class="c-page-heading__eyebrow">Chapter library</span><h1>จัดการตอนทั้งหมด</h1><p>' + Ui.esc(slug) + ' · เลือก ตรวจ และส่งตอนเข้า workflow การแปล</p></div><div class="c-page-heading__actions"><span class="c-admin-page__meta">' + totalFiltered + ' / ' + chapters.length + ' ตอน</span></div></header>' +
          '<div class="c-admin-chapters__summary">' +
          Ui.stat('แปลแล้ว', chapters.filter(c => c.status === 'translated').length, { tone: 'success' }) +
          Ui.stat('ต้นฉบับ', chapters.filter(c => c.status === 'source_only').length, { tone: 'warn' }) +
          Ui.stat('source error', importHealth.blockingSourceCount || 0, { tone: importHealth.blockingSourceCount ? 'warn' : 'success' }) +
          Ui.stat('เลือกไว้', selectedNums.size, { tone: 'accent' }) +
          '</div>' +
          '<div class="c-admin-chapters__filters">' +
          '<input id="ch-filter-search" type="text" placeholder="ค้นหาเลขตอน หรือชื่อ..." class="c-form__input c-admin-chapters__search" value="' + Ui.esc(searchQuery) + '" />' +
          '<select id="ch-filter-status" class="c-form__select c-admin-chapters__status-filter">' +
          '<option value="all"' + (filterStatus === 'all' ? ' selected' : '') + '>ทั้งหมด</option>' +
          '<option value="translated"' + (filterStatus === 'translated' ? ' selected' : '') + '>แปลแล้ว</option>' +
          '<option value="source_only"' + (filterStatus === 'source_only' ? ' selected' : '') + '>ต้นฉบับ</option>' +
          '<option value="source_error"' + (filterStatus === 'source_error' ? ' selected' : '') + '>source error</option>' +
          '<option value="source_dirty"' + (filterStatus === 'source_dirty' ? ' selected' : '') + '>source issue</option>' +
          '<option value="read"' + (filterStatus === 'read' ? ' selected' : '') + '>อ่านแล้ว</option>' +
          '<option value="unread"' + (filterStatus === 'unread' ? ' selected' : '') + '>ยังไม่อ่าน</option>' +
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
          '<div class="c-admin-chapters__pagination">' +
          '<button class="c-btn c-btn--xs" id="ch-page-prev" type="button"' + (currentPage <= 0 ? ' disabled' : '') + '>' + Ui.icon('arrow-left', 'xs') + '<span>ก่อนหน้า</span></button>' +
          '<span>หน้า ' + (currentPage + 1) + ' / ' + (maxPage + 1) + '</span>' +
          '<button class="c-btn c-btn--xs" id="ch-page-next" type="button"' + (currentPage >= maxPage ? ' disabled' : '') + '><span>ถัดไป</span>' + Ui.icon('arrow-right', 'xs') + '</button>' +
          '</div>' +
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
            Ui.showToast('ส่งงานแปลแล้ว');
            selectedNums.clear();
            await window.AdminChaptersPage.render({ slug });
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
              Ui.showToast('แปลตอน ' + num + ' สำเร็จ');
              await window.AdminChaptersPage.render({ slug });
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
    } catch (err) {
      Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
    }
  },
};
