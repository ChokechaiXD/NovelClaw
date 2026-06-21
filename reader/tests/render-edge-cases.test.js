/**
 * render-edge-cases.test.js — Comprehensive renderer + validator edge case tests.
 *
 * Covers: all block types, all 5 languages, missing/null fields, empty content,
 * output_lang/profile_lang overrides, and integration consistency checks.
 */

const assert = require('node:assert/strict');
const test = require('node:test');
const { renderChapterJson } = require('../lib/render');
const { validateChapterJs } = require('../services/validation');

// ── Renderer: All 5 languages ─────────────────────────────────────────────

test('renderChapterJson CN brackets', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'cn', output_lang: 'th',
    blocks: [
      { type: 'narration', text: 'เล่าเรื่อง' },
      { type: 'dialogue', text: 'สวัสดี' },
      { type: 'system', text: '[System]' },
      { type: 'game_title', text: '《Game》' },
      { type: 'end', text: '(จบบท)' },
    ],
  });
  assert(html.includes('class="dialogue"'));
  assert(html.includes('class="system-msg"'));
  assert(html.includes('class="game-title"'));
  assert(html.includes('class="end-marker"'));
});

test('renderChapterJson EN brackets', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'en', output_lang: 'en',
    blocks: [
      { type: 'narration', text: 'Story' },
      { type: 'dialogue', text: '\u201cHello\u201d' },
      { type: 'system', text: '[System]' },
      { type: 'end', text: '(End)' },
    ],
  });
  assert(html.includes('\u201cHello\u201d'));
  assert(html.includes('(End)'));
});

test('renderChapterJson JP brackets', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'jp',
    blocks: [
      { type: 'narration', text: '物語' },
      { type: 'dialogue', text: '\u300cこんにちは\u300d' },
      { type: 'end', text: '\uff08終\uff09' },
    ],
  });
  assert(html.includes('class="dialogue"'));
});

test('renderChapterJson KR brackets', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'kr',
    blocks: [
      { type: 'narration', text: '이야기' },
      { type: 'dialogue', text: '\u300c안녕하세요\u300d' },
      { type: 'end', text: '(\uaf43)' },
    ],
  });
  assert(html.includes('class="dialogue"'));
});

test('renderChapterJson missing lang defaults to cn', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T',
    blocks: [
      { type: 'narration', text: 'test' },
      { type: 'end', text: '(\u0e08\u0e1a\u0e1a\u0e17)' },
    ],
  });
  assert(html.includes('<p>test</p>'));
});

// ── Renderer: Edge cases ─────────────────────────────────────────────────

test('renderChapterJson null/missing fields do not crash', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'cn',
    blocks: [
      { type: 'dialogue', text: 'Hi', speaker: null },
      { type: 'end', text: '(\u0e08\u0e1a\u0e1a\u0e17)' },
    ],
  });
  assert(html.includes('class="dialogue"'));
});

test('renderChapterJson empty blocks returns empty string', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'cn', blocks: [],
  });
  assert.equal(html, '');
});

test('renderChapterJson null chapter returns error', () => {
  const html = renderChapterJson(null);
  assert(html.includes('error'));
});

test('renderChapterJson undefined chapter returns error', () => {
  const html = renderChapterJson(undefined);
  assert(html.includes('error'));
});

test('renderChapterJson handles curly bracket conversion', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'cn', output_lang: 'th',
    blocks: [
      { type: 'dialogue', text: '\u300cHello\u300d' },
      { type: 'end', text: '(\u0e08\u0e1a\u0e1a\u0e17)' },
    ],
  });
  assert(html.includes('\u201cHello\u201d'));
});

// ── Renderer: output_lang / profile_lang ──────────────────────────────────

test('renderChapterJson output_lang selects en brackets', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'cn', output_lang: 'en',
    blocks: [
      { type: 'system', text: '[System]' },
      { type: 'end', text: '(End)' },
    ],
  });
  assert(html.includes('(End)'));
  assert(html.includes('data-lang="en"'));
});

test('renderChapterJson profile_lang overrides output_lang', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'cn', output_lang: 'th', profile_lang: 'en',
    blocks: [
      { type: 'system', text: '[System]' },
      { type: 'end', text: '(End)' },
    ],
  });
  assert(html.includes('(End)'));
  assert(html.includes('data-lang="en"'));
});

// ── Validator: output_lang / profile_lang ─────────────────────────────────

test('validateChapterJs passes for correct output_lang', async () => {
  const r = await validateChapterJs('global-descent', 1, 'ตอนที่ 1 T', [
    { type: 'narration', text: 'เล่าเรื่อง' },
    { type: 'dialogue', text: '\u201cHello\u201d' },
    { type: 'end', text: '(End)' },
  ], 'ch 1', 'cn', { output_lang: 'en', novelRoot: '/nonexistent' });
  assert.equal(r.valid, true);
});

test('validateChapterJs warns for wrong output_lang', async () => {
  const r = await validateChapterJs('global-descent', 1, 'ตอนที่ 1 T', [
    { type: 'narration', text: 'เล่าเรื่อง' },
    { type: 'end', text: '(\u0e08\u0e1a\u0e1a\u0e17)' },
  ], 'ch 1', 'cn', { output_lang: 'en', novelRoot: '/nonexistent' });
  const hasEndMarkerWarning = r.warnings.some(w => w.includes('end marker') || w.includes('lang=en'));
  assert(hasEndMarkerWarning, `Expected end marker warning, got warnings: ${JSON.stringify(r.warnings)}`);
});

// ── Integration: Consistency with Python schema ─────────────────────────

test('renderChapterJson outputs correct HTML structure', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'cn',
    output_lang: 'th',
    blocks: [
      { type: 'narration', text: 'A' },
      { type: 'dialogue', text: 'B', speaker: 'C' },
      { type: 'system', text: 'D' },
      { type: 'game_title', text: 'E' },
      { type: 'end', text: '(\u0e08\u0e1a\u0e1a\u0e17)' },
    ],
  });
  assert(html.includes('class="dialogue"'), 'dialogue class');
  assert(html.includes('class="system-msg"'), 'system-msg class');
  assert(html.includes('class="game-title"'), 'game-title class');
  assert(html.includes('class="end-marker"'), 'end-marker class');
  assert(html.includes('data-speaker="C"'), 'speaker attribute');
});

test('renderChapterJson source attribute adds footer', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 Legacy', lang: 'cn',
    source: 'ch 1',
    blocks: [
      { type: 'narration', text: 'Old format still works' },
      { type: 'end', text: '(\u0e08\u0e1a\u0e1a\u0e17)' },
    ],
  });
  assert(html.includes('Old format'));
  assert(html.includes('class="end-marker"'));
  assert(html.includes('class="source-footer"'));
});
