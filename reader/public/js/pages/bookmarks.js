/* Bookmarks page. Loaded with the main reader pages. */

window.BookmarksPage = {
  async render(params = {}) {
    const page = Ui.$('page-bookmarks');
    if (!page) return;
    try {
      const list = JSON.parse(localStorage.getItem('novelclaw-bookmarks')) || [];
      const novels = await Api.getNovels();
      let html = '<div class="c-container c-bookmarks-page">' +
        '<header class="c-page-heading">' +
        '<p class="c-page-heading__eyebrow">ห้องอ่าน</p>' +
        '<h1 class="c-page-heading__title">ตอนที่บันทึกไว้</h1>' +
        '<p class="c-page-heading__subtitle">เก็บตอนที่อยากกลับมาอ่านอีกครั้งไว้ในอุปกรณ์นี้</p>' +
        '<div class="c-page-heading__actions"><a class="c-btn c-btn--ghost" href="#history" data-nav>' + Ui.icon('history', 'xs') + '<span>อ่านล่าสุด</span></a></div>' +
        '</header>' +
        '<section class="c-section"><div class="c-list c-history-list">';
      if (list.length === 0) {
        html += '<div class="c-empty c-empty--roomy"><svg class="c-empty__mascot" aria-hidden="true"><use href="#brand-mark"/></svg><div class="c-empty__title">ยังไม่มีตอนที่บันทึกไว้</div><div class="c-empty__desc">กดบันทึกจากหน้าอ่าน แล้วตอนนั้นจะปรากฏที่นี่</div></div>';
      } else {
        for (const b of list) {
          const n = novels.find(x => x.slug === b.novel);
          const title = Ui.displayTitle(n) || b.novel;
          html += '<a href="#novel/' + Ui.esc(b.novel) + '/' + Ui.esc(b.num) + '" class="c-list__item c-history-item" data-nav>' +
            '<div class="c-history-item__cover">' + Ui.coverHtml(n || { slug: b.novel, title }) + '</div>' +
            '<div class="c-list__info"><span class="c-list__title">' + Ui.esc(title) + '</span><span class="c-list__meta">ตอนที่ ' + Ui.esc(b.num) + '</span></div>' +
            '<span class="c-list__action">อ่าน ' + Ui.icon('arrow-right', 'xs') + '</span></a>';
        }
      }
      html += '</div></section></div>';
      page.innerHTML = html;
    } catch (_) {
      Ui.showEmpty(page, 'เกิดข้อผิดพลาด', 'ไม่สามารถโหลดบุ๊กมาร์กได้');
    }
  },
};
