const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function loadRenderer() {
  const code = fs.readFileSync(path.join(__dirname, '..', 'public', 'js', 'reader-renderer.js'), 'utf8');
  const sandbox = {
    document: {
      createElement() {
        let value = '';
        return {
          set textContent(next) { value = String(next); },
          get innerHTML() { return escapeHtml(value); },
        };
      },
    },
  };
  return vm.runInNewContext(`${code}\nReaderRenderer;`, sandbox);
}

test('ReaderRenderer renders semantic paragraph attrs and safe thought text', () => {
  const renderer = loadRenderer();
  const html = renderer.renderChapter({
    lang: 'th',
    paragraphs: [
      { type: 'thought', text: '<em>เขาคิดในใจ</em> <tag>' },
      { type: 'dialogue', text: '"ไปกันเถอะ"' },
    ],
  });

  assert.match(html, /data-type="thought"/);
  assert.match(html, /data-lang="th"/);
  assert.match(html, /dir="auto"/);
  assert(!html.includes('&lt;em&gt;'));
  assert(!html.includes('<em>'));
  assert(html.includes('&lt;tag&gt;'));
  assert.match(html, /data-type="dialogue"/);
});

test('ReaderRenderer classifies legacy thought markers without storing HTML tags', () => {
  const renderer = loadRenderer();
  const html = renderer.renderChapter({
    lang: 'th',
    paragraphs: ['『อย่าเพิ่งไว้ใจใคร』', '(จบบท)'],
  });

  assert.match(html, /class="c-para c-para--thought"/);
  assert(html.includes('อย่าเพิ่งไว้ใจใคร'));
  assert(!html.includes('&lt;em&gt;'));
  assert.match(html, /class="end-marker" data-type="end" data-lang="th" dir="auto"/);
});
