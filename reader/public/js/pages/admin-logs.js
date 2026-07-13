/* Admin audit log page. Loaded lazily from admin.js. */

(function () {
  window.AdminLogsPage = {
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

          const selectHtml = '<div class="c-container">' + Ui.adminNav('logs') +
            '<section class="c-control-center c-admin-cockpit c-admin-logs__cockpit">' +
            '<div class="c-control-center__head"><div>' +
            '<h2 class="c-control-center__title">' + Ui.icon('search', 'sm') + 'บันทึกตรวจสอบ</h2>' +
            '<p class="c-control-center__subtitle">ใช้ตรวจรายละเอียดรายตอนเมื่อผลแปลแปลก, failed, หรือ needs review</p>' +
            '</div><a class="c-btn c-btn--secondary" href="#admin/translate" data-nav>' + Ui.icon('book', 'xs') + '<span>ศูนย์งานแปล</span></a></div>' +
            '<div class="c-control-center__stats">' +
            Ui.stat('novels', novels.length) +
            Ui.stat('mode', 'read-only') +
            '</div></section>' +
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
          '<section class="c-control-center c-admin-cockpit c-admin-logs__cockpit">' +
          '<div class="c-control-center__head"><div>' +
          '<h2 class="c-control-center__title">' + Ui.icon('search', 'sm') + 'Audit Log</h2>' +
          '<p class="c-control-center__subtitle">' + Ui.esc(slug) + ' · ตอน ' + Ui.esc(num) + '</p>' +
          '</div><a href="#admin/logs" class="c-btn c-btn--secondary c-admin-logs__link" data-nav>' + Ui.icon('search', 'xs') + '<span>ค้นหาใหม่</span></a></div>' +
          '<div class="c-control-center__actions">' +
          '<a class="c-btn c-btn--ghost" href="#novel/' + Ui.esc(slug) + '/' + Ui.esc(num) + '" data-nav>' + Ui.icon('book', 'xs') + '<span>เปิดตอน</span></a>' +
          '<a class="c-btn c-btn--ghost" href="#admin/translate/' + Ui.esc(slug) + '" data-nav>' + Ui.icon('settings', 'xs') + '<span>ไปหน้าแปล</span></a>' +
          '</div></section>';

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
    },
  };
})();
