/* Shared admin UI helpers for status, console, and button states. */

window.AdminUi = {
  consoleBadges: {
    running: ['กำลังทำงาน', 'c-badge c-badge--amber'],
    success: ['สำเร็จ', 'c-badge c-badge--teal'],
    error: ['ขัดข้อง', 'c-badge c-badge--red'],
    idle: ['พร้อมใช้งาน', 'c-badge c-badge--gray'],
  },

  setConsole(prefix, state, title, message) {
    const consoleCard = document.getElementById(`${prefix}-console-card`);
    const consoleTitle = document.getElementById(`${prefix}-console-title`);
    const consoleBadge = document.getElementById(`${prefix}-console-badge`);
    const consoleOutput = document.getElementById(`${prefix}-console-output`);
    const badge = this.consoleBadges[state] || this.consoleBadges.idle;

    if (consoleCard) consoleCard.hidden = false;
    if (consoleTitle) consoleTitle.textContent = title || '';
    if (consoleBadge) {
      consoleBadge.textContent = badge[0];
      consoleBadge.className = badge[1];
    }
    if (consoleOutput) {
      consoleOutput.textContent = message || '';
    }
  },

  setStatus(id, baseClass, message, type = 'success') {
    const statusEl = document.getElementById(id);
    if (!statusEl) return;
    statusEl.textContent = message || '';
    statusEl.className = `${baseClass} ${baseClass}--${type}`;
  },

  setButton(btn, icon, label) {
    if (!btn) return;
    btn.innerHTML = (icon ? Ui.icon(icon, 'xs') : '') + '<span>' + Ui.esc(label || '') + '</span>';
  },
};
