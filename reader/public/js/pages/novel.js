/* Novel detail page: content-first overview and chapter index. */

const NovelPage = {
  async render(params) {
    const page = Ui.$('page-novel-detail');
    if (!page) return;
    const slug = params.slug;
    if (!slug) { Ui.showError(page, 'ไม่พบนิยาย'); return; }

    Ui.showSkeleton('page-novel-detail');

    try {
      const novels = await Api.getNovels();
      const novel = novels.find(item => item.slug === slug);
      if (!novel) { Ui.showError(page, 'ไม่พบนิยาย'); return; }

      const titleEl = document.getElementById('page-title');
      if (titleEl) titleEl.textContent = Ui.displayTitle(novel);

      const chapters = await Api.getChapters(slug);
      const enriched = Ui.enrichNovel(novel);
      const hasLastRead = enriched.lastRead != null && chapters.some(chapter => String(chapter.num) === String(enriched.lastRead));
      const continueNum = hasLastRead ? enriched.lastRead : chapters[0]?.num;
      const readHref = continueNum
        ? `#novel/${Ui.esc(slug)}/${Ui.esc(continueNum)}`
        : `#admin/import/${Ui.esc(slug)}`;
      const readLabel = hasLastRead
        ? `อ่านต่อตอนที่ ${Ui.esc(continueNum)}`
        : (continueNum ? 'เริ่มอ่านตอนแรก' : 'นำเข้าตอนแรก');

      const languageNames = {
        cn: 'จีน', zh: 'จีน', ja: 'ญี่ปุ่น', jp: 'ญี่ปุ่น',
        ko: 'เกาหลี', kr: 'เกาหลี', en: 'อังกฤษ', th: 'ไทย',
      };
      const sourceLang = languageNames[String(novel.source_lang || 'cn').toLowerCase()] || String(novel.source_lang || 'จีน').toUpperCase();
      const targetLang = languageNames[String(novel.target_lang || 'th').toLowerCase()] || String(novel.target_lang || 'ไทย').toUpperCase();

      const pageSize = 100;
      let selectedPageIdx = 0;
      if (enriched.lastRead != null) {
        const readIdx = chapters.findIndex(chapter => String(chapter.num) === String(enriched.lastRead));
        if (readIdx !== -1) selectedPageIdx = Math.floor(readIdx / pageSize);
      }

      const numPages = Math.ceil(chapters.length / pageSize);
      let rangesHtml = '';
      if (chapters.length > pageSize) {
        rangesHtml = '<nav class="c-pagination c-chapter-index__pagination" aria-label="เลือกช่วงตอน">';
        for (let index = 0; index < numPages; index++) {
          const startCh = chapters[index * pageSize].num;
          const endCh = chapters[Math.min((index + 1) * pageSize - 1, chapters.length - 1)].num;
          const current = index === selectedPageIdx;
          rangesHtml += '<button class="c-btn c-btn--sm ' + (current ? 'c-btn--primary' : 'c-btn--ghost') + ' page-range-btn" data-page-idx="' + index + '" type="button"' + (current ? ' aria-current="page"' : '') + '>ตอน ' + Ui.esc(startCh) + '–' + Ui.esc(endCh) + '</button>';
        }
        rangesHtml += '</nav>';
      }

      const renderChapterRow = (chapter) => {
        const read = Store.isRead(slug, chapter.num);
        const sourceOnly = chapter.status === 'source_only';
        const translated = chapter.status === 'translated' || chapter.isTranslated === true;
        const rawTitle = String(chapter.title || '').trim();
        const genericTitles = new Set([`ตอนที่ ${chapter.num}`, `ตอน ${chapter.num}`, `Chapter ${chapter.num}`]);
        const chapterTitle = rawTitle && !genericTitles.has(rawTitle) ? rawTitle : 'ไม่มีชื่อตอน';
        const sourceStatus = sourceOnly
          ? 'มีต้นฉบับ · รอแปลไทย'
          : (translated ? 'พร้อมอ่านภาษาไทย' : (Ui.statusMap[chapter.status] || 'รอตรวจสถานะ'));
        const statusClass = sourceOnly ? 'source-only' : (translated ? 'translated' : 'pending');
        const rowClass = `c-detail__ch-wrapper c-chapter-row c-chapter-row--${statusClass}${read ? ' c-chapter-row--read' : ''}`;

        return `
          <li class="${rowClass}" data-source-status="${Ui.esc(statusClass)}">
            <a href="#novel/${Ui.esc(slug)}/${Ui.esc(chapter.num)}" class="c-detail__ch-btn c-chapter-row__link" data-nav aria-label="ตอนที่ ${Ui.esc(chapter.num)} ${Ui.esc(chapterTitle)}">
              <span class="c-chapter-row__number">ตอนที่ ${Ui.esc(chapter.num)}</span>
              <span class="c-chapter-row__main">
                <span class="c-chapter-row__title">${Ui.esc(chapterTitle)}</span>
                <span class="c-chapter-row__meta">
                  <span class="c-chapter-row__source-status">${Ui.esc(sourceStatus)}</span>
                  ${read ? '<span class="c-detail__read-mark c-chapter-row__read-status">อ่านแล้ว</span>' : '<span class="c-chapter-row__read-status">ยังไม่ได้อ่าน</span>'}
                </span>
              </span>
              <span class="c-chapter-row__open"><span>อ่าน</span>${Ui.icon('arrow-right', 'xs')}</span>
            </a>
            ${sourceOnly ? `
              <div class="c-detail__ch-actions c-chapter-row__actions">
                <button class="ch-quick-translate-btn" data-slug="${Ui.esc(slug)}" data-num="${Ui.esc(chapter.num)}" type="button" title="แปลตอนนี้เป็นภาษาไทย" aria-label="แปลตอนที่ ${Ui.esc(chapter.num)} เป็นภาษาไทย">
                  ${Ui.icon('book', 'xs')}
                  <span>แปลตอนนี้</span>
                </button>
              </div>
            ` : ''}
          </li>`;
      };

      const start = selectedPageIdx * pageSize;
      const pageChapters = chapters.slice(start, Math.min(start + pageSize, chapters.length));
      const synopsis = String(novel.description || '').trim() || 'ยังไม่มีเรื่องย่อ';

      page.innerHTML = `
        <article class="c-container c-novel-detail" aria-labelledby="novel-detail-title">
          <header class="c-detail c-novel-detail__hero">
            <figure class="c-detail__cover c-novel-detail__cover">
              ${Ui.coverHtml(novel)}
            </figure>
            <div class="c-detail__info c-novel-detail__info">
              <p class="c-novel-detail__eyebrow">ห้องอ่านหนังสือ</p>
              <h1 class="c-detail__title c-novel-detail__title" id="novel-detail-title">${Ui.esc(Ui.displayTitle(novel))}</h1>
              <p class="c-detail__author c-novel-detail__author">เขียนโดย ${Ui.esc(novel.author || 'ไม่ระบุชื่อผู้แต่ง')}</p>
              <p class="c-detail__synopsis c-novel-detail__synopsis">${Ui.esc(synopsis.slice(0, 600))}</p>
              <div class="c-detail__meta c-novel-detail__meta" aria-label="ข้อมูลนิยาย">
                <span class="c-meta-tag c-meta-tag--accent">${Ui.esc(sourceLang)} → ${Ui.esc(targetLang)}</span>
                <span class="c-meta-tag">${Ui.esc(Ui.statusMap[novel.status] || 'ไม่ระบุสถานะ')}</span>
                <span class="c-meta-tag">แปลแล้ว ${Ui.esc(enriched.translatedCount)} จาก ${Ui.esc(enriched.totalCount)} ตอน</span>
              </div>
              <div class="c-detail__workflow-actions c-novel-detail__actions">
                <a href="${readHref}" class="c-btn c-btn--primary c-novel-detail__resume" id="novel-primary-read" data-nav>
                  ${Ui.icon('book', 'xs')}<span>${readLabel}</span>${Ui.icon('arrow-right', 'xs')}
                </a>
                <a href="#admin/novel-edit/${Ui.esc(slug)}" class="c-btn c-btn--secondary c-novel-detail__studio-link" data-nav>
                  ${Ui.icon('settings', 'xs')}<span>เปิดสตูดิโอเรื่องนี้</span>
                </a>
              </div>
            </div>
          </header>

          <section class="c-section c-chapter-index" aria-labelledby="novel-chapter-heading">
            <div class="c-section__header c-chapter-index__header">
              <div>
                <p class="c-chapter-index__eyebrow">สารบัญ</p>
                <h2 class="c-section__title c-chapter-index__title" id="novel-chapter-heading">${Ui.esc(chapters.length)} ตอน</h2>
              </div>
              ${rangesHtml}
            </div>
            <ol class="c-detail__chapters c-chapter-list" id="detail-chapters-grid-container">
              ${pageChapters.map(renderChapterRow).join('')}
            </ol>
            ${chapters.length ? '' : '<p class="c-chapter-index__empty">ยังไม่มีตอนสำหรับอ่าน เปิดสตูดิโอเพื่อนำเข้าต้นฉบับตอนแรก</p>'}
          </section>
        </article>`;

      const bindTranslateEvents = (container) => {
        for (const btn of container.querySelectorAll('.ch-quick-translate-btn')) {
          btn.addEventListener('click', async (event) => {
            event.preventDefault();
            event.stopPropagation();

            const chSlug = btn.dataset.slug;
            const chNum = parseInt(btn.dataset.num, 10);
            if (!chSlug || Number.isNaN(chNum)) return;

            btn.disabled = true;
            btn.classList.add('ch-quick-translate-btn--running');
            btn.innerHTML = '<span>กำลังแปล...</span>';

            try {
              const res = await Api.translateSingle(chSlug, chNum, true);
              if (res.ok) {
                Ui.showToast(`แปลตอนที่ ${chNum} สำเร็จแล้ว`, 'success');
                await NovelPage.render(params);
              } else {
                Ui.showToast('แปลไม่สำเร็จ: ' + (res.error?.message || 'ระบบไม่ตอบกลับ'), 'error');
              }
            } catch (err) {
              if (err.code === 'SOURCE_NOT_READY') {
                const wrapper = btn.closest('.c-detail__ch-wrapper');
                if (wrapper && !wrapper.querySelector('.ch-source-inspect-link')) {
                  const actionRow = wrapper.querySelector('.c-detail__ch-actions') || wrapper;
                  actionRow.insertAdjacentHTML('beforeend',
                    '<a class="c-btn c-btn--xs c-btn--ghost ch-source-inspect-link" href="#admin/import/' +
                    Ui.esc(chSlug) + '/' + Ui.esc(chNum) + '" data-nav>ตรวจต้นฉบับ</a>'
                  );
                }
                btn.classList.add('ch-quick-translate-btn--blocked');
                btn.title = 'ต้นฉบับยังไม่พร้อมแปล';
              }
              const prefix = err.code === 'SOURCE_NOT_READY' ? 'ต้นฉบับยังไม่พร้อมแปล: ' : 'แปลไม่สำเร็จ: ';
              Ui.showToast(prefix + err.message, 'error');
            } finally {
              btn.disabled = false;
              btn.classList.remove('ch-quick-translate-btn--running');
              btn.innerHTML = `${Ui.icon('book', 'xs')}<span>แปลตอนนี้</span>`;
            }
          });
        }
      };

      bindTranslateEvents(page);

      for (const button of page.querySelectorAll('.page-range-btn')) {
        button.addEventListener('click', function() {
          const index = parseInt(this.dataset.pageIdx, 10);
          const rangeStart = index * pageSize;
          const rangeChapters = chapters.slice(rangeStart, Math.min(rangeStart + pageSize, chapters.length));
          const list = document.getElementById('detail-chapters-grid-container');
          if (!list) return;
          list.innerHTML = rangeChapters.map(renderChapterRow).join('');
          bindTranslateEvents(list);

          for (const rangeButton of page.querySelectorAll('.page-range-btn')) {
            const current = rangeButton === this;
            rangeButton.classList.toggle('c-btn--primary', current);
            rangeButton.classList.toggle('c-btn--ghost', !current);
            if (current) rangeButton.setAttribute('aria-current', 'page');
            else rangeButton.removeAttribute('aria-current');
          }
          list.querySelector('a')?.focus();
        });
      }
    } catch (err) {
      Ui.showError(page, 'โหลดนิยายไม่สำเร็จ', err.message);
    }
  },
};
