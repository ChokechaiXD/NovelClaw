# Frontend Architecture Cleanup — Phase C

## Component Inventory

### Already Extracted (in components.js)

| Component | Used By | Count |
|-----------|---------|-------|
| `Ui.$(id)` | All pages | 16+ |
| `Ui.esc(s)` | All pages | 16+ |
| `Ui.el(tag, attrs, ...children)` | novel.js, components.js | 2 |
| `Ui.slugToHue(slug)` | home.js, pages.js, novel.js | 3 |
| `Ui.showSkeleton(container, type)` | home.js, admin.js, pages.js | 6+ |
| `Ui.showEmpty(container, title, desc)` | home.js, admin.js, pages.js | 4 |
| `Ui.showError(container, title, desc)` | All pages | 8+ |
| `Ui.displayTitle(novel)` | home.js, admin.js, pages.js, reader.js | 6+ |
| `Ui.coverSVG(slug, title)` | home.js | 1 |
| `Ui.showToast(message, type)` | app.js, admin.js, reader.js | 3 |
| `Ui.statusMap` | admin.js, novel.js | 2 |
| `Ui.enrichNovel(novel)` | home.js, novel.js | 2 |
| `Ui.updateAvatar()` | app.js | 1 |

### Repeated Patterns (need extraction)

| Pattern | Locations | Count |
|---------|-----------|-------|
| **Data table** (thead + tbody) | AdminNovelsPage, AdminChaptersPage, AdminJobsPage, AdminGlossaryPage | 4 |
| **Admin nav tabs** (`renderAdminNav()`) | All admin pages | 7 |
| **Cover card with gradient** | home.js (hero + card-grid), pages.js (library + search), novel.js (detail) | 5 |
| **Stat grid** (4 stat cards) | AdminDashboardPage, app.js (rightbar-stats) | 2 |
| **Copy-to-clipboard button** | AdminJobsPage | 1 (but pattern exists) |
| **Section header** (`c-section__header` + title + link) | home.js, admin.js, pages.js | 10+ |

## Issues Found

### 1. Divergent localStorage Key
**File**: admin.js line 262
**Key**: `'nc-bookmarks'`
**Standard**: `novelclaw-*` prefix
**Fix**: Change to `'novelclaw-bookmarks'`

### 2. Inline Styles in JS (CSS Audit covered this)
Many templates generate inline `style="..."` attributes. Top offenders:
- home.js: ~20 inline styles
- admin.js (AdminDashboardPage): ~15 inline styles
- pages.js (LibraryPage, RankingPage, ProfilePage): ~25 inline styles
- novel.js: ~8 inline styles

### 3. `renderAdminNav()` Hardcoded in admin.js
Should be in components.js as `Ui.AdminNav(active)` for reuse potential.

### 4. SectionHeader Pattern Un-extracted
The pattern `<div class="c-section__header"><h3 class="c-section__title">...</h3>...</div>` appears 10+ times.
Could be `Ui.SectionHeader(title, { link, icon, badge })`.

## Priority Fixes

### P1: localStorage key standardization
Fix `nc-bookmarks` → `novelclaw-bookmarks`

### P2: Move `renderAdminNav` to components.js
Rename to `Ui.adminNav(active)`

### P2: Extract DataTable component
Admin tables share: `<div class="c-table-wrap"><table class="c-table"><thead>...</thead><tbody>...</tbody></table></div>`

### P3: Extract StatGrid component
Admin dashboard uses stats grid pattern. Could be `Ui.statGrid(items)`.

## Standardized State Keys (From Roadmap)

| Current Key | Standardized Key | Already Standard? |
|-------------|-----------------|------------------|
| `novelclaw-settings.theme` | `novelclaw.theme` | ✗ (uses `novelclaw-settings`) |
| `novelclaw-settings.sidebarCollapsed` | `novelclaw.sidebar.collapsed` | ✗ |
| `novelclaw-settings.fontSize` | `novelclaw.reader.fontSize` | ✗ |
| `novelclaw-settings.lineHeight` | `novelclaw.reader.lineHeight` | ✗ |
| — | `novelclaw.reader.theme` | Missing |
| `novelclaw-settings.readerLang` | `novelclaw.reader.language` | ✗ |
| — | `novelclaw.admin.showHidden` | Missing |
| `nc-bookmarks` | `novelclaw.bookmarks` | ❌ Divergent key |
| `novelclaw-state` | `novelclaw.state` | ✓ Close enough |

**Note**: Changing key names breaks existing user settings. Do only with migration logic or postpone to major version.
