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
            <svg class="c-empty__mascot" aria-hidden="true"><use xlink:href="#mascot-crab-reading"/></svg>
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
      const totalChapters = novels.reduce((sum, novel) => sum + novel.totalCount, 0);
      const translatedChapters = novels.reduce((sum, novel) => sum + novel.translatedCount, 0);

      page.innerHTML = `<div class="c-container">
        <section class="c-control-center" aria-labelledby="home-heading">
          <div class="c-control-center__head">
            <div>
              <h1 class="c-control-center__title" id="home-heading">คลังอ่านบนเครื่องนี้</h1>
              <p class="c-control-center__subtitle">กลับไปอ่านต่อหรือเลือกเรื่องจากคลัง โดยไม่ต้องผ่าน dashboard หลายชั้น</p>
            </div>
            <a href="${continueHref}" class="c-btn c-btn--primary c-btn--lg" data-nav>${Ui.icon('book', 'xs')}<span>${continueNum ? `อ่านต่อตอนที่ ${Ui.esc(continueNum)}` : 'เริ่มอ่าน'}</span>${Ui.icon('arrow-right', 'xs')}</a>
          </div>
          <div class="c-control-center__stats">
            ${Ui.stat('นิยาย', novels.length)}
            ${Ui.stat('ตอนทั้งหมด', totalChapters)}
            ${Ui.stat('แปลแล้ว', translatedChapters, { tone: 'success' })}
            ${Ui.stat('รอแปล', Math.max(0, totalChapters - translatedChapters), { tone: 'warn' })}
          </div>
        </section>

        <section class="c-section" aria-labelledby="home-library-heading">
          <div class="c-section__header">
            <h2 class="c-section__title" id="home-library-heading">นิยายของคุณ</h2>
            <a href="#library" class="c-section__link" data-nav><span>เปิดคลังเต็ม</span>${Ui.icon('arrow-right', 'xs')}</a>
          </div>
          <div class="c-card-grid">${novels.map(novel => Ui.novelCard(novel)).join('')}</div>
        </section>
      </div>`;
    } catch (error) {
      Ui.showError(page, 'โหลดคลังไม่สำเร็จ', error.message);
    }
  },
};
