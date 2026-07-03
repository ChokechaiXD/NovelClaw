/* Command helpers for the admin translate workflow. */

(function () {
  function validateRunRequest({ rangeVal = '', requestedNums = [], sourceIssueByNum = {}, forceSource = false } = {}) {
    if (!rangeVal.trim()) {
      return {
        ok: false,
        title: 'ยังไม่ได้ระบุช่วงตอน',
        message: 'กรุณากรอกช่วงตอนที่ต้องการสั่งแปล เช่น 5-10 หรือ 5',
        toast: 'กรุณากรอกช่วงตอนที่ต้องการสั่งแปล',
      };
    }
    if (!requestedNums.length) {
      return {
        ok: false,
        title: 'ช่วงตอนไม่ถูกต้อง',
        message: 'ใช้รูปแบบเช่น 5, 5-10 หรือ 5,8,12-15',
        toast: 'ช่วงตอนไม่ถูกต้อง',
        renderPreview: true,
      };
    }
    const blockingNums = requestedNums.filter(num =>
      sourceIssueByNum[num]?.issues?.some(issue => issue.severity === 'error')
    );
    if (blockingNums.length && !forceSource) {
      const sample = blockingNums.slice(0, 10).join(', ');
      return {
        ok: false,
        title: 'Source ยังไม่พร้อมแปล',
        message: `พบ source error ในตอนที่เลือก ${blockingNums.length} ตอน: ${sample}`,
        toast: 'ตอนที่เลือกมี source error ต้องซ่อมหรือกด force ก่อนแปล',
        blockingNums,
      };
    }
    return { ok: true, blockingNums };
  }

  function markQueued(resultByNum = {}, nums = []) {
    for (const num of nums) {
      resultByNum[num] = { status: 'queued', reason: 'queued' };
    }
    return resultByNum;
  }

  function buildRunOptions({ forceSource = false, promptProfile = 'faithful_default', modelOverride = '', providerByModel = {} } = {}) {
    const options = { force: forceSource, promptProfile };
    if (modelOverride) {
      options.model = modelOverride;
      if (providerByModel[modelOverride]) options.provider = providerByModel[modelOverride];
    }
    return options;
  }

  function applyFailedResults({ err = {}, requestedNums = [], resultByNum = {} } = {}) {
    const failedSummary = err.details?.summary || err.payload?.error?.details?.summary || {};
    const failedChapters = failedSummary.chapters || err.details?.chapters || [];
    for (const ch of failedChapters) {
      const num = parseInt(ch.ch || ch.num, 10);
      if (Number.isFinite(num)) resultByNum[num] = ch;
    }
    if (!failedChapters.length) {
      for (const num of requestedNums) {
        resultByNum[num] = { status: 'failed', reason: err.message };
      }
    }
    return { failedSummary, failedChapters };
  }

  function deleteConfirmation({ nums = [], selectedCount = 0, range = '' } = {}) {
    const skipped = selectedCount - nums.length;
    const displayRange = range.length > 180 ? range.slice(0, 180) + '...' : range;
    const note = skipped > 0 ? `\nข้าม ${skipped} ตอนที่ยังไม่มีไฟล์แปลไทย` : '';
    return {
      skipped,
      displayRange,
      note,
      message: `ลบไฟล์แปลไทย (.th.json) ${nums.length} ตอน?\n\nตอน: ${displayRange}${note}\n\nSource/ไฟล์ต้นฉบับจะไม่ถูกลบ และสามารถกดแปลใหม่ได้ทันที`,
    };
  }

  window.AdminTranslateCommand = {
    validateRunRequest,
    markQueued,
    buildRunOptions,
    applyFailedResults,
    deleteConfirmation,
  };
})();
