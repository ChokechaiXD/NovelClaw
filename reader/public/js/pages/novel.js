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
      if (titleEl) titleEl.textContent = Ui.esc(Ui.displayTitle(novel));

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
          ${Ui.coverSVG(novel.slug, Ui.displayTitle(novel))}
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
          <a href="#novel/${slug}/${chapters[0]?.num||1}" class="c-hero__cta" data-nav>เริ่มอ่านตอนแรก</a>
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
            
            const loader = document.getElementById('reader-translation-loader');
            if (loader) loader.style.display = 'flex';
            
            try {
              const res = await Api.translateSingle(chSlug, chNum, true);
              if (res.ok) {
                Api.invalidateChapterContent(chSlug, chNum);
                Api.invalidateChapters(chSlug);
                alert(`แปลตอนที่ ${chNum} สำเร็จเรียบร้อยแล้วค่ะ!`);
                // โหลดหน้านี้ใหม่เพื่ออัปเดตสถานะปุ่ม
                await NovelPage.render(params);
              } else {
                alert('การแปลขัดข้อง: ' + (res.error?.message || 'ข้อผิดพลาดระบบ'));
              }
            } catch (err) {
              alert('เกิดข้อผิดพลาดในการแปล: ' + err.message);
            } finally {
              if (loader) loader.style.display = 'none';
            }
          });
        }
      };

      html += `
      <div class="c-section">
        ${rangesHtml}
        <div class="c-detail__chapters" id="detail-chapters-grid-container">`;

      for (const ch of pageChapters) {
        const read = Store.isRead(slug, ch.num);
        const sourceOnly = ch.status === 'source_only';
        const chClass = `c-detail__ch-btn ${read ? 'c-detail__ch-btn--read' : ''} ${sourceOnly ? 'c-detail__ch-btn--source-only' : ''}`;
        html += `
          <div class="c-detail__ch-wrapper" style="position:relative;">
            <a href="#novel/${slug}/${ch.num}" class="${chClass.trim()}" data-nav style="display:block; padding-right:${sourceOnly ? '32px' : 'var(--space-sm)'};">
              ${Ui.esc(ch.title || 'ตอนที่ ' + ch.num)}
              ${read ? '<br><span style="font-size:9px;color:var(--c-success);">✔ อ่านแล้ว</span>' : ''}
            </a>
            ${sourceOnly ? `
              <button class="ch-quick-translate-btn" data-slug="${slug}" data-num="${ch.num}" title="แปลไทยด้วย AI ทันที" style="position:absolute; right:4px; top:50%; transform:translateY(-50%); width:24px; height:24px; display:flex; align-items:center; justify-content:center; background:var(--c-accent-soft); border:1px solid var(--c-accent); border-radius:4px; color:var(--c-accent); font-size:10px; cursor:pointer; transition:all 0.15s; z-index:10;">
                ⚡
              </button>
            ` : ''}
          </div>`;
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
          grid.innerHTML = '';
          for (const ch of pChs) {
            const read = Store.isRead(slug, ch.num);
            const sourceOnly = ch.status === 'source_only';
            const chClass = `c-detail__ch-btn ${read ? 'c-detail__ch-btn--read' : ''} ${sourceOnly ? 'c-detail__ch-btn--source-only' : ''}`;
            
            const wrapper = Ui.el('div', { class: 'c-detail__ch-wrapper', style: 'position:relative;' });
            const link = Ui.el('a',
              { href: `#novel/${slug}/${ch.num}`, class: chClass.trim(), 'data-nav': '', style: `display:block; padding-right:${sourceOnly ? '32px' : 'var(--space-sm)'};` },
              `${ch.title || 'ตอนที่ ' + ch.num}${read ? ' ✔' : ''}`
            );
            wrapper.appendChild(link);
            
            if (sourceOnly) {
              const translateBtn = Ui.el('button', {
                class: 'ch-quick-translate-btn',
                'data-slug': slug,
                'data-num': ch.num,
                title: 'แปลไทยด้วย AI ทันที',
                style: 'position:absolute; right:4px; top:50%; transform:translateY(-50%); width:24px; height:24px; display:flex; align-items:center; justify-content:center; background:var(--c-accent-soft); border:1px solid var(--c-accent); border-radius:4px; color:var(--c-accent); font-size:10px; cursor:pointer; transition:all 0.15s; z-index:10;'
              }, '⚡');
              wrapper.appendChild(translateBtn);
            }
            grid.appendChild(wrapper);
          }
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
