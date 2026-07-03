/* AdminTranslatePage. Loaded lazily from admin.js. */

(function () {
  const AdminUi = window.AdminUi;
  const AdminTranslateModel = window.AdminTranslateModel;
  const AdminTranslateView = window.AdminTranslateView;
  const AdminTranslateJob = window.AdminTranslateJob;
  const AdminTranslateCatalog = window.AdminTranslateCatalog;
  const AdminTranslateSelection = window.AdminTranslateSelection;
  const AdminTranslateCommand = window.AdminTranslateCommand;
  const {
    formatImportRepairSummary,
  } = window.AdminFormat;

const AdminTranslatePage = {
  setConsole(state, title, message) {
    AdminUi.setConsole('translate', state, title, message);
  },

  _formatBatchResult(result = {}) {
    const summary = result.summary || {};
    const chapters = result.chapters || summary.chapters || [];
    const lines = [
      `[SUMMARY] translated=${summary.passed || 0} needs_review/failed=${summary.failed || 0} total=${summary.total || 0}`,
    ];
    for (const ch of chapters.slice(0, 80)) {
      const label = ch.status === 'ok' ? 'translated' : ch.status;
      const score = ch.score != null ? ` score=${ch.score}` : '';
      const issues = (ch.hardFailures || []).slice(0, 2).join('; ');
      const reason = ch.reason || issues || 'ok';
      lines.push(`- ch ${ch.ch || '-'}: ${label}${score} · ${reason}`);
    }
    if (chapters.length > 80) lines.push(`...and ${chapters.length - 80} more chapter results`);
    return lines.join('\n');
  },

  _rangeFromNums: AdminTranslateModel.rangeFromNums,
  _numsFromRange: AdminTranslateModel.numsFromRange,
  _chapterStatus: AdminTranslateModel.chapterStatus,
  _statusBadge: AdminTranslateModel.statusBadge,
  _modelCatalogSummary: AdminTranslateModel.modelCatalogSummary,
  _modelLabel: AdminTranslateModel.modelLabel,
  _qualityText: AdminTranslateModel.qualityText,
  _chapterMatches: AdminTranslateModel.chapterMatches,
  _queuePreview: AdminTranslateModel.queuePreview,

  async render(params) {
    const page = Ui.$('page-admin-translate');
    if (!page) return;
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    Ui.showSkeleton('page-admin-translate');

    try {
      const [novels, translationHealth, importHealth, llmConfig] = await Promise.all([
        Api.getNovels(),
        Api.getTranslationHealth().catch(() => ({ data: { buckets: {} } })),
        Api.getImportHealth().catch(() => ({ data: { novels: [] } })),
        Api.getLlmConfig().catch(() => ({ providers: [] })),
      ]);
      const buckets = translationHealth.data?.buckets || {};
      const importHealthBySlug = {};
      for (const item of importHealth.data?.novels || []) importHealthBySlug[item.slug] = item;
      const bucketStat = (name) => buckets[name]?.count || 0;
      const batchLogs = translationHealth.data?.batchLogs || [];
      const activeBatch = batchLogs[0] || null;
      const latestFailed = (buckets.failed?.latest || buckets.needs_review?.latest || [])
        .slice(0, 3)
        .map(item => Ui.esc(item.name))
        .join(', ');
      const batchFailures = activeBatch?.failures?.slice(0, 5).map(item =>
        '<li><span class="c-admin-translate__chapter">ตอน ' + Ui.esc(item.chapter || '-') + '</span>' +
        '<span>' + Ui.esc(item.reason || '-') + '</span></li>'
      ).join('') || '';
      const batchRecent = activeBatch?.recentLines?.map(line => Ui.esc(line)).join('\n') || '';
      let modelProviderById = {};
      let currentLlmConfig = llmConfig;
      const buildModelOptions = (cfg = {}) => {
        const catalog = AdminTranslateCatalog.modelOptions(cfg);
        modelProviderById = catalog.providerByModel;
        return catalog.html;
      };
      const modelOptions = buildModelOptions(currentLlmConfig);
      const initialReadout = AdminTranslateCatalog.readout(currentLlmConfig, currentLlmConfig.default_model || '');

      const selectedTranslateSlug = params.slug || novels.find(Ui.isVisibleNovel)?.slug || novels[0]?.slug || '';
      const novelOptions = novels.map(n => {
        const h = importHealthBySlug[n.slug] || {};
        const label = h.status === 'error' ? 'source error' : (h.status === 'warn' ? 'source warn' : 'ready');
        return `<option value="${Ui.esc(n.slug)}" data-source-status="${Ui.esc(h.status || 'ok')}"${n.slug === selectedTranslateSlug ? ' selected' : ''}>${Ui.esc(Ui.displayTitle(n) || n.slug)} · ${Ui.esc(label)}</option>`;
      }
      ).join('');

      let html = `
      <div class="c-container c-container--wide">
        ${Ui.adminNav('translate')}
        
        <div class="c-admin-translate">
          <section class="c-control-center c-admin-translate__hero">
            <div class="c-control-center__head">
              <div>
                <h2 class="c-control-center__title">${Ui.icon('book', 'sm')}Translation Cockpit</h2>
                <p class="c-control-center__subtitle">เลือกนิยาย ตรวจ source เลือก model สั่งแปล และติดตามงานจากจุดเดียว</p>
              </div>
              <div class="c-admin-translate__hero-actions">
                <a class="c-btn c-btn--secondary" href="#admin/provider" data-nav>${Ui.icon('settings', 'xs')}<span>AI Settings</span></a>
                <button class="c-btn c-btn--ghost" id="translate-health-refresh" type="button">${Ui.icon('search', 'xs')}<span>Refresh health</span></button>
              </div>
            </div>
            <div class="c-control-center__stats">
              ${Ui.stat('active', bucketStat('active'))}
              ${Ui.stat('done', bucketStat('done'), { tone: 'success' })}
              ${Ui.stat('needs review', bucketStat('needs_review'), { tone: bucketStat('needs_review') ? 'warn' : 'success' })}
              ${Ui.stat('failed', bucketStat('failed'), { tone: bucketStat('failed') ? 'warn' : 'success' })}
            </div>
            <div class="c-admin-translate__health-note">
              <span>${latestFailed ? 'ต้องตรวจล่าสุด: ' + latestFailed : 'ยังไม่มีรายการ failed หรือ needs review ล่าสุด'}</span>
              ${activeBatch ? '<span>batch ล่าสุด: ' + Ui.esc(activeBatch.name) + ' · ' + Ui.esc(activeBatch.percent || 0) + '%</span>' : '<span>ยังไม่พบ batch log</span>'}
            </div>
          </section>

          <div class="c-card c-admin-translate__panel c-admin-translate__health-panel">
            <div class="c-admin-translate__console-head">
              <h3 class="c-admin-translate__title">Translation Health</h3>
              <button class="c-btn c-btn--xs c-btn--secondary translate-health-refresh-inline" type="button">${Ui.icon('search', 'xs')}<span>รีเฟรช</span></button>
            </div>
            <div class="c-stats c-admin-translate__health-stats">
              <div class="c-stat"><span class="c-stat__num">${bucketStat('active')}</span><span class="c-stat__label">active</span></div>
              <div class="c-stat"><span class="c-stat__num c-stat__num--success">${bucketStat('done')}</span><span class="c-stat__label">done</span></div>
              <div class="c-stat"><span class="c-stat__num c-stat__num--warning">${bucketStat('needs_review')}</span><span class="c-stat__label">needs review</span></div>
              <div class="c-stat"><span class="c-stat__num">${bucketStat('failed')}</span><span class="c-stat__label">failed</span></div>
            </div>
            <p class="u-text-muted">${latestFailed ? 'ล่าสุดที่ต้องดู: ' + latestFailed : 'ยังไม่มีรายการ failed/needs_review ล่าสุด'}</p>
            ${activeBatch ? `
            <div class="c-admin-translate__batch">
              <div class="c-admin-translate__batch-head">
                <div>
                  <strong>${Ui.esc(activeBatch.name)}</strong>
                  <p class="u-text-muted">ตอน ${Ui.esc(activeBatch.current || 0)} / ${Ui.esc(activeBatch.total || 0)} · active chapter ${Ui.esc(activeBatch.activeChapter || '-')}</p>
                </div>
                <span class="c-badge c-badge--amber">${Ui.esc(activeBatch.percent || 0)}%</span>
              </div>
              <progress class="c-admin-translate__progress" value="${Ui.esc(activeBatch.percent || 0)}" max="100"></progress>
              <div class="c-admin-translate__batch-metrics">
                <span>ผ่าน ${Ui.esc(activeBatch.passed || 0)}</span>
                <span>ล้มเหลว ${Ui.esc(activeBatch.failed || 0)}</span>
                <span>timeout ${Ui.esc(activeBatch.timeout || 0)}</span>
              </div>
              <div class="c-admin-translate__batch-grid">
                <div>
                  <h4 class="c-admin-translate__subhead">ปัญหาล่าสุด</h4>
                  <ul class="c-admin-translate__failure-list">${batchFailures || '<li class="u-text-muted">ยังไม่มีปัญหาใน log นี้</li>'}</ul>
                </div>
                <div>
                  <h4 class="c-admin-translate__subhead">Recent log</h4>
                  <pre class="c-admin-translate__mini-log">${batchRecent || '—'}</pre>
                </div>
              </div>
            </div>` : '<p class="u-text-muted">ยังไม่พบ batch log</p>'}
          </div>

          <!-- BATCH TRANSLATION PANEL (simplified) -->
          <div class="c-card c-admin-translate__panel c-admin-translate__command-panel">
            <div class="c-admin-translate__panel-head">
              <div>
                <h3 class="c-admin-translate__title">Prepare translation</h3>
                <p class="u-text-muted">เลือกเรื่อง ช่วงตอน และ model ก่อนเริ่มแปล ระบบจะแสดง preview และ tracker ในหน้าเดียว</p>
              </div>
              <span class="c-badge c-badge--gray">Manual run</span>
            </div>
            <div class="c-form c-admin-translate__form">
              <div class="c-admin-translate__grid">
                <div class="c-form__group">
                  <label class="c-form__label">เลือกนิยาย</label>
                  <select class="c-form__select c-form__select--compact" id="translate-batch-novel">
                    ${novelOptions}
                  </select>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">ช่วงตอน (เช่น 5-10 หรือ 5)</label>
                  <input type="text" class="c-form__input c-form__input--compact" id="translate-batch-range" placeholder="เช่น 1-10" />
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">แปลพร้อมกัน</label>
                  <select class="c-form__select c-form__select--compact" id="translate-batch-concurrent">
                    <option value="1">1 ตอน (default)</option>
                    <option value="2">2 ตอน</option>
                    <option value="3">3 ตอน</option>
                  </select>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">Prompt preset</label>
                  <select class="c-form__select c-form__select--compact" id="translate-prompt-profile">
                    <option value="faithful_default">Faithful default</option>
                    <option value="flowing_thai">Flowing Thai</option>
                    <option value="strict_literal">Strict literal</option>
                  </select>
                </div>
                <div class="c-form__group">
                  <label class="c-form__label">Model override</label>
                  <input type="text" class="c-form__input c-form__input--compact" id="translate-model-override" list="translate-model-list" value="${Ui.esc(currentLlmConfig.default_model || '')}" placeholder="ค้นหา model" />
                  <datalist id="translate-model-list">${modelOptions}</datalist>
                  <div class="c-admin-translate__model-readout" aria-live="polite">
                    <span><small>Provider</small><strong id="translate-selected-provider-readout">${Ui.esc(initialReadout.providerLabel)}</strong></span>
                    <span><small>Model</small><strong id="translate-selected-model-readout">${Ui.esc(currentLlmConfig.default_model || '-')}</strong></span>
                    <span><small>Key</small><strong id="translate-provider-key-readout">${Ui.esc(initialReadout.keyLabel)}</strong></span>
                  </div>
                  <div class="c-admin-translate__model-tools">
                    <span id="translate-model-catalog-note" class="u-text-muted">${Ui.esc(AdminTranslatePage._modelCatalogSummary(currentLlmConfig))}</span>
                    <button class="c-btn c-btn--xs c-btn--ghost" id="translate-refresh-models" type="button">${Ui.icon('search', 'xs')}<span>Refresh models</span></button>
                    <button class="c-btn c-btn--xs c-btn--ghost" id="translate-provider-check" type="button">${Ui.icon('info', 'xs')}<span>Check model</span></button>
                  </div>
                </div>
              </div>
              <div id="translate-source-health" class="c-admin-translate__source-health"></div>
              <div id="translate-queue-preview" class="c-admin-translate__queue-preview" aria-live="polite">
                <div class="c-admin-translate__queue-state">ยังไม่ได้เลือกตอน กรอกช่วงตอนหรือเลือกจากตารางเพื่อดู preview</div>
              </div>
              <div class="c-admin-translate__job-panel" id="translate-job-panel">
                <div class="c-admin-translate__job-head">
                  <div>
                    <h4 class="c-admin-translate__subhead">ตัวติดตามงานแปล</h4>
                    <p class="u-text-muted">เริ่มงานแล้วหน้านี้จะตามสถานะให้อัตโนมัติ</p>
                  </div>
                  <span id="translate-job-badge" class="c-badge c-badge--gray">Idle</span>
                </div>
                <div class="c-admin-translate__job-progress" aria-label="Translation progress">
                  <div id="translate-job-progress-fill" class="c-admin-translate__job-progress-fill"></div>
                </div>
                <div class="c-admin-translate__preview-grid c-admin-translate__job-metrics">
                  <span><strong id="translate-job-progress-text">0%</strong><small>progress</small></span>
                  <span><strong id="translate-job-done">0</strong><small>done</small></span>
                  <span><strong id="translate-job-review">0</strong><small>needs review</small></span>
                  <span><strong id="translate-job-failed">0</strong><small>failed</small></span>
                </div>
                <div id="translate-job-current" class="c-admin-translate__job-current">ยังไม่มีงานที่กำลังรัน</div>
                <pre id="translate-job-events" class="c-admin-translate__mini-log">Waiting for a run.</pre>
                <div class="c-admin-translate__job-actions">
                  <button class="c-btn c-btn--sm c-btn--ghost" id="translate-job-refresh" type="button">${Ui.icon('info', 'xs')}<span>Refresh</span></button>
                  <button class="c-btn c-btn--sm c-btn--danger" id="translate-job-cancel" type="button" hidden>${Ui.icon('close', 'xs')}<span>Cancel</span></button>
                </div>
              </div>
              <div class="c-admin-translate__actions">
                <button class="c-btn c-btn--primary" id="translate-batch-run-btn" type="button">${Ui.icon('book', 'xs')}<span>เริ่มแปล</span></button>
                <label class="c-admin-import__check"><input id="translate-force-source" type="checkbox"> force แปลแม้ source error</label>
              </div>
              <div class="c-admin-translate__chapter-panel c-admin-translate__chapter-panel--embedded">
                <div class="c-admin-translate__chapter-head">
                  <div>
                    <h4 class="c-admin-translate__subhead">เลือกตอนที่จะแปล</h4>
                    <p class="u-text-muted" id="translate-chapter-summary">กำลังโหลดรายการตอน...</p>
                  </div>
                  <div class="c-admin-translate__chapter-actions">
                    <button class="c-btn c-btn--xs c-btn--secondary" id="translate-select-untranslated" type="button">${Ui.icon('search', 'xs')}<span>ยังไม่แปล</span></button>
                    <button class="c-btn c-btn--xs c-btn--secondary" id="translate-select-translated" type="button">${Ui.icon('bookmarks', 'xs')}<span>มีไฟล์แปล</span></button>
                    <button class="c-btn c-btn--xs c-btn--secondary" id="translate-select-review" type="button">${Ui.icon('search', 'xs')}<span>ควรดู/ล้มเหลว</span></button>
                    <button class="c-btn c-btn--xs c-btn--secondary" id="translate-select-source-errors" type="button">${Ui.icon('info', 'xs')}<span>source error</span></button>
                    <button class="c-btn c-btn--xs c-btn--ghost" id="translate-clear-selection" type="button">${Ui.icon('info', 'xs')}<span>ล้าง</span></button>
                    <button class="c-btn c-btn--xs c-btn--primary" id="translate-run-selected" type="button">${Ui.icon('book', 'xs')}<span>แปลที่เลือก</span></button>
                    <button class="c-btn c-btn--xs c-btn--danger" id="translate-delete-selected" type="button">${Ui.icon('close', 'xs')}<span>ลบแปลที่เลือก</span></button>
                    <button class="c-btn c-btn--xs c-btn--secondary" id="translate-run-untranslated" type="button">${Ui.icon('book', 'xs')}<span>แปลที่ยังไม่แปล</span></button>
                    <button class="c-btn c-btn--xs c-btn--secondary" id="translate-retry-review" type="button">${Ui.icon('book', 'xs')}<span>Retry ควรดู</span></button>
                    <button class="c-btn c-btn--xs c-btn--secondary" id="translate-force-selected" type="button">${Ui.icon('book', 'xs')}<span>Force selected</span></button>
                    <button class="c-btn c-btn--xs c-btn--ghost" id="translate-repair-source" type="button">${Ui.icon('settings', 'xs')}<span>ซ่อม source/index</span></button>
                  </div>
                </div>
                <div class="c-admin-translate__tools">
                  <div class="c-admin-translate__filters" role="group" aria-label="กรองสถานะตอน">
                    <button class="c-btn c-btn--xs c-btn--secondary translate-filter-btn" data-filter="all" type="button">ทั้งหมด</button>
                    <button class="c-btn c-btn--xs c-btn--ghost translate-filter-btn" data-filter="untranslated" type="button">ยังไม่แปล</button>
                    <button class="c-btn c-btn--xs c-btn--ghost translate-filter-btn" data-filter="translated" type="button">แปลแล้ว</button>
                    <button class="c-btn c-btn--xs c-btn--ghost translate-filter-btn" data-filter="review" type="button">ควรดู</button>
                    <button class="c-btn c-btn--xs c-btn--ghost translate-filter-btn" data-filter="source_not_ready" type="button">source error</button>
                  </div>
                  <input class="c-form__input c-form__input--compact c-admin-translate__search" id="translate-chapter-search" type="search" placeholder="ค้นเลขตอน / ชื่อตอน / model / issue" />
                  <div class="c-admin-translate__smart">
                    <button class="c-btn c-btn--xs c-btn--ghost" id="translate-next-20" type="button">ถัดไป 20</button>
                    <button class="c-btn c-btn--xs c-btn--ghost" id="translate-next-50" type="button">ถัดไป 50</button>
                    <button class="c-btn c-btn--xs c-btn--ghost" id="translate-clean-untranslated" type="button">source clean ทั้งหมด</button>
                    <button class="c-btn c-btn--xs c-btn--ghost" id="translate-preview-queue" type="button">Preview queue</button>
                  </div>
                </div>
                <div id="translate-repair-preview" class="c-admin-translate__repair-preview" hidden></div>
                <div id="translate-detail-panel" class="c-admin-translate__detail-panel" hidden></div>
                <div id="translate-chapter-table" class="c-admin-translate__chapter-table" aria-live="polite">
                  <div class="c-admin-translate__chapter-empty">กำลังโหลด...</div>
                </div>
              </div>
            </div>
          </div>

          <!-- TRANSLATION CONSOLE -->
          <div class="c-card c-admin-translate__panel c-admin-translate__console-card" id="translate-console-card">
            <div class="c-admin-translate__console-head">
              <h4 class="c-admin-translate__console-title" id="translate-console-title">Console</h4>
              <span id="translate-console-badge" class="c-badge c-badge--gray">Idle</span>
            </div>
            <pre id="translate-console-output" class="c-admin-translate__console" aria-live="polite">พร้อมรับคำสั่ง ยังไม่มีงานใหม่</pre>
          </div>

        </div>
      </div>`;

      page.innerHTML = html;
      document.getElementById('translate-health-refresh')?.addEventListener('click', () => this.render(params));
      document.querySelector('.translate-health-refresh-inline')?.addEventListener('click', () => this.render(params));

      const updateModelCatalogNote = () => {
        const input = document.getElementById('translate-model-override');
        const selectedModel = input?.value.trim() || currentLlmConfig.default_model || '';
        const readout = AdminTranslateCatalog.readout(currentLlmConfig, selectedModel);
        const providerEl = document.getElementById('translate-selected-provider-readout');
        const modelEl = document.getElementById('translate-selected-model-readout');
        const keyEl = document.getElementById('translate-provider-key-readout');
        const note = document.getElementById('translate-model-catalog-note');
        if (providerEl) providerEl.textContent = readout.providerLabel;
        if (modelEl) modelEl.textContent = readout.modelLabel;
        if (keyEl) keyEl.textContent = readout.keyLabel;
        if (note) note.textContent = readout.catalogSummary;
      };
      document.getElementById('translate-model-override')?.addEventListener('input', updateModelCatalogNote);
      const refreshModelCatalog = async (silent = false) => {
        const btn = document.getElementById('translate-refresh-models');
        if (btn && !silent) {
          btn.disabled = true;
          AdminUi.setButton(btn, 'search', 'Refreshing...');
        }
        try {
          currentLlmConfig = await Api.getLlmConfig({ refreshModels: true });
          const list = document.getElementById('translate-model-list');
          if (list) list.innerHTML = buildModelOptions(currentLlmConfig);
          updateModelCatalogNote();
          if (!silent) Ui.showToast('อัปเดตรายชื่อโมเดลแล้ว');
        } catch (err) {
          if (!silent) Ui.showToast('Refresh models ไม่สำเร็จ: ' + err.message, 'error');
        } finally {
          if (btn && !silent) {
            btn.disabled = false;
            AdminUi.setButton(btn, 'search', 'Refresh models');
          }
        }
      };
      document.getElementById('translate-refresh-models')?.addEventListener('click', () => refreshModelCatalog(false));
      document.getElementById('translate-provider-check')?.addEventListener('click', async () => {
        const btn = document.getElementById('translate-provider-check');
        const modelOverride = document.getElementById('translate-model-override')?.value.trim() || currentLlmConfig.default_model || '';
        if (btn) {
          btn.disabled = true;
          AdminUi.setButton(btn, 'info', 'Checking...');
        }
        try {
          const cfg = await Api.getLlmConfig({ refreshModels: true });
          currentLlmConfig = cfg;
          const list = document.getElementById('translate-model-list');
          if (list) list.innerHTML = buildModelOptions(currentLlmConfig);
          updateModelCatalogNote();
          const check = AdminTranslateCatalog.providerCheck(cfg, modelOverride);
          AdminTranslatePage.setConsole(check.modelExists ? 'success' : 'error', 'Provider check', check.lines);
        } catch (err) {
          AdminTranslatePage.setConsole('error', 'Provider check failed', err.message);
          Ui.showToast('เช็ค provider ไม่สำเร็จ: ' + err.message, 'error');
        } finally {
          if (btn) {
            btn.disabled = false;
            AdminUi.setButton(btn, 'info', 'Check model');
          }
        }
      });

      const updateSourceHealth = () => {
        const slugVal = document.getElementById('translate-batch-novel')?.value || '';
        const h = importHealthBySlug[slugVal] || {};
        const box = document.getElementById('translate-source-health');
        if (!box) return;
        box.innerHTML = AdminTranslateView.sourceHealthHtml({ slug: slugVal, health: h });
      };
      document.getElementById('translate-batch-novel')?.addEventListener('change', updateSourceHealth);
      updateSourceHealth();

      let tableChapters = [];
      let sourceIssueByNum = {};
      let lastResultByNum = {};
      let filterState = 'all';
      let searchQuery = '';
      const selectedNums = new Set();
      let activeRunId = '';

      const renderJobPanel = (run = null) => {
        return AdminTranslateJob.renderPanel({
          run,
          resultByNum: lastResultByNum,
          currentModel: currentLlmConfig.default_model || '-',
          renderChapterTable,
        });
      };

      const stopRunPolling = () => {
        if (AdminTranslatePage._pollTimer) clearInterval(AdminTranslatePage._pollTimer);
        AdminTranslatePage._pollTimer = null;
      };

      const pollRun = (runId) => {
        activeRunId = runId || '';
        stopRunPolling();
        if (!activeRunId) return;
        const tick = async () => {
          try {
            const resp = await Api.getTranslateRun(activeRunId);
            const run = resp.data || resp;
            renderJobPanel(run);
            if (!AdminTranslateJob.isActiveStatus(run.status)) {
              stopRunPolling();
              await loadChapterTable(true);
              renderQueuePreview();
              if (runBtn) {
                runBtn.disabled = false;
                AdminUi.setButton(runBtn, 'book', 'เริ่มแปล');
              }
              Ui.showToast(run.status === 'done' ? 'งานแปลเสร็จแล้ว' : 'งานแปลหยุดด้วยสถานะ ' + run.status, run.status === 'done' ? 'success' : 'warning');
            }
          } catch (err) {
            stopRunPolling();
            AdminTranslatePage.setConsole('error', 'Run tracker failed', err.message);
          }
        };
        tick();
        AdminTranslatePage._pollTimer = setInterval(tick, 2000);
      };

      const refreshRuns = async () => {
        try {
          const resp = await Api.getTranslateRuns();
          const data = resp.data || resp;
          const slugVal = document.getElementById('translate-batch-novel')?.value || '';
          const run = (data.active || []).find(item => item.slug === slugVal) || (data.active || [])[0] || null;
          renderJobPanel(run);
          if (run?.runId && AdminTranslateJob.isActiveStatus(run.status)) pollRun(run.runId);
        } catch (err) {
          AdminTranslatePage.setConsole('error', 'Run list failed', err.message);
        }
      };

      const visibleChapters = () => AdminTranslateSelection.visibleChapters({
        chapters: tableChapters,
        sourceIssueByNum,
        lastResultByNum,
        filterState,
        searchQuery,
      });

      const renderQueuePreview = () => {
        const box = document.getElementById('translate-queue-preview');
        if (!box) return null;
        const range = document.getElementById('translate-batch-range')?.value || AdminTranslatePage._rangeFromNums([...selectedNums]);
        if (!range.trim()) {
          box.hidden = false;
          box.innerHTML = AdminTranslateView.queueStateHtml('ยังไม่ได้เลือกตอน กรอกช่วงตอนหรือเลือกจากตารางเพื่อดู preview');
          return null;
        }
        const nums = AdminTranslatePage._numsFromRange(range);
        if (!nums.length) {
          box.hidden = false;
          box.innerHTML = AdminTranslateView.queueStateHtml('ช่วงตอนไม่ถูกต้อง ใช้รูปแบบเช่น 5, 5-10 หรือ 5,8,12-15');
          return null;
        }
        const force = document.getElementById('translate-force-source')?.checked === true;
        const preview = AdminTranslatePage._queuePreview(tableChapters, sourceIssueByNum, lastResultByNum, nums, force);
        box.hidden = false;
        box.innerHTML = AdminTranslateView.queuePreviewHtml(preview);
        return preview;
      };

      const renderChapterTable = () => {
        const table = document.getElementById('translate-chapter-table');
        const summaryEl = document.getElementById('translate-chapter-summary');
        if (!table || !summaryEl) return;
        const visible = visibleChapters();
        const view = AdminTranslateView.chapterTable({
          chapters: tableChapters,
          visibleChapters: visible,
          selectedNums,
          sourceIssueByNum,
          lastResultByNum,
        });
        summaryEl.textContent = view.summary;
        table.innerHTML = view.html;
      };

      const syncRangeFromSelection = () => {
        const range = AdminTranslatePage._rangeFromNums([...selectedNums]);
        const input = document.getElementById('translate-batch-range');
        if (input) input.value = range;
        renderChapterTable();
        return range;
      };

      const loadChapterTable = async (preserveResults = false) => {
        const slugVal = document.getElementById('translate-batch-novel')?.value || '';
        const table = document.getElementById('translate-chapter-table');
        const summaryEl = document.getElementById('translate-chapter-summary');
        if (!slugVal || !table || !summaryEl) return;
        summaryEl.textContent = 'กำลังโหลดรายการตอน...';
        table.innerHTML = '<div class="c-admin-translate__chapter-empty">กำลังโหลด...</div>';
        try {
          const [chapters, healthResp] = await Promise.all([
            Api.getChapters(slugVal, { withQuality: true }),
            Api.getImportHealth(slugVal, { includeChapters: true }).catch(() => ({ data: { chapters: [] } })),
          ]);
          tableChapters = chapters || [];
          sourceIssueByNum = {};
          for (const ch of healthResp.data?.chapters || []) sourceIssueByNum[ch.num] = ch;
          selectedNums.clear();
          if (!preserveResults) lastResultByNum = {};
          renderChapterTable();
          renderQueuePreview();
        } catch (err) {
          summaryEl.textContent = 'โหลดรายการตอนไม่สำเร็จ';
          table.innerHTML = '<div class="c-admin-translate__chapter-empty">โหลดไม่สำเร็จ: ' + Ui.esc(err.message) + '</div>';
        }
      };

      const selectMatching = (predicate) => {
        selectedNums.clear();
        const nums = AdminTranslateSelection.matchingNums({
          chapters: tableChapters,
          sourceIssueByNum,
          lastResultByNum,
          filterState,
          searchQuery,
          predicate,
        });
        for (const num of nums) selectedNums.add(num);
        return syncRangeFromSelection();
      };

      const setSelectedNums = (nums) => {
        selectedNums.clear();
        for (const num of nums) selectedNums.add(num);
        syncRangeFromSelection();
        renderQueuePreview();
        return AdminTranslatePage._rangeFromNums([...selectedNums]);
      };

      const selectedTranslatedNums = () => AdminTranslateSelection.selectedTranslatedNums({
        chapters: tableChapters,
        selectedNums,
      });

      const showChapterDetail = (num) => {
        const ch = tableChapters.find(item => item.num === num);
        if (!ch) return;
        const sourceIssue = sourceIssueByNum[num];
        const resultIssue = lastResultByNum[num];
        const panel = document.getElementById('translate-detail-panel');
        if (!panel) return;
        panel.hidden = false;
        panel.innerHTML = AdminTranslateView.chapterDetailHtml({ num, chapter: ch, sourceIssue, resultIssue });
      };

      document.getElementById('translate-chapter-table')?.addEventListener('change', (event) => {
        const checkbox = event.target.closest('input[type="checkbox"]');
        if (!checkbox) return;
        if (checkbox.id === 'translate-select-all') {
          selectedNums.clear();
          if (checkbox.checked) for (const ch of visibleChapters()) selectedNums.add(ch.num);
        } else if (checkbox.classList.contains('translate-chapter-check')) {
          const num = parseInt(checkbox.dataset.num, 10);
          if (Number.isFinite(num)) {
            if (checkbox.checked) selectedNums.add(num);
            else selectedNums.delete(num);
          }
        }
        syncRangeFromSelection();
        renderQueuePreview();
      });

      document.getElementById('translate-chapter-table')?.addEventListener('click', async (event) => {
        const detailBtn = event.target.closest('.translate-detail-btn');
        const inspectBtn = event.target.closest('.translate-inspect-btn');
        if (detailBtn) {
          showChapterDetail(parseInt(detailBtn.dataset.num, 10));
          return;
        }
        if (inspectBtn) {
          const slugVal = document.getElementById('translate-batch-novel')?.value || '';
          const num = parseInt(inspectBtn.dataset.num, 10);
          if (!slugVal || !Number.isFinite(num)) return;
          inspectBtn.disabled = true;
          AdminUi.setButton(inspectBtn, 'search', '...');
          try {
            const data = await Api.inspectSource(slugVal, num);
            const diagnostic = data.data?.diagnostic || data.diagnostic || {};
            const issues = diagnostic.issues || [];
            AdminTranslatePage.setConsole(
              issues.some(issue => issue.severity === 'error') ? 'error' : 'idle',
              `Source inspect: ตอน ${num}`,
              [
                data.data?.title || data.title || '',
                `${diagnostic.paragraphCount || 0} paragraphs · ${diagnostic.charCount || 0} chars`,
                issues.length ? issues.map(issue => `${issue.severity}:${issue.code}`).join(', ') : 'clean',
                '',
                (data.data?.cleanedText || data.cleanedText || '').slice(0, 1800),
              ].join('\n')
            );
          } catch (err) {
            Ui.showToast(err.message, 'error');
          } finally {
            inspectBtn.disabled = false;
            AdminUi.setButton(inspectBtn, 'search', 'ตรวจ');
          }
        }
      });

      document.getElementById('translate-select-untranslated')?.addEventListener('click', () => {
        selectMatching(status => status === 'untranslated');
      });
      document.getElementById('translate-select-translated')?.addEventListener('click', () => {
        selectMatching((status, ch) => ch.hasTh || ch.isTranslated || ch.status === 'translated');
      });
      document.getElementById('translate-select-review')?.addEventListener('click', () => {
        selectMatching(status => status === 'needs_review' || status === 'failed');
      });
      document.getElementById('translate-select-source-errors')?.addEventListener('click', () => {
        selectMatching(status => status === 'source_not_ready');
      });
      document.getElementById('translate-clear-selection')?.addEventListener('click', () => {
        selectedNums.clear();
        syncRangeFromSelection();
        renderQueuePreview();
      });
      document.querySelectorAll('.translate-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          filterState = btn.dataset.filter || 'all';
          document.querySelectorAll('.translate-filter-btn').forEach(item => {
            item.classList.toggle('c-btn--secondary', item === btn);
            item.classList.toggle('c-btn--ghost', item !== btn);
          });
          renderChapterTable();
          renderQueuePreview();
        });
      });
      document.getElementById('translate-chapter-search')?.addEventListener('input', (event) => {
        searchQuery = event.target.value || '';
        renderChapterTable();
      });
      const nextUntranslatedAfterProgress = (limit) => {
        return AdminTranslateSelection.nextUntranslatedAfterProgress({
          chapters: tableChapters,
          sourceIssueByNum,
          lastResultByNum,
          limit,
        });
      };
      document.getElementById('translate-next-20')?.addEventListener('click', () => {
        setSelectedNums(nextUntranslatedAfterProgress(20));
      });
      document.getElementById('translate-next-50')?.addEventListener('click', () => {
        setSelectedNums(nextUntranslatedAfterProgress(50));
      });
      document.getElementById('translate-clean-untranslated')?.addEventListener('click', () => {
        const nums = tableChapters
          .filter(ch => AdminTranslatePage._chapterStatus(ch, sourceIssueByNum[ch.num], lastResultByNum[ch.num]) === 'untranslated')
          .map(ch => ch.num);
        setSelectedNums(nums);
      });
      document.getElementById('translate-preview-queue')?.addEventListener('click', () => {
        renderQueuePreview();
      });
      document.getElementById('translate-batch-range')?.addEventListener('input', () => {
        renderQueuePreview();
      });
      document.getElementById('translate-force-source')?.addEventListener('change', () => {
        renderQueuePreview();
      });
      document.getElementById('translate-job-refresh')?.addEventListener('click', () => {
        refreshRuns();
      });
      document.getElementById('translate-job-cancel')?.addEventListener('click', async () => {
        if (!activeRunId) return;
        const btn = document.getElementById('translate-job-cancel');
        if (btn) btn.disabled = true;
        try {
          const resp = await Api.cancelTranslateRun(activeRunId);
          renderJobPanel(resp.data || resp);
        } catch (err) {
          Ui.showToast('ยกเลิกงานไม่สำเร็จ: ' + err.message, 'error');
        } finally {
          if (btn) btn.disabled = false;
        }
      });

      document.getElementById('translate-batch-novel')?.addEventListener('change', () => {
        updateSourceHealth();
        loadChapterTable();
        refreshRuns();
      });
      loadChapterTable().finally(() => {
        setTimeout(() => { refreshModelCatalog(true); }, 1000);
        refreshRuns();
      });

      // ── Bind Batch Translation Event
      const runBtn = document.getElementById('translate-batch-run-btn');
      const runBatch = async (rangeOverride = '', runOptions = {}) => {
          let launchedRun = false;
          const slugVal = document.getElementById('translate-batch-novel').value;
          const rangeVal = rangeOverride || document.getElementById('translate-batch-range').value;
          const concurrentVal = parseInt(document.getElementById('translate-batch-concurrent').value, 10);
          const promptProfile = document.getElementById('translate-prompt-profile')?.value || 'faithful_default';
          const modelOverride = document.getElementById('translate-model-override')?.value.trim() || '';
          const forceSource = runOptions.force === true || document.getElementById('translate-force-source')?.checked === true;
          const requestedNums = AdminTranslatePage._numsFromRange(rangeVal);

          const validation = AdminTranslateCommand.validateRunRequest({
            rangeVal,
            requestedNums,
            sourceIssueByNum,
            forceSource,
          });
          if (!validation.ok) {
            AdminTranslatePage.setConsole('error', validation.title, validation.message);
            Ui.showToast(validation.toast, 'error');
            if (validation.renderPreview) renderQueuePreview();
            return;
          }
          renderQueuePreview();

          AdminTranslateCommand.markQueued(lastResultByNum, requestedNums);
          renderChapterTable();

          AdminTranslatePage.setConsole(
            'running',
            `รันการแปลช่วงตอน: ${rangeVal}`,
            `กำลังส่งคำสั่งแปล\\nนิยาย: ${slugVal}\\nforce source: ${forceSource ? 'yes' : 'no'}`
          );

          try {
            if (runBtn) {
              runBtn.disabled = true;
              AdminUi.setButton(runBtn, 'book', 'กำลังดำเนินการแปล...');
            }

            const options = AdminTranslateCommand.buildRunOptions({
              forceSource,
              promptProfile,
              modelOverride,
              providerByModel: modelProviderById,
            });
            const res = await Api.startTranslateRun(slugVal, rangeVal, concurrentVal, options);
            const run = res.data || res;
            activeRunId = run.runId || '';
            launchedRun = true;
            renderJobPanel(run);
            AdminTranslatePage.setConsole(
              'running',
              `เริ่มงานแปลแล้ว: ${rangeVal}`,
              `run: ${activeRunId}\nmodel: ${run.model || currentLlmConfig.default_model || '-'}\nprovider: ${run.provider || currentLlmConfig.default_provider || '-'}`
            );
            pollRun(activeRunId);
            Ui.showToast('เริ่มงานแปลแล้ว กำลังติดตามสถานะ');
          } catch (err) {
            const failed = AdminTranslateCommand.applyFailedResults({
              err,
              requestedNums,
              resultByNum: lastResultByNum,
            });
            renderChapterTable();
            AdminTranslatePage.setConsole(
              'error',
              `แปลไม่สำเร็จ: ${rangeVal}`,
              failed.failedChapters.length
                ? AdminTranslatePage._formatBatchResult({ summary: failed.failedSummary, chapters: failed.failedChapters })
                : `[ERROR] การแปลเกิดข้อผิดพลาด:\\n\\n${err.message}`
            );
            Ui.showToast('การแปลเกิดข้อผิดพลาด: ' + err.message, 'error');
          } finally {
            if (runBtn && !launchedRun) {
              runBtn.disabled = false;
              AdminUi.setButton(runBtn, 'book', 'เริ่มแปล');
            }
          }
      };
      if (runBtn) runBtn.addEventListener('click', () => runBatch());
      const runSelected = (options = {}) => {
        const range = AdminTranslatePage._rangeFromNums([...selectedNums]);
        if (!range) {
          Ui.showToast('เลือกตอนก่อนสั่งแปล', 'error');
          return;
        }
        runBatch(range, options);
      };
      document.getElementById('translate-run-selected')?.addEventListener('click', () => {
        runSelected();
      });
      document.getElementById('translate-delete-selected')?.addEventListener('click', async () => {
        const slugVal = document.getElementById('translate-batch-novel')?.value || '';
        const btn = document.getElementById('translate-delete-selected');
        const nums = selectedTranslatedNums();
        if (!slugVal || !btn) return;
        if (!selectedNums.size) {
          Ui.showToast('เลือกตอนที่ต้องการลบไฟล์แปลก่อน', 'error');
          return;
        }
        if (!nums.length) {
          Ui.showToast('ตอนที่เลือกยังไม่มีไฟล์แปลไทยให้ลบ', 'warning');
          return;
        }
        const range = AdminTranslatePage._rangeFromNums(nums);
        const deleteInfo = AdminTranslateCommand.deleteConfirmation({
          nums,
          selectedCount: selectedNums.size,
          range,
        });
        if (!confirm(deleteInfo.message)) {
          return;
        }

        btn.disabled = true;
        AdminUi.setButton(btn, 'close', 'กำลังลบ...');
        AdminTranslatePage.setConsole('running', 'Deleting selected translations', `slug: ${slugVal}\nchapters: ${deleteInfo.displayRange}`);
        try {
          const res = await Api.deleteTranslatedChapters(slugVal, nums);
          const data = res.data || res;
          await loadChapterTable(false);
          renderQueuePreview();
          AdminTranslatePage.setConsole(
            'success',
            'Deleted selected translations',
            `slug: ${slugVal}\ndeleted: ${data.deleted || 0}\nchapters: ${AdminTranslatePage._rangeFromNums(data.nums || [])}\nsource files kept: yes`
          );
          Ui.showToast('ลบไฟล์แปลไทยแล้ว ' + (data.deleted || 0) + ' ตอน');
        } catch (err) {
          AdminTranslatePage.setConsole('error', 'Delete selected translations failed', err.message);
          Ui.showToast('ลบไฟล์แปลไม่สำเร็จ: ' + err.message, 'error');
        } finally {
          btn.disabled = false;
          AdminUi.setButton(btn, 'close', 'ลบแปลที่เลือก');
        }
      });
      document.getElementById('translate-run-untranslated')?.addEventListener('click', () => {
        const range = selectMatching(status => status === 'untranslated');
        if (!range) {
          Ui.showToast('ไม่มีตอนที่ยังไม่แปลและ source พร้อมในหน้านี้', 'error');
          return;
        }
        runBatch(range);
      });
      document.getElementById('translate-retry-review')?.addEventListener('click', () => {
        const range = selectMatching(status => status === 'needs_review' || status === 'failed');
        if (!range) {
          Ui.showToast('ยังไม่มีตอนที่ควร retry', 'error');
          return;
        }
        runBatch(range);
      });
      document.getElementById('translate-force-selected')?.addEventListener('click', () => {
        runSelected({ force: true });
      });
      document.getElementById('translate-repair-source')?.addEventListener('click', async () => {
        const slugVal = document.getElementById('translate-batch-novel')?.value || '';
        const btn = document.getElementById('translate-repair-source');
        const panel = document.getElementById('translate-repair-preview');
        if (!slugVal || !btn) return;
        btn.disabled = true;
        AdminUi.setButton(btn, 'settings', 'Checking...');
        AdminTranslatePage.setConsole('running', 'Repair preview', 'Checking source titles/noise and rebuilding index for ' + slugVal + '...');
        try {
          const preview = await Api.repairImport(slugVal, 'all', { dryRun: true });
          const previewRepair = preview.data?.repair || {};
          const previewMessage = formatImportRepairSummary(slugVal, previewRepair);
          AdminTranslatePage.setConsole('idle', 'Repair preview', previewMessage);
          if (panel) {
            panel.hidden = false;
            panel.innerHTML = AdminTranslateView.repairPreviewHtml(slugVal, previewMessage);
            document.getElementById('translate-cancel-repair')?.addEventListener('click', () => {
              panel.hidden = true;
              panel.innerHTML = '';
            });
            document.getElementById('translate-apply-repair')?.addEventListener('click', async () => {
              const applyBtn = document.getElementById('translate-apply-repair');
              if (applyBtn) {
                applyBtn.disabled = true;
                AdminUi.setButton(applyBtn, 'settings', 'Repairing...');
              }
              try {
                AdminTranslatePage.setConsole('running', 'Repair running', 'Applying source/index repairs for ' + slugVal + '...');
                const result = await Api.repairImport(slugVal, 'all');
                const repair = result.data?.repair || {};
                AdminTranslatePage.setConsole('success', 'Repair complete', formatImportRepairSummary(slugVal, repair));
                const health = await Api.getImportHealth(slugVal).catch(() => null);
                if (health?.data) importHealthBySlug[slugVal] = health.data;
                updateSourceHealth();
                await loadChapterTable();
                panel.hidden = true;
                panel.innerHTML = '';
                Ui.showToast('ซ่อม source/index แล้ว');
              } catch (err) {
                AdminTranslatePage.setConsole('error', 'Repair failed', err.message);
                Ui.showToast('ซ่อมไม่สำเร็จ: ' + err.message, 'error');
                if (applyBtn) {
                  applyBtn.disabled = false;
                  AdminUi.setButton(applyBtn, 'settings', 'Apply repair');
                }
              }
            });
          }
        } catch (err) {
          AdminTranslatePage.setConsole('error', 'Repair failed', err.message);
          Ui.showToast('ซ่อมไม่สำเร็จ: ' + err.message, 'error');
        } finally {
          btn.disabled = false;
          AdminUi.setButton(btn, 'settings', 'ซ่อม source/index');
        }
      });

    } catch (err) {
      Ui.showError(page, 'โหลดหน้าแปลล้มเหลว', err.message);
    }
  }
};

  window.AdminTranslatePage = AdminTranslatePage;
})();
