# CSS Audit — Phase A

## Overview

Single CSS file: `reader/public/design-system.css`
- 1,574 lines, ~60KB
- ITCSS 5-layer structure (tokens → generic → elements → BEM components → utilities)
- Inline SVG sprite in index.html (no external SVG sprite file)

## Strengths

✅ CSS variables for spacing (`--space-sm`, `--space-md`, `--space-lg`)
✅ CSS variables for colors (theme-dependent via `body[data-theme]`)
✅ CSS variables for radius, shadow, typography
✅ BEM naming convention (`c-card`, `c-card__title`, `c-card__cover`)
✅ Only ONE CSS file — no import spaghetti
✅ Tokens section at top of file

## Issues Found

### 1. `--space-*` Token Scale Mismatch with Roadmap Spec
Roadmap specifies: `--space-1: 4px` through `--space-6: 32px`
Current: `--space-2xs: 2px` through `--space-3xl: 64px`

**Difference**: Roadmap wants numeric scale (1-6), current uses named scale (2xs-3xl). 
**Assessment**: Current scale is more descriptive. Either keep as-is or migrate to 1-6. MIGRATING BREAKS EXISTING USAGE.

### 2. `--radius-*` Scale Mismatch
Roadmap: `--radius-sm: 8px`, `--radius-md: 12px`, `--radius-lg: 18px`
Current: `--radius-sm: 6px`, `--radius: 10px`, `--radius-lg: 14px`, `--radius-xl: 18px`, `--radius-full: 9999px`

**Assessment**: Current values are fine. Keep current.

### 3. Critical Layout Rules Are Inline (Through JS)
Despite CSS organization, many layout rules are set inline via JS:

**In `home.js`**: Most card rendering uses inline styles
**In `admin.js`**: Stats grid, badges, cards all use inline styles in template strings
**In `pages.js`**: Library sort dropdown, search results, ranking items use inline styles
**In `novel.js`**: Cover gradient, progress bar all inline

**This is the BIGGEST CSS issue** — the JS code generates HTML with inline styles instead of using CSS classes.

### 4. Missing Layout Tokens from Roadmap
Roadmap wants:
- `--app-sidebar-width: 300px` — Current: `--sidebar-w: 280px` (close but different value)
- `--app-rightbar-width: 320px` — Current: `--rightbar-w: 300px`
- `--app-content-max: 1120px` — Current: `--page-max-admin: 1120px` (there, named differently)
- `--reader-width: 820px` — Current: `--reader-max-w: 800px`
- `--motion-fast: 160ms` — Missing
- `--motion-med: 220ms` — Missing

### 5. Reader Typography Uses Direct Values
In `reader.js`, the renderer applies `--reader-font-size` and `--reader-line-height` as CSS custom properties on `<html>`. This is correct, but no CSS fallback exists if the JS fails to set them.

### 6. No Mobile Breakpoints Section
Responsive rules are scattered throughout the CSS file. No single `@media` section for mobile/tablet.

### 7. Inline SVG in HTML
All SVG icons (18 symbols) and mascot (3 expressions) are inline in `index.html`. This works but adds ~300 lines to the HTML file. An external SVG sprite file would be cleaner but adds an HTTP request.

## Priority Fixes

1. **High**: Move critical inline styles from JS into CSS classes:
   - Card grid layouts
   - Stats grid
   - Badge styling
   - Profile gradients
   - Progress bars

2. **Medium**: Add `--motion-fast` and `--motion-med` animation duration tokens

3. **Medium**: Consolidate sidebar/rightbar/reader width tokens to match roadmap spec

4. **Low**: Add centralized responsive breakpoints section

## CSS Size Impact
- Current: ~60KB (minifiable to ~40KB)
- Acceptable for single-page app
- No render-blocking CSS split needed
