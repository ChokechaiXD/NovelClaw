const assert = require('node:assert/strict');
const test = require('node:test');
const { renderChapterJson } = require('../lib/test-renderer');

test('renderChapterJson uses output_lang bracket profile', () => {
  const html = renderChapterJson({
    num: 1,
    title: 'ตอนที่ 1 Test',
    lang: 'cn',
    output_lang: 'en',
    blocks: [
      { type: 'narration', text: 'เล่าเรื่อง' },
      { type: 'dialogue', text: 'Hello' },
      { type: 'system', text: '[System]' },
      { type: 'end', text: '(End)' },
    ],
  });

  assert.match(html, /<p class="dialogue".*data-lang="en"/);
  assert.match(html, /<p class="system-msg".*data-lang="en"/);
  assert.match(html, /<p class="end-marker".*data-lang="en">\(End\)<\/p>/);
});

test('renderChapterJson allows explicit profile_lang override', () => {
  const html = renderChapterJson({
    num: 1,
    title: 'ตอนที่ 1 Test',
    lang: 'cn',
    output_lang: 'en',
    profile_lang: 'cn',
    blocks: [
      { type: 'dialogue', text: 'Hello' },
      { type: 'end', text: '(จบบท)' },
    ],
  });

  assert.match(html, /<p class="dialogue".*data-lang="cn"/);
  assert.match(html, /<p class="end-marker".*data-lang="cn">\(จบบท\)<\/p>/);
});
