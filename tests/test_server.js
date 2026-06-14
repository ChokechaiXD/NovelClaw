// test_server.js — Server renderer tests
//
// Tests the BRACKETS config + renderChapterJson() function exported by
// server.js. We import it directly (no HTTP) by setting NODE_PATH so
// the express/marked dependencies resolve from reader/node_modules.

const assert = require('node:assert');
const path = require('node:path');

// Make reader/node_modules resolvable
process.env.NODE_PATH = path.join(__dirname, '..', 'reader', 'node_modules');
require('node:module').Module._initPaths();

const { renderChapterJson, BRACKETS } = require(
  path.join(__dirname, '..', 'reader', 'server.js')
);

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    passed++;
  } catch (e) {
    console.log(`  ✗ ${name}: ${e.message}`);
    failed++;
  }
}

console.log('BRACKETS config:');
for (const [lang, b] of Object.entries(BRACKETS)) {
  console.log(`  ${lang}: d=${b.dialogueOpen}..${b.dialogueClose} e=${b.endMarker}`);
}

console.log('\nrenderChapterJson:');

test('CN (default) — 「」 → curly, brackets preserved', () => {
  const ch = {
    num: 1, title: 'ตอนที่ 1', source: 'ch 1',
    blocks: [
      { type: 'narration', text: 'เฉาซิงเดิน' },
      { type: 'dialogue', text: '「สวัสดี」' },
      { type: 'system', text: '【HP:100】' },
      { type: 'end', text: '(จบบท)' },
    ],
  };
  const html = renderChapterJson(ch);
  assert(html.includes('<p>เฉาซิงเดิน</p>'), 'narration rendered');
  assert(html.includes('<p class="dialogue" data-lang="cn">\u201Cสวัสดี\u201D</p>'),
         'dialogue with curly quotes and data-lang=cn');
  assert(html.includes('<p class="system-msg" data-lang="cn">【HP:100】</p>'),
         'system message preserved with brackets');
  assert(html.includes('<p class="end-marker" data-lang="cn">(จบบท)</p>'),
         'end marker preserved');
});

test('JP — title uses 『』, data-lang="jp"', () => {
  const ch = {
    num: 1, title: 'test', source: 'ch 1', lang: 'jp',
    blocks: [
      { type: 'dialogue', text: '「hi」' },
      { type: 'game_title', text: '『Game Title』' },
      { type: 'end', text: 'x' },
    ],
  };
  const html = renderChapterJson(ch);
  assert(html.includes('data-lang="jp"'), 'lang attribute set to jp');
  assert(html.includes('『Game Title』'), 'game title preserved with kagi');
});

test('EN — curly quotes, [system], (End)', () => {
  const ch = {
    num: 1, title: 'test', source: 'ch 1', lang: 'en',
    blocks: [
      { type: 'dialogue', text: '\u201CHello\u201D' },
      { type: 'system', text: '[HP:100]' },
      { type: 'end', text: '(End)' },
    ],
  };
  const html = renderChapterJson(ch);
  assert(html.includes('data-lang="en"'), 'lang attribute set to en');
  assert(html.includes('\u201CHello\u201D'), 'curly quotes preserved');
  assert(html.includes('[HP:100]'), 'square brackets preserved');
  assert(html.includes('(End)'), 'EN end marker');
});

test('TH — curly quotes, 【】, (จบบท)', () => {
  const ch = {
    num: 1, title: 'test', source: 'ch 1', lang: 'th',
    blocks: [
      { type: 'dialogue', text: '\u201Cสวัสดี\u201D' },
      { type: 'system', text: '【HP:100】' },
      { type: 'end', text: '(จบบท)' },
    ],
  };
  const html = renderChapterJson(ch);
  assert(html.includes('data-lang="th"'), 'lang=th');
  assert(html.includes('【HP:100】'), 'system with CN brackets');
});

test('Missing lang defaults to cn', () => {
  const ch = {
    num: 1, title: 'test', source: 'ch 1',
    blocks: [
      { type: 'dialogue', text: '「hi」' },
      { type: 'end', text: '(จบบท)' },
    ],
  };
  const html = renderChapterJson(ch);
  assert(html.includes('data-lang="cn"'), 'default lang=cn');
});

test('Unknown lang falls back to cn', () => {
  const ch = {
    num: 1, title: 'test', source: 'ch 1', lang: 'xyz',
    blocks: [
      { type: 'dialogue', text: '「hi」' },
      { type: 'end', text: '(จบบท)' },
    ],
  };
  const html = renderChapterJson(ch);
  assert(html.includes('data-lang="cn"'), 'unknown lang → cn fallback');
});

test('Source footer rendered', () => {
  const ch = {
    num: 1, title: 'test', source: 'ch 99',
    blocks: [
      { type: 'narration', text: 'hi' },
      { type: 'end', text: '(จบบท)' },
    ],
  };
  const html = renderChapterJson(ch);
  assert(html.includes('<hr/>'), 'hr separator');
  assert(html.includes('<p class="source-footer">ch 99</p>'), 'source footer');
});

test('Nested 『』 → curly single quotes (JP-style nested)', () => {
  const ch = {
    num: 1, title: 't', source: 's',
    blocks: [
      { type: 'dialogue', text: '「『nested』」' },
      { type: 'end', text: '(จบบท)' },
    ],
  };
  const html = renderChapterJson(ch);
  assert(html.includes('\u201C'), 'outer 「 → " (U+201C)');
  assert(html.includes('\u2018'), 'inner 『 → \' (U+2018)');
  assert(html.includes('\u2019'), 'inner 』 → \' (U+2019)');
});

test('All 5 languages have full BRACKETS config', () => {
  for (const lang of ['cn', 'jp', 'kr', 'en', 'th']) {
    const b = BRACKETS[lang];
    assert(b, `BRACKETS.${lang} exists`);
    assert(b.dialogueOpen, `${lang}.dialogueOpen exists`);
    assert(b.dialogueClose, `${lang}.dialogueClose exists`);
    assert(b.systemOpen, `${lang}.systemOpen exists`);
    assert(b.systemClose, `${lang}.systemClose exists`);
    assert(b.gameOpen, `${lang}.gameOpen exists`);
    assert(b.gameClose, `${lang}.gameClose exists`);
    assert(b.endMarker, `${lang}.endMarker exists`);
  }
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
