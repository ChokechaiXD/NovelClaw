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
