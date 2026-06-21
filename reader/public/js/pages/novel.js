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

      const chapters = await Api.getChapters(slug);
      const enriched = Ui.enrichNovel(novel);

      // Pagination
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
        <div class="c-detail__cover" style="background:linear-gradient(135deg,hsl(${enriched.hue},70%,40%),hsl(${(enriched.hue+40)%360},60%,30%));color:#000;">
          ${(novel.title||slug).charAt(0)}
        </div>
        <div class="c-detail__info">
          <h2 class="c-detail__title">${Ui.esc(novel.title||slug)}</h2>
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
      html += `
      <div class="c-detail__tabs">
        <button class="c-btn c-btn--primary detail-tab-btn active" data-tab="chapters">รายการตอน (${chapters.length})</button>
        <button class="c-btn c-btn--ghost detail-tab-btn" data-tab="reviews">รีวิว</button>
      </div>`;

      // ── Chapter List ──────────────────────────────────────────────────
      const numPages = Math.ceil(chapters.length / pageSize);
      let rangesHtml = '';
      if (chapters.length > pageSize) {
        rangesHtml = '<div class="c-pagination">';
        for (let i = 0; i < numPages; i++) {
          const startCh = chapters[i * pageSize].num;
          const endCh = chapters[Math.min((i + 1) * pageSize - 1, chapters.length - 1)].num;
          rangesHtml += `<button class="c-btn c-btn--sm ${i === selectedPageIdx ? 'c-btn--primary' : 'c-btn--ghost'} page-range-btn" data-page-idx="${i}">${startCh} - ${endCh}</button>`;
        }
        rangesHtml += '</div>';
      }

      const start = selectedPageIdx * pageSize;
      const end = Math.min(start + pageSize, chapters.length);
      const pageChapters = chapters.slice(start, end);

      html += `
      <div class="c-section">
        ${rangesHtml}
        <div class="c-detail__chapters" id="detail-chapters-grid-container">`;

      for (const ch of pageChapters) {
        const read = Store.isRead(slug, ch.num);
        html += `
          <a href="#novel/${slug}/${ch.num}" class="c-detail__ch-btn ${read ? 'c-detail__ch-btn--read' : ''}" data-nav>
            ตอนที่ ${ch.num}
            ${ch.title ? `<br><span style="font-size:10px;color:var(--c-text-muted);">${Ui.esc(ch.title)}</span>` : ''}
            ${read ? '<br><span style="font-size:9px;color:var(--c-success);">✔ อ่านแล้ว</span>' : ''}
          </a>`;
      }

      html += `</div></div>`;
      html += '</div>';

      page.innerHTML = html;

      // ── Wire pagination ──────────────────────────────────────────────
      page.querySelectorAll('.page-range-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const idx = parseInt(btn.dataset.pageIdx, 10);
          const pStart = idx * pageSize;
          const pEnd = Math.min(pStart + pageSize, chapters.length);
          const pChs = chapters.slice(pStart, pEnd);
          const grid = document.getElementById('detail-chapters-grid-container');
          if (!grid) return;
          grid.innerHTML = '';
          for (const ch of pChs) {
            const read = Store.isRead(slug, ch.num);
            grid.appendChild(Ui.el('a',
              { href: `#novel/${slug}/${ch.num}`, class: `c-detail__ch-btn ${read ? 'c-detail__ch-btn--read' : ''}`, 'data-nav': '' },
              `ตอนที่ ${ch.num}${ch.title ? ch.title : ''}${read ? '✔' : ''}`
            ));
          }
          page.querySelectorAll('.page-range-btn').forEach(b => b.classList.remove('c-btn--primary'));
          btn.classList.add('c-btn--primary');
        });
      });

      // ── Load synopsis ────────────────────────────────────────────────
      this._loadSynopsis(slug, novel);

    } catch (err) {
      Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
    }
  },

  async _loadSynopsis(slug, novel) {
    try {
      const res = await fetch(`/api/novel/${slug}/meta`);
      if (res.ok) {
        const meta = await res.json();
        const synopsis = document.querySelector('.c-detail__synopsis');
        if (synopsis && meta.description) {
          synopsis.textContent = meta.description.slice(0, 300);
        } else if (synopsis) {
          synopsis.textContent = 'ยังไม่มีคำอธิบาย';
        }
      }
    } catch {}
  }
};
