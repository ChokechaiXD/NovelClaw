export function createExportController({
  state, el, showToast, openModal, closeModal, maxChapterNo,
}) {
  function openExportModal() {
    if (!state.currentSlug) return;
    openModal(el.modalExport);
    el.exportStart.value = 1;
    el.exportEnd.value = maxChapterNo();
  }

  function doExport() {
    if (!state.currentSlug) return;
    const format = el.exportFormat.value;
    const start = el.exportStart.value || 1;
    const end = el.exportEnd.value || maxChapterNo();
    const params = new URLSearchParams({ format, start, end });
    window.open(`/api/novels/${encodeURIComponent(state.currentSlug)}/export?${params}`, '_blank', 'noopener');
    closeModal(el.modalExport);
    showToast('เริ่มดาวน์โหลดไฟล์ E-Book เรียบร้อยแล้ว', 'success');
  }

  function bindExportEvents() {
    el.btnOpenExport?.addEventListener('click', openExportModal);
    el.btnCloseExport?.addEventListener('click', () => closeModal(el.modalExport));
    el.btnDoExport?.addEventListener('click', doExport);
  }

  return { bindExportEvents, openExportModal, doExport };
}
