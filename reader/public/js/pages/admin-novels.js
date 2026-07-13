/* Admin novels page. Loaded lazily from admin.js. */

window.AdminNovelsPage = {
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
              const summary = AdminFormat.formatImportRepairSummary(slug, previewRepair);
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
              setTimeout(() => window.AdminNovelsPage.render(params), 900);
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
            if (confirm('คำเตือน: คุณต้องการลบนิยาย "' + slug + '" ใช่หรือไม่?\nการลบนี้จะทำลายโฟลเดอร์นิยาย บทแปล และศัพท์เฉพาะทั้งหมดอย่างถาวรและไม่สามารถเรียกคืนได้!')) {
              try {
                btn.disabled = true;
                AdminUi.setButton(btn, 'close', 'กำลังลบ...');
                await Api.deleteNovel(slug);
                Ui.showToast('ลบนิยาย "' + slug + '" เรียบร้อยแล้วค่ะ');
                await window.AdminNovelsPage.render(params);
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
        '<header class="c-page-heading c-page-heading--studio"><div><span class="c-page-heading__eyebrow">Library</span><h1>รายการนิยายทั้งหมด</h1><p>ค้นหา ตรวจสุขภาพ และจัดการนิยายในคลังจากหน้าเดียว</p></div><div class="c-page-heading__actions"><span id="admin-novel-count" class="c-admin-page__meta"></span></div></header>' +
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
    } catch (err) {
      Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
    }
  },
};
