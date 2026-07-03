/* Translation queue model helpers for the admin translate page. */

(function () {
  const statusBadges = {
    translated: ['แปลแล้ว', 'c-badge c-badge--teal'],
    untranslated: ['ยังไม่แปล', 'c-badge c-badge--gray'],
    needs_review: ['ควรดู', 'c-badge c-badge--amber'],
    failed: ['ล้มเหลว', 'c-badge c-badge--red'],
    source_not_ready: ['source error', 'c-badge c-badge--red'],
    queued: ['รอแปล', 'c-badge c-badge--gray'],
    running: ['กำลังแปล', 'c-badge c-badge--amber'],
  };

  function rangeFromNums(nums = []) {
    const sorted = [...new Set(nums.map(n => parseInt(n, 10)).filter(Number.isFinite))].sort((a, b) => a - b);
    const ranges = [];
    for (let i = 0; i < sorted.length; i++) {
      const start = sorted[i];
      let end = start;
      while (i + 1 < sorted.length && sorted[i + 1] === end + 1) {
        end = sorted[++i];
      }
      ranges.push(start === end ? String(start) : `${start}-${end}`);
    }
    return ranges.join(',');
  }

  function numsFromRange(range = '') {
    const nums = new Set();
    for (const part of String(range).split(',')) {
      const token = part.trim();
      if (!token) continue;
      const match = token.match(/^(\d+)(?:\s*-\s*(\d+))?$/);
      if (!match) continue;
      const start = parseInt(match[1], 10);
      const end = parseInt(match[2] || match[1], 10);
      if (!Number.isFinite(start) || !Number.isFinite(end)) continue;
      const lo = Math.max(1, Math.min(start, end));
      const hi = Math.max(start, end);
      for (let n = lo; n <= hi && nums.size < 5000; n++) nums.add(n);
    }
    return [...nums].sort((a, b) => a - b);
  }

  function chapterStatus(ch = {}, sourceIssue = null, resultIssue = null) {
    const resultStatus = resultIssue?.status;
    if (resultStatus === 'ok') return 'translated';
    if (resultStatus === 'queued' || resultStatus === 'running') return resultStatus;
    if (resultStatus && resultStatus !== 'ok') return resultStatus === 'failed' ? 'failed' : 'needs_review';
    if (ch.workflowStatus) return ch.workflowStatus;
    const blockingIssue = sourceIssue?.issues?.some(issue => issue.severity === 'error');
    if (blockingIssue) return 'source_not_ready';
    const quality = ch.qualityRecord || ch.quality;
    if (quality && quality.passed === false) return 'needs_review';
    if (ch.isTranslated || ch.status === 'translated') return 'translated';
    return 'untranslated';
  }

  function statusBadge(status) {
    return statusBadges[status] || [status || '-', 'c-badge c-badge--gray'];
  }

  function modelCatalogSummary(cfg = {}) {
    const providers = cfg.providers || [];
    const modelCount = providers.reduce((sum, provider) => sum + ((provider.models || []).length), 0);
    const liveCount = providers.filter(provider => provider.modelSource === 'live' || provider.model_source === 'live').length;
    const fallbackCount = providers.filter(provider => provider.modelError || provider.model_error).length;
    const source = liveCount ? `${liveCount} live provider` : 'static fallback';
    return `${modelCount} models · ${source}${fallbackCount ? ` · ${fallbackCount} fallback` : ''}`;
  }

  function modelLabel(provider = {}, model = {}) {
    const parts = [provider.label || provider.id, model.label || model.id];
    const tags = [model.tier, provider.modelSource || provider.model_source].filter(Boolean);
    return parts.filter(Boolean).join(' · ') + (tags.length ? ' · ' + tags.join(' · ') : '');
  }

  function qualityText(ch = {}, resultIssue = null) {
    const quality = ch.qualityRecord || ch.quality || {};
    const hardFailures = resultIssue?.hardFailures || quality.hardFailures || [];
    const warnings = resultIssue?.warnings || quality.warnings || [];
    const score = resultIssue?.score ?? quality.score ?? ch.score;
    const parts = [];
    if (score !== null && score !== undefined) parts.push(`score ${score}`);
    if (quality.lengthRatio) parts.push(`len ${Math.round(quality.lengthRatio * 100)}%`);
    if (hardFailures.length) parts.push(hardFailures.slice(0, 2).join(', '));
    else if (warnings.length) parts.push('warn: ' + warnings.slice(0, 2).join(', '));
    return parts.join(' · ') || '-';
  }

  function chapterMatches(ch = {}, status = '', sourceIssue = null, resultIssue = null, filter = 'all', query = '') {
    if (filter !== 'all') {
      const wanted = filter === 'review' ? ['needs_review', 'failed'] : [filter];
      if (!wanted.includes(status)) return false;
    }
    const q = query.trim().toLowerCase();
    if (!q) return true;
    const workflowText = (ch.workflowReasons || []).join(' ');
    const issueText = (resultIssue?.reason
      || workflowText
      || (sourceIssue?.issues || []).map(issue => issue.code).join(' ')).toLowerCase();
    return String(ch.num).includes(q)
      || String(ch.title || '').toLowerCase().includes(q)
      || String(ch.model || '').toLowerCase().includes(q)
      || issueText.includes(q);
  }

  function queuePreview(chapters = [], sourceIssueByNum = {}, resultByNum = {}, nums = [], force = false) {
    const wanted = new Set(nums);
    const counts = { total: 0, ready: 0, translated: 0, untranslated: 0, review: 0, sourceBlocked: 0, forced: 0 };
    for (const ch of chapters) {
      if (wanted.size && !wanted.has(ch.num)) continue;
      const sourceIssue = sourceIssueByNum[ch.num];
      const status = chapterStatus(ch, sourceIssue, resultByNum[ch.num]);
      counts.total += 1;
      if (status === 'translated') counts.translated += 1;
      if (status === 'untranslated') counts.untranslated += 1;
      if (status === 'needs_review' || status === 'failed') counts.review += 1;
      if (status === 'source_not_ready') counts.sourceBlocked += 1;
      if (status !== 'source_not_ready' || force) counts.ready += 1;
      if (status === 'source_not_ready' && force) counts.forced += 1;
    }
    const warnings = [];
    if (counts.total > 250) warnings.push('batch ใหญ่มาก ควรแบ่งเป็นช่วงย่อยถ้าต้องการติดตามง่าย');
    if (counts.sourceBlocked && !force) warnings.push('มี source error ในช่วงนี้ ต้องซ่อมหรือ force ก่อนแปล');
    if (counts.forced) warnings.push('force จะข้าม source gate เฉพาะตอนที่เลือก');
    return { counts, warnings };
  }

  window.AdminTranslateModel = {
    rangeFromNums,
    numsFromRange,
    chapterStatus,
    statusBadge,
    modelCatalogSummary,
    modelLabel,
    qualityText,
    chapterMatches,
    queuePreview,
  };
})();
