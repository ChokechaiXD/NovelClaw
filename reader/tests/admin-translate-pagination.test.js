const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const viewSource = fs.readFileSync(
  path.join(__dirname, '..', 'public', 'js', 'pages', 'admin-translate-view.js'),
  'utf8'
);
const pageSource = fs.readFileSync(
  path.join(__dirname, '..', 'public', 'js', 'pages', 'admin-translate.js'),
  'utf8'
);

function loadView() {
  const window = {
    AdminTranslateModel: {
      chapterStatus(chapter) { return chapter.status || 'untranslated'; },
      statusBadge(status) { return [status, `c-badge--${status}`]; },
      qualityText(chapter) { return chapter.quality || '-'; },
    },
  };
  const Ui = {
    esc(value) {
      return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },
    icon() { return ''; },
  };
  vm.runInNewContext(viewSource, { Ui, window });
  return window.AdminTranslateView;
}

function chapters(count) {
  return Array.from({ length: count }, (_, index) => ({
    num: index + 1,
    title: `Chapter ${index + 1}`,
    status: 'untranslated',
  }));
}

test('chapter table bounds a 1,132 chapter novel to 100 rendered rows', () => {
  const view = loadView();
  const allChapters = chapters(1132);

  const rendered = view.chapterTable({
    chapters: allChapters,
    visibleChapters: allChapters,
  });

  assert.equal(rendered.page, 1);
  assert.equal(rendered.pageCount, 12);
  assert.equal(rendered.visibleCount, 1132);
  assert.equal(rendered.renderedCount, 100);
  assert.equal((rendered.html.match(/<tr data-status=/g) || []).length, 100);
  assert.match(rendered.html, /id="translate-page-prev"[^>]* disabled/);
  assert.match(rendered.html, /id="translate-page-next" data-translate-page="2"/);
  assert.match(rendered.html, /หน้า 1 \/ 12 · ตอน 1–100 จาก 1132/);
});

test('chapter table clamps an out-of-range page and renders the final slice', () => {
  const view = loadView();
  const allChapters = chapters(1132);

  const rendered = view.chapterTable({
    chapters: allChapters,
    visibleChapters: allChapters,
    page: 99,
  });

  assert.equal(rendered.page, 12);
  assert.equal(rendered.renderedCount, 32);
  assert.equal((rendered.html.match(/<tr data-status=/g) || []).length, 32);
  assert.match(rendered.html, /data-num="1101"/);
  assert.match(rendered.html, /id="translate-page-next"[^>]* disabled/);
});

test('filtering paginates only matched chapters while select-all covers every match', () => {
  const view = loadView();
  const allChapters = chapters(250);
  const filtered = allChapters.slice(100);
  const selectedNums = new Set(filtered.map(chapter => chapter.num));

  const rendered = view.chapterTable({
    chapters: allChapters,
    visibleChapters: filtered,
    selectedNums,
    page: 2,
  });

  assert.equal(rendered.visibleCount, 150);
  assert.equal(rendered.renderedCount, 50);
  assert.match(rendered.summary, /แสดง 150 · หน้า 2\/2/);
  assert.match(rendered.html, /id="translate-select-all" type="checkbox" checked/);
  assert.match(rendered.html, /aria-label="เลือกทุกตอนที่ตรงกับตัวกรอง"/);

  const empty = view.chapterTable({ chapters: allChapters, visibleChapters: [] });
  assert.equal(empty.renderedCount, 0);
  assert.doesNotMatch(empty.html, /<tr data-status=/);
  assert.match(empty.html, /ไม่พบตอนที่ตรงกับตัวกรอง/);
});

test('page controller preserves full filtered selection semantics', () => {
  assert.match(pageSource, /page:\s*chapterPage/);
  assert.match(pageSource, /pageSize:\s*chapterPageSize/);
  assert.match(pageSource, /data-translate-page/);
  assert.match(
    pageSource,
    /if \(checkbox\.checked\) for \(const ch of visibleChapters\(\)\) selectedNums\.add\(ch\.num\)/
  );
  assert.ok((pageSource.match(/chapterPage = 1;/g) || []).length >= 3);
});
