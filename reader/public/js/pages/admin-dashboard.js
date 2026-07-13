/* Admin dashboard page. Loaded lazily from admin.js. */

(function () {
  window.AdminDashboardPage = {
    async render(params) {
      const page = Ui.$('page-admin');
      if (!page) return;
      Ui.showSkeleton('page-admin');
      try {
        const novels = await Api.getNovels();
        const totalChapters = novels.reduce((a, n) => a + (n.chapterCount || 0), 0);
        const translatedChapters = novels.reduce((a, n) => a + (n.translatedChapters || 0), 0);
        const untranslated = totalChapters - translatedChapters;

        const progressPct = totalChapters ? Math.round((translatedChapters / totalChapters) * 100) : 0;
        const firstNovel = novels.find(Ui.isVisibleNovel) || novels[0];
        page.innerHTML = '<div class="c-container">' + Ui.adminNav('dashboard') +
          '<section class="c-control-center c-admin-cockpit">' +
          '<div class="c-control-center__head"><div>' +
          '<h2 class="c-control-center__title">' + Ui.icon('home', 'sm') + 'ศูนย์จัดการระบบ</h2>' +
          '<p class="c-control-center__subtitle">จุดรวมงานดูแลระบบ: นำเข้า source, สั่งแปล, ตรวจตอน, จัดคำศัพท์ และตั้งค่า AI</p>' +
          '</div><a class="c-btn c-btn--primary" href="#admin/translate' + (firstNovel ? '/' + Ui.esc(firstNovel.slug) : '') + '" data-nav>' + Ui.icon('book', 'xs') + '<span>คิวแปล</span></a></div>' +
          '<div class="c-control-center__stats">' +
          Ui.stat('นิยาย', novels.length) +
          Ui.stat('ตอนทั้งหมด', totalChapters) +
          Ui.stat('แปลแล้ว', translatedChapters, { tone: 'success' }) +
          Ui.stat('รอแปล', untranslated, { tone: untranslated ? 'warn' : 'success' }) +
          '</div>' +
          '<div class="c-card__progress c-admin-cockpit__progress" aria-label="ความคืบหน้าการแปล ' + progressPct + '%"><span class="c-card__progress-bar"><span class="c-card__progress-fill ' + Ui.progressClass(progressPct) + '"></span></span><span class="c-card__progress-pct">' + progressPct + '%</span></div>' +
          '<div class="c-control-center__actions">' +
          '<a class="c-btn c-btn--secondary" href="#admin/import" data-nav>' + Ui.icon('library', 'xs') + '<span>ศูนย์นำเข้า</span></a>' +
          '<a class="c-btn c-btn--secondary" href="#admin/novels" data-nav>' + Ui.icon('info', 'xs') + '<span>จัดการคลัง</span></a>' +
          '<a class="c-btn c-btn--secondary" href="#admin/glossary" data-nav>' + Ui.icon('bookmarks', 'xs') + '<span>คำศัพท์</span></a>' +
          '<a class="c-btn c-btn--ghost" href="#admin/provider" data-nav>' + Ui.icon('settings', 'xs') + '<span>ตั้งค่า AI</span></a>' +
          '</div></section>' +
          '<section class="c-section"><div class="c-admin-dashboard__grid">' +
          '<a href="#admin/chapters' + (firstNovel ? '/' + Ui.esc(firstNovel.slug) : '') + '" class="c-card c-admin-dashboard__tile" data-nav>' +
          Ui.icon('book', 'md') + '<div><div class="c-admin-dashboard__tile-title">จัดการตอน</div><div class="c-admin-dashboard__tile-meta">เลือกตอน ซ่อม source และเปิดหน้าอ่าน</div></div></a>' +
          '<a href="#admin/logs" class="c-card c-admin-dashboard__tile" data-nav>' +
          Ui.icon('search', 'md') + '<div><div class="c-admin-dashboard__tile-title">บันทึกตรวจสอบ</div><div class="c-admin-dashboard__tile-meta">ตรวจผลลัพธ์รายตอนเมื่อจำเป็น</div></div></a>' +
          '<a href="#settings" class="c-card c-admin-dashboard__tile" data-nav>' +
          Ui.icon('settings', 'md') + '<div><div class="c-admin-dashboard__tile-title">ตั้งค่าเครื่องนี้</div><div class="c-admin-dashboard__tile-meta">ธีม ตัวอักษร และโปรแกรมแก้ไข</div></div></a>' +
          '</div></section></div>';
      } catch (err) {
        Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
      }
    },
  };
})();
