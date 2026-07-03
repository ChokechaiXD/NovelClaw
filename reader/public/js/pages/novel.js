/* ═══════════════════════════════════════════════════════════════════════
   novel.js — Novel Detail Page
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const NovelPage = {
  async render(params) {
    const page = Ui.$('page-novel-detail');
    if (!page) return;
    const slug = params.slug;
    if (!slug) { Ui.showError(page, 'ไม่พบ Slug'); return; }

    Ui.showSkeleton('page-novel-detail');

    try {
      const novels = await Api.getNovels();
      const novel = novels.find(n => n.slug === slug);
      if (!novel) { Ui.showError(page, 'ไม่พบนิยาย'); return; }

      // Update topbar title with novel name
      const titleEl = document.getElementById('page-title');
      if (titleEl) titleEl.textContent = Ui.displayTitle(novel);

      const chapters = await Api.getChapters(slug);
      const enriched = Ui.enrichNovel(novel);

      const pageSize = 100;
      let selectedPageIdx = 0;
      if (enriched.lastRead) {
        const readIdx = chapters.findIndex(c => c.num === enriched.lastRead);
        if (readIdx !== -1) selectedPageIdx = Math.floor(readIdx / pageSize);
      }

      let html = '<div class="c-container">';

      // ── Header Card ──────────────────────────────────────────────────
      html += `
      <div class="c-detail">
        <div class="c-detail__cover">
          ${Ui.coverHtml(novel)}
        </div>
        <div class="c-detail__info">
          <h2 class="c-detail__title">${Ui.esc(Ui.displayTitle(novel))}</h2>
          <p class="c-detail__author">ผู้แต่ง: ${Ui.esc(novel.author||'ไม่ระบุ')}</p>
          <div class="c-detail__meta">
            <span class="c-hero__tag c-hero__tag--lang">${novel.source_lang||'cn'} → ${novel.target_lang||'th'}</span>
            <span class="c-hero__tag">${Ui.statusMap[novel.status]||'ไม่ระบุ'}</span>
            <span class="c-hero__tag">แปลไป ${enriched.translatedCount} / ${enriched.totalCount} ตอน (${enriched.translationPct}%)</span>
          </div>
          <p class="c-detail__synopsis">กำลังโหลดคำอธิบาย...</p>
          <div class="c-detail__workflow-actions">
            <a href="#novel/${slug}/${chapters[0]?.num||1}" class="c-btn c-btn--primary" data-nav>${Ui.icon('book', 'xs')}<span>เริ่มอ่าน</span>${Ui.icon('arrow-right', 'xs')}</a>
            <a href="#admin/translate" class="c-btn c-btn--secondary" data-nav>${Ui.icon('book', 'xs')}<span>สั่งแปล</span></a>
            <a href="#admin/import/${Ui.esc(slug)}" class="c-btn c-btn--ghost" data-nav>${Ui.icon('library', 'xs')}<span>นำเข้า/ซ่อม source</span></a>
            <a href="#admin/novel-edit/${Ui.esc(slug)}" class="c-btn c-btn--ghost" data-nav>${Ui.icon('settings', 'xs')}<span>แก้ข้อมูล/ปก</span></a>
          </div>
        </div>
      </div>`;

      // ── Tabs ──────────────────────────────────────────────────────────

      // ── Chapter List ──────────────────────────────────────────────────
      const numPages = Math.ceil(chapters.length / pageSize);
      let rangesHtml = '';
      if (chapters.length > pageSize) {
        rangesHtml = '<div class="c-pagination">';
        for (let i = 0; i < numPages; i++) {
          const startCh = chapters[i * pageSize].num;
          const endCh = chapters[Math.min((i + 1) * pageSize - 1, chapters.length - 1)].num;
          rangesHtml += '<button class="c-btn c-btn--sm ' + (i === selectedPageIdx ? 'c-btn--primary' : 'c-btn--ghost') + ' page-range-btn" data-page-idx="' + i + '">' + startCh + ' - ' + endCh + '</button>';
        }
        rangesHtml += '</div>';
      }

      const start = selectedPageIdx * pageSize;
      const end = Math.min(start + pageSize, chapters.length);
      const pageChapters = chapters.slice(start, end);

      const renderChapterButton = (ch) => {
        const read = Store.isRead(slug, ch.num);
        const sourceOnly = ch.status === 'source_only';
        const chClass = `c-detail__ch-btn ${read ? 'c-detail__ch-btn--read' : ''} ${sourceOnly ? 'c-detail__ch-btn--source-only c-detail__ch-btn--with-action' : ''}`;
        return `
          <div class="c-detail__ch-wrapper">
            <a href="#novel/${Ui.esc(slug)}/${Ui.esc(ch.num)}" class="${chClass.trim()}" data-nav>
              ${Ui.esc(ch.title || 'ตอนที่ ' + ch.num)}
              ${read ? '<br><span class="c-detail__read-mark">อ่านแล้ว</span>' : ''}
            </a>
            ${sourceOnly ? `
              <div class="c-detail__ch-actions">
                <button class="ch-quick-translate-btn" data-slug="${Ui.esc(slug)}" data-num="${Ui.esc(ch.num)}" type="button" title="แปลไทยด้วย AI ทันที" aria-label="แปลตอนที่ ${Ui.esc(ch.num)}">
                  <svg class="c-icon c-icon--xs c-icon--stroke"><use xlink:href="#icon-book"/></svg>
                  <span>แปล</span>
                </button>
              </div>
            ` : ''}
          </div>`;
      };

      // ฟังก์ชันสำหรับผูก Event สั่งแปลตอนแบบเจาะจง
      const bindTranslateEvents = (container) => {
        const translateBtns = container.querySelectorAll('.ch-quick-translate-btn');
        for (const btn of translateBtns) {
          btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            const chSlug = btn.dataset.slug;
            const chNum = parseInt(btn.dataset.num, 10);
            if (!chSlug || isNaN(chNum)) return;
            
            btn.disabled = true;
            btn.classList.add('ch-quick-translate-btn--running');
            btn.innerHTML = '<span>กำลังแปล...</span>';
            
            try {
              const res = await Api.translateSingle(chSlug, chNum, true);
              if (res.ok) {
                Ui.showToast(`แปลตอนที่ ${chNum} สำเร็จเรียบร้อยแล้วค่ะ`, 'success');
                // โหลดหน้านี้ใหม่เพื่ออัปเดตสถานะปุ่ม
                await NovelPage.render(params);
              } else {
                Ui.showToast('การแปลขัดข้อง: ' + (res.error?.message || 'ข้อผิดพลาดระบบ'), 'error');
              }
            } catch (err) {
              if (err.code === 'SOURCE_NOT_READY') {
                const wrapper = btn.closest('.c-detail__ch-wrapper');
                if (wrapper && !wrapper.querySelector('.ch-source-inspect-link')) {
                  const actionRow = wrapper.querySelector('.c-detail__ch-actions') || wrapper;
                  actionRow.insertAdjacentHTML('beforeend',
                    '<a class="c-btn c-btn--xs c-btn--ghost ch-source-inspect-link" href="#admin/import/' +
                    Ui.esc(chSlug) + '/' + Ui.esc(chNum) + '" data-nav>ตรวจ source</a>'
                  );
                }
                btn.classList.add('ch-quick-translate-btn--blocked');
                btn.title = 'Source ยังไม่พร้อมแปล';
              }
              Ui.showToast((err.code === 'SOURCE_NOT_READY' ? 'Source ยังไม่พร้อมแปล: ' : 'เกิดข้อผิดพลาดในการแปล: ') + err.message, 'error');
            } finally {
              btn.disabled = false;
              btn.classList.remove('ch-quick-translate-btn--running');
              btn.innerHTML = '<svg class="c-icon c-icon--xs c-icon--stroke"><use xlink:href="#icon-book"/></svg><span>แปล</span>';
            }
          });
        }
      };

      html += `
      <div class="c-section">
        ${rangesHtml}
        <div class="c-detail__chapters" id="detail-chapters-grid-container">`;

      for (const ch of pageChapters) {
        html += renderChapterButton(ch);
      }

      html += `</div></div>`;
      html += '</div>';

      page.innerHTML = html;
      bindTranslateEvents(page);

      // ── Wire pagination ──────────────────────────────────────────────
      const buttons = page.querySelectorAll('.page-range-btn');
      for (let b = 0; b < buttons.length; b++) {
        const btn = buttons[b];
        btn.addEventListener('click', function() {
          const idx = parseInt(this.dataset.pageIdx, 10);
          const pStart = idx * pageSize;
          const pEnd = Math.min(pStart + pageSize, chapters.length);
          const pChs = chapters.slice(pStart, pEnd);
          const grid = document.getElementById('detail-chapters-grid-container');
          if (!grid) return;
          grid.innerHTML = pChs.map(renderChapterButton).join('');
          bindTranslateEvents(grid);
          // Swap classes: remove primary from all, add ghost; add primary to clicked, remove ghost
          const allBtns = page.querySelectorAll('.page-range-btn');
          for (let i = 0; i < allBtns.length; i++) {
            allBtns[i].classList.remove('c-btn--primary');
            allBtns[i].classList.add('c-btn--ghost');
          }
          this.classList.remove('c-btn--ghost');
          this.classList.add('c-btn--primary');
        });
      }

      // ── Load synopsis ────────────────────────────────────────────────
      this._loadSynopsis(novel);

    } catch (err) {
      Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
    }
  },

  _loadSynopsis(novel) {
    const synopsis = document.querySelector('.c-detail__synopsis');
    if (synopsis) {
      synopsis.textContent = (novel.description || '').slice(0, 300) || 'ยังไม่มีคำอธิบาย';
    }
  },
};
