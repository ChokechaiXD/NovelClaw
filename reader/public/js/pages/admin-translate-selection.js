/* Selection helpers for the admin translate chapter table. */

(function () {
  const Model = window.AdminTranslateModel;

  function visibleChapters({ chapters = [], sourceIssueByNum = {}, lastResultByNum = {}, filterState = 'all', searchQuery = '' } = {}) {
    return chapters.filter(ch => {
      const resultIssue = lastResultByNum[ch.num];
      const sourceIssue = sourceIssueByNum[ch.num];
      const status = Model.chapterStatus(ch, sourceIssue, resultIssue);
      return Model.chapterMatches(ch, status, sourceIssue, resultIssue, filterState, searchQuery);
    });
  }

  function matchingNums({ chapters = [], sourceIssueByNum = {}, lastResultByNum = {}, filterState = 'all', searchQuery = '', predicate = null } = {}) {
    const nums = [];
    for (const ch of visibleChapters({ chapters, sourceIssueByNum, lastResultByNum, filterState, searchQuery })) {
      const status = Model.chapterStatus(ch, sourceIssueByNum[ch.num], lastResultByNum[ch.num]);
      if (!predicate || predicate(status, ch)) nums.push(ch.num);
    }
    return nums;
  }

  function selectedTranslatedNums({ chapters = [], selectedNums = new Set() } = {}) {
    const selected = selectedNums instanceof Set ? selectedNums : new Set(selectedNums || []);
    return [...selected]
      .map(num => chapters.find(ch => ch.num === num))
      .filter(ch => ch && (ch.hasTh || ch.isTranslated || ch.status === 'translated'))
      .map(ch => ch.num)
      .sort((a, b) => a - b);
  }

  function nextUntranslatedAfterProgress({ chapters = [], sourceIssueByNum = {}, lastResultByNum = {}, limit = 20 } = {}) {
    const lastTranslated = chapters.reduce((max, ch) => {
      const status = Model.chapterStatus(ch, sourceIssueByNum[ch.num], lastResultByNum[ch.num]);
      return status === 'translated' ? Math.max(max, ch.num) : max;
    }, 0);
    return chapters
      .filter(ch => ch.num > lastTranslated)
      .filter(ch => Model.chapterStatus(ch, sourceIssueByNum[ch.num], lastResultByNum[ch.num]) === 'untranslated')
      .slice(0, limit)
      .map(ch => ch.num);
  }

  window.AdminTranslateSelection = {
    visibleChapters,
    matchingNums,
    selectedTranslatedNums,
    nextUntranslatedAfterProgress,
  };
})();
