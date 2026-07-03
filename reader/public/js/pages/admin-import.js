/* Admin source import page. Loaded lazily from admin.js. */

(function () {
  const AdminUi = window.AdminUi;
  const AdminImportModel = window.AdminImportModel;
  const {
    formatImportRepairSummary,
    formatTocRecoverySummary,
  } = window.AdminFormat;

  window.AdminImportPage = {
  _preview: null,
  _sites: [],
  _health: null,

  setConsole(state, title, message) {
    AdminUi.setConsole('import', state, title, message);
  },

  _data(resp) {
    return AdminImportModel.data(resp);
  },

  _slugFromTitle(title) {
    return AdminImportModel.slugFromTitle(title);
  },

  _summary(data) {
    return AdminImportModel.summary(data);
  },

  _siteOptions() {
    return AdminImportModel.siteOptions(this._sites || []);
  },

  _siteCatalogHtml() {
    return AdminImportModel.siteCatalogHtml(this._sites || []);
  },

  _healthBadge(status) {
    return AdminImportModel.healthBadge(status);
  },

  _issueText(issueSummary = {}) {
    return AdminImportModel.issueText(issueSummary);
  },

  _issueRange(n = {}) {
    return AdminImportModel.issueRange(n);
  },

  _renderHealthPanel() {
    const health = this._health || { summary: {}, novels: [] };
    const summary = health.summary || {};
    const novels = health.novels || [];
    const risky = novels.filter(n => n.status !== 'ok' || n.staleIndexTitleCount > 0);
    const rows = (risky.length ? risky : novels.slice(0, 5)).map(n => {
      const badgeText = n.status === 'error' ? 'ต้องตรวจ' : (n.status === 'warn' ? 'ควรดู' : 'พร้อม');
      const genericCount = n.issueSummary?.byCode?.generic_title || 0;
      const toc = n.sourceToc || {};
      const tocText = toc.exists
        ? 'toc: ' + (toc.chapterCount || 0) + (toc.site ? ' · ' + toc.site : '')
        : 'toc: missing';
      const recoverButton = genericCount > 0
        ? '<button class="c-btn c-btn--sm c-btn--ghost import-recover-toc-btn" data-slug="' + Ui.esc(n.slug) + '" type="button">' + Ui.icon('library', 'xs') + '<span>กู้ TOC</span></button>'
        : '';
      const issueRange = this._issueRange(n);
      return '<tr>' +
        '<td><strong>' + Ui.esc(n.title || n.slug) + '</strong><div class="u-text-muted">' + Ui.esc(n.slug) + '</div></td>' +
        '<td>' + Ui.esc(n.sourceSite || '-') + '<div class="u-text-muted">' + Ui.esc(tocText) + '</div></td>' +
        '<td class="c-admin-table__mono">' + (n.sourceFileCount || 0) + '</td>' +
        '<td><span class="' + this._healthBadge(n.status) + '">' + badgeText + '</span></td>' +
        '<td>' + Ui.esc(this._issueText(n.issueSummary)) + (n.staleIndexTitleCount ? '<div class="u-text-muted">stale title × ' + n.staleIndexTitleCount + '</div>' : '') + (n.blockingSourceCount ? '<div class="u-text-muted">blocked × ' + n.blockingSourceCount + '</div>' : '') + '</td>' +
        '<td><div class="c-admin-import__row-actions">' +
        '<button class="c-btn c-btn--sm c-btn--secondary import-repair-btn" data-slug="' + Ui.esc(n.slug) + '" type="button">' + Ui.icon('settings', 'xs') + '<span>ซ่อม</span></button>' +
        '<button class="c-btn c-btn--sm c-btn--ghost import-view-issues-btn" data-slug="' + Ui.esc(n.slug) + '" type="button">' + Ui.icon('info', 'xs') + '<span>ปัญหา</span></button>' +
        '<button class="c-btn c-btn--sm c-btn--ghost import-inspect-btn" data-slug="' + Ui.esc(n.slug) + '" data-num="' + Ui.esc(issueRange.split(',')[0] || '1') + '" type="button">' + Ui.icon('search', 'xs') + '<span>ตรวจ</span></button>' +
        '<button class="c-btn c-btn--sm c-btn--secondary import-reimport-range-btn" data-slug="' + Ui.esc(n.slug) + '" data-range="' + Ui.esc(issueRange) + '" type="button">' + Ui.icon('library', 'xs') + '<span>นำเข้าใหม่</span></button>' +
        recoverButton + '</div></td>' +
        '</tr>';
    }).join('');

    return '<div class="c-card c-admin-import__panel c-admin-import__health">' +
      '<div class="c-admin-import__health-head"><h3 class="c-admin-import__title">Import Health</h3><button class="c-btn c-btn--sm c-btn--ghost import-health-refresh-btn" type="button">' + Ui.icon('search', 'xs') + '<span>รีเฟรช</span></button></div>' +
      '<div class="c-admin-import__health-stats">' +
      Ui.stat('นิยาย', summary.novels || 0, { tone: 'accent' }) +
      Ui.stat('source files', summary.sourceFiles || 0, { tone: 'accent' }) +
      Ui.stat('errors', summary.errors || 0, { tone: summary.errors ? 'warn' : 'success' }) +
      Ui.stat('warnings', summary.warnings || 0, { tone: summary.warnings ? 'warn' : 'success' }) +
      '</div>' +
      '<div class="c-table-wrap c-admin-import__health-table"><table class="c-table"><thead><tr><th>นิยาย</th><th>เว็บ</th><th>source</th><th>สถานะ</th><th>ปัญหา</th><th>ซ่อม</th></tr></thead><tbody>' +
      (rows || '<tr><td colspan="6" class="u-text-muted">ยังไม่มีข้อมูล import source</td></tr>') +
      '</tbody></table></div>' +
      '</div>';
  },

  _previewDiagnosticsHtml(data) {
    const diag = data.diagnostics || {};
    const sample = data.sampleChapter;
    const statusClass = diag.recommendImport ? 'c-badge c-badge--teal' : 'c-badge c-badge--amber';
    let html = '<div class="c-admin-import__diagnostics">' +
      '<span class="' + statusClass + '">' + (diag.recommendImport ? 'sample พร้อม import' : 'ควรตรวจ sample') + '</span>' +
      '<span class="c-badge ' + (diag.hasSampleContent ? 'c-badge--teal' : 'c-badge--red') + '">' + (diag.hasSampleContent ? 'มีเนื้อหา' : 'ไม่พบเนื้อหา') + '</span>';
    if (diag.sampleError) html += '<span class="c-badge c-badge--red">' + Ui.esc(diag.sampleError) + '</span>';
    html += '</div>';
    if (sample) {
      const warningHtml = (sample.warnings || []).map(w => '<span class="c-badge c-badge--amber">' + Ui.esc(w) + '</span>').join('');
      html += '<div class="c-admin-import__sample-card">' +
        '<div class="c-admin-import__sample-meta"><strong>' + Ui.esc(sample.title || '') + '</strong><span>' + (sample.paragraphCount || 0) + ' paragraphs · ' + (sample.charCount || 0) + ' chars</span></div>' +
        (warningHtml ? '<div class="c-admin-import__diagnostics">' + warningHtml + '</div>' : '') +
        '<div class="c-admin-import__sample-text">' + (sample.paragraphs || []).map(p => '<p>' + Ui.esc(p) + '</p>').join('') + '</div>' +
        '</div>';
    }
    return html;
  },

  _renderSourceInspector() {
    const novels = this._health?.novels || [];
    const options = novels
      .filter(n => (n.sourceFileCount || 0) > 0)
      .map(n => '<option value="' + Ui.esc(n.slug) + '">' + Ui.esc(n.title || n.slug) + '</option>')
      .join('');
    return '<div class="c-card c-admin-import__panel c-admin-source-inspector">' +
      '<h3 class="c-admin-import__title">Source Inspector</h3>' +
      '<div class="c-admin-source-inspector__form">' +
      '<div class="c-form__group"><label class="c-form__label" for="inspect-slug">นิยาย</label><select class="c-form__select" id="inspect-slug">' + options + '</select></div>' +
      '<div class="c-form__group"><label class="c-form__label" for="inspect-num">ตอน</label><input class="c-form__input" id="inspect-num" type="number" min="1" value="1"></div>' +
      '<button class="c-btn c-btn--secondary" id="inspect-run" type="button">' + Ui.icon('search', 'xs') + '<span>ตรวจ source</span></button>' +
      '</div>' +
      '<div id="inspect-output" class="c-admin-source-inspector__output" hidden></div>' +
      '</div>';
  },

  _renderInspection(data) {
    const out = document.getElementById('inspect-output');
    if (!out) return;
    const diagnostic = data.diagnostic || {};
    const issues = diagnostic.issues || [];
    const issueHtml = issues.length
      ? issues.map(issue => '<span class="c-badge ' + (issue.severity === 'error' ? 'c-badge--red' : 'c-badge--amber') + '">' + Ui.esc(issue.code) + '</span>').join('')
      : '<span class="c-badge c-badge--teal">clean</span>';
    out.hidden = false;
    out.innerHTML = '<div class="c-admin-source-inspector__summary">' +
      '<strong>' + Ui.esc(data.title || 'Untitled') + '</strong>' +
      '<span>' + (diagnostic.paragraphCount || 0) + ' paragraphs · ' + (diagnostic.charCount || 0) + ' chars</span>' +
      '<div class="c-admin-import__diagnostics">' + issueHtml + '</div>' +
      '</div>' +
      '<div class="c-admin-source-inspector__grid">' +
      '<div><div class="c-form__label">Raw source</div><pre class="c-admin-source-inspector__pre"><code>' + Ui.esc(data.raw || '') + '</code></pre></div>' +
      '<div><div class="c-form__label">Parsed clean text</div><pre class="c-admin-source-inspector__pre"><code>' + Ui.esc(data.cleanedText || '') + '</code></pre></div>' +
      '</div>';
  },

  _renderPreview(data) {
    const box = document.getElementById('import-preview');
    if (!box) return;
    const chapters = data.chapters || [];
    const sampleRows = chapters.slice(0, 8).map(ch =>
      '<tr><td class="c-admin-table__mono">' + Ui.esc(ch.num) + '</td><td>' + Ui.esc(ch.title || '') + '</td></tr>'
    ).join('');
    box.hidden = false;
    box.innerHTML =
      '<div class="c-card c-admin-import__preview">' +
      '<div class="c-admin-import__preview-grid">' +
      '<div><span class="c-form__label">ชื่อเรื่อง</span><strong>' + Ui.esc(data.title || '') + '</strong></div>' +
      '<div><span class="c-form__label">เว็บ</span><strong>' + Ui.esc(data.displayName || data.site || '') + '</strong></div>' +
      '<div><span class="c-form__label">ภาษา</span><strong>' + Ui.esc(data.sourceLang || '') + '</strong></div>' +
      '<div><span class="c-form__label">จำนวนตอน</span><strong>' + Ui.esc(data.chapterCount || 0) + '</strong></div>' +
      '</div>' +
      this._previewDiagnosticsHtml(data) +
      '<div class="c-admin-import__run-grid">' +
      '<div class="c-form__group"><label class="c-form__label" for="import-slug">Slug</label><input class="c-form__input" id="import-slug" value="' + Ui.esc(document.getElementById('import-target-slug')?.value || this._slugFromTitle(data.title)) + '" /></div>' +
      '<div class="c-form__group"><label class="c-form__label" for="import-range">ช่วงตอน</label><input class="c-form__input" id="import-range" placeholder="1-20" value="' + Ui.esc(document.getElementById('import-target-range')?.value || '') + '" /></div>' +
      '<label class="c-admin-import__check"><input type="checkbox" id="import-force" /> overwrite</label>' +
      '<button class="c-btn c-btn--primary" id="import-run" type="button">' + Ui.icon('library', 'xs') + '<span>นำเข้า source</span></button>' +
      '</div>' +
      '<div class="c-table-wrap c-admin-import__sample"><table class="c-table"><thead><tr><th>ตอน</th><th>ชื่อ</th></tr></thead><tbody>' + sampleRows + '</tbody></table></div>' +
      '</div>';

    document.getElementById('import-run')?.addEventListener('click', async () => {
      const btn = document.getElementById('import-run');
      const slug = document.getElementById('import-slug')?.value.trim();
      const range = document.getElementById('import-range')?.value.trim();
      const force = document.getElementById('import-force')?.checked;
      if (!slug) {
        Ui.showToast('กรุณาระบุ slug', 'error');
        return;
      }
      btn.disabled = true;
      AdminUi.setButton(btn, 'library', 'กำลังนำเข้า...');
      this.setConsole('running', 'Import running', 'Fetching and cleaning source chapters...');
      try {
        const result = this._data(await Api.importRun({
          url: data.url,
          site: data.site || 'auto',
          slug,
          range,
          force,
        }));
        this.setConsole('success', 'Import complete', this._summary(result));
        Ui.showToast('นำเข้า source สำเร็จ');
      } catch (err) {
        this.setConsole('error', 'Import failed', err.message);
        Ui.showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
        AdminUi.setButton(btn, 'library', 'นำเข้า source');
      }
    });
  },

  async render(params) {
    const page = Ui.$('page-admin-import');
    if (!page) return;
    let sitesPayload = {};
    try {
      sitesPayload = this._data(await Api.getImportSites());
      this._sites = sitesPayload.sites || [];
    } catch (err) {
      this._sites = [];
    }
    try {
      this._health = this._data(await Api.getImportHealth());
    } catch (err) {
      this._health = { summary: {}, novels: [] };
    }

    const importSummary = this._health?.summary || {};
    page.innerHTML = `
      <div class="c-container">
        ${Ui.adminNav('import')}
        <section class="c-control-center c-admin-cockpit c-admin-import__cockpit">
          <div class="c-control-center__head">
            <div>
              <h2 class="c-control-center__title">${Ui.icon('library', 'sm')}Import Studio</h2>
              <p class="c-control-center__subtitle">URL / Paste / Source Inspector ใช้ pipeline เดียวกันเพื่อให้ source สะอาดพร้อมแปล</p>
            </div>
            <a class="c-btn c-btn--primary" href="#admin/translate${params?.slug ? '/' + Ui.esc(params.slug) : ''}" data-nav>${Ui.icon('book', 'xs')}<span>Translate Queue</span></a>
          </div>
          <div class="c-control-center__stats">
            ${Ui.stat('adapters', this._sites.length)}
            ${Ui.stat('source files', importSummary.sourceFiles || 0)}
            ${Ui.stat('errors', importSummary.errors || 0, { tone: importSummary.errors ? 'warn' : 'success' })}
            ${Ui.stat('warnings', importSummary.warnings || 0, { tone: importSummary.warnings ? 'warn' : 'success' })}
          </div>
          <div class="c-control-center__actions">
            <a class="c-btn c-btn--secondary" href="#admin/novels" data-nav>${Ui.icon('info', 'xs')}<span>Library Manager</span></a>
            <button class="c-btn c-btn--ghost import-health-refresh-btn" type="button">${Ui.icon('search', 'xs')}<span>Refresh Health</span></button>
          </div>
        </section>
        <div class="c-admin-import">
          ${this._renderHealthPanel()}
          <div class="c-card c-admin-import__panel">
            <h3 class="c-admin-import__title">URL Import</h3>
            <div class="c-form c-admin-import__form">
              <div class="c-form__group c-admin-import__url-group">
                <label class="c-form__label" for="import-url">URL สารบัญ</label>
                <input class="c-form__input" id="import-url" placeholder="https://..." />
              </div>
              <div class="c-form__group">
                <label class="c-form__label" for="import-site">Adapter</label>
                <select class="c-form__select" id="import-site">
                  ${this._siteOptions()}
                </select>
              </div>
              <div class="c-form__group">
                <label class="c-form__label" for="import-target-slug">Target slug</label>
                <input class="c-form__input" id="import-target-slug" value="${Ui.esc(params?.slug || '')}" />
              </div>
              <div class="c-form__group">
                <label class="c-form__label" for="import-target-range">ช่วง</label>
                <input class="c-form__input" id="import-target-range" value="${Ui.esc(params?.num || '')}" placeholder="เช่น 563,598 หรือ 800-900" />
              </div>
              <button class="c-btn c-btn--secondary c-admin-import__preview-btn" id="import-preview-btn" type="button">${Ui.icon('search', 'xs')}<span>ดูตัวอย่าง</span></button>
            </div>
            ${this._siteCatalogHtml()}
            <div id="import-preview" hidden></div>
          </div>

          <div class="c-card c-admin-import__panel">
            <h3 class="c-admin-import__title">Paste Text</h3>
            <div class="c-form c-admin-import__paste-form">
              <div class="c-form__group"><label class="c-form__label" for="paste-slug">Slug</label><input class="c-form__input" id="paste-slug" /></div>
              <div class="c-form__group"><label class="c-form__label" for="paste-title">ชื่อเรื่อง</label><input class="c-form__input" id="paste-title" /></div>
              <div class="c-form__group"><label class="c-form__label" for="paste-lang">ภาษา source</label><input class="c-form__input" id="paste-lang" value="cn" /></div>
              <div class="c-form__group"><label class="c-form__label" for="paste-rule">Split rule</label><input class="c-form__input" id="paste-rule" placeholder="(?:ตอนที่|第|Chapter)\\s*(\\d+)" /></div>
              <div class="c-form__group c-admin-import__textarea-group"><label class="c-form__label" for="paste-content">ข้อความ</label><textarea class="c-form__textarea" id="paste-content"></textarea></div>
              <label class="c-admin-import__check"><input type="checkbox" id="paste-force" /> overwrite</label>
              <button class="c-btn c-btn--primary" id="paste-run" type="button">${Ui.icon('library', 'xs')}<span>บันทึก source</span></button>
            </div>
          </div>

          ${this._renderSourceInspector()}

          <div class="c-card c-admin-translate__panel" id="import-console-card" hidden>
            <div class="c-admin-translate__console-head">
              <h4 id="import-console-title">Import</h4>
              <span id="import-console-badge" class="c-badge c-badge--gray">พร้อมใช้งาน</span>
            </div>
            <pre class="c-admin-translate__console" id="import-console-output"></pre>
          </div>
        </div>
      </div>`;

    if (params?.slug) {
      const range = params.num || '';
      const importSlugInput = document.getElementById('import-target-slug');
      const importRangeInput = document.getElementById('import-target-range');
      const inspectSlugSelect = document.getElementById('inspect-slug');
      const inspectNumInput = document.getElementById('inspect-num');
      if (importSlugInput) importSlugInput.value = params.slug;
      if (importRangeInput) importRangeInput.value = range;
      if (inspectSlugSelect) inspectSlugSelect.value = params.slug;
      if (inspectNumInput && range) inspectNumInput.value = String(range).split(',')[0] || '1';
      if (range) {
        this.setConsole('idle', 'Re-import range ready', 'slug: ' + params.slug + '\nrange: ' + range + '\nใส่ URL สารบัญหรือ URL source แล้วกด Preview/Import เพื่อดึงช่วงนี้ใหม่');
      }
    }

    page.querySelectorAll('.import-health-refresh-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        await this.render(params);
      });
    });

    page.querySelectorAll('.import-view-issues-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const slug = btn.dataset.slug;
        if (!slug) return;
        btn.disabled = true;
        AdminUi.setButton(btn, 'search', 'Loading...');
        try {
          const health = this._data(await Api.getImportHealth(slug, { includeChapters: true }));
          const lines = (health.chapters || []).slice(0, 80).map(ch => {
            const codes = (ch.issues || []).map(issue => issue.code + ':' + issue.severity).join(', ');
            return String(ch.num).padStart(4, '0') + '  ' + codes + '  ' + (ch.title || '');
          });
          this.setConsole(
            health.status === 'error' ? 'error' : 'idle',
            'Source issues: ' + slug,
            [
              'status: ' + health.status,
              'blocking: ' + (health.blockingSourceCount || 0),
              'warnings: ' + (health.issueSummary?.warningCount || 0),
              '',
              ...(lines.length ? lines : ['ไม่มี source issue']),
            ].join('\n')
          );
        } catch (err) {
          this.setConsole('error', 'Issue load failed', err.message);
        } finally {
          btn.disabled = false;
          AdminUi.setButton(btn, 'info', 'ปัญหา');
        }
      });
    });

    page.querySelectorAll('.import-inspect-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const slug = btn.dataset.slug || '';
        const num = btn.dataset.num || '1';
        const slugEl = document.getElementById('inspect-slug');
        const numEl = document.getElementById('inspect-num');
        if (slugEl) slugEl.value = slug;
        if (numEl) numEl.value = num;
        document.getElementById('inspect-run')?.click();
      });
    });

    page.querySelectorAll('.import-reimport-range-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const slug = btn.dataset.slug || '';
        const range = btn.dataset.range || '';
        const importSlugInput = document.getElementById('import-target-slug');
        const importRangeInput = document.getElementById('import-target-range');
        if (importSlugInput) importSlugInput.value = slug;
        if (importRangeInput) importRangeInput.value = range;
        this.setConsole('idle', 'Re-import range ready', 'slug: ' + slug + '\nrange: ' + (range || '-') + '\nใส่ URL แล้วกด Preview เพื่อดึง source ใหม่เฉพาะช่วงนี้');
        document.getElementById('import-url')?.focus();
      });
    });

    page.querySelectorAll('.import-repair-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const slug = btn.dataset.slug;
        if (!slug) return;
        btn.disabled = true;
        AdminUi.setButton(btn, 'search', 'Checking...');
        this.setConsole('running', 'Repair preview', 'Checking source titles, noise lines, and chapter index for ' + slug + '...');
        try {
          const preview = await Api.repairImport(slug, 'all', { dryRun: true });
          const previewRepair = preview.data?.repair || {};
          const previewMessage = formatImportRepairSummary(slug, previewRepair);
          this.setConsole('idle', 'Repair preview', previewMessage);
          if (!confirm('Repair preview\n\n' + previewMessage + '\n\nApply these changes?')) {
            btn.disabled = false;
            AdminUi.setButton(btn, 'settings', 'ซ่อม');
            return;
          }

          AdminUi.setButton(btn, 'settings', 'Repairing...');
          this.setConsole('running', 'Repair running', 'Applying source title/noise repairs and rebuilding chapter index for ' + slug + '...');
          const result = await Api.repairImport(slug, 'all');
          const repair = result.data?.repair || {};
          const message = formatImportRepairSummary(slug, repair);
          this.setConsole('success', 'Repair complete', message);
          Ui.showToast('ซ่อมแล้ว: title ' + (repair.titlesRepaired || 0) + ', index rebuilt');
          btn.disabled = false;
          AdminUi.setButton(btn, 'settings', 'Done');
        } catch (err) {
          this.setConsole('error', 'Repair failed', err.message);
          Ui.showToast(err.message, 'error');
          btn.disabled = false;
          AdminUi.setButton(btn, 'settings', 'ซ่อม');
        }
      });
    });

    page.querySelectorAll('.import-recover-toc-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const slug = btn.dataset.slug;
        if (!slug) return;
        btn.disabled = true;
        AdminUi.setButton(btn, 'search', 'Checking...');
        this.setConsole('running', 'TOC recovery preview', 'Fetching source table of contents for ' + slug + '...');
        try {
          const preview = this._data(await Api.recoverImportToc(slug, { dryRun: true }));
          const previewMessage = formatTocRecoverySummary(slug, preview);
          this.setConsole('idle', 'TOC recovery preview', previewMessage);
          if (!preview.chapterCount) {
            Ui.showToast('ไม่พบตอนจากสารบัญต้นทาง', 'error');
            btn.disabled = false;
            AdminUi.setButton(btn, 'library', 'กู้ TOC');
            return;
          }
          if (!confirm('TOC recovery preview\n\n' + previewMessage + '\n\nSave this toc.json?')) {
            btn.disabled = false;
            AdminUi.setButton(btn, 'library', 'กู้ TOC');
            return;
          }

          AdminUi.setButton(btn, 'library', 'Saving...');
          this.setConsole('running', 'TOC recovery running', 'Saving toc.json for ' + slug + '...');
          const result = this._data(await Api.recoverImportToc(slug, { dryRun: false }));
          this.setConsole('success', 'TOC recovery complete', formatTocRecoverySummary(slug, result));
          Ui.showToast('สร้าง toc.json แล้ว กด Repair เพื่อซ่อม generic title ต่อ');
          btn.disabled = false;
          AdminUi.setButton(btn, 'library', 'Done');
        } catch (err) {
          this.setConsole('error', 'TOC recovery failed', err.message);
          Ui.showToast(err.message, 'error');
          btn.disabled = false;
          AdminUi.setButton(btn, 'library', 'กู้ TOC');
        }
      });
    });

    document.getElementById('inspect-run')?.addEventListener('click', async () => {
      const btn = document.getElementById('inspect-run');
      const slug = document.getElementById('inspect-slug')?.value || '';
      const num = document.getElementById('inspect-num')?.value || '1';
      if (!slug) {
        Ui.showToast('ยังไม่มี source ให้ inspect', 'error');
        return;
      }
      btn.disabled = true;
      AdminUi.setButton(btn, 'search', 'Inspecting...');
      try {
        const data = this._data(await Api.inspectSource(slug, num));
        this._renderInspection(data);
      } catch (err) {
        Ui.showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
        AdminUi.setButton(btn, 'search', 'ตรวจ source');
      }
    });

    document.getElementById('import-preview-btn')?.addEventListener('click', async () => {
      const btn = document.getElementById('import-preview-btn');
      const url = document.getElementById('import-url')?.value.trim();
      const site = document.getElementById('import-site')?.value || 'auto';
      if (!url) {
        Ui.showToast('กรุณาระบุ URL', 'error');
        return;
      }
      btn.disabled = true;
      AdminUi.setButton(btn, 'search', 'Loading...');
      this.setConsole('running', 'Preview running', 'Fetching table of contents and sample chapter...');
      try {
        const data = this._data(await Api.importPreview({ url, site }));
        this._preview = data;
        this._renderPreview(data);
        const diag = data.diagnostics || {};
        this.setConsole('success', 'Preview ready', `${data.chapterCount || 0} chapters found\nsample content: ${diag.hasSampleContent ? 'yes' : 'no'}\nrecommend import: ${diag.recommendImport ? 'yes' : 'review first'}`);
      } catch (err) {
        this.setConsole('error', 'Preview failed', err.message);
        Ui.showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
        AdminUi.setButton(btn, 'search', 'ดูตัวอย่าง');
      }
    });

    document.getElementById('paste-run')?.addEventListener('click', async () => {
      const btn = document.getElementById('paste-run');
      const slug = document.getElementById('paste-slug')?.value.trim();
      const title = document.getElementById('paste-title')?.value.trim();
      const sourceLang = document.getElementById('paste-lang')?.value.trim() || 'cn';
      const splitRule = document.getElementById('paste-rule')?.value.trim();
      const content = document.getElementById('paste-content')?.value || '';
      const force = document.getElementById('paste-force')?.checked;
      if (!slug || !content.trim()) {
        Ui.showToast('กรุณาระบุ slug และข้อความ', 'error');
        return;
      }
      btn.disabled = true;
      AdminUi.setButton(btn, 'library', 'กำลังบันทึก...');
      this.setConsole('running', 'Paste import running', 'Cleaning pasted source...');
      try {
        const result = this._data(await Api.importPaste({ slug, title, sourceLang, splitRule, content, force }));
        this.setConsole('success', 'Paste import complete', this._summary(result));
        Ui.showToast('บันทึก source สำเร็จ');
      } catch (err) {
        this.setConsole('error', 'Paste import failed', err.message);
        Ui.showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
        AdminUi.setButton(btn, 'library', 'บันทึก source');
      }
    });
  }
};

// ── ADMIN TRANSLATE PAGE (Simplified) ──────────────────────────
})();
