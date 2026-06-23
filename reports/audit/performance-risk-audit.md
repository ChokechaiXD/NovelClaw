# Performance Risk Audit — Phase A

## 1. Large Chapter DOM

**Risk**: High
**Scenario**: Chapter 139 has 244 paragraphs. Some chapters could be larger.
**Current behavior**: All paragraphs rendered into DOM at once.
**Mitigation**: None yet.

## 2. Search Index Growth

**Risk**: Medium
**Scenario**: 1,239 chapters × ~10KB text each = ~12MB index file
**Current**: search-index.th.json stores `text` field at 10,000 chars max per entry
**Risk**: Index rebuild becomes slow. Index file becomes large.

## 3. Admin Chapter List with 1,000+ Rows

**Risk**: Medium
**Scenario**: AdminChaptersPage renders 100 chapters per page (pagination exists)
**Current**: Page size = 100. Filtering/search is client-side only.
**Risk**: The data is fetched ALL at once (via getChapters() which loads the index). This is fine since index is ~50KB. But switching between pages could be slow if DOM large.

## 4. Frequent localStorage Writes

**Risk**: Low
**Scenario**: `Store.markRead()` called every chapter load. `Store.setLastPosition()` called every chapter load.
**Current**: Both call `saveState()` which serializes entire state.
**Risk**: If user rapidly navigates chapters, could cause stutter.

## 5. Activity Feed Polling

**Risk**: Low
**Scenario**: `setInterval(updateActivityFeed, 30000)` in app.js
**Current**: Fetches all novels + reads localStorage history every 30 seconds
**Risk**: On slow connections, unneeded network calls every 30s.

## 6. Cache Strategy

### API-side cache
- `_novelsCache` TTL: 5 minutes ✓
- `_chaptersCache` per-slug TTL: 5 minutes ✓
- `chapter-repo` cache TTL: 5 minutes ✓
- Cache invalidation on save/delete/rebuild ✓

### Reader image/SVG caching
- All SVGs are inline in index.html (no caching needed) ✓
- Chapter JSON responses: `Cache-Control: no-cache, no-store, must-revalidate` (intentional for dev) 🟡 Could add stale-while-revalidate for prod

## 7. Font Size / Line Height Changes

**Currently**: Changing font size or line height in reader or settings:
- Sets CSS custom property on `<html>` (instant, no re-render) ✓
- Saves to localStorage
- Other pages read the value on load

**Assessment**: Good. No re-render needed.

## 8. Scroll Progress Debounce

**Risk**: Medium
**Currently**: `scroll` event directly updates progress bar width
**Risk**: No debounce — fires many times per second. Minor performance impact.
**Fix**: Add `debounce()` utility and debounce scroll handler at ~100ms.

## Performance Recommendations (Priority Order)

### P1: Debounce scroll progress updates
Add `requestAnimationFrame` or debounce at 100ms for scroll handler.

### P2: Limit search index text field
Current 10,000 char cap is good. Document it and ensure no growth.

### P3: Add stale-while-revalidate caching for chapter JSON
Reader loads are the most frequent API call. 60s stale cache would speed up back-navigation.

### P4: Remove 30s activity feed polling
Only poll when user is on home page. Cancel interval on page change.

### P5: Measure with `performance.now()` 
Add dev-mode timing to chapter render and search to baseline improvements.
