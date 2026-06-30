function parseTranslateJsonOutput(stdout) {
  const results = [];
  for (const line of String(stdout || '').split(/\r?\n/)) {
    const text = line.trim();
    if (!text || !text.startsWith('{')) continue;
    try { results.push(JSON.parse(text)); } catch {}
  }
  return results;
}

function parseBatchTranslateSummary(stdout) {
  const text = String(stdout || '');
  const chapters = parseTranslateJsonOutput(text);
  if (chapters.length) {
    const passed = chapters.filter(ch => ch.status === 'ok').length;
    const failed = chapters.filter(ch => ch.status === 'failed' || ch.status === 'needs_review').length;
    return {
      passed,
      failed,
      total: chapters.length,
      chapters: chapters.map(ch => ({
        ch: ch.ch,
        status: ch.status,
        score: ch.quality?.score ?? ch.score ?? null,
        reason: ch.reason || '',
        hardFailures: ch.quality?.hardFailures || ch.score?.hardFailures || [],
        warnings: ch.quality?.warnings || [],
      })),
    };
  }
  const summary = text.match(/(\d+)\s+ผ่าน,\s+(\d+)\s+ล้มเหลว\s+จาก\s+(\d+)\s+ตอน/);
  if (summary) {
    return {
      passed: parseInt(summary[1], 10) || 0,
      failed: parseInt(summary[2], 10) || 0,
      total: parseInt(summary[3], 10) || 0,
    };
  }
  const failed = (text.match(/❌|FAILED:/g) || []).length;
  const passed = (text.match(/✅/g) || []).length;
  return { passed, failed, total: passed + failed };
}

module.exports = {
  parseTranslateJsonOutput,
  parseBatchTranslateSummary,
};
