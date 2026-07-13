/* home.js — Reading-first local library landing page. */

const HomePage = {
  async render() {
    const page = Ui.$('page-home');
    if (!page) return;
    Ui.showSkeleton(page);

    try {
      const novels = (await Api.getNovels())
        .filter(Ui.isVisibleNovel)
        .map(Ui.enrichNovel);

      if (!novels.length) {
        page.innerHTML = `<div class="c-container">
          <div class="c-empty c-empty--roomy">
            <svg class="c-empty__mascot" aria-hidden="true"><use href="#brand-mark"/></svg>
            <h1 class="c-empty__title">ยังไม่มีนิยายในคลัง</h1>
            <p class="c-empty__desc">นำเข้าไฟล์หรือ URL แล้วเริ่มอ่านจากเครื่องนี้ได้ทันที</p>
            <a class="c-btn c-btn--primary" href="#admin/import" data-nav>${Ui.icon('library', 'xs')}<span>นำเข้านิยาย</span></a>
          </div>
        </div>`;
        return;
      }

      const recent = Store.getHistory().find(entry => novels.some(novel => novel.slug === entry.slug));
      const continueNovel = novels.find(novel => novel.slug === recent?.slug)
        || novels.find(novel => novel.lastRead)
        || novels[0];
      const continueNum = recent?.num || continueNovel.lastRead;
      const continueHref = `#novel/${Ui.esc(continueNovel.slug)}${continueNum ? `/${Ui.esc(continueNum)}` : ''}`;
      page.innerHTML = `<div class="c-container">
        <section class="c-home-folio" aria-labelledby="home-heading">
          <a class="c-home-folio__cover" href="#novel/${Ui.esc(continueNovel.slug)}" data-nav aria-label="เปิด ${Ui.esc(Ui.displayTitle(continueNovel))}">
            ${Ui.coverHtml(continueNovel, { priority: true })}
          </a>
          <div class="c-home-folio__body">
            <p class="c-home-folio__eyebrow">อ่านต่อจากครั้งล่าสุด</p>
            <h1 class="c-home-folio__title" id="home-heading">${Ui.esc(Ui.displayTitle(continueNovel))}</h1>
            <p class="c-home-folio__meta">${Ui.esc(continueNovel.author || 'ไม่ระบุผู้แต่ง')} · ${Ui.esc((continueNovel.source_lang || 'auto').toUpperCase())} → ${Ui.esc((continueNovel.target_lang || 'th').toUpperCase())}</p>
            <p class="c-home-folio__note">${continueNum ? `ค้างไว้ที่ตอน ${Ui.esc(continueNum)}` : 'เรื่องนี้พร้อมให้เริ่มอ่าน'} · มีฉบับแปล ${continueNovel.translatedCount}/${continueNovel.totalCount} ตอน</p>
            <div class="c-home-folio__actions">
              <a href="${continueHref}" class="c-btn c-btn--primary c-btn--lg" data-nav>${Ui.icon('book', 'xs')}<span>${continueNum ? `อ่านต่อตอนที่ ${Ui.esc(continueNum)}` : 'เริ่มอ่าน'}</span>${Ui.icon('arrow-right', 'xs')}</a>
              <a href="#novel/${Ui.esc(continueNovel.slug)}" class="c-btn c-btn--ghost" data-nav>ดูสารบัญ</a>
            </div>
          </div>
          <div class="c-home-folio__ribbon" aria-label="ตำแหน่งอ่านล่าสุด ตอน ${Ui.esc(continueNum || 1)} จาก ${continueNovel.totalCount}">
            <span>ตอนล่าสุด</span>
            <strong>${Ui.esc(continueNum || 1)}</strong>
            <small>จาก ${continueNovel.totalCount}</small>
          </div>
        </section>

        <section class="c-section" aria-labelledby="home-library-heading">
          <div class="c-section__header">
            <div>
              <p class="c-section__eyebrow">ห้องอ่าน</p>
              <h2 class="c-section__title" id="home-library-heading">นิยายในคลัง</h2>
            </div>
            <a href="#library" class="c-section__link" data-nav><span>ดูทั้งหมด ${novels.length} เรื่อง</span>${Ui.icon('arrow-right', 'xs')}</a>
          </div>
          <div class="c-card-grid">${novels.map(novel => Ui.novelCard(novel)).join('')}</div>
        </section>
      </div>`;
    } catch (error) {
      Ui.showError(page, 'โหลดคลังไม่สำเร็จ', error.message);
    }
  },
};
