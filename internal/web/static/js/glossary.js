import { escapeHTML } from './utils.js';

export function createGlossaryController({
  state, el, api, showToast, openModal, closeModal,
}) {
  async function openGlossary() {
    if (!state.currentSlug) return;
    openModal(el.modalGlossary);
    el.discStatus.textContent = '';
    try {
      const res = await api(`/api/novels/${state.currentSlug}/glossary`);
      state.glossaryTerms = res.terms || [];
      renderGlossaryTable();
    } catch (err) {
      console.error('load glossary failed', err);
    }
  }

  function renderGlossaryTable() {
    if (!state.glossaryTerms.length) {
      el.glossaryTbody.innerHTML = '<tr><td colspan="4" class="table-empty">ยังไม่มีคำศัพท์</td></tr>';
      return;
    }
    el.glossaryTbody.innerHTML = state.glossaryTerms.map((term, index) => `
      <tr class="glossary-row">
        <td>${escapeHTML(term.term)}</td>
        <td>${escapeHTML(term.target)}</td>
        <td class="muted-cell">${escapeHTML(term.category || '')}</td>
        <td class="glossary-actions">
          <button type="button" class="btn btn-outline btn-sm btn-remove-term" data-idx="${index}">✕</button>
        </td>
      </tr>`).join('');
  }

  async function discoverGlossary() {
    if (!state.currentSlug) return;
    const start = Number.parseInt(el.discStart.value, 10) || 1;
    const end = Number.parseInt(el.discEnd.value, 10) || start;
    const model = el.transModelSelect.value || state.defaultModel;
    el.discStatus.textContent = '⏳ กำลังสแกนชื่อตัวละคร...';
    try {
      const res = await api(`/api/novels/${state.currentSlug}/glossary/discover`, {
        method: 'POST',
        body: JSON.stringify({ novelSlug: state.currentSlug, startChapter: start, endChapter: end, model }),
      });
      const count = res.discovered?.length || 0;
      state.glossaryTerms = res.glossary?.terms || [];
      renderGlossaryTable();
      el.discStatus.textContent = `✅ พบศัพท์ใหม่ ${count} คำ — ตรวจรายการแล้วกด "บันทึก Glossary" เพื่อเก็บถาวร`;
      showToast(`สแกนพบศัพท์ใหม่ ${count} คำ (ยังไม่บันทึก — ตรวจรายการก่อน)`, 'info');
    } catch (err) {
      el.discStatus.textContent = '❌ สแกนล้มเหลว';
      showToast(`การสแกนศัพท์ล้มเหลว: ${err.message}`, 'error');
    }
  }

  function addManualTerm(event) {
    event.preventDefault();
    const term = el.termOrig?.value.trim() || '';
    const target = el.termTarget?.value.trim() || '';
    const category = el.termCategory?.value || '';
    if (!term || !target) return;
    state.glossaryTerms.push({ term, target, category });
    renderGlossaryTable();
    el.termOrig.value = '';
    el.termTarget.value = '';
  }
  async function saveGlossary() {
    if (!state.currentSlug) return;
    try {
      await api(`/api/novels/${state.currentSlug}/glossary`, {
        method: 'POST',
        body: JSON.stringify({ novelSlug: state.currentSlug, terms: state.glossaryTerms }),
      });
      showToast('บันทึก Glossary เรียบร้อยแล้ว', 'success');
      closeModal(el.modalGlossary);
    } catch (err) {
      console.error('save glossary failed', err);
    }
  }

  function renderGlossaryQA(res) {
    const issues = res.issues || [];
    if (!issues.length) {
      el.glossaryQaResults.innerHTML = `<div class="glossary-qa-ok">✅ ตรวจ ${res.scanned} ตอน — ศัพท์สอดคล้องทั้งหมด</div>`;
      return;
    }
    const byChapter = new Map();
    for (const issue of issues) {
      if (!byChapter.has(issue.chapterNo)) byChapter.set(issue.chapterNo, []);
      byChapter.get(issue.chapterNo).push(issue);
    }
    el.glossaryQaResults.innerHTML = `
      <div class="glossary-qa-warning">⚠️ พบ ${issues.length} จุดใน ${byChapter.size} ตอน (สแกน ${res.scanned} ตอน)</div>` +
      Array.from(byChapter.entries()).map(([chapterNo, list]) => `
        <div class="glossary-qa-row">
          <span class="glossary-qa-chapter">ตอนที่ ${chapterNo}</span>
          <span class="glossary-qa-terms">
            ${list.map(issue => `${escapeHTML(issue.term)} → ${escapeHTML(issue.expected)}`).join(', ')}
          </span>
          <button type="button" class="btn btn-outline btn-sm btn-qa-repair" data-ch="${chapterNo}">🔧 ซ่อม</button>
        </div>`).join('');
  }

  async function runGlossaryQA() {
    if (!state.currentSlug) return;
    const start = Number.parseInt(el.qaStart?.value, 10) || 1;
    const end = Number.parseInt(el.qaEnd?.value, 10) || start;
    el.btnGlossaryCheck.disabled = true;
    el.btnGlossaryCheck.textContent = '⏳ กำลังตรวจ...';
    try {
      const res = await api(`/api/novels/${state.currentSlug}/glossary/check?start=${start}&end=${end}`);
      renderGlossaryQA(res);
      el.glossaryQaResults.style.display = 'block';
    } catch (err) {
      showToast(`การตรวจสอบล้มเหลว: ${err.message}`, 'error');
    } finally {
      el.btnGlossaryCheck.disabled = false;
      el.btnGlossaryCheck.textContent = '🔍 ตรวจสอบ';
    }
  }

  async function repairChapter(button) {
    if (!state.currentSlug || !button?.dataset.ch) return;
    const chapterNo = button.dataset.ch;
    button.disabled = true;
    button.textContent = '⏳';
    try {
      await api(`/api/novels/${state.currentSlug}/chapters/${chapterNo}/repair`, { method: 'POST' });
      showToast(`ซ่อมตอนที่ ${chapterNo} เรียบร้อย`, 'success');
      button.textContent = '✅';
    } catch (err) {
      showToast(`ซ่อมตอนที่ ${chapterNo} ล้มเหลว: ${err.message}`, 'error');
      button.textContent = '❌';
      button.disabled = false;
    }
  }
  function bindGlossaryEvents() {
    el.btnOpenGlossary?.addEventListener('click', openGlossary);
    el.btnCloseGlossary?.addEventListener('click', () => closeModal(el.modalGlossary));
    el.btnRunDiscovery?.addEventListener('click', discoverGlossary);
    el.formAddTerm?.addEventListener('submit', addManualTerm);
    el.btnSaveGlossary?.addEventListener('click', saveGlossary);
    el.btnGlossaryCheck?.addEventListener('click', runGlossaryQA);
    el.glossaryTbody?.addEventListener('click', event => {
      const button = event.target.closest('.btn-remove-term');
      if (!button) return;
      const index = Number.parseInt(button.dataset.idx, 10);
      if (Number.isInteger(index) && index >= 0) {
        state.glossaryTerms.splice(index, 1);
        renderGlossaryTable();
      }
    });
    el.glossaryQaResults?.addEventListener('click', event => {
      const button = event.target.closest('.btn-qa-repair');
      if (button) repairChapter(button);
    });
  }

  return { bindGlossaryEvents, openGlossary, renderGlossaryTable };
}
