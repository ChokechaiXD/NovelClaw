const assert = require('node:assert/strict');
const test = require('node:test');
const { validateChapterJs } = require('../services/validation');

test('validateChapterJs checks output_lang end marker', async () => {
  const result = await validateChapterJs('global-descent', 1, 'ตอนที่ 1 Test', [
    { type: 'narration', text: 'เล่าเรื่อง' },
    { type: 'dialogue', text: '\u201cHello\u201d' },
    { type: 'end', text: '(End)' },
  ], 'source', 'cn', { output_lang: 'en', novelRoot: '/nonexistent' });

  assert.equal(result.valid, true);
  assert.equal(result.warnings.some((warning) => warning.includes('lang=en')), false);
});

test('validateChapterJs warns when output_lang marker does not match', async () => {
  const result = await validateChapterJs('global-descent', 1, 'ตอนที่ 1 Test', [
    { type: 'narration', text: 'เล่าเรื่อง' },
    { type: 'dialogue', text: '\u201cHello\u201d' },
    { type: 'end', text: '(\u0e08\u0e1a\u0e1a\u0e17)' },
  ], 'source', 'cn', { output_lang: 'en', novelRoot: '/nonexistent' });

  assert.equal(result.valid, true);
  assert.equal(result.warnings.some((warning) => warning.includes('lang=en')), true);
});
