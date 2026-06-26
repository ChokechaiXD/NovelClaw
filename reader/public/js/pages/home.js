/* ═══════════════════════════════════════════════════════════════════════
   home.js — Home Dashboard Page
   NovelClaw Reader
   ═══════════════════════════════════════════════════════════════════════ */

const HomePage = {
  async render(params) {
    const page = Ui.$('page-home');
    if (!page) return;
    Ui.showSkeleton('page-home');

    try {
      const novels = await Api.getNovels();
      // Filter out test/fixture novels from reader-facing pages
      const visibleNovels = novels.filter(n => !n.slug?.startsWith('test-') && !n.slug?.startsWith('tmp-') && !n.slug?.startsWith('fixture-') && n.totalChapters > 0);
      const enriched = visibleNovels.map(Ui.enrichNovel);

      let html = '<div class="c-container">';

      // ── Hero ────────────────────────────────────────────────────────
      const featured = enriched[0];
      if (featured) {
        html += `
        <div class="c-hero">
          <div class="c-hero__content">
            <span class="c-hero__badge"><svg style="width:14px;height:14px;margin-right:4px;vertical-align:-2px;"><use xlink:href="#icon-ranking"/></svg>ยอดนิยม</span>
            <h2 class="c-hero__title">${Ui.esc(Ui.displayTitle(featured))}</h2>
            <p class="c-hero__subtitle">${Ui.esc(featured.slug)} • ${Ui.esc(featured.source_lang||'cn')} → ${Ui.esc(featured.target_lang||'th')}</p>
            <div class="c-hero__meta">
              <span class="c-hero__tag c-hero__tag--lang">${Ui.esc(featured.source_lang||'cn')} → ${Ui.esc(featured.target_lang||'th')}</span>
              <span class="c-hero__tag">${Ui.esc(Ui.statusMap[featured.status]||'ไม่ระบุ')}</span>
            </div>
            <div class="c-progress">
              <div class="c-progress__info">
                <span>${featured.translatedCount} / ${featured.totalCount} ตอน</span>
                <span>${featured.translationPct}%</span>
              </div>
              <div class="c-progress__bar"><div class="c-progress__fill" style="width:${featured.translationPct}%"></div></div>
            </div>
            <div class="c-hero__actions">
              <a href="#novel/${Ui.esc(featured.slug)}" class="c-hero__cta" data-nav>อ่านต่อ →</a>
              <div class="c-hero__info">
                <span class="c-hero__info-label">อ่านล่าสุด</span>
                <span class="c-hero__info-value">${featured.lastRead ? 'ตอนที่ ' + featured.lastRead : 'ยังไม่ได้อ่าน'}</span>
              </div>
            </div>
          </div>
        </div>`;
      }

      // ── Continue Reading ────────────────────────────────────────────
      html += `
      <section class="c-section">
        <div class="c-section__header">
          <h3 class="c-section__title"><svg style="width:16px;height:16px;margin-right:6px;vertical-align:-2px;"><use xlink:href="#icon-book"/></svg>อ่านต่อ</h3>
          <a href="#library" class="c-section__link" data-nav>ดูทั้งหมด ❯</a>
        </div>
        <div class="c-card-grid">`;

      for (const n of enriched) {
        html += `
          <a href="#novel/${n.slug}" class="c-card" data-nav>
            <div class="c-card__cover">${Ui.coverSVG(n.slug, Ui.displayTitle(n))}</div>
            <div class="c-card__info">
              <span class="c-card__title">${Ui.esc(Ui.displayTitle(n))}</span>
              <span class="c-card__meta">${n.lastRead ? 'ตอนที่ ' + n.lastRead + ' / ' + n.totalCount : '0 / ' + n.totalCount}</span>
              <div class="c-card__progress">
                <div class="c-card__progress-bar"><div class="c-card__progress-fill" style="width:${n.translationPct}%"></div></div>
                <span class="c-card__progress-pct">${n.translationPct}%</span>
              </div>
            </div>
          </a>`;
      }

      html += `
          <a href="#admin/import" class="c-card c-card--add" data-nav>
            <span style="font-size:24px;color:var(--c-text-muted); font-weight:600;">+</span>
            <span style="font-size:var(--text-xs);color:var(--c-text-muted);">เพิ่มนิยาย</span>
          </a>
        </div>
      </section>`;

      // ── Latest Updates ──────────────────────────────────────────────
      html += `
      <section class="c-section">
        <div class="c-section__header"><h3 class="c-section__title">อัปเดตล่าสุด</h3></div>
        <div class="c-updates">`;

      for (const n of enriched) {
        html += `
          <a href="#novel/${n.slug}" class="c-update" data-nav>
            <div class="c-update__cover">
              ${Ui.coverSVG(n.slug, Ui.displayTitle(n))}
            </div>
            <span class="c-update__title">${Ui.esc(Ui.displayTitle(n))}</span>
            <span class="c-update__ch">ตอนที่ ${n.chapterCount||0}</span>
          </a>`;
      }

      html += `</div></section>`;

      // ── Weekly Popular ──────────────────────────────────────────────
      html += `
      <section class="c-section">
        <div class="c-section__header">
          <h3 class="c-section__title"><svg style="width:16px;height:16px;margin-right:6px;vertical-align:-2px;"><use xlink:href="#icon-ranking"/></svg>ยอดนิยมประจำสัปดาห์</h3>
        </div>
        <div class="c-popular">`;

      enriched.forEach((n, idx) => {
        const rankClass = idx === 0 ? 'c-popular__rank--1' : idx === 1 ? 'c-popular__rank--2' : idx === 2 ? 'c-popular__rank--3' : '';
        html += `
          <a href="#novel/${n.slug}" class="c-popular__item" data-nav>
            <span class="c-popular__rank ${rankClass}">${idx + 1}</span>
            <div class="c-popular__cover">${Ui.coverSVG(n.slug, Ui.displayTitle(n))}</div>
            <div class="c-popular__info">
              <span class="c-popular__title">${Ui.esc(Ui.displayTitle(n))}</span>
              <span class="c-popular__meta">${n.source_lang||'cn'} → ${n.target_lang||'th'} • โดย ${n.author||'ไม่ระบุ'}</span>
              <span class="c-popular__views"><svg style="width:12px;height:12px;margin-right:4px;vertical-align:-2px;"><use xlink:href="#icon-book"/></svg>${n.chapterCount||0}+ ตอน</span>
            </div>
          </a>`;
      });

      html += `</div></section>`;
      html += '</div>';

      page.innerHTML = html;
    } catch (err) {
      Ui.showError(page, 'โหลดไม่สำเร็จ', err.message);
    }
  }
};
