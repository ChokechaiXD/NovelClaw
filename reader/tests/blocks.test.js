const test = require('node:test');
const assert = require('node:assert/strict');

const { extractMarkdownTitle, parseFrontmatter, parseMarkdownToBlocks } = require('../lib/blocks');

test('source markdown frontmatter is stripped before title and blocks parsing', () => {
  const markdown = `---
source_url: "https://www.royalroad.com/fiction/103742/example/chapter/1"
source_site: "royalroad"
source_lang: "en"
---
# Prologue - The End of Eternity

The first paragraph.

The second paragraph.`;

  const parsed = parseMarkdownToBlocks(markdown, 1);

  assert.equal(extractMarkdownTitle(markdown), 'Prologue - The End of Eternity');
  assert.equal(parsed.frontmatter.source_lang, 'en');
  assert.equal(parsed.title, 'Prologue - The End of Eternity');
  assert.deepEqual(
    parsed.blocks.filter((block) => block.type !== 'end').map((block) => block.text),
    ['The first paragraph.', 'The second paragraph.'],
  );
});

test('parseFrontmatter returns body unchanged when markdown has no frontmatter', () => {
  const parsed = parseFrontmatter('# Chapter\n\nBody');

  assert.equal(parsed.body, '# Chapter\n\nBody');
  assert.deepEqual(parsed.data, {});
});
