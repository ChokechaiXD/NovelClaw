/* Admin studio landing page. Loaded lazily from admin.js. */

(function () {
  const runStatusLabel = (status) => ({
    running: 'กำลังแปล',
    queued: 'รอเริ่ม',
    cancelling: 'กำลังหยุด',
    done: 'เสร็จแล้ว',
    failed: 'ต้องตรวจ',
    cancelled: 'ยกเลิกแล้ว',
  }[status] || 'บันทึกแล้ว');

  const formatRunTime = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat('th-TH', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
  };

  window.AdminDashboardPage = {
    async render() {
      const page = Ui.$('page-admin');
      if (!page) return;
      Ui.showSkeleton('page-admin');

      try {
        const runsPromise = typeof Api.getTranslateRuns === 'function'
          ? Api.getTranslateRuns().catch(() => ({ data: { active: [], recent: [] } }))
          : Promise.resolve({ data: { active: [], recent: [] } });
        const [allNovels, runsResponse] = await Promise.all([Api.getNovels(), runsPromise]);
        const novels = allNovels.filter(novel => {
          const slug = novel?.slug || '';
          return !slug.startsWith('test-') && !slug.startsWith('tmp-') && !slug.startsWith('fixture-');
        });
        const runs = runsResponse.data || runsResponse;
        const activeRuns = Array.isArray(runs.active) ? runs.active : [];
        const recentRuns = Array.isArray(runs.recent) ? runs.recent : [];
        const novelBySlug = new Map(novels.map(novel => [novel.slug, novel]));

        const totals = novels.reduce((result, novel) => {
          const total = Math.max(0, Number(novel.totalChapters || novel.chapterCount || 0));
          const translated = Math.min(total, Math.max(0, Number(novel.translatedChapters || 0)));
          result.total += total;
          result.translated += translated;
          return result;
        }, { total: 0, translated: 0 });
        const pendingNovels = novels.map(novel => {
          const total = Math.max(0, Number(novel.totalChapters || novel.chapterCount || 0));
          const translated = Math.min(total, Math.max(0, Number(novel.translatedChapters || 0)));
          return { novel, total, translated, remaining: total - translated };
        }).filter(item => item.remaining > 0).sort((a, b) => b.remaining - a.remaining);
        const emptyNovels = novels.filter(novel => !(novel.totalChapters || novel.chapterCount || 0));

        const titleForSlug = (slug) => Ui.displayTitle(novelBySlug.get(slug)) || slug || 'งานแปล';
        const issueCount = run => Math.max(0, Number(run?.failed || 0)) + Math.max(0, Number(run?.needsReview || 0));
        const activeRun = activeRuns[0] || null;
        const newestRecentRun = recentRuns[0] || null;
        const reviewRun = newestRecentRun && (newestRecentRun.status === 'failed' || issueCount(newestRecentRun) > 0)
          ? newestRecentRun
          : null;
        const latestRun = activeRun || recentRuns[0] || null;

        let nextTask;
        if (activeRun) {
          nextTask = {
            eyebrow: 'กำลังทำ',
            title: 'กำลังแปล ' + titleForSlug(activeRun.slug),
            meta: 'ตอน ' + (activeRun.range || '-') + ' · เสร็จ ' + (activeRun.done || 0) + '/' + (activeRun.total || 0) + ' ตอน',
            href: '#admin/translate/' + encodeURIComponent(activeRun.slug || ''),
            cta: 'เปิดงานแปล',
            icon: 'book',
          };
        } else if (reviewRun) {
          const count = issueCount(reviewRun);
          nextTask = {
            eyebrow: 'รอตรวจ',
            title: 'ตรวจผล ' + titleForSlug(reviewRun.slug),
            meta: count ? count + ' ตอนต้องตรวจจากงานล่าสุด' : 'งานล่าสุดจบด้วยข้อผิดพลาด',
            href: reviewRun.slug ? '#admin/chapters/' + encodeURIComponent(reviewRun.slug) : '#admin/logs',
            cta: 'ตรวจผลรายตอน',
            icon: 'search',
          };
        } else if (!novels.length) {
          nextTask = {
            eyebrow: 'เริ่มที่นี่',
            title: 'นำเข้านิยายเรื่องแรก',
            meta: 'วางข้อความหรือเตรียม source ก่อนเริ่มแปล',
            href: '#admin/import',
            cta: 'เปิดหน้านำเข้า',
            icon: 'library',
          };
        } else if (emptyNovels.length) {
          const emptyNovel = emptyNovels[0];
          nextTask = {
            eyebrow: 'รอต้นฉบับ',
            title: 'เติมต้นฉบับให้ ' + Ui.displayTitle(emptyNovel),
            meta: 'เรื่องนี้ยังไม่มีตอนพร้อมแปล',
            href: '#admin/import/' + encodeURIComponent(emptyNovel.slug),
            cta: 'นำเข้าต้นฉบับ',
            icon: 'library',
          };
        } else if (pendingNovels.length) {
          const pending = pendingNovels[0];
          nextTask = {
            eyebrow: 'ทำต่อได้',
            title: 'แปลต่อ ' + Ui.displayTitle(pending.novel),
            meta: 'เหลือ ' + pending.remaining + ' จาก ' + pending.total + ' ตอน',
            href: '#admin/translate/' + encodeURIComponent(pending.novel.slug),
            cta: 'เตรียมงานแปล',
            icon: 'book',
          };
        } else {
          nextTask = {
            eyebrow: 'งานเป็นปัจจุบัน',
            title: 'แปลครบทุกตอนในคลังแล้ว',
            meta: totals.total + ' ตอนพร้อมอ่านและตรวจทาน',
            href: '#admin/chapters',
            cta: 'เปิดรายการตอน',
            icon: 'search',
          };
        }

        const latestTitle = latestRun ? titleForSlug(latestRun.slug) : '';
        const latestTime = latestRun ? formatRunTime(latestRun.finishedAt || latestRun.startedAt) : '';
        const latestDetails = latestRun ? [
          latestRun.range ? 'ตอน ' + latestRun.range : '',
          (latestRun.total || latestRun.done) ? 'เสร็จ ' + (latestRun.done || 0) + '/' + (latestRun.total || 0) : '',
          issueCount(latestRun) ? 'ต้องตรวจ ' + issueCount(latestRun) : '',
          latestTime,
        ].filter(Boolean).join(' · ') : '';

        page.innerHTML = `
          <div class="c-container c-container--wide c-studio">
            ${Ui.adminNav('dashboard')}

            <header class="c-studio-hero">
              <div class="c-studio-hero__copy">
                <span class="c-studio-hero__eyebrow">NovelClaw Studio</span>
                <h1 class="c-studio-hero__title">สตูดิโองานแปล</h1>
                <p class="c-studio-hero__lede">จัดต้นฉบับ แปล ตรวจผล และดูแลคำศัพท์ตามลำดับเดียวกันทุกเรื่อง</p>
              </div>
              <a class="c-btn c-btn--primary c-studio-hero__action" href="${nextTask.href}" data-nav>
                ${Ui.icon(nextTask.icon, 'xs')}<span>${Ui.esc(nextTask.cta)}</span>${Ui.icon('arrow-right', 'xs')}
              </a>
            </header>

            <section class="c-studio-flow" aria-labelledby="studio-flow-title">
              <div class="c-studio-section-head">
                <div>
                  <span class="c-studio-section-head__kicker">Workflow</span>
                  <h2 id="studio-flow-title" class="c-studio-section-head__title">ทำงานทีละขั้น</h2>
                </div>
                <p>${totals.translated}/${totals.total} ตอนแปลแล้ว</p>
              </div>
              <ol class="c-studio-flow__list">
                <li><a class="c-studio-flow__card" href="#admin/import" data-nav><span class="c-studio-flow__number">01</span><span class="c-studio-flow__icon">${Ui.icon('library', 'sm')}</span><strong>นำเข้า</strong><span>${novels.length ? novels.length + ' เรื่องในคลัง' : 'เตรียมต้นฉบับเรื่องแรก'}</span></a></li>
                <li><a class="c-studio-flow__card" href="#admin/translate" data-nav><span class="c-studio-flow__number">02</span><span class="c-studio-flow__icon">${Ui.icon('book', 'sm')}</span><strong>แปล</strong><span>${pendingNovels.length ? (totals.total - totals.translated) + ' ตอนยังไม่แปล' : 'ไม่มีตอนค้างแปล'}</span></a></li>
                <li><a class="c-studio-flow__card" href="#admin/chapters" data-nav><span class="c-studio-flow__number">03</span><span class="c-studio-flow__icon">${Ui.icon('search', 'sm')}</span><strong>ตรวจผล</strong><span>เปิดสถานะและคุณภาพรายตอน</span></a></li>
                <li><a class="c-studio-flow__card" href="#admin/glossary" data-nav><span class="c-studio-flow__number">04</span><span class="c-studio-flow__icon">${Ui.icon('bookmarks', 'sm')}</span><strong>คำศัพท์</strong><span>รักษาชื่อเฉพาะให้สม่ำเสมอ</span></a></li>
              </ol>
            </section>

            <div class="c-studio-workbench">
              <section class="c-studio-focus" aria-labelledby="studio-focus-title">
                <span class="c-studio-focus__eyebrow">${Ui.esc(nextTask.eyebrow)}</span>
                <div class="c-studio-focus__body">
                  <span class="c-studio-focus__icon">${Ui.icon(nextTask.icon, 'md')}</span>
                  <div><h2 id="studio-focus-title">${Ui.esc(nextTask.title)}</h2><p>${Ui.esc(nextTask.meta)}</p></div>
                </div>
                <a class="c-studio-focus__link" href="${nextTask.href}" data-nav><span>${Ui.esc(nextTask.cta)}</span>${Ui.icon('arrow-right', 'xs')}</a>
              </section>

              <section class="c-studio-recent" aria-labelledby="studio-recent-title">
                <div class="c-studio-section-head c-studio-section-head--compact">
                  <div><span class="c-studio-section-head__kicker">ล่าสุด</span><h2 id="studio-recent-title" class="c-studio-section-head__title">งานแปลล่าสุด</h2></div>
                  ${latestRun ? '<span class="c-badge c-badge--' + (issueCount(latestRun) ? 'amber' : 'teal') + '">' + Ui.esc(runStatusLabel(latestRun.status)) + '</span>' : ''}
                </div>
                ${latestRun ? `
                  <a class="c-studio-recent__run" href="#admin/translate/${encodeURIComponent(latestRun.slug || '')}" data-nav>
                    <strong>${Ui.esc(latestTitle)}</strong>
                    <span>${Ui.esc(latestDetails || runStatusLabel(latestRun.status))}</span>
                    ${latestRun.total ? '<progress value="' + Math.min(latestRun.done || 0, latestRun.total) + '" max="' + latestRun.total + '"></progress>' : ''}
                  </a>` : '<div class="c-studio-recent__empty"><strong>ยังไม่มีประวัติงานแปล</strong><span>งานที่เริ่มจากหน้าแปลจะแสดงที่นี่</span></div>'}
              </section>
            </div>

            <section class="c-studio-tools" aria-labelledby="studio-tools-title">
              <div class="c-studio-section-head">
                <div><span class="c-studio-section-head__kicker">Tools</span><h2 id="studio-tools-title" class="c-studio-section-head__title">เครื่องมือดูแลคลัง</h2></div>
              </div>
              <div class="c-studio-tools__grid">
                <a class="c-studio-tool" href="#admin/novels" data-nav>${Ui.icon('library', 'sm')}<span><strong>คลังนิยาย</strong><small>${novels.length} เรื่อง</small></span>${Ui.icon('arrow-right', 'xs')}</a>
                <a class="c-studio-tool" href="#admin/chapters" data-nav>${Ui.icon('book', 'sm')}<span><strong>รายการตอน</strong><small>${totals.total} ตอน</small></span>${Ui.icon('arrow-right', 'xs')}</a>
                <a class="c-studio-tool" href="#admin/provider" data-nav>${Ui.icon('settings', 'sm')}<span><strong>ระบบ AI</strong><small>ผู้ให้บริการและโมเดล</small></span>${Ui.icon('arrow-right', 'xs')}</a>
                <a class="c-studio-tool" href="#admin/logs" data-nav>${Ui.icon('info', 'sm')}<span><strong>บันทึกงาน</strong><small>ตรวจเหตุการณ์และข้อผิดพลาด</small></span>${Ui.icon('arrow-right', 'xs')}</a>
              </div>
            </section>
          </div>`;
      } catch (err) {
        Ui.showError(page, 'โหลดสตูดิโอไม่สำเร็จ', err.message);
      }
    },
  };
})();
