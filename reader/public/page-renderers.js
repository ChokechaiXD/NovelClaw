/* ═══════════════════════════════════════════════════════════
   NovelClaw Page Renderers v2.0
   Wires Router pages to API-driven content
   ═══════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────────
  let novelsCache = null;
  let chaptersCache = {};

  // ── HTML Escaping ──────────────────────────────────────────────────────
  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ── Helpers ────────────────────────────────────────────────────────────
  async function api(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }

  function $(id) { return document.getElementById(id); }

  // ── UI State Helpers (Skeleton / Empty / Error) ──────────────────────────
  function showSkeleton(container, type) {
    if (typeof container === 'string') container = $(container);
    if (!container) return;
    if (type === 'card') {
      container.innerHTML = '<div class="skel skel-card" style="margin-bottom:16px;"></div>'.repeat(3);
    } else if (type === 'list') {
      container.innerHTML = '<div class="skel skel-line"></div>'.repeat(6);
    } else if (type === 'detail') {
      container.innerHTML = '<div class="skel skel-block" style="margin-bottom:24px;"></div><div class="skel skel-line"></div><div class="skel skel-line"></div><div class="skel skel-line" style="width:45%;"></div>';
    } else {
      container.innerHTML = '<div class="skel skel-block" style="margin-bottom:16px;"></div><div class="skel skel-line"></div><div class="skel skel-line"></div><div class="skel skel-line" style="width:55%;"></div>';
    }
  }

  function showEmpty(container, title, desc) {
    if (typeof container === 'string') container = $(container);
    if (!container) return;
    container.innerHTML = '<div class="empty-state"><svg><use xlink:href="#mascot-crab-reading"/></svg><div class="empty-state-title">' + (title || 'ยังไม่มีข้อมูล') + '</div><div class="empty-state-desc">' + (desc || '') + '</div></div>';
  }

  function showError(container, title, desc) {
    if (typeof container === 'string') container = $(container);
    if (!container) return;
    container.innerHTML = '<div class="error-state"><svg><use xlink:href="#mascot-crab-excited"/></svg><div class="error-state-title">' + (title || 'เกิดข้อผิดพลาด') + '</div><div class="error-state-desc">' + (desc || '') + '</div><button class="error-state-retry" onclick="location.reload()">ลองอีกครั้ง</button></div>';
  }

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k.startsWith("on") && typeof v === "function")
        node.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === "dataset") Object.assign(node.dataset, v);
      else if (["selected", "checked", "disabled", "readonly", "required"].includes(k.toLowerCase())) {
        if (v) { node.setAttribute(k, ""); node[k] = true; }
        else { node.removeAttribute(k); node[k] = false; }
      } else node.setAttribute(k, v);
    }
    for (const c of children.flat()) {
      if (c == null) continue;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return node;
  }

  function slugToHue(slug) {
    return slug.split("").reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
  }

  const statusMap = { ongoing: "กำลังแปล", complete: "จบแล้ว", in_progress: "กำลังแปล" };

  const STORAGE_KEY = "novelclaw-reader-v1";
  function loadState() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
  }
  function getLastPosition(slug) { return loadState()[slug + "-last"] || null; }
  function isRead(slug, num) {
    const s = loadState();
    return !!(s[slug] && s[slug][num]);
  }

  // ── Profile & Roles Global Helpers ─────────────────────────────────────
  const GRADIENTS = [
    { name: "Flame", value: "linear-gradient(135deg,#f59e0b,#ef4444)" },
    { name: "Neon", value: "linear-gradient(135deg,#00f5d4,#38bdf8)" },
    { name: "Forest", value: "linear-gradient(135deg,#10b981,#059669)" },
    { name: "Twilight", value: "linear-gradient(135deg,#a78bfa,#ec4899)" },
    { name: "Obsidian", value: "linear-gradient(135deg,#64748b,#1e293b)" }
  ];

  const ROLES_CONFIG = {
    admin: { label: "ผู้ดูแลระบบ (Admin)", limit: "ไม่จำกัด (Unlimited)", class: "admin" },
    paid: { label: "สมาชิกพิเศษ (Paid)", limit: "1,000 / วัน", class: "translator" },
    user: { label: "สมาชิกทั่วไป (User)", limit: "50 / วัน", class: "reader" },
    bot: { label: "บอทเชื่อมต่อ (Bot)", limit: "10,000 / วัน (API)", class: "bot" }
  };

  function getProfile() {
    const defaultProfile = {
      name: "P'Choke",
      email: "chokechai@gmail.com",
      role: "admin",
      avatarColorIndex: 0,
      tokensUsed: 0
    };
    try {
      const stored = localStorage.getItem("novelclaw-profile");
      if (stored) return JSON.parse(stored);
    } catch {}
    localStorage.setItem("novelclaw-profile", JSON.stringify(defaultProfile));
    return defaultProfile;
  }

  function saveProfile(prof) {
    try {
      localStorage.setItem("novelclaw-profile", JSON.stringify(prof));
      updateTopbarAvatar(prof);
    } catch {}
  }

  function updateTopbarAvatar(prof) {
    const avatarEl = document.getElementById("profile-avatar");
    if (avatarEl) {
      avatarEl.textContent = prof.name ? prof.name.charAt(0).toUpperCase() : "P";
      const gradient = GRADIENTS[prof.avatarColorIndex] || GRADIENTS[0];
      avatarEl.style.background = gradient.value;
    }
  }

  function showToast(message, type = "success") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = el("div", { id: "toast-container", style: "position: fixed; bottom: 24px; right: 24px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; pointer-events: none;" });
      document.body.appendChild(container);
    }
    const t = el("div", {
      class: `toast show ${type}`,
      style: "pointer-events: auto; transform: translateY(0); opacity: 1; transition: all 0.3s; margin-top: 8px;"
    }, message);
    container.appendChild(t);
    setTimeout(() => {
      t.style.opacity = "0";
      t.style.transform = "translateY(20px)";
      setTimeout(() => t.remove(), 300);
    }, 3000);
  }

  // ── Activity Feed ─────────────────────────────────────────────────────
  async function updateActivityFeed() {
    const feed = $("activity-feed");
    if (!feed) return;
    try {
      const novels = await getNovels();
      let html = "";
      for (const n of novels) {
        html += `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border-subtle);font-size:11px;">
          <div style="width:24px;height:24px;border-radius:4px;background:linear-gradient(135deg,hsl(${slugToHue(n.slug)},70%,40%),hsl(${(slugToHue(n.slug)+40)%360},60%,30%));display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#000;flex-shrink:0;">${(n.title||n.slug).charAt(0)}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${n.title||n.slug}</div>
            <div style="color:var(--text-muted);font-family:var(--font-mono);font-size:9px;">${n.chapterCount||0} ตอน</div>
          </div>
          <span class="status-dot ${n.status==='ongoing'?'online':'idle'}"></span>
        </div>`;
      }
      if (!html) showEmpty(feed, "ยังไม่มีนิยาย", "เพิ่มนิยายเรื่องแรกของคุณ");
      feed.innerHTML = html;
    } catch {
      showError(feed, "โหลดไม่สำเร็จ");
    }
  }

  // ── Data helpers ──────────────────────────────────────────────────────
  async function getNovels() {
    if (!novelsCache) novelsCache = await api("/api/novels");
    return novelsCache;
  }

  async function getChapters(slug) {
    if (!chaptersCache[slug]) {
      const data = await api(`/api/novel/${encodeURIComponent(slug)}/chapters`);
      chaptersCache[slug] = data.chapters;
    }
    return chaptersCache[slug];
  }

  // ═══════════════════════════════════════════════════════════════════════
  // PAGE RENDERERS
  // ═══════════════════════════════════════════════════════════════════════

  // ── HOME DASHBOARD ────────────────────────────────────────────────────
  async function renderHome(params) {
    const page = $("page-home");
    if (!page) return;
    showSkeleton('page-home');

    try {
      const novels = await getNovels();
      const enriched = novels.map((n) => {
        const lastRead = getLastPosition(n.slug);
        const readCount = n.chapterCount || 0;
        const totalCount = n.totalChapters || readCount;
        const progressPct = totalCount > 0 ? Math.round((readCount / totalCount) * 100) : 0;
        const hue = slugToHue(n.slug);
        return { ...n, lastRead, readCount, totalCount, progressPct, hue };
      });

      const featured = enriched[0];
      let html = "";

      // ── Hero Banner ────
      if (featured) {
        html += `
        <div class="hero-banner" style="margin-bottom:24px;background:linear-gradient(135deg,hsl(${featured.hue},60%,30%),hsl(${(featured.hue+40)%360},50%,20%));">
          <div class="hero-content">
            <span class="hero-badge">🔥 ยอดนิยม</span>
            <h2 class="hero-title">${featured.title || featured.slug}</h2>
            <p class="hero-subtitle">${featured.slug} • ${featured.source_lang||'cn'} → ${featured.target_lang||'th'}</p>
            <div class="hero-meta-row">
              <span class="hero-tag lang-tag">${featured.source_lang||'cn'} → ${featured.target_lang||'th'}</span>
              <span class="hero-tag">${statusMap[featured.status]||'ไม่ระบุ'}</span>
            </div>
            <div class="hero-progress-section">
              <div class="hero-progress-info">
                <span class="hero-progress-text">${featured.readCount} / ${featured.totalCount} ตอน</span>
                <span class="hero-progress-percent">${featured.progressPct}%</span>
              </div>
              <div class="hero-progress-bar">
                <div class="hero-progress-fill" style="width:${featured.progressPct}%"></div>
              </div>
            </div>
            <div class="hero-actions">
              <a href="#novel/${featured.slug}" class="hero-cta" data-nav>อ่านต่อ →</a>
              <div class="hero-last-read-box">
                <span class="last-read-label">อ่านล่าสุด</span>
                <span class="last-read-ch">${featured.lastRead ? `ตอนที่ ${featured.lastRead}` : 'ยังไม่ได้อ่าน'}</span>
              </div>
            </div>
          </div>
        </div>`;
      }

      // ── Continue Reading ────
      html += `
      <section class="dash-section" style="margin-bottom:28px;">
        <div class="section-header">
          <h3 class="section-title">📖 อ่านต่อ</h3>
          <a href="#library" class="section-link" data-nav>ดูทั้งหมด ❯</a>
        </div>
        <div class="continue-grid">`;

      for (const n of enriched) {
        html += `
          <a href="#novel/${n.slug}" class="continue-card" data-nav>
            <div class="continue-cover" style="background:linear-gradient(135deg,hsl(${n.hue},70%,40%),hsl(${(n.hue+40)%360},60%,30%));color:#000;">${(n.title||n.slug).charAt(0)}</div>
            <div class="continue-info">
              <span class="continue-title">${n.title||n.slug}</span>
              <span class="continue-ch">${n.lastRead ? `ตอนที่ ${n.lastRead} / ${n.totalCount}` : `0 / ${n.totalCount}`}</span>
              <div class="continue-progress">
                <div class="continue-progress-bar"><div class="continue-progress-fill" style="width:${n.progressPct}%"></div></div>
                <span class="continue-progress-pct">${n.progressPct}%</span>
              </div>
            </div>
          </a>`;
      }

      html += `
          <a href="#admin/novels" class="continue-card add-novel-card" style="border:2px dashed var(--border);display:flex;align-items:center;justify-content:center;gap:8px;padding:24px;" data-nav>
            <span style="font-size:24px;color:var(--text-muted);">+</span>
            <span style="font-size:12px;color:var(--text-muted);">เพิ่มนิยาย</span>
          </a>
        </div>
      </section>`;

      // ── Latest Updates ────
      html += `
      <section class="dash-section" style="margin-bottom:28px;">
        <div class="section-header">
          <h3 class="section-title">🆕 อัปเดตล่าสุด</h3>
        </div>
        <div class="updates-row">`;

      for (const n of enriched) {
        html += `
          <a href="#novel/${n.slug}" class="update-card" data-nav>
            <div class="update-cover-wrapper">
              <span class="new-badge">NEW</span>
              <div class="update-cover" style="background:linear-gradient(135deg,hsl(${n.hue},70%,40%),hsl(${(n.hue+40)%360},60%,30%));color:#000;">${(n.title||n.slug).charAt(0)}</div>
            </div>
            <span class="update-title">${n.title||n.slug}</span>
            <span class="update-ch">ตอนที่ ${n.readCount}</span>
          </a>`;
      }

      html += `</div></section>`;

      // ── Weekly Popular ────
      html += `
      <section class="dash-section">
        <div class="section-header">
          <h3 class="section-title">🏆 ยอดนิยมประจำสัปดาห์</h3>
        </div>
        <div class="popular-list">`;

      let rank = 1;
      for (const n of enriched) {
        const badgeColor = rank === 1 ? "#f59e0b" : rank === 2 ? "#94a3b8" : rank === 3 ? "#b45309" : "var(--text-muted)";
        html += `
          <a href="#novel/${n.slug}" class="popular-item" data-nav>
            <span class="rank-badge" style="color:${badgeColor}">${rank++}</span>
            <div class="popular-cover" style="background:linear-gradient(135deg,hsl(${n.hue},70%,40%),hsl(${(n.hue+40)%360},60%,30%));color:#000;">${(n.title||n.slug).charAt(0)}</div>
            <div class="popular-info">
              <span class="popular-title">${n.title||n.slug}</span>
              <span class="popular-meta">${n.source_lang||'cn'} → ${n.target_lang||'th'} • โดย ${n.author||'ไม่ระบุ'}</span>
              <span class="popular-views">📖 ${n.readCount}+ ตอน</span>
            </div>
          </a>`;
      }
      html += `</div></section>`;

      page.innerHTML = html;

    } catch (err) {
      showError(page, "โหลดไม่สำเร็จ", err.message);
    }
  }

  // ── LIBRARY ────────────────────────────────────────────────────────────
  async function renderLibrary(params) {
    const page = $("page-library");
    if (!page) return;
    showSkeleton(page);

    try {
      const novels = await getNovels();
      const library = novels.filter(n => getLastPosition(n.slug) !== null);

      let html = `
      <section class="dash-section">
        <div class="section-header">
          <h3 class="section-title">📚 หอสมุดของฉัน</h3>
          <span style="font-size:11px;color:var(--text-muted);">${library.length} เรื่อง</span>
        </div>
        <div class="continue-grid">`;

      if (library.length === 0) {
        showEmpty(page, "หอสมุดว่างเปล่า", "เริ่มอ่านนิยายกันเลย!");
        return; // showEmpty set innerHTML already
      } else {
        for (const n of library) {
          const hue = slugToHue(n.slug);
          const lastRead = getLastPosition(n.slug);
          html += `
          <a href="#novel/${n.slug}" class="continue-card" data-nav>
            <div class="continue-cover" style="background:linear-gradient(135deg,hsl(${hue},70%,40%),hsl(${(hue+40)%360},60%,30%));color:#000;">${(n.title||n.slug).charAt(0)}</div>
            <div class="continue-info">
              <span class="continue-title">${n.title||n.slug}</span>
              <span class="continue-ch">อ่านล่าสุด: ตอนที่ ${lastRead||'—'}</span>
              <span style="font-size:10px;color:var(--accent);font-weight:600;">${n.chapterCount||0} ตอน</span>
            </div>
          </a>`;
        }
      }
      html += `</div></section>`;
      page.innerHTML = html;

    } catch (err) {
      showError(page, "โหลดไม่สำเร็จ", err.message);
    }
  }

  // ── SEARCH ─────────────────────────────────────────────────────────────
  async function renderSearch(params) {
    const page = $("page-search");
    if (!page) return;
    page.innerHTML = `
    <section class="dash-section">
      <div class="section-header">
        <h3 class="section-title">🔍 ค้นหานิยาย</h3>
      </div>
      <div class="search-category-box">
        <input type="text" id="search-input-field" placeholder="พิมพ์ชื่อนิยาย ผู้แต่ง หรือคีย์เวิร์ด..." class="search-input-large" />
        <div class="category-tags">
          <span class="tag active" data-genre="all">ทั้งหมด</span>
          <span class="tag" data-genre="fantasy">แฟนตาซี</span>
          <span class="tag" data-genre="action">แอคชัน</span>
          <span class="tag" data-genre="sci-fi">ไซไฟ</span>
          <span class="tag" data-genre="romance">โรแมนติก</span>
          <span class="tag" data-genre="horror">สยองขวัญ</span>
        </div>
      </div>
      <div class="continue-grid" id="search-results-grid">
        <p style="grid-column:1/-1;text-align:center;padding:48px;color:var(--text-muted);">พิมพ์คำค้นหาเพื่อเริ่มค้นหา</p>
      </div>
    </section>`;

    // Wire events
    const input = document.getElementById("search-input-field");
    const tagContainer = page.querySelector(".category-tags");
    let activeGenre = "all";

    if (tagContainer) {
      tagContainer.addEventListener("click", (e) => {
        const tag = e.target.closest(".tag");
        if (tag) {
          tagContainer.querySelectorAll(".tag").forEach(t => t.classList.remove("active"));
          tag.classList.add("active");
          activeGenre = tag.dataset.genre;
          doSearch(input ? input.value : "", activeGenre);
        }
      });
    }
    if (input) {
      input.addEventListener("input", () => doSearch(input.value, activeGenre));
    }

    async function doSearch(query, genre) {
      const grid = document.getElementById("search-results-grid");
      if (!grid) return;
      try {
        const novels = await getNovels();
        const q = query.trim().toLowerCase();
        const filtered = novels.filter(n => {
          if (q) return esc(n.title || "").toLowerCase().includes(q) || n.slug.includes(q);
          return false;
        });
        grid.innerHTML = "";
        if (filtered.length === 0 && q) {
          showEmpty(grid, "ไม่พบนิยายตามคำค้นหา", "ลองเปลี่ยนคำค้นหาดูใหม่");
          return;
        }
        if (!q) {
          grid.innerHTML = '<p style="grid-column:1/-1;text-align:center;padding:32px;color:var(--text-muted);">พิมพ์คำค้นหาเพื่อเริ่มค้นหา</p>';
          return;
        }
        for (const n of filtered) {
          const hue = slugToHue(n.slug);
          grid.innerHTML += `
          <a href="#novel/${n.slug}" class="continue-card" data-nav>
            <div class="continue-cover" style="background:linear-gradient(135deg,hsl(${hue},70%,40%),hsl(${(hue+40)%360},60%,30%));color:#000;">${(n.title||n.slug).charAt(0)}</div>
            <div class="continue-info">
              <span class="continue-title">${n.title||n.slug}</span>
              <span class="continue-ch">โดย: ${n.author||'Mika'}</span>
              <span style="font-size:10px;color:var(--text-muted);">${n.source_lang||'CN'} → ${n.target_lang||'TH'} • ${n.chapterCount||0} ตอน</span>
            </div>
          </a>`;
        }
      } catch (err) {
        grid.innerHTML = `<p style="color:var(--error);">ค้นหาไม่สำเร็จ: ${err.message}</p>`;
      }
    }
  }

  // ── RANKING ────────────────────────────────────────────────────────────
  async function renderRanking(params) {
    const page = $("page-ranking");
    if (!page) return;
    showSkeleton(page);

    try {
      const novels = await getNovels();
      const sorted = [...novels].sort((a, b) => (b.chapterCount || 0) - (a.chapterCount || 0));

      let html = `
      <section class="dash-section">
        <div class="section-header">
          <h3 class="section-title">🏆 อันดับนิยายทั้งหมด</h3>
        </div>
        <div class="popular-list">`;

      let rank = 1;
      for (const n of sorted) {
        const hue = slugToHue(n.slug);
        const badgeColor = rank === 1 ? "#f59e0b" : rank === 2 ? "#94a3b8" : rank === 3 ? "#b45309" : "var(--text-muted)";
        html += `
        <a href="#novel/${n.slug}" class="popular-item" data-nav>
          <span class="rank-badge" style="color:${badgeColor}">${rank++}</span>
          <div class="popular-cover" style="background:linear-gradient(135deg,hsl(${hue},70%,40%),hsl(${(hue+40)%360},60%,30%));color:#000;">${(n.title||n.slug).charAt(0)}</div>
          <div class="popular-info">
            <span class="popular-title">${n.title||n.slug}</span>
            <span class="popular-meta">${n.source_lang||'cn'} → ${n.target_lang||'th'} • โดย ${n.author||'ไม่ระบุ'}</span>
            <span class="popular-views">📖 ${n.chapterCount||0} ตอน</span>
          </div>
        </a>`;
      }
      html += `</div></section>`;
      page.innerHTML = html;

    } catch (err) {
      showError(page, "โหลดไม่สำเร็จ", err.message);
    }
  }

  // ── NOVEL DETAIL ──────────────────────────────────────────────────────
  async function renderNovelDetail(params) {
    const page = $("page-novel-detail");
    if (!page) return;
    const slug = params.slug;
    if (!slug) { showError(page, "ไม่พบ Slug"); return; }

    showSkeleton(page);

    try {
      const novels = await getNovels();
      const novel = novels.find(n => n.slug === slug);
      if (!novel) { showError(page, "ไม่พบนิยาย"); return; }

      const chapters = await getChapters(slug);
      const hue = slugToHue(slug);

      // Pagination logic for large novel chapters list
      const pageSize = 100;
      let selectedPageIdx = 0;
      let lastReadNum = getLastPosition(slug);
      if (lastReadNum) {
        const readIdx = chapters.findIndex(c => c.num === lastReadNum);
        if (readIdx !== -1) {
          selectedPageIdx = Math.floor(readIdx / pageSize);
        }
      }

      function getChaptersPageHtml(pageIdx) {
        const start = pageIdx * pageSize;
        const end = Math.min(start + pageSize, chapters.length);
        const pageChapters = chapters.slice(start, end);
        let chHtml = '';
        for (const ch of pageChapters) {
          const read = isRead(slug, ch.num);
          chHtml += `
            <a href="#novel/${slug}/${ch.num}" class="detail-ch-btn" data-nav style="${read ? 'opacity:0.7;' : ''}">
              ตอนที่ ${ch.num}
              ${ch.title ? `<br><span style="font-size:10px;color:var(--text-muted);">${ch.title}</span>` : ''}
              ${read ? '<br><span style="font-size:9px;color:var(--success);">✔ อ่านแล้ว</span>' : ''}
            </a>`;
        }
        return chHtml;
      }

      let rangesHtml = '';
      if (chapters.length > pageSize) {
        rangesHtml = '<div class="chapters-pagination" style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; padding:0 4px;">';
        const numPages = Math.ceil(chapters.length / pageSize);
        for (let i = 0; i < numPages; i++) {
          const startCh = chapters[i * pageSize].num;
          const endCh = chapters[Math.min((i + 1) * pageSize - 1, chapters.length - 1)].num;
          const label = `${startCh} - ${endCh}`;
          rangesHtml += `<button class="btn btn-sm ${i === selectedPageIdx ? 'btn-primary' : 'btn-ghost'} page-range-btn" data-page-idx="${i}" style="font-size:11px; font-weight:600; padding:6px 12px; border-radius:var(--radius-sm); border:1px solid var(--border);">${label}</button>`;
        }
        rangesHtml += '</div>';
      }

      let html = `
      <div class="detail-header-card" style="margin-bottom:24px;">
        <div class="detail-cover" style="background:linear-gradient(135deg,hsl(${hue},70%,40%),hsl(${(hue+40)%360},60%,30%));display:flex;align-items:center;justify-content:center;font-size:2rem;font-weight:800;color:#000;">
          ${(novel.title||slug).charAt(0)}
        </div>
        <div class="detail-info">
          <h2 class="detail-title">${novel.title||slug}</h2>
          <p class="detail-author">ผู้แต่ง: ${novel.author||'ไม่ระบุ'}</p>
          <div class="detail-meta">
            <span class="hero-tag lang-tag">${novel.source_lang||'cn'} → ${novel.target_lang||'th'}</span>
            <span class="hero-tag">${statusMap[novel.status]||'ไม่ระบุ'}</span>
          </div>
          <p class="detail-synopsis">${novel.meta ? (typeof marked !== 'undefined' ? marked.parse(novel.meta.replace(/^---[\s\S]*?---\s*/, '').trim().slice(0,300)) : novel.meta.replace(/^---[\s\S]*?---\s*/, '').trim().slice(0,300)) : 'ยังไม่มีคำอธิบาย'}</p>
          <a href="#novel/${slug}/${chapters[0]?.num||1}" class="hero-cta" data-nav>📖 เริ่มอ่านตอนแรก</a>
        </div>
      </div>
      
      <div class="detail-tabs-bar" style="display:flex; gap:12px; margin-bottom:24px; border-bottom:1px solid var(--border); padding-bottom:8px;">
        <button class="btn btn-primary detail-tab-btn active" data-tab="chapters" style="font-size:13px; font-weight:600; padding:8px 16px;">📑 รายการตอน (${chapters.length})</button>
        <button class="btn btn-ghost detail-tab-btn" data-tab="reviews" style="font-size:13px; font-weight:600; padding:8px 16px;">⭐ รีวิวและเรตติ้ง</button>
      </div>

      <div id="detail-tab-chapters-panel" class="detail-tab-panel">
        <section class="dash-section">
          ${rangesHtml}
          <div class="detail-chapters-grid" id="detail-chapters-grid-container">
            ${getChaptersPageHtml(selectedPageIdx)}
          </div>
        </section>
      </div>

      <div id="detail-tab-reviews-panel" class="detail-tab-panel" style="display:none; flex-direction:column; gap:24px;">
      </div>`;

      page.innerHTML = html;

      // Tab switching logic
      const tabBtns = page.querySelectorAll(".detail-tab-btn");
      const panels = page.querySelectorAll(".detail-tab-panel");
      
      tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
          const tab = btn.dataset.tab;
          tabBtns.forEach(b => {
            b.classList.remove("btn-primary");
            b.classList.add("btn-ghost");
            b.classList.remove("active");
          });
          btn.classList.add("btn-primary");
          btn.classList.remove("btn-ghost");
          btn.classList.add("active");

          panels.forEach(p => p.style.display = "none");
          if (tab === "chapters") {
            document.getElementById("detail-tab-chapters-panel").style.display = "block";
          } else if (tab === "reviews") {
            const reviewsPanel = document.getElementById("detail-tab-reviews-panel");
            reviewsPanel.style.display = "flex";
            loadAndRenderReviews(slug, reviewsPanel);
          }
        });
      });

      // Pagination events
      if (chapters.length > pageSize) {
        const rangeBtns = page.querySelectorAll(".page-range-btn");
        const gridContainer = page.querySelector("#detail-chapters-grid-container");
        rangeBtns.forEach(btn => {
          btn.addEventListener("click", () => {
            rangeBtns.forEach(b => {
              b.classList.remove("btn-primary");
              b.classList.add("btn-ghost");
            });
            btn.classList.add("btn-primary");
            btn.classList.remove("btn-ghost");
            const pageIdx = parseInt(btn.dataset.pageIdx, 10);
            gridContainer.innerHTML = getChaptersPageHtml(pageIdx);
          });
        });
      }

    } catch (err) {
      showError(page, "โหลดไม่สำเร็จ", err.message);
    }
  }

  async function loadAndRenderReviews(slug, container) {
    container.innerHTML = '<div style="color:var(--text-secondary); font-size:13px;">กำลังโหลดรีวิว...</div>';
    try {
      const reviews = await api(`/api/novel/${encodeURIComponent(slug)}/reviews`);
      const count = reviews.length;
      
      let avg = 0.0;
      const dist = { 5:0, 4:0, 3:0, 2:0, 1:0 };
      if (count > 0) {
        const sum = reviews.reduce((acc, r) => acc + r.rating, 0);
        avg = (sum / count).toFixed(1);
        reviews.forEach(r => {
          const ratingKey = Math.min(5, Math.max(1, Math.round(r.rating)));
          dist[ratingKey] = (dist[ratingKey] || 0) + 1;
        });
      }

      const getStarsHtml = (rating) => {
        let stars = "";
        for (let i = 1; i <= 5; i++) {
          stars += i <= rating ? "★" : "☆";
        }
        return stars;
      };

      let html = `
      <div class="reviews-summary-card" style="display:flex; gap:32px; background:var(--bg-secondary); border:1px solid var(--border); border-radius:var(--radius-lg); padding:24px; flex-wrap:wrap;">
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-width:120px; flex:1;">
          <span style="font-size:3rem; font-weight:800; color:var(--text-primary); line-height:1;">${avg}</span>
          <span style="color:#fbbf24; font-size:1.5rem; margin:8px 0;">${getStarsHtml(Math.round(avg))}</span>
          <span style="font-size:11px; color:var(--text-muted);">${count} รีวิว</span>
        </div>
        <div style="flex:2; display:flex; flex-direction:column; gap:8px; min-width:240px;">
      `;

      for (let star = 5; star >= 1; star--) {
        const starCount = dist[star];
        const pct = count > 0 ? Math.round((starCount / count) * 100) : 0;
        html += `
          <div style="display:flex; align-items:center; gap:12px; font-size:12px; color:var(--text-secondary);">
            <span style="width:40px; display:flex; justify-content:flex-end; gap:2px; font-family:var(--font-mono);">${star} ★</span>
            <div style="flex:1; height:8px; background:var(--bg-tertiary); border-radius:4px; overflow:hidden; border:1px solid var(--border);">
              <div style="width:${pct}%; height:100%; background:linear-gradient(to right, var(--accent) 0%, var(--purple) 100%); border-radius:4px;"></div>
            </div>
            <span style="width:30px; text-align:right; font-family:var(--font-mono); color:var(--text-muted);">${pct}%</span>
          </div>
        `;
      }

      html += `
        </div>
      </div>

      <div class="review-form-card" style="background:var(--bg-secondary); border:1px solid var(--border); border-radius:var(--radius-lg); padding:24px;">
        <h4 style="font-size:1.1rem; font-weight:700; margin-bottom:16px; display:flex; align-items:center; gap:6px;">เขียนรีวิวใหม่</h4>
        <form id="novel-review-form" onsubmit="return false;" style="display:flex; flex-direction:column; gap:16px;">
          <div style="display:flex; align-items:center; gap:12px;">
            <label style="font-size:13px; color:var(--text-secondary); width:80px;">เรตติ้ง</label>
            <div class="star-rating-selector" style="display:flex; gap:6px; font-size:26px; cursor:pointer; color:var(--text-muted); user-select:none;">
              <span data-val="1">☆</span><span data-val="2">☆</span><span data-val="3">☆</span><span data-val="4">☆</span><span data-val="5">☆</span>
            </div>
            <input type="hidden" id="review-rating-input" value="5" />
          </div>
          <div style="display:flex; align-items:center; gap:12px;">
            <label style="font-size:13px; color:var(--text-secondary); width:80px;">ชื่อผู้ใช้</label>
            <input type="text" id="review-user-input" value="P'Choke" placeholder="กรอกชื่อของคุณ..." style="flex:1; max-width:250px; background:var(--bg-tertiary); border:1px solid var(--border); color:var(--text-primary); padding:8px 12px; border-radius:var(--radius-sm); font-size:0.9rem; outline:none;" required />
          </div>
          <div style="display:flex; flex-direction:column; gap:6px;">
            <label style="font-size:13px; color:var(--text-secondary);">ข้อความรีวิว</label>
            <textarea id="review-text-input" placeholder="แชร์ความประทับใจของพี่โชคกันค่ะ..." style="width:100%; min-height:100px; background:var(--bg-tertiary); border:1px solid var(--border); color:var(--text-primary); padding:12px; border-radius:var(--radius-sm); font-size:0.95rem; line-height:1.6; resize:vertical; outline:none;" required></textarea>
          </div>
          <button type="submit" class="hero-cta" style="align-self:flex-end; padding:10px 24px; font-size:0.9rem;">ส่งรีวิว</button>
        </form>
      </div>

      <div class="reviews-list-section" style="display:flex; flex-direction:column; gap:16px;">
        <h4 style="font-size:1.1rem; font-weight:700; margin-bottom:8px;">รีวิวทั้งหมด (${count})</h4>
      `;

      if (count === 0) {
        html += `
        <div style="text-align:center; padding:48px; background:var(--bg-secondary); border:1px dashed var(--border); border-radius:var(--radius-lg); color:var(--text-muted); font-size:13px;">
          ยังไม่มีรีวิวสำหรับนิยายเรื่องนี้ค่ะ ประเดิมคนแรกกันเลยไหมคะพี่โชค 🦊💅
        </div>
        `;
      } else {
        const sortedReviews = [...reviews].sort((a,b) => b.ts - a.ts);
        sortedReviews.forEach(r => {
          html += `
          <div style="background:var(--bg-secondary); border:1px solid var(--border); border-radius:var(--radius-lg); padding:20px; display:flex; flex-direction:column; gap:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-weight:700; font-size:0.95rem; color:var(--text-primary);">${esc(r.user)}</span>
                <span style="color:#fbbf24; font-size:1.1rem; font-family:var(--font-mono);">${getStarsHtml(r.rating)}</span>
              </div>
              <span style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${new Date(r.ts).toLocaleString("th-TH", {day:"numeric", month:"short", year:"numeric", hour:"2-digit", minute:"2-digit"})}</span>
            </div>
            <p style="font-size:0.95rem; color:var(--text-primary); line-height:1.65; white-space:pre-wrap; word-break:break-word;">${esc(r.text)}</p>
          </div>
          `;
        });
      }

      html += `</div>`;
      container.innerHTML = html;

      const starSpans = container.querySelectorAll(".star-rating-selector span");
      const ratingInput = container.querySelector("#review-rating-input");

      const updateStars = (val) => {
        starSpans.forEach(span => {
          const ratingVal = parseInt(span.dataset.val, 10);
          if (ratingVal <= val) {
            span.textContent = "★";
            span.style.color = "#fbbf24";
          } else {
            span.textContent = "☆";
            span.style.color = "var(--text-muted)";
          }
        });
      };

      updateStars(5);

      starSpans.forEach(span => {
        span.addEventListener("click", () => {
          const val = parseInt(span.dataset.val, 10);
          ratingInput.value = val;
          updateStars(val);
        });

        span.addEventListener("mouseenter", () => {
          const val = parseInt(span.dataset.val, 10);
          updateStars(val);
        });
      });

      const selectorContainer = container.querySelector(".star-rating-selector");
      if (selectorContainer) {
        selectorContainer.addEventListener("mouseleave", () => {
          updateStars(parseInt(ratingInput.value, 10));
        });
      }

      const form = container.querySelector("#novel-review-form");
      if (form) {
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          const rating = parseInt(ratingInput.value, 10);
          const user = container.querySelector("#review-user-input").value.trim();
          const text = container.querySelector("#review-text-input").value.trim();

          if (!user || !text || !rating) {
            showToast("กรุณากรอกข้อมูลให้ครบถ้วนก่อนส่งนะคะพี่โชค! 🦊", "warning");
            return;
          }

          try {
            const saveBtn = form.querySelector("button[type='submit']");
            if (saveBtn) {
              saveBtn.disabled = true;
              saveBtn.textContent = "กำลังส่ง...";
            }
            
            const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/reviews/save`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ user, rating, text })
            });

            if (!res.ok) throw new Error(res.statusText);

            loadAndRenderReviews(slug, container);
          } catch (err) {
            showToast(`ไม่สามารถส่งรีวิวได้: ${err.message}`, "error");
            const saveBtn = form.querySelector("button[type='submit']");
            if (saveBtn) {
              saveBtn.disabled = false;
              saveBtn.textContent = "ส่งรีวิว";
            }
          }
        });
      }

    } catch (err) {
      container.innerHTML = `<p style="color:var(--error); font-size:13px;">โหลดรีวิวไม่สำเร็จ: ${err.message}</p>`;
    }
  }

  // ── READER ─────────────────────────────────────────────────────────────
  async function renderReader(params) {
    const page = $("page-reader");
    if (!page) return;
    const slug = params.slug;
    const chapterNum = parseInt(params.chapter, 10);
    if (!slug || !chapterNum) {
      showError(page, "ไม่พบข้อมูลตอน");
      return;
    }

    page.innerHTML = `
    <div class="reader-toolbar">
      <!-- Row 1: Back + Novel Title + Chapter Nav -->
      <div class="toolbar-row">
        <a href="#novel/${slug}" class="btn btn-sm btn-ghost toolbar-back" data-nav>
          <svg style="width:14px;height:14px;color:var(--text-secondary);"><use xlink:href="#icon-arrow-left"></use></svg>
          <span class="back-text">กลับ</span>
        </a>
        <span class="toolbar-novel-title" id="reader-toolbar-novel-title">—</span>
        <div class="toolbar-nav">
          <button class="btn btn-icon btn-ghost" id="reader-prev" title="ตอนก่อนหน้า">
            <svg style="width:16px;height:16px;color:var(--text-secondary);"><use xlink:href="#icon-arrow-left"></use></svg>
          </button>
          <span class="toolbar-position" id="reader-position">— / —</span>
          <button class="btn btn-icon btn-ghost" id="reader-next" title="ตอนถัดไป">
            <svg style="width:16px;height:16px;color:var(--text-secondary);"><use xlink:href="#icon-arrow-right"></use></svg>
          </button>
        </div>
      </div>
      <!-- Row 2: Chapter Title + Settings -->
      <div class="toolbar-row">
        <span class="toolbar-chapter-title" id="reader-toolbar-chapter-num">ตอนที่ —</span>
        <div class="toolbar-settings">
          <button class="btn btn-icon btn-ghost" id="reader-font-sm" title="ลดขนาดอักษร">
            <svg style="width:14px;height:14px;color:var(--text-secondary);"><use xlink:href="#icon-minus"></use></svg>
          </button>
          <button class="btn btn-icon btn-ghost" id="reader-font-lg" title="เพิ่มขนาดอักษร">
            <svg style="width:14px;height:14px;color:var(--text-secondary);"><use xlink:href="#icon-plus"></use></svg>
          </button>
          <button class="btn btn-icon btn-ghost" id="reader-theme-toggle" title="เปลี่ยนธีม"></button>
          <div class="toolbar-divider"></div>
          <button class="btn btn-icon btn-ghost" id="reader-distraction-toggle" title="โหมดอ่านเต็มจอ">
            <svg style="width:16px;height:16px;color:var(--text-secondary);"><use xlink:href="#icon-hamburger"></use></svg>
          </button>
        </div>
      </div>
    </div>
    <div class="chapter" style="max-width:720px;margin:0 auto;">
      <div class="chapter-meta-row" id="reader-meta-row">
        <span id="reader-reading-time"></span>
      </div>
      <header class="chapter-header">
        <h2 class="chapter-title" id="reader-title">กำลังโหลด...</h2>
      </header>
      <div class="divider"></div>
      <div class="chapter-content" id="reader-content">
        <p style="text-align:center;padding:2em;color:var(--text-muted);">กำลังโหลดเนื้อหา...</p>
      </div>
      <div class="divider"></div>
      <footer class="chapter-footer">
        <p class="chapter-meta" id="reader-meta"></p>
      </footer>
      <nav class="chapter-nav-bottom" style="display:flex; justify-content:center; align-items:center; gap:20px; margin-top:48px; padding-top:32px; border-top:1px solid var(--border-subtle);">
        <button class="nav-btn" id="reader-prev-2" style="display:flex; align-items:center; justify-content:center; gap:6px; min-width: 130px; font-weight: 600;" disabled>
          <svg style="width: 14px; height: 14px; color: currentColor;"><use xlink:href="#icon-arrow-left"></use></svg>
          <span>ตอนก่อนหน้า</span>
        </button>
        <button class="nav-btn" id="reader-back-top" style="min-width:auto; padding:10px 20px; font-weight: 600;">↑ กลับด้านบน</button>
        <button class="nav-btn" id="reader-next-2" style="display:flex; align-items:center; justify-content:center; gap:6px; min-width: 130px; font-weight: 600;" disabled>
          <span>ตอนถัดไป</span>
          <svg style="width: 14px; height: 14px; color: currentColor;"><use xlink:href="#icon-arrow-right"></use></svg>
        </button>
      </nav>

      <section class="chapter-comments-section" style="margin-top:48px; border-top:1px solid var(--border); padding-top:32px;">
        <h3 id="comments-toggle-header" style="font-size:1.15rem; font-weight:700; margin-bottom:20px; display:flex; align-items:center; gap:8px; cursor:pointer; user-select:none;" title="คลิกเพื่อแสดง/ซ่อนความคิดเห็น">
          <span>💬 ความคิดเห็นประจำตอน (<span id="comments-count">0</span>)</span>
          <span id="comments-toggle-chevron" style="margin-left:auto; font-size: 14px; color: var(--text-muted); transition: transform 0.2s;">❯</span>
        </h3>
        
        <div id="comments-collapsible-wrapper" style="display:none; flex-direction:column; gap:24px;">
          <div id="comments-feed" style="display:flex; flex-direction:column; gap:16px; margin-bottom:24px;">
            <!-- Comments -->
          </div>
          <div class="comment-form-card" style="background:var(--bg-secondary); border:1px solid var(--border); border-radius:var(--radius-lg); padding:20px;">
            <h4 style="font-size:0.95rem; font-weight:600; margin-bottom:14px;">แสดงความคิดเห็น</h4>
            <form id="comment-form" onsubmit="return false;" style="display:flex; flex-direction:column; gap:12px;">
              <div style="display:flex; gap:12px; align-items:center;">
                <label style="font-size:0.8rem; color:var(--text-secondary); width:80px;">ชื่อผู้ใช้</label>
                <input type="text" id="comment-user-input" value="P'Choke" placeholder="ชื่อของคุณ..." style="flex:1; max-width:200px; background:var(--bg-tertiary); border:1px solid var(--border); color:var(--text-primary); padding:8px 12px; border-radius:var(--radius-sm); font-size:0.9rem; outline:none;" required />
              </div>
              <div style="display:flex; flex-direction:column; gap:6px;">
                <textarea id="comment-text-input" placeholder="พิมพ์ความคิดเห็นของพี่โชคตรงนี้..." style="width:100%; min-height:80px; background:var(--bg-tertiary); border:1px solid var(--border); color:var(--text-primary); padding:12px; border-radius:var(--radius-sm); font-size:0.95rem; line-height:1.5; resize:vertical; outline:none;" required></textarea>
              </div>
              <button type="submit" class="hero-cta" style="align-self:flex-end; padding:8px 20px; font-size:0.9rem;">ส่งความคิดเห็น</button>
            </form>
          </div>
        </div>
      </section>
    </div>`;

    // State
    let chapters = await getChapters(slug);
    let idx = chapters.findIndex(c => c.num === chapterNum);
    if (idx === -1) idx = 0;

    async function loadChapter(idx) {
      const ch = chapters[idx];
      if (!ch) return;
      try {
        const data = await api(`/api/novel/${encodeURIComponent(slug)}/chapter/${ch.num}`);
        const titleEl = document.getElementById("reader-title");
        const contentEl = document.getElementById("reader-content");
        const posEl = document.getElementById("reader-position");
        const prev = document.getElementById("reader-prev");
        const next = document.getElementById("reader-next");
        const prev2 = document.getElementById("reader-prev-2");
        const next2 = document.getElementById("reader-next-2");
        const rtEl = document.getElementById("reader-reading-time");
        const metaEl = document.getElementById("reader-meta");

        if (titleEl) titleEl.textContent = data.title || `ตอนที่ ${ch.num}`;
        if (contentEl) contentEl.innerHTML = data.html || "<p>ไม่มีเนื้อหา</p>";
        if (posEl) posEl.textContent = `${idx + 1} / ${chapters.length}`;
        if (prev) prev.disabled = idx <= 0;
        if (next) next.disabled = idx >= chapters.length - 1;
        if (prev2) prev2.disabled = idx <= 0;
        if (next2) next2.disabled = idx >= chapters.length - 1;

        // Update toolbar titles
        const tbNovelTitle = document.getElementById("reader-toolbar-novel-title");
        const tbChapterNum = document.getElementById("reader-toolbar-chapter-num");
        const novelNameEl = document.getElementById("reader-novel-name");
        let novelTitleText = slug;
        if (tbNovelTitle) {
          const novels = await getNovels();
          const novel = novels.find(n => n.slug === slug);
          novelTitleText = novel ? (novel.title || slug) : slug;
          tbNovelTitle.textContent = novelTitleText;
        }
        if (tbChapterNum) {
          tbChapterNum.textContent = data.title || `ตอนที่ ${ch.num}`;
        }
        if (novelNameEl) {
          novelNameEl.textContent = novelTitleText;
          novelNameEl.title = novelTitleText;
        }

        const text = (data.html || "").replace(/<[^>]+>/g, "").replace(/\s+/g, "");
        if (rtEl) rtEl.textContent = `⏱ ${Math.max(1, Math.round(text.length / 250))} นาที`;
        if (metaEl && data.metaHtml) {
          metaEl.innerHTML = `<details><summary>หมายเหตุการแปล</summary>${data.metaHtml}</details>`;
        } else if (metaEl) {
          metaEl.innerHTML = "";
        }

        // Update URL
        window.history.replaceState(null, "", `#novel/${slug}/${ch.num}`);

        // Mark as read
        markRead(slug, ch.num);
        setLastPosition(slug, ch.num);

        // Load comments
        loadChapterComments(slug, ch.num);

        // Scroll to top
        const scrollContainer = document.querySelector('.main-content');
        if (scrollContainer) scrollContainer.scrollTop = 0;
      } catch (err) {
        const titleEl = document.getElementById("reader-title");
        const contentEl = document.getElementById("reader-content");
        if (titleEl) titleEl.textContent = 'เกิดข้อผิดพลาด';
        if (contentEl) contentEl.innerHTML = `<p style="text-align:center;padding:2em;color:var(--error);">โหลดไม่สำเร็จ: ${err.message}</p>`;
      }
    }

    async function loadChapterComments(slug, num) {
      const feed = document.getElementById("comments-feed");
      const countEl = document.getElementById("comments-count");
      if (!feed) return;

      feed.innerHTML = '<div style="color:var(--text-muted); font-size:12px;">กำลังโหลดความคิดเห็น...</div>';
      try {
        const comments = await api(`/api/novel/${encodeURIComponent(slug)}/chapter/${num}/comments`);
        if (countEl) countEl.textContent = String(comments.length);

        if (comments.length === 0) {
          feed.innerHTML = `
          <div style="text-align:center; padding:24px; background:var(--bg-secondary); border:1px dashed var(--border); border-radius:var(--radius-lg); color:var(--text-muted); font-size:13px;">
            ยังไม่มีความคิดเห็นในตอนนี้ค่ะ มาร่วมประเดิมคนแรกกันไหมคะพี่โชค 🦊💅
          </div>
          `;
        } else {
          let html = "";
          const sorted = [...comments].sort((a,b) => b.ts - a.ts);
          sorted.forEach(c => {
            html += `
            <div style="background:var(--bg-secondary); border:1px solid var(--border); border-radius:var(--radius-lg); padding:16px; display:flex; flex-direction:column; gap:8px;">
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <span style="font-weight:700; font-size:0.9rem; color:var(--text-primary);">${esc(c.user)}</span>
                <span style="font-size:10px; color:var(--text-muted); font-family:var(--font-mono);">${new Date(c.ts).toLocaleString("th-TH", {day:"numeric", month:"short", hour:"2-digit", minute:"2-digit"})}</span>
              </div>
              <p style="font-size:0.92rem; color:var(--text-primary); line-height:1.55; white-space:pre-wrap; word-break:break-word;">${esc(c.text)}</p>
            </div>
            `;
          });
          feed.innerHTML = html;
        }
      } catch (err) {
        feed.innerHTML = `<p style="color:var(--error); font-size:12px;">โหลดความคิดเห็นไม่สำเร็จ: ${err.message}</p>`;
      }
    }

    function markRead(slug, num) {
      const s = loadState();
      s[slug] = s[slug] || {};
      s[slug][num] = Date.now();
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
    }
    function setLastPosition(slug, num) {
      const s = loadState();
      s[slug + "-last"] = num;
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
    }

    // Wire events
    document.getElementById("reader-prev").addEventListener("click", () => { if (idx > 0) loadChapter(--idx); });
    document.getElementById("reader-next").addEventListener("click", () => { if (idx < chapters.length - 1) loadChapter(++idx); });
    document.getElementById("reader-prev-2").addEventListener("click", () => { if (idx > 0) loadChapter(--idx); });
    document.getElementById("reader-next-2").addEventListener("click", () => { if (idx < chapters.length - 1) loadChapter(++idx); });
    document.getElementById("reader-back-top").addEventListener("click", () => {
      const scrollContainer = document.querySelector('.main-content');
      if (scrollContainer) scrollContainer.scrollTo({ top: 0, behavior: "smooth" });
    });

    // Wire comment submission
    const commentForm = document.getElementById("comment-form");
    if (commentForm) {
      commentForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const ch = chapters[idx];
        if (!ch) return;
        
        const userInput = document.getElementById("comment-user-input");
        const textInput = document.getElementById("comment-text-input");
        
        const user = userInput ? userInput.value.trim() : "";
        const text = textInput ? textInput.value.trim() : "";
        
        if (!user || !text) {
          showToast("กรุณากรอกชื่อและข้อความให้ครบถ้วนก่อนส่งนะคะพี่โชค! 🦊", "warning");
          return;
        }
        
        try {
          const submitBtn = commentForm.querySelector("button[type='submit']");
          submitBtn.disabled = true;
          submitBtn.textContent = "กำลังส่ง...";
          
          const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/chapter/${ch.num}/comment`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user, text })
          });
          
          if (!res.ok) throw new Error(res.statusText);
          
          if (textInput) textInput.value = "";
          
          loadChapterComments(slug, ch.num);
        } catch (err) {
          showToast(`ไม่สามารถส่งความคิดเห็นได้: ${err.message}`, "error");
        } finally {
          const submitBtn = commentForm.querySelector("button[type='submit']");
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = "ส่งความคิดเห็น";
          }
        }
      });
    }

    // Font size
    let fontStep = 0;
    document.getElementById("reader-font-sm").addEventListener("click", () => {
      fontStep = Math.max(-2, fontStep - 1);
      document.documentElement.style.setProperty("--font-size", `${17 + fontStep * 2}px`);
    });
    document.getElementById("reader-font-lg").addEventListener("click", () => {
      fontStep = Math.min(3, fontStep + 1);
      document.documentElement.style.setProperty("--font-size", `${17 + fontStep * 2}px`);
    });

    // Theme toggle
    const THEMES = ["dark", "amoled", "light", "sepia"];
    const THEME_ICONS = { light: "#icon-sun", dark: "#icon-moon", amoled: "#icon-moon", sepia: "#icon-book" };
    let currentTheme = document.body.dataset.theme || "dark";
    
    function updateReaderThemeIcon(theme) {
      const btn = document.getElementById("reader-theme-toggle");
      if (btn) {
        btn.innerHTML = `<svg style="width:16px; height:16px; color: var(--text-secondary);"><use xlink:href="${THEME_ICONS[theme] || '#icon-moon'}"></use></svg>`;
      }
    }
    
    updateReaderThemeIcon(currentTheme);

    document.getElementById("reader-theme-toggle").addEventListener("click", () => {
      currentTheme = THEMES[(THEMES.indexOf(currentTheme) + 1) % THEMES.length];
      document.body.dataset.theme = currentTheme;
      updateReaderThemeIcon(currentTheme);
      
      // Update global setting
      const s = loadState(); s.theme = currentTheme;
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
      const globalToggle = document.getElementById("theme-toggle-new");
      if (globalToggle) globalToggle.classList.toggle("active", currentTheme === "dark");
    });

    // Distraction-Free Toggle
    const distractionToggle = document.getElementById("reader-distraction-toggle");
    if (distractionToggle) {
      distractionToggle.addEventListener("click", () => {
        const appEl = document.getElementById("app-layout");
        if (appEl) {
          const isCollapsed = appEl.classList.contains("sidebar-collapsed") && appEl.classList.contains("rightbar-collapsed");
          if (isCollapsed) {
            appEl.classList.remove("sidebar-collapsed", "rightbar-collapsed");
          } else {
            appEl.classList.add("sidebar-collapsed", "rightbar-collapsed");
          }
          showToast(isCollapsed ? "เปิดแสดงแถบเมนูแล้วค่ะ" : "เข้าสู่โหมดอ่านหนังสือเต็มจอเรียบร้อยค่ะพี่โชค! 📖✨");
        }
      });
    }

    // Comments collapsible drawer toggle
    const commentsHeader = document.getElementById("comments-toggle-header");
    const commentsWrapper = document.getElementById("comments-collapsible-wrapper");
    const commentsChevron = document.getElementById("comments-toggle-chevron");
    if (commentsHeader && commentsWrapper && commentsChevron) {
      commentsHeader.addEventListener("click", () => {
        const isCollapsed = commentsWrapper.style.display === "none";
        commentsWrapper.style.display = isCollapsed ? "flex" : "none";
        commentsChevron.style.transform = isCollapsed ? "rotate(90deg)" : "rotate(0deg)";
      });
    }

    // Keyboard shortcuts — remove old listener first to prevent accumulation
    if (_readerKeyHandler) document.removeEventListener("keydown", _readerKeyHandler);
    _readerKeyHandler = function readerKeys(e) {
      if (e.target.matches("input, textarea")) return;
      if (e.key === "ArrowLeft") { if (idx > 0) loadChapter(--idx); e.preventDefault(); }
      if (e.key === "ArrowRight") { if (idx < chapters.length - 1) loadChapter(++idx); e.preventDefault(); }
    };
    document.addEventListener("keydown", _readerKeyHandler);

    // Load first chapter
    await loadChapter(idx);
  }

  // ── PROFILE ────────────────────────────────────────────────────────────
  async function renderProfile(params) {
    const page = $("page-profile");
    if (!page) return;
    const stats = loadState();
    const totalRead = Object.keys(stats).filter(k => !k.includes("-")).reduce((a, slug) => a + Object.keys(stats[slug]||{}).length, 0);
    
    const prof = getProfile();
    const currentGrad = GRADIENTS[prof.avatarColorIndex] || GRADIENTS[0];
    
    page.innerHTML = "";
    
    // Profile section container
    const section = el("section", { class: "dash-section" },
      el("div", { class: "section-header" }, el("h3", { class: "section-title" }, "👤 โปรไฟล์ของฉัน")),
      
      // User Card View
      el("div", { style: "display:flex;gap:24px;align-items:center;padding:24px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-lg);margin-bottom:24px;flex-wrap:wrap;" },
        el("div", {
          class: "avatar avatar-lg",
          id: "profile-lg-avatar",
          style: `width:64px;height:64px;font-size:24px;background:${currentGrad.value}; font-weight: 700; color: #fff;`
        }, prof.name ? prof.name.charAt(0).toUpperCase() : "P"),
        el("div", { style: "flex: 1; min-width: 200px;" },
          el("h3", { id: "profile-disp-name", style: "font-size:18px;font-weight:700;" }, prof.name),
          el("p", { id: "profile-disp-email", style: "font-size:12px;color:var(--text-secondary);font-family:var(--font-mono);" }, prof.email),
          el("div", { style: "margin-top: 8px; display:flex; align-items:center; gap:8px;" },
            el("span", { class: `admin-badge ${prof.role}` }, prof.role.toUpperCase()),
            el("span", { style: "font-size: 11px; color: var(--text-muted);" }, `โควตาแปล: ${ROLES_CONFIG[prof.role]?.limit || ""}`)
          )
        )
      ),
      
      // Edit Form
      el("div", { class: "settings-form", style: "margin-bottom:24px;" },
        el("h4", { style: "font-size: 14px; font-weight:700; margin-bottom: 12px; color:var(--text-primary);" }, "📝 แก้ไขข้อมูลโปรไฟล์"),
        
        el("div", { class: "settings-row" },
          el("label", {}, "ชื่อผู้ใช้งาน"),
          el("input", { type: "text", id: "prof-input-name", value: prof.name, required: true })
        ),
        el("div", { class: "settings-row" },
          el("label", {}, "อีเมลผู้ใช้งาน"),
          el("input", { type: "email", id: "prof-input-email", value: prof.email, required: true })
        ),
        el("div", { class: "settings-row" },
          el("label", {}, "ระดับสิทธิ์การใช้งาน (Role)"),
          el("select", { id: "prof-input-role" },
            Object.keys(ROLES_CONFIG).map(r => el("option", { value: r, selected: prof.role === r }, ROLES_CONFIG[r].label))
          )
        ),
        el("div", { class: "settings-row" },
          el("label", {}, "สไตล์อวตาร (Gradient)"),
          el("div", { style: "display:flex; gap:12px; margin-top:8px; flex-wrap: wrap;" },
            GRADIENTS.map((g, idx) => el("div", {
              class: `avatar-picker-dot ${prof.avatarColorIndex === idx ? "active" : ""}`,
              dataset: { index: String(idx) },
              style: `width:36px; height:36px; border-radius:50%; background:${g.value}; cursor:pointer; border: ${prof.avatarColorIndex === idx ? "3px solid var(--accent)" : "1px solid var(--border)"}; transition: all 0.2s;`
            }))
          )
        ),
        
        el("button", {
          class: "hero-cta",
          style: "align-self:flex-start; margin-top:16px; padding:10px 24px;",
          onclick: () => {
            const newName = $("prof-input-name").value.trim();
            const newEmail = $("prof-input-email").value.trim();
            const newRole = $("prof-input-role").value;
            if (!newName || !newEmail) {
              showToast("กรุณากรอกข้อมูลให้ครบถ้วนด้วยนะคะพี่โชค! 🦊", "warning");
              return;
            }
            prof.name = newName;
            prof.email = newEmail;
            prof.role = newRole;
            saveProfile(prof);
            
            // Update UI elements instantly
            $("profile-disp-name").textContent = newName;
            $("profile-disp-email").textContent = newEmail;
            const badge = page.querySelector(".admin-badge");
            if (badge) {
              badge.className = `admin-badge ${newRole}`;
              badge.textContent = newRole.toUpperCase();
            }
            const lgAvatar = $("profile-lg-avatar");
            if (lgAvatar) {
              lgAvatar.textContent = newName.charAt(0).toUpperCase();
              lgAvatar.style.background = GRADIENTS[prof.avatarColorIndex].value;
            }
            
            showToast("บันทึกข้อมูลโปรไฟล์เรียบร้อยแล้วค่ะพี่โชค! 🦊💅");
          }
        }, "บันทึกข้อมูล")
      ),
      
      // Stat cards
      el("div", { class: "stat-card-row" },
        el("div", { class: "stat-bubble" }, el("span", { class: "bubble-num" }, String(totalRead)), el("span", { class: "bubble-label" }, "ตอนที่อ่านแล้ว")),
        el("div", { class: "stat-bubble" }, el("span", { class: "bubble-num" }, String(Object.keys(stats).filter(k => !k.includes("-")).length || 1)), el("span", { class: "bubble-label" }, "นิยายที่อ่าน"))
      )
    );
    
    page.appendChild(section);
    
    // Wire avatar color picker clicks
    const dots = page.querySelectorAll(".avatar-picker-dot");
    dots.forEach(dot => {
      dot.addEventListener("click", () => {
        dots.forEach(d => {
          d.classList.remove("active");
          d.style.border = "1px solid var(--border)";
        });
        dot.classList.add("active");
        dot.style.border = "3px solid var(--accent)";
        prof.avatarColorIndex = parseInt(dot.dataset.index, 10);
        
        // Live preview of gradient change
        const lgAvatar = $("profile-lg-avatar");
        if (lgAvatar) {
          lgAvatar.style.background = GRADIENTS[prof.avatarColorIndex].value;
        }
      });
    });
  }

  // ── HISTORY ────────────────────────────────────────────────────────────
  function renderHistory(params) {
    const page = $("page-history");
    if (!page) return;
    const list = loadState();
    const entries = [];
    for (const key of Object.keys(list)) {
      if (key.includes("-")) continue;
      const slug = key;
      const positions = list[slug];
      if (!positions) continue;
      const nums = Object.keys(positions).map(Number).sort((a,b)=>b-a);
      for (const num of nums.slice(0, 5)) {
        entries.push({ slug, num, ts: positions[num] });
      }
    }
    entries.sort((a,b) => b.ts - a.ts);
    const recent = entries.slice(0, 30);

    let html = `
    <section class="dash-section">
      <div class="section-header"><h3 class="section-title">⏱ ประวัติการอ่าน</h3></div>
      <div class="list-layout">`;
    if (recent.length === 0) {
      html += '<p style="text-align:center;padding:32px;color:var(--text-muted);">ไม่มีประวัติการอ่าน</p>';
    } else {
      for (const e of recent) {
        html += `
        <a href="#novel/${e.slug}/${e.num}" class="list-item-row" data-nav>
          <div class="list-item-info">
            <span class="list-item-title">${e.slug} — ตอนที่ ${e.num}</span>
            <span class="list-item-meta">${new Date(e.ts).toLocaleString("th-TH",{hour:"2-digit",minute:"2-digit",day:"numeric",month:"short"})}</span>
          </div>
          <span style="color:var(--accent);font-weight:600;font-size:12px;">อ่านต่อ →</span>
        </a>`;
      }
    }
    html += `</div></section>`;
    page.innerHTML = html;
  }

  // ── BOOKMARKS ─────────────────────────────────────────────────────────
  function renderBookmarks(params) {
    const page = $("page-bookmarks");
    if (!page) return;
    try {
      const list = JSON.parse(localStorage.getItem("nc-bookmarks")) || [];
      let html = `
      <section class="dash-section">
        <div class="section-header"><h3 class="section-title">🔖 บุ๊กมาร์ก</h3></div>
        <div class="list-layout">`;
      if (list.length === 0) {
        html += '<p style="text-align:center;padding:32px;color:var(--text-muted);">ไม่มีบุ๊กมาร์ก</p>';
      } else {
        for (const b of list) {
          html += `
          <div class="list-item-row" style="cursor:default;">
            <div class="list-item-info">
              <a href="#novel/${b.novel}/${b.num}" class="list-item-title" data-nav>${b.novel} — ตอนที่ ${b.num}</a>
              <span class="list-item-meta">บุ๊กมาร์กเมื่อ ${new Date(b.ts).toLocaleDateString("th-TH")}</span>
            </div>
          </div>`;
        }
      }
      html += `</div></section>`;
      page.innerHTML = html;
    } catch {
      page.innerHTML = '<p style="text-align:center;padding:32px;color:var(--text-muted);">ไม่มีบุ๊กมาร์ก</p>';
    }
  }

  // ── SETTINGS ──────────────────────────────────────────────────────────
  function renderSettings(params) {
    const page = $("page-settings");
    if (!page) return;
    const THEMES = ["dark", "amoled", "light", "sepia"];
    const themeNames = { dark: "🌙 ดาร์ก", amoled: "🌌 อะโมเลด", light: "☀️ สว่าง", sepia: "📖 ซีเปีย" };
    const currentTheme = document.body.dataset.theme || "dark";
    page.innerHTML = `
    <section class="dash-section">
      <div class="section-header"><h3 class="section-title">⚙️ ตั้งค่า</h3></div>
      <div class="settings-form">
        <div class="settings-row">
          <label>ธีม</label>
          <select id="settings-theme">
            ${THEMES.map(t => `<option value="${t}" ${t===currentTheme?'selected':''}>${themeNames[t]}</option>`).join("")}
          </select>
        </div>
        <div class="settings-row">
          <label>ขนาดตัวอักษร</label>
          <div class="font-size-adjuster">
            <button class="nav-btn" id="sett-font-dec">A−</button>
            <span id="sett-font-val">16px</span>
            <button class="nav-btn" id="sett-font-inc">A+</button>
          </div>
        </div>
      </div>
    </section>`;

    let fontStep = 0;
    document.getElementById("settings-theme").addEventListener("change", (e) => {
      const themeVal = e.target.value;
      document.body.dataset.theme = themeVal;
      const s = loadState(); s.theme = themeVal;
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
      const globalToggle = document.getElementById("theme-toggle-new");
      if (globalToggle) globalToggle.classList.toggle("active", themeVal === "dark");
    });
    document.getElementById("sett-font-dec").addEventListener("click", () => {
      fontStep = Math.max(-2, fontStep - 1);
      const val = 16 + fontStep * 2;
      document.documentElement.style.setProperty("--font-size", `${val}px`);
      document.getElementById("sett-font-val").textContent = `${val}px`;
    });
    document.getElementById("sett-font-inc").addEventListener("click", () => {
      fontStep = Math.min(3, fontStep + 1);
      const val = 16 + fontStep * 2;
      document.documentElement.style.setProperty("--font-size", `${val}px`);
      document.getElementById("sett-font-val").textContent = `${val}px`;
    });
  }

  // ── ADMIN NAV HELPER ───────────────────────────────────────────────────
  function renderAdminNav(activeTab) {
    const tabs = [
      { id: "dash", label: "📊 แดชบอร์ด", hash: "#admin" },
      { id: "novels", label: "📚 จัดการนิยาย", hash: "#admin/novels" },
      { id: "users", label: "👤 จัดการผู้ใช้", hash: "#admin/users" },
      { id: "glossary", label: "🗂️ จัดการ Glossary", hash: "#admin/glossary/global-descent" }
    ];
    return `<div class="admin-nav-links" style="display:flex; gap:8px; margin-bottom:20px; border-bottom:1px solid var(--border); padding-bottom:12px;">
      ${tabs.map(t => `<a href="${t.hash}" class="btn ${activeTab === t.id ? 'btn-primary' : 'btn-ghost'}" style="font-size:11px; font-weight:600; padding:6px 12px; border-radius:var(--radius-sm);">${t.label}</a>`).join("")}
    </div>`;
  }

  // ── ADMIN ──────────────────────────────────────────────────────────────
  async function renderAdmin(params) {
    const page = $("page-admin");
    if (!page) return;
    showSkeleton(page);

    try {
      const novels = await getNovels();
      const totalChapters = novels.reduce((a, n) => a + (n.chapterCount || 0), 0);
      
      let html = `
      ${renderAdminNav("dash")}
      <div class="admin-topbar" style="margin-top: 12px;">
        <h3 class="section-title" style="margin:0;">🛡️ ระบบหลังบ้าน</h3>
      </div>
      
      <div class="stat-card-row" style="margin-top: 16px; margin-bottom: 20px;">
        <div class="stat-bubble">
          <span class="bubble-num">${novels.length}</span>
          <span class="bubble-label">นิยายทั้งหมด</span>
        </div>
        <div class="stat-bubble">
          <span class="bubble-num">${totalChapters}</span>
          <span class="bubble-label">ตอนที่แปลแล้ว</span>
        </div>
      </div>
      
      <div class="chart-container" style="margin-top:24px; background:var(--bg-card); border:1px solid var(--border); padding:20px; border-radius:var(--radius-lg);">
        <div class="chart-header" style="margin-bottom:16px;">
          <h4 class="chart-title" style="font-size:12px; font-weight:600; color:var(--text-secondary);">📊 สถิติการใช้งานระบบแปล (6 เดือนย้อนหลัง)</h4>
        </div>
        <div class="bar-chart" id="admin-transactions-chart" style="display:flex; align-items:flex-end; gap:20px; height:200px; padding:10px 0;">
          <!-- Dynamically populated -->
        </div>
      </div>`;
      
      page.innerHTML = html;

      // Populate Chart
      const chart = $("admin-transactions-chart");
      if (chart) {
        const months = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.'];
        const values = [5400, 7200, 8900, 10200, 11500, 12450];
        const maxVal = 15000;
        months.forEach((m, idx) => {
          const val = values[idx];
          const pct = Math.round((val / maxVal) * 100);
          
          const barWrap = el('div', { class: 'chart-bar-wrap', style: 'display:flex; flex-direction:column; align-items:center; flex:1; height:100%; justify-content:flex-end; gap:8px;' },
            el('div', {
              class: 'chart-bar',
              style: `height: ${pct}%; width:32px; border-radius:4px 4px 0 0; background: linear-gradient(to top, rgba(56, 189, 248, 0.2) 0%, var(--accent) 100%); transition: height 0.3s;`,
              title: `฿ ${val}`
            }),
            el('span', { class: 'chart-label', style: 'font-size:10px; color:var(--text-muted); font-family:var(--font-mono);' }, m)
          );
          chart.appendChild(barWrap);
        });
      }
    } catch (err) {
      showError(page, "โหลดไม่สำเร็จ", err.message);
    }
  }

  // ── ADMIN NOVELS ───────────────────────────────────────────────────────
  async function renderAdminNovels(params) {
    const page = $("page-admin-novels");
    if (!page) return;
    
    // Inject sub nav
    let navContainer = page.querySelector(".admin-nav-tabs");
    if (!navContainer) {
      navContainer = el("div", { class: "admin-nav-tabs" });
      page.insertBefore(navContainer, page.firstChild);
    }
    navContainer.innerHTML = renderAdminNav("novels");

    const tbody = $("admin-novels-tbody");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:32px;"><div class="skel skel-line" style="margin-bottom:12px;"></div><div class="skel skel-line"></div><div class="skel skel-line" style="width:40%;"></div></td></tr>';
    
    try {
      const novels = await getNovels();
      tbody.innerHTML = '';
      novels.forEach(n => {
        const row = el('tr', {},
          el('td', { style: 'font-weight:600; font-family:var(--font-mono);' }, n.slug),
          el('td', {}, n.title || ''),
          el('td', {}, `${n.source_lang.toUpperCase()} → ${n.target_lang.toUpperCase()}`),
          el('td', { style: 'font-family:var(--font-mono);' }, String(n.chapterCount)),
          el('td', {}, el('span', { class: `admin-badge ${n.status}` }, n.status === 'ongoing' ? 'แปลต่อ' : 'จบแล้ว')),
          el('td', {},
            el('div', { class: 'admin-action-row' },
              el('button', {
                class: 'admin-btn edit',
                onclick: () => editNovelMeta(n)
              }, 'ตั้งค่าเรื่อง'),
              el('button', {
                class: 'admin-btn edit',
                style: 'background:var(--accent-glow); color:var(--accent); border-color:rgba(56, 189, 248, 0.2);',
                onclick: () => Router.navigate(`admin/chapters/${n.slug}`)
              }, 'จัดการตอน'),
              el('button', {
                class: 'admin-btn delete',
                onclick: () => deleteNovel(n.slug)
              }, 'ลบ')
            )
          )
        );
        tbody.appendChild(row);
      });

      // Wire create button
      const createBtn = $("admin-btn-create-novel");
      if (createBtn) {
        createBtn.onclick = () => editNovelMeta(null);
      }
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="6" class="error" style="text-align:center;">โหลดไม่สำเร็จ: ${err.message}</td></tr>`;
    }
  }

  function editNovelMeta(novel = null) {
    if (novel) {
      Router.navigate(`admin/novel-edit/${novel.slug}`);
    } else {
      Router.navigate(`admin/novel-edit`);
    }
  }

  async function deleteNovel(slug) {
    if (!confirm(`พี่โชคแน่ใจที่จะลบนิยายเรื่อง "${slug}" และตอนทั้งหมดใช่ไหมคะ? บันทึกไฟล์จะหายถาวรนะคะ!`)) return;
    try {
      const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/delete`, { method: 'POST' });
      if (!res.ok) throw new Error(res.statusText);
      novelsCache = null; // Clear cache
      renderAdminNovels();
    } catch (err) {
      showToast(`ลบนิยายไม่สำเร็จ: ${err.message}`, "error");
    }
  }

  // ── ADMIN NOVEL EDIT ───────────────────────────────────────────────────
  async function renderAdminNovelEdit(params) {
    const page = $("page-admin-novel-edit");
    if (!page) return;

    const slug = params.slug;
    const titleTitle = $("admin-novel-edit-title");
    const formOldSlug = $("admin-form-old-slug");
    const formSlug = $("admin-form-slug");
    const formTitle = $("admin-form-title");
    const formAuthor = $("admin-form-author");
    const formSrcLang = $("admin-form-src-lang");
    const formTgtLang = $("admin-form-tgt-lang");
    const formStatus = $("admin-form-status");
    const formTotalChapters = $("admin-form-total-chapters");

    if (slug) {
      if (titleTitle) titleTitle.textContent = `แก้ไขข้อมูลนิยาย: ${slug}`;
      if (formOldSlug) formOldSlug.value = slug;
      if (formSlug) { formSlug.value = slug; formSlug.disabled = true; }
      
      try {
        const novels = await getNovels();
        const novel = novels.find(n => n.slug === slug);
        if (novel) {
          if (formTitle) formTitle.value = novel.title || "";
          if (formAuthor) formAuthor.value = novel.author || "";
          if (formSrcLang) formSrcLang.value = novel.source_lang || "cn";
          if (formTgtLang) formTgtLang.value = novel.target_lang || "th";
          if (formStatus) formStatus.value = novel.status || "ongoing";
          if (formTotalChapters) formTotalChapters.value = novel.totalChapters || 100;
        }
      } catch (err) {
        console.error("Failed to load novel for edit:", err);
      }
    } else {
      if (titleTitle) titleTitle.textContent = 'เพิ่มนิยายเรื่องใหม่';
      if (formOldSlug) formOldSlug.value = '';
      if (formSlug) { formSlug.value = ''; formSlug.disabled = false; }
      if (formTitle) formTitle.value = '';
      if (formAuthor) formAuthor.value = '';
      if (formSrcLang) formSrcLang.value = 'cn';
      if (formTgtLang) formTgtLang.value = 'th';
      if (formStatus) formStatus.value = 'ongoing';
      if (formTotalChapters) formTotalChapters.value = 100;
    }

    // Wire cancel/submit buttons
    const cancelBtn = $("admin-novel-form-cancel");
    if (cancelBtn) {
      cancelBtn.onclick = () => Router.navigate("admin/novels");
    }

    const submitBtn = $("admin-novel-form-submit");
    if (submitBtn) {
      submitBtn.onclick = async () => {
        const saveSlug = formSlug.value.trim();
        const saveTitle = formTitle.value.trim();
        const saveAuthor = formAuthor.value.trim();
        const saveSrcLang = formSrcLang.value.trim();
        const saveTgtLang = formTgtLang.value.trim();
        const saveStatus = formStatus.value;
        const saveTotalChapters = parseInt(formTotalChapters.value, 10) || 100;

        if (!saveSlug || !saveTitle) {
          showToast('กรุณากรอกข้อมูลที่จำเป็นให้ครบถ้วนด้วยค่ะพี่โชค! 🦊', "warning");
          return;
        }

        try {
          const res = await fetch('/api/novel/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              slug: saveSlug,
              title: saveTitle,
              author: saveAuthor,
              source_lang: saveSrcLang,
              target_lang: saveTgtLang,
              status: saveStatus,
              total_chapters: saveTotalChapters
            })
          });
          if (!res.ok) throw new Error(res.statusText);
          novelsCache = null; // Clear cache
          Router.navigate("admin/novels");
        } catch (err) {
          showToast(`บันทึกข้อมูลนิยายไม่สำเร็จ: ${err.message}`, "error");
        }
      };
    }
  }

  // ── ADMIN CHAPTERS ─────────────────────────────────────────────────────
  async function renderAdminChapters(params) {
    const page = $("page-admin-chapters");
    if (!page) return;
    const slug = params.slug;
    if (!slug) {
      showError(page, "ไม่พบ Slug นิยาย");
      return;
    }

    const titleEl = $("admin-chapters-title");
    const subtitleEl = $("admin-chapters-subtitle");
    const tbody = $("admin-chapters-tbody");
    
    if (titleEl) titleEl.textContent = `จัดการตอนในเรื่อง: ${slug}`;
    if (subtitleEl) subtitleEl.textContent = `Slug: ${slug}`;
    
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:32px;"><div class="skel skel-line" style="margin-bottom:12px;"></div><div class="skel skel-line"></div><div class="skel skel-line" style="width:50%;"></div></td></tr>';
    
    try {
      const data = await api(`/api/novel/${encodeURIComponent(slug)}/chapters`);
      const chapters = data.chapters || [];
      tbody.innerHTML = '';
      
      if (chapters.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding: 32px;"><div class="empty-state" style="padding:24px;"><svg style="width:48px;height:48px;"><use xlink:href="#mascot-crab-reading"/></svg><div class="empty-state-title">ยังไม่มีตอนแปล</div></div></td></tr>';
      }
      
      chapters.forEach(ch => {
        const row = el('tr', {},
          el('td', { style: 'font-weight:600; font-family:var(--font-mono);' }, String(ch.num).padStart(4, '0')),
          el('td', {}, ch.title || `ตอนที่ ${ch.num}`),
          el('td', {}, 'JSON Canonical'),
          el('td', {},
            el('div', { class: 'admin-action-row' },
              el('button', {
                class: 'admin-btn edit',
                onclick: () => Router.navigate(`admin/translate/${slug}/${ch.num}`)
              }, 'แปล / แก้ไข'),
              el('button', {
                class: 'admin-btn delete',
                onclick: () => deleteChapter(slug, ch.num)
              }, 'ลบ')
            )
          )
        );
        tbody.appendChild(row);
      });

      // Wire EPUB Import Form
      const epubForm = $("epub-import-form");
      const epubFileInput = $("epub-file-input");
      const epubStartNum = $("epub-start-num");
      const epubStatus = $("epub-import-status");
      
      if (epubForm) {
        if (epubStatus) {
          epubStatus.style.display = "none";
          epubStatus.innerHTML = "";
        }
        if (epubFileInput) epubFileInput.value = "";
        
        epubForm.onsubmit = async (e) => {
          e.preventDefault();
          const file = epubFileInput ? epubFileInput.files[0] : null;
          const startNum = epubStartNum ? parseInt(epubStartNum.value, 10) || 1 : 1;
          
          if (!file) {
            showToast("กรุณาเลือกไฟล์ EPUB ก่อนนะคะพี่โชค! 🦊", "warning");
            return;
          }
          
          if (epubStatus) {
            epubStatus.style.display = "block";
            epubStatus.innerHTML = `<span style="color:var(--accent);">กำลังประมวลผลไฟล์ EPUB...</span>`;
          }
          
          const formData = new FormData();
          formData.append("epub", file);
          formData.append("start_num", startNum);
          
          try {
            const submitBtn = $("epub-import-submit-btn");
            if (submitBtn) {
              submitBtn.disabled = true;
              submitBtn.textContent = "กำลังนำเข้า...";
            }
            
            const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/import-epub`, {
              method: "POST",
              body: formData
            });
            
            const result = await res.json();
            if (!res.ok) throw new Error(result.error || res.statusText);
            
            showToast(`นำเข้าเนื้อหาสำเร็จเรียบร้อยแล้วค่ะ! 🦊✨`, "success");
            if (epubStatus) {
              epubStatus.innerHTML = `<span style="color:var(--success);">นำเข้าสำเร็จแล้วค่ะ!</span>`;
            }
            if (epubFileInput) epubFileInput.value = "";
            renderAdminChapters(params);
          } catch (err) {
            showToast(`นำเข้าล้มเหลว: ${err.message}`, "error");
            if (epubStatus) {
              epubStatus.innerHTML = `<span style="color:var(--error);">ล้มเหลว: ${err.message}</span>`;
            }
          } finally {
            const submitBtn = $("epub-import-submit-btn");
            if (submitBtn) {
              submitBtn.disabled = false;
              submitBtn.textContent = "นำเข้าเนื้อหา";
            }
          }
        };
      }

      const createBtn = $("admin-btn-create-chapter");
      if (createBtn) {
        createBtn.onclick = () => {
          const nextNum = chapters.length > 0 ? chapters[chapters.length - 1].num + 1 : 1;
          Router.navigate(`admin/translate/${slug}/${nextNum}`);
        };
      }

      const backBtn = $("admin-btn-back-to-novels");
      if (backBtn) {
        backBtn.onclick = () => Router.navigate("admin/novels");
      }
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="4" class="error" style="text-align:center;">โหลดไม่สำเร็จ: ${err.message}</td></tr>`;
    }

    async function deleteChapter(slug, num) {
      if (!confirm(`พี่โชคแน่ใจที่จะลบตอนที่ ${num} ใช่ไหมคะ?`)) return;
      try {
        const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/chapter/${num}/delete`, { method: 'POST' });
        if (!res.ok) throw new Error(res.statusText);
        // Refresh list
        renderAdminChapters(params);
      } catch (err) {
        showToast(`ลบตอนไม่สำเร็จ: ${err.message}`, "error");
      }
    }
  }

  // ── ADMIN TRANSLATE ────────────────────────────────────────────────────
  async function renderAdminTranslate(params) {
    const page = $("page-admin-translate");
    if (!page) return;
    
    const slug = params.slug;
    const num = parseInt(params.num, 10);
    if (!slug || !num) {
      showError(page, "ไม่พบข้อมูลตอนแปล");
      return;
    }

    const headerTitle = $("trans-novel-ch-title");
    const titleInput = $("trans-title-input");
    const sourceBlocksContainer = $("trans-source-blocks");
    const langSelect = $("trans-lang-select");
    const sourceFooterInput = $("trans-source-footer");

    if (headerTitle) headerTitle.textContent = `แปลตอนที่ ${num} — เรื่อง: ${slug}`;
    if (sourceBlocksContainer) sourceBlocksContainer.innerHTML = '<div class="skel skel-block" style="height:60px;"></div>';

    let chapterTitle = `ตอนที่ ${num}`;
    let lang = 'cn';
    let blocks = [];
    let sourceFooter = '';

    try {
      const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/chapter/${num}`);
      if (res.ok) {
        const detail = await res.json();
        if (detail.title) chapterTitle = detail.title;
        if (detail.lang) lang = detail.lang;
        if (detail.blocks && detail.blocks.length > 0) {
          blocks = detail.blocks.map(b => ({
            type: b.type || 'narration',
            text: b.text || '',
            speaker: b.speaker || ''
          }));
          sourceFooter = detail.source || '';
        } else if (detail.html) {
          const parser = new DOMParser();
          const doc = parser.parseFromString(detail.html, 'text/html');
          const paragraphs = doc.querySelectorAll('p');
          paragraphs.forEach(p => {
            let type = 'narration';
            let speaker = '';
            let text = p.innerText.trim();
            if (p.classList.contains('system-msg')) {
              type = 'system';
            } else if (p.classList.contains('dialogue')) {
              type = 'dialogue';
              speaker = p.dataset.speaker || '';
            } else if (p.classList.contains('game-title')) {
              type = 'game_title';
            } else if (p.classList.contains('end-marker')) {
              type = 'end';
            }
            blocks.push({ type, text, speaker });
          });
          
          const footerEl = doc.querySelector('.source-footer');
          if (footerEl) {
            sourceFooter = footerEl.innerText.trim();
            blocks = blocks.filter(b => b.text !== sourceFooter);
          }
        }
      } else {
        blocks = [{ type: 'narration', text: '', speaker: '' }];
      }
    } catch (err) {
      blocks = [{ type: 'narration', text: '', speaker: '' }];
    }

    if (titleInput) titleInput.value = chapterTitle;
    if (langSelect) langSelect.value = lang;
    if (sourceFooterInput) sourceFooterInput.value = sourceFooter;

    const renderBlocks = () => {
      if (!sourceBlocksContainer) return;
      sourceBlocksContainer.innerHTML = '';
      
      blocks.forEach((b, idx) => {
        const card = el('div', { class: 'trans-block-card', style: 'background:var(--bg-secondary); border:1px solid var(--border); border-radius:var(--radius-lg); padding:16px; display:flex; flex-direction:column; gap:12px;' },
          el('div', { class: 'trans-block-meta', style: 'display:flex; justify-content:space-between; align-items:center;' },
            el('select', {
              style: 'background:var(--bg-tertiary); border:1px solid var(--border); color:var(--text-primary); padding:4px 8px; border-radius:var(--radius-sm); font-size:0.75rem; outline:none;',
              onclick: (e) => e.stopPropagation(),
              onchange: (e) => {
                blocks[idx].type = e.target.value;
                renderBlocks();
              }
            },
              el('option', { value: 'narration', selected: b.type === 'narration' }, 'คำบรรยาย (Narration)'),
              el('option', { value: 'dialogue', selected: b.type === 'dialogue' }, 'บทสนทนา (Dialogue)'),
              el('option', { value: 'system', selected: b.type === 'system' }, 'ข้อความระบบ 【System】'),
              el('option', { value: 'game_title', selected: b.type === 'game_title' }, 'ชื่อเกม/ชื่อเรื่อง 《Title》'),
              el('option', { value: 'end', selected: b.type === 'end' }, 'ป้ายปิดท้าย (End Marker)')
            ),
            b.type === 'dialogue' ? el('input', {
              type: 'text',
              placeholder: 'ชื่อผู้พูด...',
              value: b.speaker || '',
              style: 'background:var(--bg-tertiary); border:1px solid var(--border); color:var(--text-primary); padding:4px 8px; border-radius:var(--radius-sm); font-size:0.8rem; width:120px; outline:none;',
              oninput: (e) => { blocks[idx].speaker = e.target.value; }
            }) : null,
            el('span', {
              class: 'trans-block-delete',
              style: 'cursor:pointer; color:var(--error); font-size:0.75rem; font-weight:700;',
              onclick: () => {
                blocks.splice(idx, 1);
                renderBlocks();
              }
            }, '✕ ลบย่อหน้านี้')
          ),
          el('textarea', {
            class: 'trans-textarea',
            style: 'width:100%; min-height:90px; background:var(--bg-tertiary); border:1px solid var(--border); color:var(--text-primary); padding:12px; border-radius:var(--radius-sm); font-size:0.95rem; line-height:1.65; resize:vertical; outline:none;',
            placeholder: 'กรอกเนื้อหาข้อความตรงนี้...',
            value: b.text || '',
            oninput: (e) => { blocks[idx].text = e.target.value; }
          })
        );
        sourceBlocksContainer.appendChild(card);
      });
    };
    
    renderBlocks();

    const autoBtn = $("trans-btn-auto");
    if (autoBtn) {
      autoBtn.onclick = async () => {
        const prof = getProfile();
        const email = prof ? prof.email : "";
        if (!email) {
          showToast("กรุณาเข้าสู่ระบบก่อนทำการแปลค่ะ 🦊", "error");
          return;
        }

        autoBtn.disabled = true;
        const originalText = autoBtn.innerHTML;
        autoBtn.innerHTML = "✨ กำลังแปลด้วย AI...";

        try {
          const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/chapter/${num}/auto-translate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.error || res.statusText);
          }

          const data = await res.json();
          if (data.ok && data.chapter) {
            const ch = data.chapter;
            blocks = ch.blocks || [];
            chapterTitle = ch.title || `ตอนที่ ${num}`;
            sourceFooter = ch.source || '';
            lang = ch.lang || 'cn';

            if (titleInput) titleInput.value = chapterTitle;
            if (langSelect) langSelect.value = lang;
            if (sourceFooterInput) sourceFooterInput.value = sourceFooter;

            renderBlocks();
            showToast("แปลอัตโนมัติด้วย AI สำเร็จแล้วค่ะพี่โชค! 🦊✨", "success");
          } else {
            throw new Error("Invalid response from server");
          }
        } catch (err) {
          showToast(`แปลด้วย AI ไม่สำเร็จ: ${err.message}`, "error");
        } finally {
          autoBtn.disabled = false;
          autoBtn.innerHTML = originalText;
        }
      };
    }

    const saveBtn = $("trans-btn-save");
    if (saveBtn) {
      saveBtn.onclick = async () => {
        const saveTitle = titleInput.value.trim() || `ตอนที่ ${num}`;
        const saveLang = langSelect.value;
        const saveSourceFooter = sourceFooterInput.value.trim();
        
        try {
          const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/chapter/${num}/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: saveTitle,
              lang: saveLang,
              blocks,
              source: saveSourceFooter
            })
          });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.details || errData.error || res.statusText);
          }
          // Clear chapter cache for this novel
          delete chaptersCache[slug];
          Router.navigate(`admin/chapters/${slug}`);
        } catch (err) {
          showToast(`บันทึกตอนไม่สำเร็จ: ${err.message}`, "error");
        }
      };
    }

    const cancelBtn = $("trans-btn-cancel");
    if (cancelBtn) {
      cancelBtn.onclick = () => {
        Router.navigate(`admin/chapters/${slug}`);
      };
    }

    const addBlockBtn = $("trans-btn-add-block");
    if (addBlockBtn) {
      addBlockBtn.onclick = () => {
        blocks.push({ type: 'narration', text: '', speaker: '' });
        renderBlocks();
        const col = sourceBlocksContainer.closest('.translation-column');
        if (col) col.scrollTop = col.scrollHeight;
      };
    }
  }

  // ── ADMIN USERS ────────────────────────────────────────────────────────
  async function renderAdminUsers(params) {
    const page = $("page-admin-users");
    if (!page) return;

    // Inject sub nav
    let navContainer = page.querySelector(".admin-nav-tabs");
    if (!navContainer) {
      navContainer = el("div", { class: "admin-nav-tabs" });
      page.insertBefore(navContainer, page.firstChild);
    }
    navContainer.innerHTML = renderAdminNav("users");

    const tbody = $("admin-users-tbody");
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:32px;"><div class="skel skel-line" style="margin-bottom:12px;"></div><div class="skel skel-line"></div></td></tr>';
    
    try {
      const res = await fetch("/api/admin/users");
      if (!res.ok) throw new Error("Failed to load users from backend");
      const users = await res.json();
      
      tbody.innerHTML = "";
      users.forEach((u, uIdx) => {
        const roleSelect = el("select", {
          style: "background:var(--bg-tertiary); border:1px solid var(--border); color:var(--text-primary); padding:4px 8px; border-radius:var(--radius-sm); font-size:0.8rem; outline:none;",
          onchange: async (e) => {
            const newRole = e.target.value;
            u.role = newRole;
            u.tokensLimit = newRole === "admin" ? -1
                          : newRole === "paid" ? 1000
                          : newRole === "user" ? 50
                          : 10000;
            
            // Save updated users back to backend
            try {
              const saveRes = await fetch("/api/admin/users/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(users)
              });
              if (saveRes.ok) {
                showToast(`เปลี่ยนบทบาทของ ${u.name} เป็น ${newRole.toUpperCase()} เรียบร้อยแล้วค่ะ! 🦊💅`);
                renderAdminUsers(params);
              } else {
                throw new Error("Failed to save updated users");
              }
            } catch (saveErr) {
              showToast(`บันทึกการเปลี่ยนแปลงไม่สำเร็จ: ${saveErr.message}`, true);
            }
          }
        },
          Object.keys(ROLES_CONFIG).map(r => el("option", { value: r, selected: u.role === r }, r.toUpperCase()))
        );

        const usageStr = u.tokensLimit === -1 ? "ไม่จำกัด" : `${u.tokensUsed.toLocaleString()} / ${u.tokensLimit.toLocaleString()} tokens`;
        const row = el("tr", {},
          el("td", { style: "font-weight:600;" }, u.name),
          el("td", { style: "color: var(--text-secondary); font-family:var(--font-mono);" }, u.email),
          el("td", {}, roleSelect),
          el("td", { style: "font-family:var(--font-mono); font-size:0.8rem;" }, usageStr),
          el("td", { style: u.active === "ออนไลน์" ? "color: var(--accent); font-weight:600;" : "color: var(--text-muted);" }, u.active)
        );
        tbody.appendChild(row);
      });
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--error);">โหลดไม่สำเร็จ: ${err.message}</td></tr>`;
    }
  }

  // ── ADMIN GLOSSARY ─────────────────────────────────────────────────────
  async function renderAdminGlossary(params) {
    const page = $("page-admin-glossary");
    if (!page) return;

    const slug = params.slug || 'global-descent';

    // Inject sub nav
    let navContainer = page.querySelector(".admin-nav-tabs");
    if (!navContainer) {
      navContainer = el("div", { class: "admin-nav-tabs" });
      page.insertBefore(navContainer, page.firstChild);
    }
    navContainer.innerHTML = renderAdminNav("glossary");

    const tbody = $("glossary-tbody");
    const rulesContainer = $("style-rules-container");
    if (!tbody || !rulesContainer) return;

    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:32px;"><div class="skel skel-line" style="margin-bottom:12px;"></div><div class="skel skel-line"></div><div class="skel skel-line" style="width:40%;"></div></td></tr>';
    rulesContainer.innerHTML = '<div class="skel skel-line" style="margin-bottom:12px;"></div><div class="skel skel-line"></div>';

    try {
      const data = await api(`/api/novel/${encodeURIComponent(slug)}/glossary/data`);
      const terms = data.terms || [];
      const rules = data.rules || {};

      tbody.innerHTML = '';
      
      function renderRow(t) {
        const tr = el('tr', {},
          el('td', {}, el('input', { type: 'text', value: t.source || '', class: 'glossary-in-source', style: 'width:100%; background:transparent; border:none; color:var(--text-primary); font-size:0.8rem; outline:none;' })),
          el('td', {}, el('input', { type: 'text', value: t.thai || '', class: 'glossary-in-thai', style: 'width:100%; background:transparent; border:none; color:var(--text-primary); font-size:0.8rem; outline:none;' })),
          el('td', {}, el('input', { type: 'text', value: t.category || '', class: 'glossary-in-category', style: 'width:100%; background:transparent; border:none; color:var(--text-primary); font-size:0.8rem; outline:none;' })),
          el('td', {}, el('select', { class: 'glossary-in-lock', style: 'background:var(--bg-tertiary); border:none; color:var(--text-primary); font-size:0.8rem; outline:none;' },
            el('option', { value: 'locked', selected: t.lock === 'locked' }, 'locked'),
            el('option', { value: 'reference', selected: t.lock === 'reference' }, 'reference'),
            el('option', { value: 'auto', selected: t.lock === 'auto' || !t.lock }, 'auto')
          )),
          el('td', {}, el('input', { type: 'text', value: t.notes || '', class: 'glossary-in-notes', style: 'width:100%; background:transparent; border:none; color:var(--text-primary); font-size:0.8rem; outline:none;' })),
          el('td', { style: 'text-align:center;' }, el('span', {
            style: 'cursor:pointer; color:var(--error); font-weight:bold; font-size:1.1rem;',
            onclick: () => tr.remove()
          }, '✕'))
        );
        return tr;
      }

      terms.forEach(t => {
        tbody.appendChild(renderRow(t));
      });

      rulesContainer.innerHTML = '';
      const groups = ['punctuation', 'naturalness', 'policies'];
      groups.forEach(group => {
        const items = rules[group] || [];
        const lines = items.map(item => item.text || item).join('\n');
        
        const ruleGroup = el('div', { style: 'display:flex; flex-direction:column; gap:6px;' },
          el('label', { style: 'font-size:0.8rem; font-weight:600; color:var(--accent); text-transform:uppercase;' }, group),
          el('textarea', {
            class: 'style-rule-textarea',
            dataset: { group },
            style: 'background:var(--bg-tertiary); border:1px solid var(--border); color:var(--text-primary); padding:8px 12px; border-radius:var(--radius-sm); font-size:0.85rem; font-family:var(--font-mono); height:120px; resize:vertical; outline:none;',
            value: lines
          })
        );
        rulesContainer.appendChild(ruleGroup);
      });

      const searchInput = $("glossary-search");
      if (searchInput) {
        searchInput.value = '';
        searchInput.oninput = (e) => {
          const q = e.target.value.toLowerCase().trim();
          const rows = tbody.querySelectorAll('tr');
          rows.forEach(row => {
            const srcInput = row.querySelector('.glossary-in-source');
            const thInput = row.querySelector('.glossary-in-thai');
            const catInput = row.querySelector('.glossary-in-category');
            const notesInput = row.querySelector('.glossary-in-notes');
            
            const src = srcInput ? srcInput.value.toLowerCase() : '';
            const th = thInput ? thInput.value.toLowerCase() : '';
            const cat = catInput ? catInput.value.toLowerCase() : '';
            const notes = notesInput ? notesInput.value.toLowerCase() : '';
            
            if (!q || src.includes(q) || th.includes(q) || cat.includes(q) || notes.includes(q)) {
              row.style.display = '';
            } else {
              row.style.display = 'none';
            }
          });
        };
      }

      const addTermBtn = $("glossary-btn-add-term");
      if (addTermBtn) {
        addTermBtn.onclick = () => {
          if (searchInput) {
            searchInput.value = '';
            tbody.querySelectorAll('tr').forEach(r => r.style.display = '');
          }
          const newRow = renderRow({ source: '', thai: '', category: 'ตัวละคร', lock: 'auto', notes: '' });
          tbody.appendChild(newRow);
          const sourceIn = newRow.querySelector('.glossary-in-source');
          if (sourceIn) sourceIn.focus();
        };
      }

      const backBtn = $("glossary-btn-back-to-dash");
      if (backBtn) {
        backBtn.onclick = () => {
          Router.navigate("admin");
        };
      }

      const saveBtn = $("glossary-btn-save");
      if (saveBtn) {
        saveBtn.onclick = async () => {
          saveBtn.disabled = true;
          saveBtn.textContent = 'กำลังบันทึก...';
          
          const saveTermsPayload = [];
          tbody.querySelectorAll('tr').forEach(tr => {
            const srcIn = tr.querySelector('.glossary-in-source');
            const thIn = tr.querySelector('.glossary-in-thai');
            const catIn = tr.querySelector('.glossary-in-category');
            const lockSel = tr.querySelector('.glossary-in-lock');
            const notesIn = tr.querySelector('.glossary-in-notes');
            
            const source = srcIn ? srcIn.value.trim() : '';
            const thai = thIn ? thIn.value.trim() : '';
            if (!source || !thai) return;
            
            saveTermsPayload.push({
              source,
              thai,
              category: catIn ? catIn.value.trim() : 'ตัวละคร',
              lock: lockSel ? lockSel.value : 'auto',
              notes: notesIn ? notesIn.value.trim() : '',
              priority: 3
            });
          });

          const saveRulesPayload = {};
          rulesContainer.querySelectorAll('.style-rule-textarea').forEach(ta => {
            const group = ta.dataset.group;
            const lines = ta.value.split('\n').map(l => l.trim()).filter(Boolean);
            saveRulesPayload[group] = lines.map(text => ({ text }));
          });

          try {
            const res = await fetch(`/api/novel/${encodeURIComponent(slug)}/glossary/save`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ terms: saveTermsPayload, rules: saveRulesPayload })
            });
            if (!res.ok) throw new Error(res.statusText);
            showToast('บันทึกคลังคำศัพท์และกฎสำเร็จเรียบร้อยแล้วค่ะพี่โชค! 🦊✨', "success");
            renderAdminGlossary(params);
          } catch (saveErr) {
            showToast(`บันทึกไม่สำเร็จ: ${saveErr.message}`, "error");
          } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'บันทึกข้อมูลทั้งหมด';
          }
        };
      }

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="6" class="error" style="text-align:center;">โหลดคำศัพท์ไม่สำเร็จ: ${err.message}</td></tr>`;
      rulesContainer.innerHTML = `<p class="error">โหลดกฎไม่สำเร็จ: ${err.message}</p>`;
    }
  }

  // ── NOTIFICATIONS ──────────────────────────────────────────────────────
  async function renderNotifications(params) {
    const page = $("page-notifications");
    if (!page) return;
    showSkeleton(page);

    try {
      const notifications = await api("/api/notifications");
      
      let html = `
      <section class="dash-section">
        <div class="section-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
          <h3 class="section-title">🔔 การแจ้งเตือนทั้งหมด</h3>
          ${notifications.some(n => !n.read) ? `<button class="btn btn-sm btn-ghost" id="notif-mark-read" style="font-size:11px; font-weight:600; color:var(--accent);">ทำเครื่องหมายว่าอ่านแล้วทั้งหมด</button>` : ""}
        </div>
        <div class="notifications-list" style="display:flex; flex-direction:column; gap:12px;">
      `;

      if (notifications.length === 0) {
        html += `
        <div style="text-align:center; padding:48px; background:var(--bg-secondary); border:1px dashed var(--border); border-radius:var(--radius-lg); color:var(--text-muted); font-size:13px;">
          ไม่มีการแจ้งเตือนใด ๆ ค่ะ ✨
        </div>
        `;
      } else {
        const sorted = [...notifications].sort((a,b) => b.ts - a.ts);
        sorted.forEach(n => {
          const isUnread = !n.read;
          const bgStyle = isUnread ? "background:var(--bg-secondary); border-left:3px solid var(--accent);" : "background:var(--bg-secondary); opacity:0.85;";
          const dotStyle = isUnread ? "display:inline-block; width:6px; height:6px; background:var(--accent); border-radius:50%; margin-right:8px;" : "display:none;";
          
          html += `
          <div class="notif-card" style="${bgStyle} border-top:1px solid var(--border); border-right:1px solid var(--border); border-bottom:1px solid var(--border); border-radius:var(--radius); padding:16px; display:flex; flex-direction:column; gap:6px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="${dotStyle}"></span>
              <span style="font-size:0.92rem; color:var(--text-primary); font-weight:${isUnread ? "600" : "400"}; line-height:1.5; flex:1;">${esc(n.text)}</span>
            </div>
            <span style="font-size:10px; color:var(--text-muted); font-family:var(--font-mono); align-self:flex-end;">${new Date(n.ts).toLocaleString("th-TH", {day:"numeric", month:"short", hour:"2-digit", minute:"2-digit"})}</span>
          </div>
          `;
        });
      }

      html += `</div></section>`;
      page.innerHTML = html;

      const markReadBtn = $("notif-mark-read");
      if (markReadBtn) {
        markReadBtn.onclick = async () => {
          try {
            markReadBtn.disabled = true;
            markReadBtn.textContent = "กำลังดำเนินการ...";
            const res = await fetch("/api/notifications/read", { method: "POST" });
            if (!res.ok) throw new Error(res.statusText);
            
            renderNotifications(params);
            updateNotificationBadge();
          } catch (err) {
            showToast(`ไม่สามารถทำเครื่องหมายว่าอ่านแล้วได้: ${err.message}`, "error");
          }
        };
      }

      updateNotificationBadge();

    } catch (err) {
      showError(page, "โหลดไม่สำเร็จ", err.message);
    }
  }

  async function updateNotificationBadge() {
    const notifBtn = $("notif-btn");
    if (!notifBtn) return;
    try {
      const notifications = await api("/api/notifications");
      const unreadCount = notifications.filter(n => !n.read).length;
      
      notifBtn.style.position = "relative";
      
      const oldBadge = notifBtn.querySelector(".notif-badge");
      if (oldBadge) oldBadge.remove();
      
      if (unreadCount > 0) {
        const badge = el("span", {
          class: "notif-badge",
          style: "position: absolute; top: -2px; right: -2px; background: var(--error); color: #fff; font-size: 8px; min-width: 14px; height: 14px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 1.5px solid var(--bg-secondary); padding: 2px;"
        }, String(unreadCount));
        notifBtn.appendChild(badge);
      }
    } catch (err) {
      console.warn("Failed to update notification badge:", err);
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // REGISTER WITH ROUTER
  // ═══════════════════════════════════════════════════════════════════════

  // ── Single shared keyboard handler for reader ────────────────────────
  let _readerKeyHandler = null;

  function init() {
    // Register all page renderers
    if (window.Router) {
      Router.register("home", renderHome);
      Router.register("library", renderLibrary);
      Router.register("search", renderSearch);
      Router.register("ranking", renderRanking);
      Router.register("reader", renderReader);
      Router.register("novel-detail", renderNovelDetail);
      Router.register("profile", renderProfile);
      Router.register("history", renderHistory);
      Router.register("bookmarks", renderBookmarks);
      Router.register("settings", renderSettings);
      Router.register("notifications", renderNotifications);
      Router.register("admin", renderAdmin);
      Router.register("admin-novels", renderAdminNovels);
      Router.register("admin-novel-edit", renderAdminNovelEdit);
      Router.register("admin-chapters", renderAdminChapters);
      Router.register("admin-translate", renderAdminTranslate);
      Router.register("admin-users", renderAdminUsers);
      Router.register("admin-glossary", renderAdminGlossary);

      // Fix initial route race: Router.init() fires handleRoute on DOMContentLoaded
      // BEFORE page-renderers registers. Force re-render after registration.
      setTimeout(() => {
        window.dispatchEvent(new Event("hashchange"));
      }, 0);
    }

    // Topbar notification bell click
    const notifBtn = document.getElementById("notif-btn");
    if (notifBtn) {
      notifBtn.addEventListener("click", () => {
        Router.navigate("notifications");
      });
    }

    // Update notification badge on boot
    updateNotificationBadge();

    // Update activity feed every 30s
    updateActivityFeed();
    setInterval(updateActivityFeed, 30000);

    // Sidebar theme toggle
    const themeToggle = document.getElementById("theme-toggle-new");
    if (themeToggle) {
      themeToggle.addEventListener("click", () => {
        const current = document.body.dataset.theme || "dark";
        const target = current === "dark" ? "light" : "dark";
        document.body.dataset.theme = target;
        themeToggle.classList.toggle("active", target === "dark");
        
        // Save to state
        const s = loadState(); s.theme = target;
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}

        // Sync setting page dropdown if visible
        const settingsTheme = document.getElementById("settings-theme");
        if (settingsTheme) settingsTheme.value = target;
      });
    }

    // Sidebar AI Translate toggle
    const translateToggle = document.getElementById("translate-toggle-new");
    if (translateToggle) {
      translateToggle.addEventListener("click", () => {
        translateToggle.classList.toggle("active");
      });
    }

    // Initialize topbar avatar
    updateTopbarAvatar(getProfile());

    // Initialize theme from localStorage on boot
    const savedTheme = loadState().theme || "dark";
    document.body.dataset.theme = savedTheme;
    if (themeToggle) {
      themeToggle.classList.toggle("active", savedTheme === "dark");
    }
  }

  // Auto-init
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

})();
