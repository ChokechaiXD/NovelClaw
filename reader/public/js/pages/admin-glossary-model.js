/* Data helpers for the admin glossary workflow. */

window.AdminGlossaryModel = {
  resolveSlug(novels = [], currentSlug = '', requestedSlug = '') {
    if (requestedSlug && novels.some(n => n.slug === requestedSlug)) return requestedSlug;
    if (currentSlug && novels.some(n => n.slug === currentSlug)) return currentSlug;
    const firstReal = novels.find(n =>
      !n.slug?.startsWith('test-') &&
      !n.slug?.startsWith('fixture-') &&
      !n.slug?.startsWith('tmp-')
    );
    return firstReal?.slug || novels[0]?.slug || '';
  },

  stats(terms = []) {
    return {
      total: terms.length,
      verified: terms.filter(t => t.verified !== false).length,
      locked: terms.filter(t => t.lock === 'locked').length,
      needsReview: terms.filter(t => t.verified === false).length,
    };
  },

  verificationState(term = {}) {
    const verified = term.verified !== false;
    return {
      verified,
      label: verified ? 'ยืนยันแล้ว' : 'รอตรวจ',
      badgeClass: verified ? 'c-badge--teal' : 'c-badge--amber',
    };
  },

  lockBadgeClass(lock = 'auto') {
    if (lock === 'locked') return 'c-badge--teal';
    if (lock === 'reference') return 'c-badge--purple';
    return 'c-badge--gray';
  },

  validateInput({ source = '', thai = '', terms = [], editingIndex = -1 } = {}) {
    if (!source || !thai) {
      return { ok: false, message: 'กรุณากรอกทั้งคำศัพท์เดิม (จีน) และคำแปล (ไทย)' };
    }
    const duplicateIndex = terms.findIndex(t => t.source === source);
    if (editingIndex === -1 && duplicateIndex !== -1) {
      return { ok: false, message: 'คำศัพท์ "' + source + '" มีอยู่แล้วในคลังศัพท์' };
    }
    if (editingIndex !== -1 && duplicateIndex !== -1 && duplicateIndex !== editingIndex) {
      return { ok: false, message: 'คำศัพท์ "' + source + '" มีอยู่แล้วในคลังศัพท์' };
    }
    return { ok: true };
  },

  termFromInput({ source = '', thai = '', category = 'คำศัพท์', lock = 'auto', existing = null } = {}) {
    return {
      ...(existing || {}),
      source,
      thai,
      category,
      priority: existing?.priority || 3,
      lock,
      explanation: existing?.explanation || '',
      notes: existing?.notes || '',
      verified: true,
    };
  },
};
