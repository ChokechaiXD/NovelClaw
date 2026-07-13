/**
 * lib/blocks.js — Markdown-to-blocks parser for source chapters
 *
 * Extracted from server.js to avoid circular dependency with chapter-repo.
 */

function parseFrontmatter(mdText) {
  const normalized = String(mdText || '').replace(/\r\n/g, '\n').trim();
  const match = normalized.match(/^---\n([\s\S]*?)\n---(?:\n|$)/);
  if (!match) return { body: normalized, text: '', data: {} };

  const data = {};
  for (const rawLine of match[1].split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const kv = line.match(/^([A-Za-z_][\w-]*):\s*(.*?)\s*$/);
    if (!kv) continue;
    data[kv[1]] = kv[2].replace(/^['"]|['"]$/g, '');
  }

  return {
    body: normalized.slice(match[0].length).trim(),
    text: match[1].trim(),
    data,
  };
}

function extractMarkdownTitle(mdText) {
  const parsed = parseFrontmatter(mdText);
  const titleMatch = parsed.body.match(/^#\s+(.+?)(?:\n|$)/);
  return titleMatch ? titleMatch[1].trim() : '';
}

function parseMarkdownToBlocks(mdText, chapterNum) {
  const leadingMeta = parseFrontmatter(mdText);
  const parts = leadingMeta.body.split(/\n-{3,}\n/);

  let body = '';
  const metaSections = [];
  if (leadingMeta.text) metaSections.push(leadingMeta.text);

  if (parts.length >= 3) {
    const firstPart = parts[0].trim();
    const lines = firstPart.split('\n');
    if (lines.length <= 6) {
      body = parts[1].trim();
      metaSections.push(parts.slice(2).join('\n\n'));
    } else {
      body = parts.slice(0, -1).join('\n\n---\n\n');
      metaSections.push(parts[parts.length - 1]);
    }
  } else if (parts.length === 2) {
    const firstPart = parts[0].trim();
    const lines = firstPart.split('\n');
    if (lines.length <= 6) {
      body = parts[1].trim();
    } else {
      body = parts[0].trim();
      metaSections.push(parts[1].trim());
    }
  } else {
    body = parts[0].trim();
  }

  let title = '';
  const titleMatch = body.match(/^#\s+(.+)/);
  if (titleMatch) {
    title = titleMatch[1].trim();
    body = body.slice(titleMatch[0].length).trim();
  } else {
    const fallbackMatch = leadingMeta.body.match(/^#\s+(.+)/);
    if (fallbackMatch) {
      title = fallbackMatch[1].trim();
    }
  }

  const notes = [];
  const metaText = metaSections.filter(Boolean).join('\n\n');
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

  return { title, blocks, notes, frontmatter: leadingMeta.data };
}

module.exports = { parseMarkdownToBlocks, parseFrontmatter, extractMarkdownTitle };
