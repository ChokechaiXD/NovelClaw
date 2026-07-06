# NovelClaw — Troubleshooting Guide

## Reader Issues

### White Screen (CSS Variables Empty)
**Cause**: Unclosed `@media` block in `design-system.css`
**Fix**: Balance braces — every `{` must have matching `}`

### Page Not Loading
1. Open browser console (F12)
2. Check for 404 errors on JS/CSS files
3. Check server logs for startup errors
4. Run `node --check reader/public/js/app.js` for syntax errors

### Cannot Connect to Reader
```
netstat -ano | grep 4173
```
If port is in use:
```bash
# Find and kill the process
netstat -ano | findstr :4173
taskkill /PID <PID> /F
```

## Translation Pipeline Issues

### novelctl Fails on `unrecognized arguments: 94`
**Cause**: Using space-separated range instead of dash-range
**Fix**: Use `139` for single, `140-150` for range, not `140 150`

### translate.py Creates Wrong Format
**Cause**: Calling `translate.py` directly instead of `novelctl.py`
**Fix**: Always use `python tools/novelctl.py --slug <name> translate <range>`

### Pydantic `model_serializer` Warnings
**Cause**: Cosmetic — chapter.model_dump() triggers serializer warning
**Fix**: Ignore (cosmetic only, does not affect functionality)

### Stale Search Index After Translation
**Fix**: Run `python tools/novelctl.py --slug <name> rebuild`

## Glossary Issues

### TM Source Cache Stale
**Cause**: Old schema data in translation memory
**Fix**: Delete `.tmemory/global-descent.json` source_cache

## Git Issues

### `git add -A` Times Out
**Cause**: Git root = C:\ — scanning entire drive
**Fix**: Add files individually: `git add <absolute-path>/file`

## CI Issues

### CI Fails on Syntax Check
**Cause**: Windows-specific shell commands (`dir /s /b`) in npm scripts
**Fix**: Use Node-based glob in scripts, not shell commands

## Crash Recovery

### After Power Loss During Translation
```bash
python tools/novelctl.py status
python tools/novelctl.py --slug <name> resume
```

### Corrupted Chapter JSON
```bash
python tools/novelctl.py --slug <name> repair <range>
```

### Needs Review Queue
```bash
python tools/novelctl.py --slug <name> check
```
Check `jobs/needs_review/` for files with specific failure reasons.
