/* Render helpers for the admin translate workflow. */

(function () {
  const Model = window.AdminTranslateModel;
  const DEFAULT_CHAPTER_PAGE_SIZE = 100;

  function sourceIssueText(health = {}) {
    const byCode = health.issueSummary?.byCode || {};
    return Object.entries(byCode)
      .filter(([, count]) => count > 0)
      .slice(0, 3)
      .map(([code, count]) => code + ' × ' + count)
      .join(', ');
  }

  function sourceHealthHtml({ slug = '', health = {} } = {}) {
    const status = health.status || 'ok';
    const cls = status === 'error'
      ? 'c-badge c-badge--red'
      : (status === 'warn' ? 'c-badge c-badge--amber' : 'c-badge c-badge--teal');
    const label = status === 'error' ? 'source error' : (status === 'warn' ? 'source warning' : 'source ready');
    const issueText = sourceIssueText(health) || 'พร้อมแปล';
    return '<span class="' + cls + '">' + Ui.esc(label) + '</span>' +
      '<span>' + Ui.esc(issueText) + '</span>' +
      (status !== 'ok'
        ? '<a class="c-btn c-btn--xs c-btn--ghost" href="#admin/import/' + Ui.esc(slug) + '" data-nav>' + Ui.icon('info', 'xs') + '<span>ดูสุขภาพนำเข้า</span></a>'
        : '');
  }

  function queueStateHtml(message) {
    return '<div class="c-admin-translate__queue-state">' + Ui.esc(message) + '</div>';
  }

  function queuePreviewHtml(preview = {}) {
    const c = preview.counts || {};
    const warnings = (preview.warnings || []).length
      ? '<div class="c-admin-translate__preview-warnings">' + preview.warnings.map(w => '<span class="c-badge c-badge--amber">' + Ui.esc(w) + '</span>').join('') + '</div>'
      : '';
    return '<div class="c-admin-translate__preview-grid">' +
      '<span><strong>' + Ui.esc(c.total || 0) + '</strong><small>ตอนที่เลือก</small></span>' +
      '<span><strong>' + Ui.esc(c.ready || 0) + '</strong><small>พร้อมแปล</small></span>' +
      '<span><strong>' + Ui.esc(c.untranslated || 0) + '</strong><small>ยังไม่แปล</small></span>' +
      '<span><strong>' + Ui.esc(c.translated || 0) + '</strong><small>แปลแล้ว</small></span>' +
      '<span><strong>' + Ui.esc(c.review || 0) + '</strong><small>ควร retry</small></span>' +
      '<span><strong>' + Ui.esc(c.sourceBlocked || 0) + '</strong><small>source error</small></span>' +
      '</div>' + warnings;
  }

  function paginateChapters(chapters = [], requestedPage = 1, requestedPageSize = DEFAULT_CHAPTER_PAGE_SIZE) {
    const parsedSize = Number.parseInt(requestedPageSize, 10);
    const pageSize = Number.isFinite(parsedSize) && parsedSize > 0
      ? parsedSize
      : DEFAULT_CHAPTER_PAGE_SIZE;
    const pageCount = Math.max(1, Math.ceil(chapters.length / pageSize));
    const parsedPage = Number.parseInt(requestedPage, 10);
    const page = Math.min(pageCount, Math.max(1, Number.isFinite(parsedPage) ? parsedPage : 1));
    const startIndex = (page - 1) * pageSize;
    const items = chapters.slice(startIndex, startIndex + pageSize);
    return {
      items,
      page,
      pageCount,
      pageSize,
      start: items.length ? startIndex + 1 : 0,
      end: startIndex + items.length,
      total: chapters.length,
    };
  }

  function chapterPaginationHtml(pagination) {
    if (pagination.pageCount <= 1) return '';
    const previousPage = Math.max(1, pagination.page - 1);
    const nextPage = Math.min(pagination.pageCount, pagination.page + 1);
    return `<nav class="c-admin-translate__chapter-actions" aria-label="แบ่งหน้ารายการตอน">
      <button class="c-btn c-btn--xs c-btn--ghost" id="translate-page-prev" data-translate-page="${previousPage}" type="button"${pagination.page === 1 ? ' disabled' : ''} aria-label="ไปหน้าก่อนหน้า">ก่อนหน้า</button>
      <span class="u-text-muted" id="translate-page-status" tabindex="-1" aria-live="polite">หน้า ${pagination.page} / ${pagination.pageCount} · ตอน ${pagination.start}–${pagination.end} จาก ${pagination.total}</span>
      <button class="c-btn c-btn--xs c-btn--ghost" id="translate-page-next" data-translate-page="${nextPage}" type="button"${pagination.page === pagination.pageCount ? ' disabled' : ''} aria-label="ไปหน้าถัดไป">ถัดไป</button>
    </nav>`;
  }

  function chapterTable({ chapters = [], visibleChapters = null, selectedNums = new Set(), sourceIssueByNum = {}, lastResultByNum = {}, page = 1, pageSize = DEFAULT_CHAPTER_PAGE_SIZE } = {}) {
    const selected = selectedNums instanceof Set ? selectedNums : new Set(selectedNums || []);
    if (!chapters.length) {
      return {
        summary: 'ยังไม่มีตอนในนิยายนี้',
        html: '<div class="c-admin-translate__chapter-empty">ไม่มีตอนให้แสดง</div>',
        page: 1,
        pageCount: 1,
        visibleCount: 0,
        renderedCount: 0,
      };
    }

    const counts = { translated: 0, untranslated: 0, needs_review: 0, failed: 0, source_not_ready: 0, queued: 0, running: 0 };
    for (const ch of chapters) {
      const status = Model.chapterStatus(ch, sourceIssueByNum[ch.num], lastResultByNum[ch.num]);
      counts[status] = (counts[status] || 0) + 1;
    }

    const filtered = Array.isArray(visibleChapters) ? visibleChapters : chapters;
    const pagination = paginateChapters(filtered, page, pageSize);
    const summary = `ทั้งหมด ${chapters.length} ตอน · แสดง ${filtered.length} · หน้า ${pagination.page}/${pagination.pageCount} · แปลแล้ว ${counts.translated || 0} · ยังไม่แปล ${counts.untranslated || 0} · ควรดู ${counts.needs_review || 0} · source error ${counts.source_not_ready || 0} · เลือก ${selected.size}`;
    if (!filtered.length) {
      return {
        summary,
        html: '<div class="c-admin-translate__chapter-empty">ไม่พบตอนที่ตรงกับตัวกรอง</div>',
        page: 1,
        pageCount: 1,
        visibleCount: 0,
        renderedCount: 0,
      };
    }

    const rows = pagination.items.map(ch => {
      const resultIssue = lastResultByNum[ch.num];
      const sourceIssue = sourceIssueByNum[ch.num];
      const status = Model.chapterStatus(ch, sourceIssue, resultIssue);
      const [label, badgeClass] = Model.statusBadge(status);
      const checked = selected.has(ch.num) ? ' checked' : '';
      const issueText = resultIssue?.reason
        || (ch.workflowReasons || []).slice(0, 2).join(', ')
        || (ch.workflowSourceIssues || []).map(issue => issue.code).slice(0, 2).join(', ')
        || (sourceIssue?.issues || []).map(issue => issue.code).slice(0, 2).join(', ');
      const qualityText = Model.qualityText(ch, resultIssue);
      const modelText = ch.model && ch.model !== 'unknown' ? ch.model : '';
      return `<tr data-status="${Ui.esc(status)}">
        <td><input class="translate-chapter-check" type="checkbox" data-num="${Ui.esc(ch.num)}"${checked} aria-label="เลือกตอน ${Ui.esc(ch.num)}"></td>
        <td class="c-admin-translate__chapter-num">${Ui.esc(ch.num)}</td>
        <td class="c-admin-translate__chapter-title">${Ui.esc(ch.title || ('ตอนที่ ' + ch.num))}</td>
        <td><span class="${badgeClass}">${Ui.esc(label)}</span></td>
        <td class="c-admin-translate__quality">${Ui.esc(qualityText)}</td>
        <td class="c-admin-translate__model">${Ui.esc(modelText || '-')}</td>
        <td class="c-admin-translate__issue">${Ui.esc(issueText || '-')}</td>
        <td class="c-admin-translate__row-actions">
          <button class="c-btn c-btn--xs c-btn--ghost translate-detail-btn" data-num="${Ui.esc(ch.num)}" type="button">ดู</button>
          ${sourceIssue ? '<button class="c-btn c-btn--xs c-btn--ghost translate-inspect-btn" data-num="' + Ui.esc(ch.num) + '" type="button">ตรวจ</button>' : ''}
        </td>
      </tr>`;
    }).join('');
    const allChecked = filtered.every(ch => selected.has(ch.num)) ? ' checked' : '';
    const html = `${chapterPaginationHtml(pagination)}
    <div class="c-admin-translate__table-wrap">
      <table class="c-table c-admin-translate__table">
        <thead>
          <tr>
            <th><input id="translate-select-all" type="checkbox"${allChecked} aria-label="เลือกทุกตอนที่ตรงกับตัวกรอง"></th>
            <th>ตอน</th>
            <th>ชื่อ</th>
            <th>สถานะ</th>
            <th>คุณภาพ</th>
            <th>model</th>
            <th>ปัญหา</th>
            <th>ดู</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
    return {
      summary,
      html,
      page: pagination.page,
      pageCount: pagination.pageCount,
      visibleCount: pagination.total,
      renderedCount: pagination.items.length,
    };
  }

  function chapterDetailHtml({ num, chapter = {}, sourceIssue = null, resultIssue = null } = {}) {
    const quality = chapter.qualityRecord || chapter.quality || {};
    const status = Model.chapterStatus(chapter, sourceIssue, resultIssue);
    const [label, badgeClass] = Model.statusBadge(status);
    const issues = resultIssue?.hardFailures
      || quality.hardFailures
      || chapter.workflowSourceIssues?.map(issue => issue.code)
      || sourceIssue?.issues?.map(issue => issue.code)
      || [];
    const warnings = resultIssue?.warnings || quality.warnings || [];
    const workflowReasons = chapter.workflowReasons || [];
    return '<div class="c-admin-translate__detail-head">' +
      '<strong>ตอน ' + Ui.esc(num) + ' · ' + Ui.esc(chapter.title || '') + '</strong>' +
      '<span class="' + badgeClass + '">' + Ui.esc(label) + '</span>' +
      '</div>' +
      '<div class="c-admin-translate__detail-grid">' +
      '<span>score: <strong>' + Ui.esc(resultIssue?.score ?? quality.score ?? chapter.score ?? '-') + '</strong></span>' +
      '<span>length: <strong>' + Ui.esc(quality.lengthRatio ? Math.round(quality.lengthRatio * 100) + '%' : '-') + '</strong></span>' +
      '<span>model: <strong>' + Ui.esc(chapter.model || resultIssue?.model || '-') + '</strong></span>' +
      '<span>provider: <strong>' + Ui.esc(chapter.provider || resultIssue?.provider || '-') + '</strong></span>' +
      '</div>' +
      '<pre class="c-admin-translate__detail-pre">' + Ui.esc([
        issues.length ? 'issues: ' + issues.join('; ') : 'issues: -',
        warnings.length ? 'warnings: ' + warnings.join('; ') : 'warnings: -',
        workflowReasons.length ? 'workflow: ' + workflowReasons.join('; ') : '',
        resultIssue?.reason ? 'last result: ' + resultIssue.reason : '',
      ].filter(Boolean).join('\n')) + '</pre>';
  }

  function repairPreviewHtml(slug, previewMessage) {
    return '<div class="c-admin-translate__repair-head">' +
      '<strong>Repair preview: ' + Ui.esc(slug) + '</strong>' +
      '<span class="c-badge c-badge--amber">preview</span>' +
      '</div>' +
      '<pre class="c-admin-translate__detail-pre">' + Ui.esc(previewMessage) + '</pre>' +
      '<div class="c-admin-translate__repair-actions">' +
      '<button class="c-btn c-btn--sm c-btn--primary" id="translate-apply-repair" type="button">' + Ui.icon('settings', 'xs') + '<span>Apply repair</span></button>' +
      '<button class="c-btn c-btn--sm c-btn--ghost" id="translate-cancel-repair" type="button">Cancel</button>' +
      '</div>';
  }

  window.AdminTranslateView = {
    sourceIssueText,
    sourceHealthHtml,
    queueStateHtml,
    queuePreviewHtml,
    paginateChapters,
    chapterTable,
    chapterDetailHtml,
    repairPreviewHtml,
  };
})();
