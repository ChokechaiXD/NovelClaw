/**
 * lib/blocks.js — Markdown-to-blocks parser for legacy .md chapters
 *
 * Extracted from server.js to avoid circular dependency with chapter-repo.
 */

function parseMarkdownToBlocks(mdText, chapterNum) {
  const normalized = mdText.replace(/\r\n/g, '\n').trim();
  const parts = normalized.split(/\n-{3,}\n/);

  let body = '';
  let metaText = '';

  if (parts.length >= 3) {
    const firstPart = parts[0].trim();
    const lines = firstPart.split('\n');
    if (lines.length <= 6) {
      body = parts[1].trim();
      metaText = parts.slice(2).join('\n\n');
    } else {
      body = parts.slice(0, -1).join('\n\n---\n\n');
      metaText = parts[parts.length - 1];
    }
  } else if (parts.length === 2) {
    const firstPart = parts[0].trim();
    const lines = firstPart.split('\n');
    if (lines.length <= 6) {
      body = parts[1].trim();
      metaText = '';
    } else {
      body = parts[0].trim();
      metaText = parts[1].trim();
    }
  } else {
    body = parts[0].trim();
    metaText = '';
  }

  let title = '';
  const titleMatch = body.match(/^#\s+(.+)/);
  if (titleMatch) {
    title = titleMatch[1].trim();
    body = body.slice(titleMatch[0].length).trim();
  } else {
    const fallbackMatch = parts[0].trim().match(/^#\s+(.+)/);
    if (fallbackMatch) {
      title = fallbackMatch[1].trim();
    }
  }

  const notes = [];
  if (metaText) {
    for (const line of metaText.split('\n')) {
      const trimmed = line.trim();
      if (trimmed.startsWith('- ')) {
        notes.push(trimmed.slice(2));
      }
    }
  }

  const paragraphs = body.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
  const blocks = [];

  for (const p of paragraphs) {
    if (p === '(จบบท)' || p === '（終）' || p === '(끝)' || p === '(End)') {
      blocks.push({ type: 'end', text: p });
      continue;
    }

    if (p.startsWith('【') && p.endsWith('】')) {
      blocks.push({ type: 'system', text: p });
    } else if (p.startsWith('「') && p.endsWith('」')) {
      blocks.push({ type: 'dialogue', text: p, speaker: '' });
    } else if (p.startsWith('"') && p.endsWith('"') || p.startsWith('\u201C') && p.endsWith('\u201D')) {
      blocks.push({ type: 'dialogue', text: p, speaker: '' });
    } else if (p.startsWith('《') && p.endsWith('》')) {
      blocks.push({ type: 'game_title', text: p });
    } else {
      const speakerRegex = /^([^「」""\u201C\u201D:\n]+)(?:พูด|กล่าว|ถาม|ตะโกน|บอก|:|\s)+([「""\u201C\u201D][^「」""\u201C\u201D]+[」""\u201C\u201D])$/;
      const dialogueMatch = p.match(speakerRegex);
      if (dialogueMatch) {
        blocks.push({
          type: 'dialogue',
          text: dialogueMatch[2],
          speaker: dialogueMatch[1].trim()
        });
      } else {
        blocks.push({ type: 'narration', text: p });
      }
    }
  }

  if (!blocks.some(b => b.type === 'end')) {
    blocks.push({ type: 'end', text: '(จบบท)' });
  }

  return { title, blocks, notes };
}

module.exports = { parseMarkdownToBlocks };
