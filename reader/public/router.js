/* ═══════════════════════════════════════════════════════════
   NovelClaw Router v1 — Hash-based SPA Router
   ═══════════════════════════════════════════════════════════ */

const Router = (() => {
  "use strict";

  // ── Route Definitions ─────────────────────────────────────
  const routes = {
    "home":        { page: "home", title: "Home" },
    "novel":       { page: "novel-detail", title: "Novel" },
    "reader":      { page: "reader", title: "Reader" },
    "library":     { page: "library", title: "Library" },
    "search":      { page: "search", title: "Search" },
    "ranking":     { page: "ranking", title: "Ranking" },
    "profile":     { page: "profile", title: "Profile" },
    "history":     { page: "history", title: "History" },
    "bookmarks":   { page: "bookmarks", title: "Bookmarks" },
    "downloads":   { page: "downloads", title: "Downloads" },
    "notifications": { page: "notifications", title: "Notifications" },
    "settings":    { page: "settings", title: "Settings" },
    "admin":       { page: "admin", title: "Admin" },
    "admin-novels": { page: "admin-novels", title: "Novel Management" },
    "admin-chapters": { page: "admin-chapters", title: "Chapter Management" },
    "admin-translate": { page: "admin-translate", title: "Translation Center" },
    "admin-translate-job": { page: "admin-translate-job", title: "Translation Compare" },
    "admin-novel-edit": { page: "admin-novel-edit", title: "Novel Metadata" },
    "admin-users": { page: "admin-users", title: "User Management" },
    "admin-glossary": { page: "admin-glossary", title: "Glossary & Style Rules" },
  };

  // ── Route Parser ───────────────────────────────────────────
  function parseHash(hash) {
    const h = hash.replace(/^#/, "");
    const parts = h.split("/").filter(Boolean);

    // Default
    if (!parts.length || parts[0] === "home") {
      return { route: "home", params: {} };
    }

    // #novel/:slug
    if (parts[0] === "novel" && parts.length === 2) {
      return { route: "novel", params: { slug: parts[1] } };
    }

    // #novel/:slug/:num (reader)
    if (parts[0] === "novel" && parts.length === 3) {
      return { route: "reader", params: { slug: parts[1], chapter: parts[2] } };
    }

    // #admin
    if (parts[0] === "admin") {
      if (parts[1] === "novels") return { route: "admin-novels", params: {} };
      if (parts[1] === "chapters" && parts[2]) return { route: "admin-chapters", params: { slug: parts[2] } };
      if (parts[1] === "translate") {
        return { route: "admin-translate", params: { slug: parts[2] || "", num: parts[3] || "" } };
      }
      if (parts[1] === "novel-edit") return { route: "admin-novel-edit", params: { slug: parts[2] || "" } };
      if (parts[1] === "users") return { route: "admin-users", params: {} };
      if (parts[1] === "glossary") return { route: "admin-glossary", params: { slug: parts[2] || "" } };
      return { route: "admin", params: {} };
    }

    // Simple routes: #library, #search, #ranking, etc.
    if (routes[parts[0]]) {
      return { route: parts[0], params: {} };
    }

    // Fallback to home
    return { route: "home", params: {} };
  }

  // ── State ──────────────────────────────────────────────────
  let currentRoute = null;
  let currentParams = {};
  let pageRenderers = {};

  // ── Navigation ─────────────────────────────────────────────
  function navigate(path) {
    window.location.hash = path;
  }

  function getNavItem(page) {
    const map = {
      "home": "",
      "library": "library",
      "search": "search",
      "ranking": "ranking",
      "profile": "profile",
      "history": "history",
      "bookmarks": "bookmarks",
      "downloads": "downloads",
      "notifications": "notifications",
      "settings": "settings",
      "admin": "admin",
    };
    return map[page] || null;
  }

  // ── Route Handler ──────────────────────────────────────────
  function handleRoute() {
    const { route, params } = parseHash(window.location.hash);
    const config = routes[route];

    if (!config) {
      navigate("home");
      return;
    }

    // Update active states
    document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
    const navKey = getNavItem(config.page);
    if (navKey) {
      const navEl = document.querySelector(`.nav-item[data-page="${navKey}"]`);
      if (navEl) navEl.classList.add("active");
    }

    // Update main header title
    const headerTitle = document.getElementById("page-title");
    if (headerTitle) headerTitle.textContent = config.title;

    // Show/hide pages
    document.querySelectorAll(".page").forEach(el => el.classList.remove("active"));
    const pageEl = document.getElementById(`page-${config.page}`);
    if (pageEl) pageEl.classList.add("active");

    // Toggle rightbar visibility depending on route
    const appEl = document.getElementById("app-layout");
    if (appEl) {
      const hideRightbarRoutes = [
        "reader",
        "admin-novels",
        "admin-chapters",
        "admin-translate",
        "admin-novel-edit",
        "admin-users",
        "admin-glossary"
      ];
      if (hideRightbarRoutes.includes(route)) {
        appEl.classList.add("has-no-rightbar");
      } else {
        appEl.classList.remove("has-no-rightbar");
      }
    }

    // Route params display
    const paramEl = document.getElementById("route-params");
    if (paramEl && Object.keys(params).length) {
      paramEl.textContent = JSON.stringify(params);
      paramEl.style.display = "inline";
    } else if (paramEl) {
      paramEl.style.display = "none";
    }

    // Call page renderer if exists
    if (pageRenderers[config.page]) {
      pageRenderers[config.page](params);
    }

    currentRoute = route;
    currentParams = params;
  }

  // ── Register Page Renderer ────────────────────────────────
  function register(page, renderFn) {
    pageRenderers[page] = renderFn;
  }

  // ── Init ───────────────────────────────────────────────────
  function init() {
    window.addEventListener("hashchange", handleRoute);
    // Handle initial route
    if (!window.location.hash) {
      window.location.hash = "home";
    } else {
      handleRoute();
    }
    // Handle sidebar nav clicks
    document.querySelectorAll(".nav-item").forEach(el => {
      el.addEventListener("click", () => {
        const page = el.dataset.page;
        if (page) navigate(page);
      });
    });
    // Restore collapsed states on page load (desktop only)
    const appEl = document.getElementById("app-layout");
    if (appEl && window.innerWidth > 768) {
      if (localStorage.getItem("sidebar-collapsed") === "true") {
        appEl.classList.add("sidebar-collapsed");
      }
    }
    if (appEl && window.innerWidth > 1024) {
      if (localStorage.getItem("rightbar-collapsed") === "true") {
        appEl.classList.add("rightbar-collapsed");
      }
    }

    // Left Sidebar Toggle
    const toggleBtn = document.getElementById("sidebar-toggle");
    const sidebarClose = document.getElementById("sidebar-close");
    const sidebar = document.querySelector(".sidebar");
    const overlay = document.getElementById("sidebar-overlay");

    function toggleLeftSidebar() {
      if (window.innerWidth <= 768) {
        sidebar.classList.toggle("open");
        if (overlay) {
          overlay.style.display = sidebar.classList.contains("open") ? "block" : "none";
        }
      } else {
        if (appEl) {
          appEl.classList.toggle("sidebar-collapsed");
          localStorage.setItem("sidebar-collapsed", appEl.classList.contains("sidebar-collapsed"));
        }
      }
    }

    if (toggleBtn) toggleBtn.addEventListener("click", toggleLeftSidebar);
    if (sidebarClose) sidebarClose.addEventListener("click", () => {
      if (window.innerWidth <= 768) {
        sidebar.classList.remove("open");
        if (overlay) overlay.style.display = "none";
      } else {
        if (appEl) {
          appEl.classList.add("sidebar-collapsed");
          localStorage.setItem("sidebar-collapsed", "true");
        }
      }
    });

    if (overlay) {
      overlay.addEventListener("click", () => {
        if (sidebar) sidebar.classList.remove("open");
        const rightbar = document.querySelector(".rightbar");
        if (rightbar) rightbar.classList.remove("open");
        overlay.style.display = "none";
      });
    }

    // Right Sidebar Toggle
    const rightbarToggle = document.getElementById("rightbar-toggle");
    const rightbarClose = document.getElementById("rightbar-close");
    const rightbar = document.querySelector(".rightbar");

    function toggleRightSidebar() {
      if (window.innerWidth <= 1024) {
        if (rightbar) {
          rightbar.classList.toggle("open");
          if (overlay) {
            overlay.style.display = rightbar.classList.contains("open") ? "block" : "none";
          }
        }
      } else {
        if (appEl) {
          appEl.classList.toggle("rightbar-collapsed");
          localStorage.setItem("rightbar-collapsed", appEl.classList.contains("rightbar-collapsed"));
        }
      }
    }

    if (rightbarToggle) rightbarToggle.addEventListener("click", toggleRightSidebar);
    if (rightbarClose) rightbarClose.addEventListener("click", () => {
      if (window.innerWidth <= 1024) {
        if (rightbar) rightbar.classList.remove("open");
        if (overlay) overlay.style.display = "none";
      } else {
        if (appEl) {
          appEl.classList.add("rightbar-collapsed");
          localStorage.setItem("rightbar-collapsed", "true");
        }
      }
    });
  }

  // ── Public API ─────────────────────────────────────────────
  return { init, navigate, register, getCurrentRoute: () => currentRoute, getParams: () => currentParams };
})();
window.Router = Router;

// Auto-init when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", Router.init);
} else {
  Router.init();
}
