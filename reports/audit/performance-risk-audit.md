# Performance Risk Audit

## 1. Admin Chapters — Large Data Sets
Chapters total: 1239
Risk: Admin chapters page renders ALL rows client-side
Mitigation: ✅ Pagination (100/page) + search/filter already implemented

## 2. Chapter File Size
0001.th.json: 25,001 bytes
All 63 .th.json files: 2260 KB
Est. at 1200 translated: 43041 KB

## 3. Search Index Size
search-index.th.json: 1,764,147 bytes (1722.8 KB)

## 4. DOM Complexity Risks
- Reader page: all paragraphs rendered as DOM nodes
  - Short chapter (1 th.json): ~244 paragraphs
  - Risk: no virtualization
- Admin chapters: 1,239 rows in a table (paginated ✅)
- Job dashboard: small dataset ✅

## 5. localStorage Usage
localStorage keys used: 0

## 6. Index Rebuild Time
Read chapters.json: 2411ms
Parse JSON: 6ms