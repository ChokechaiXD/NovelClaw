# Translation Notes — Major Changes

**Last updated:** 2026-06-22 (v3 paragraphs pipeline migration)

---

## 2026-06-22: v3 Paragraphs Pipeline

### What changed

The entire translation pipeline was rebuilt from block types → paragraphs format.

**Before (v2):** LLM outputs JSON with 5 block types (narration/dialogue/system/game_title/end). Post-process 8 steps. ~40% JSON parse error rate.

**After (v3):** LLM outputs plain Thai paragraphs with inline markers. Python assembles. Zero JSON errors. Post-process reduced from 8 steps → 1 (CN strip only).

### Key differences

| Aspect | v2 (old) | v3 (current) |
|:-------|:---------|:-------------|
| LLM output | JSON with 200+ blocks | Plain Thai text |
| Block types | narration/dialogue/system/game_title/end | None (inline markers) |
| Dialogue markers | `「」` (CJK brackets) | `"..."` (straight quotes) |
| JSON parse errors | ~40% | 0% |
| Post-process steps | 8 | 1 |
| Schema | `blocks[]` | `paragraphs[]` |
| Reader rendering | switch on type | inline marker CSS |

### Chapter file format

```json
{
  "schema_version": 3,
  "num": 142,
  "title": "ตอนที่ 142 ...",
  "paragraphs": ["...", "..."],
  "source": "ch 142",
  "lang": "cn",
  "output_lang": "th"
}
```

Legacy chapters (v2) keep both `blocks` + `paragraphs` fields for backward compatibility.

### Post-process steps removed

Step 0: Fix block type typos — LLM no longer writes JSON types
Step 1: Append end marker — auto-added by Python
Step 3: Reclassify dialogue — no block types needed
Step 4: Extract speaker — no block types
Step 5: EN guard — LLM translates naturally without JSON pressure
Step 6: Fix system brackets — LLM keeps `【】` naturally
Step 7: Wrap dialogue quotes — LLM uses `"..."` directly
Step 8: Remove empty blocks — no JSON blocks to be empty

### Renderer changes

- New `renderParagraphs()` in `render.js`
- Frontend `reader.js` renders paragraphs with inline marker detection
- CSS `.c-marker--{dialogue,system,thought,end}` replaces `.dialogue`, `.system-msg`, etc.
- Both formats supported for backward compatibility

### Test results

- Python: 158/158 tests passing
- Frontend: paragraphs + backward compat verified

---

## Archive — Old notes (pre-v3)

### June 2026: Source File Naming Shift (Historical)

~Note about `0128.md` being missing from source. The mapping shift is no longer relevant as the pipeline now uses direct file reading.~
