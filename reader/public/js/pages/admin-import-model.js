/* Data and HTML helpers for the admin source import workflow. */

window.AdminImportModel = {
  data(resp) {
    return resp && resp.data ? resp.data : (resp || {});
  },

  slugFromTitle(title) {
    return String(title || 'imported-novel')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'imported-novel';
  },

  summary(data = {}) {
    const results = data.results || [];
    const warningCount = results.reduce((sum, item) => sum + ((item.warnings || []).length > 0 ? 1 : 0), 0);
    return [
      'imported: ' + (data.imported || 0),
      'skipped: ' + (data.skipped || 0),
      'failed: ' + (data.failed || 0),
      'warnings: ' + warningCount,
    ].join('\n');
  },

  siteOptions(sites = []) {
    return '<option value="auto">auto</option>' + sites.map(site => {
      const label = `${site.displayName || site.id} (${site.sourceLang || '?'}, ${site.quality || 'beta'})`;
      return '<option value="' + Ui.esc(site.id) + '">' + Ui.esc(label) + '</option>';
    }).join('');
  },

  siteCatalogHtml(sites = []) {
    if (!sites.length) return '';
    const rows = sites.map(site =>
      '<tr>' +
      '<td><strong>' + Ui.esc(site.displayName || site.id) + '</strong><div class="u-text-muted">' + Ui.esc((site.domains || []).join(', ')) + '</div></td>' +
      '<td>' + Ui.esc(site.sourceLang || '') + '</td>' +
      '<td>' + Ui.esc(site.adapterType || '') + '</td>' +
      '<td><span class="c-badge c-badge--gray">' + Ui.esc(site.quality || '') + '</span></td>' +
      '<td>' + (site.access?.requiresJs ? '<span class="c-badge c-badge--amber">JS</span>' : '<span class="c-badge c-badge--teal">HTML</span>') + '</td>' +
      '</tr>'
    ).join('');
    return '<div class="c-table-wrap c-admin-import__sites"><table class="c-table"><thead><tr><th>เว็บ</th><th>ภาษา</th><th>ชนิด</th><th>คุณภาพ</th><th>โหมด</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
  },

  healthBadge(status) {
    if (status === 'error') return 'c-badge c-badge--red';
    if (status === 'warn') return 'c-badge c-badge--amber';
    return 'c-badge c-badge--teal';
  },

  issueText(issueSummary = {}) {
    const byCode = issueSummary.byCode || {};
    const entries = Object.entries(byCode).filter(([, count]) => count > 0);
    if (!entries.length) return 'ปกติ';
    return entries.slice(0, 3).map(([code, count]) => code + ' × ' + count).join(', ');
  },

  issueRange(n = {}) {
    const nums = n.blockingSourceNums || [];
    if (nums.length) return nums.join(',');
    const firstIssue = n.sampleIssues?.[0]?.num;
    return firstIssue ? String(firstIssue) : '';
  },
};
