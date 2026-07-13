const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const dashboardSource = fs.readFileSync(
  path.join(__dirname, '..', 'public', 'js', 'pages', 'admin-dashboard.js'),
  'utf8'
);

function createDashboardHarness(novels, runs) {
  const page = { innerHTML: '' };
  const Ui = {
    $(id) { return id === 'page-admin' ? page : null; },
    adminNav() { return '<nav>studio</nav>'; },
    displayTitle(novel) { return novel?.translatedTitle || novel?.title || novel?.slug || ''; },
    esc(value) {
      return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },
    icon(id) { return `<i data-icon="${id}"></i>`; },
    isVisibleNovel(novel) { return (novel.chapterCount || novel.totalChapters || 0) > 0; },
    showError(_page, title, message) { throw new Error(`${title}: ${message}`); },
    showSkeleton() {},
  };
  const Api = {
    async getNovels() { return novels; },
    async getTranslateRuns() { return { data: runs }; },
  };
  const window = {};
  vm.runInNewContext(dashboardSource, { Api, Ui, window });
  return {
    page,
    render: () => window.AdminDashboardPage.render(),
  };
}

test('studio dashboard derives chapter totals and active work from APIs', async () => {
  const harness = createDashboardHarness([
    { slug: 'demo', translatedTitle: 'นิยายทดสอบ', chapterCount: 12, translatedChapters: 7 },
  ], {
    active: [{ slug: 'demo', status: 'running', range: '8-12', done: 2, total: 5 }],
    recent: [],
  });

  await harness.render();

  assert.match(harness.page.innerHTML, /สตูดิโองานแปล/);
  assert.match(harness.page.innerHTML, /7\/12 ตอนแปลแล้ว/);
  assert.match(harness.page.innerHTML, /กำลังแปล นิยายทดสอบ/);
  assert.match(harness.page.innerHTML, /เสร็จ 2\/5 ตอน/);
  assert.doesNotMatch(harness.page.innerHTML, /ศูนย์จัดการระบบ|c-control-center|c-mini-stat/);
});

test('studio dashboard prioritizes review from the latest failed run', async () => {
  const harness = createDashboardHarness([
    { slug: 'demo', translatedTitle: 'นิยายทดสอบ', chapterCount: 12, translatedChapters: 4 },
  ], {
    active: [],
    recent: [{ slug: 'demo', status: 'failed', range: '5-8', done: 4, total: 4, failed: 1, needsReview: 2 }],
  });

  await harness.render();

  assert.match(harness.page.innerHTML, /ตรวจผล นิยายทดสอบ/);
  assert.match(harness.page.innerHTML, /3 ตอนต้องตรวจจากงานล่าสุด/);
  assert.match(harness.page.innerHTML, /href="#admin\/chapters\/demo"/);
});

test('studio dashboard keeps a real zero-chapter novel in the import workflow', async () => {
  const harness = createDashboardHarness([
    { slug: 'waiting-source', translatedTitle: 'เรื่องรอต้นฉบับ', chapterCount: 0, translatedChapters: 0 },
  ], { active: [], recent: [] });

  await harness.render();

  assert.match(harness.page.innerHTML, /เติมต้นฉบับให้ เรื่องรอต้นฉบับ/);
  assert.match(harness.page.innerHTML, /href="#admin\/import\/waiting-source"/);
  assert.match(harness.page.innerHTML, /1 เรื่องในคลัง/);
});

test('studio navigation exposes one ordered workflow and secondary tools', () => {
  const componentsSource = fs.readFileSync(
    path.join(__dirname, '..', 'public', 'js', 'components.js'),
    'utf8'
  );
  const context = {
    document: { addEventListener() {} },
  };
  vm.runInNewContext(`${componentsSource}\nthis.Ui = Ui;`, context);

  const html = context.Ui.adminNav('chapters');

  const workflowLabels = ['นำเข้า', 'แปล', 'ตรวจผล', 'คำศัพท์'];
  for (let index = 1; index < workflowLabels.length; index += 1) {
    assert.ok(html.indexOf(workflowLabels[index - 1]) < html.indexOf(workflowLabels[index]));
  }
  assert.match(html, /aria-label="ลำดับงานหลัก"/);
  assert.match(html, /<span>คลัง<\/span>/);
  assert.match(html, /<span>ทุกตอน<\/span>/);
  assert.match(html, /<span>AI<\/span>/);
  assert.match(html, /<span>ล็อก<\/span>/);
  assert.equal((html.match(/aria-current="page"/g) || []).length, 1);
});
