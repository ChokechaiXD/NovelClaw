# Reader Render Performance

**Date**: 2026-06-24

## Changes made

- Extracted `ReaderRenderer` into separate module (`reader-renderer.js`)
- Single-pass marker replacement (dialogue → system → thought)
- AbortController-based event cleanup (no listener leak)

## Render path

`reader.js` → `ReaderRenderer.renderChapter(data)` →
`_renderParagraphs()` → `_applyMarkers()` → HTML string

## Observations

- Marker styling is now O(3n) per chapter (3 regex passes)
- No DOM operations during render — all string-based
- Skeleton shimmer shows before render completes
- `Ui.debounce(progressUpdate, 100)` prevents layout thrash on scroll

## Future optimization ideas

- Virtual rendering for 1000+ paragraph chapters
- Cache rendered paragraph HTML in sessionStorage
- Lazy paragraph loading for mobile
