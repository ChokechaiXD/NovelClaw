/* Bookmarks page. Loaded with the main reader pages. */

window.BookmarksPage = {
  async render(params = {}) {
    const page = Ui.$('page-bookmarks');
    if (!page) return;
    try {
      const list = JSON.parse(localStorage.getItem('novelclaw-bookmarks')) || [];
      if (list.length === 0) {
        Ui.showEmpty(page, 'ยังไม่มีบุ๊กมาร์ก', 'เมื่อบุ๊กมาร์กตอนที่ชอบจะปรากฏที่นี่');
        return;
      }
      const novels = await Api.getNovels();
      let html = '<div class="c-container c-bookmarks-page">' +
        '<section class="c-control-center c-bookmarks-cockpit">' +
        '<div class="c-control-center__head"><div>' +
        '<h2 class="c-control-center__title">' + Ui.icon('bookmarks', 'sm') + 'Bookmarks</h2>' +
        '<p class="c-control-center__subtitle">รวมตอนที่ปักไว้ กลับไปอ่านต่อได้ทันทีโดยไม่ต้องค้นหาในรายการตอน</p>' +
        '</div><a class="c-btn c-btn--secondary" href="#library" data-nav>' + Ui.icon('library', 'xs') + '<span>เปิดคลัง</span></a></div>' +
        '<div class="c-control-center__stats">' +
        Ui.stat('bookmarks', list.length) +
        Ui.stat('novels', new Set(list.map(b => b.novel)).size) +
        '</div></section>' +
        '<section class="c-section"><div class="c-list c-history-list">';
      for (const b of list) {
        const n = novels.find(x => x.slug === b.novel);
        const title = Ui.displayTitle(n) || b.novel;
        html += '<a href="#novel/' + Ui.esc(b.novel) + '/' + Ui.esc(b.num) + '" class="c-list__item c-history-item" data-nav>' +
          '<div class="c-history-item__cover">' + Ui.coverHtml(n || { slug: b.novel, title }) + '</div>' +
          '<div class="c-list__info"><span class="c-list__title">' + Ui.esc(title) + '</span><span class="c-list__meta">ตอนที่ ' + Ui.esc(b.num) + '</span></div>' +
          '<span class="c-list__action">อ่าน ' + Ui.icon('arrow-right', 'xs') + '</span></a>';
      }
      html += '</div></section></div>';
      page.innerHTML = html;
    } catch (_) {
      Ui.showEmpty(page, 'เกิดข้อผิดพลาด', 'ไม่สามารถโหลดบุ๊กมาร์กได้');
    }
  },
};
