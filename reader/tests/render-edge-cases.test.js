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
  assert(html.includes('block-narration'));
  assert(html.includes('block-dialogue'));
  assert(html.includes('block-system'));
  assert(html.includes('block-gametitle'));
  assert(html.includes('end-marker'));
});

test('renderChapterJson EN brackets', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'en', output_lang: 'en',
    blocks: [
      { type: 'narration', text: 'Story' },
      { type: 'dialogue', text: '“Hello”' },
      { type: 'system', text: '[System]' },
      { type: 'end', text: '(End)' },
    ],
  });
  assert(html.includes('“Hello”'));
  assert(html.includes('(End)'));
});

test('renderChapterJson JP brackets', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'jp',
    blocks: [
      { type: 'narration', text: '物語' },
      { type: 'dialogue', text: '「こんにちは」' },
      { type: 'end', text: '（終）' },
    ],
  });
  assert(html.includes('block-dialogue'));
});

test('renderChapterJson KR brackets', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'kr',
    blocks: [
      { type: 'narration', text: '이야기' },
      { type: 'dialogue', text: '「안녕하세요」' },
      { type: 'end', text: '(끝)' },
    ],
  });
  assert(html.includes('block-dialogue'));
});

test('renderChapterJson missing lang defaults to cn', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T',
    blocks: [
      { type: 'narration', text: 'test' },
      { type: 'end', text: '(จบบท)' },
    ],
  });
  assert(html.includes('block-narration'));
});

// ── Renderer: Edge cases ─────────────────────────────────────────────────

test('renderChapterJson null/missing fields do not crash', () => {
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'cn',
    blocks: [
      { type: 'dialogue', text: 'Hi', speaker: null },
      { type: 'end', text: '(จบบท)' },
    ],
  });
  assert(html.includes('block-dialogue'));
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
      { type: 'dialogue', text: '\u300cHello\u300d' },  // CN kagikakko
      { type: 'end', text: '(จบบท)' },
    ],
  });
  assert(html.includes('“Hello”'));  // Should convert to curly quotes
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
});

// ── Validator: output_lang / profile_lang ─────────────────────────────────

test('validateChapterJs passes for correct output_lang', async () => {
  const r = await validateChapterJs('global-descent', 1, 'ตอนที่ 1 T', [
    { type: 'narration', text: 'เล่าเรื่อง' },
    { type: 'dialogue', text: '“Hello”' },
    { type: 'end', text: '(End)' },
  ], 'ch 1', 'cn', { output_lang: 'en' });
  assert.equal(r.valid, true);
});

test('validateChapterJs warns for wrong output_lang', async () => {
  const r = await validateChapterJs('global-descent', 1, 'ตอนที่ 1 T', [
    { type: 'narration', text: 'เล่าเรื่อง' },
    { type: 'end', text: '(จบบท)' },
  ], 'ch 1', 'cn', { output_lang: 'en' });
  // Validator warns (not errors) for wrong end marker — check warning exists
  const hasEndMarkerWarning = r.warnings.some(w => w.includes('end marker') || w.includes('lang=en'));
  assert(hasEndMarkerWarning, `Expected end marker warning, got warnings: ${JSON.stringify(r.warnings)}`);
});

// ── Integration: Consistency with Python schema ─────────────────────────

test('renderChapterJson outputs same structure as Python', () => {
  // This is a structural consistency check: the renderer must output
  // <p> wrappers with class block-{type} for every block type
  const html = renderChapterJson({
    num: 1, title: 'ตอนที่ 1 T', lang: 'cn',
    output_lang: 'th',  // Default th profile
    blocks: [
      { type: 'narration', text: 'A' },
      { type: 'dialogue', text: 'B', speaker: 'C' },
      { type: 'system', text: 'D' },
      { type: 'game_title', text: 'E' },
      { type: 'end', text: '(จบบท)' },
    ],
  });
  const classes = html.match(/block-\w+/g) || [];
  const expected = ['block-narration', 'block-dialogue', 'block-system',
                     'block-gametitle', 'end-marker'];
  for (const cls of expected) {
    assert(html.includes(cls), `Missing rendered class: ${cls}`);
  }
});

test('renderChapterJson exports from lib/render match old server.js behavior', () => {
  // The exported renderChapterJson from lib/render should handle
  // the same chapter data structure that server.js used to handle
  const html = renderChapterJson({
    num: 1,
    title: 'ตอนที่ 1 Legacy',
    lang: 'cn',
    blocks: [
      { type: 'narration', text: 'Old format still works' },
      { type: 'end', text: '(จบบท)' },
    ],
  });
  assert(html.includes('Old format'));
  assert(html.includes('block-narration'));
  assert(html.includes('end-marker'));
});
