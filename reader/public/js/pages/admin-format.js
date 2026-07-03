/* Shared admin formatting helpers for long-running source operations. */

window.AdminFormat = {
  formatImportRepairSummary(slug, repair = {}) {
    const sample = (repair.changes || []).slice(0, 5).map(item => {
      const before = item.titleBefore || '(missing)';
      const after = item.titleAfter || '(unchanged)';
      return '  - ' + item.filename + ': ' + before + ' -> ' + after +
        (item.noiseLinesRemoved ? ' | noise -' + item.noiseLinesRemoved : '');
    });
    return [
      'slug: ' + slug,
      'source files changed: ' + (repair.filesChanged || 0),
      'titles repaired: ' + (repair.titlesRepaired || 0),
      'noise lines removed: ' + (repair.noiseLinesRemoved || 0),
      'titles unchanged: ' + (repair.titlesUnchanged || 0),
      'index rebuild: ' + (repair.indexRebuilt ? 'yes' : 'no'),
      sample.length ? 'sample:' : '',
      ...sample,
    ].filter(Boolean).join('\n');
  },

  formatTocRecoverySummary(slug, data = {}) {
    const sample = (data.sampleChapters || []).slice(0, 8).map(item =>
      '  - ' + item.num + ': ' + (item.title || '(untitled)')
    );
    return [
      'slug: ' + slug,
      'site: ' + (data.site || 'auto'),
      'url: ' + (data.url || '-'),
      'title: ' + (data.title || '-'),
      'chapters found: ' + (data.chapterCount || 0),
      'toc path: ' + (data.tocPath || '-'),
      sample.length ? 'sample:' : '',
      ...sample,
    ].filter(Boolean).join('\n');
  },
};
