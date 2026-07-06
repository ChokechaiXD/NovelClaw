# NovelClaw — Command Reference

## Translation Pipeline

All translation via `novelctl.py`:

```bash
# Translate (Safe mode — stop on fail)
python tools/novelctl.py --slug global-descent --mode safe translate 139

# Translate (Autopilot — skip on fail)
python tools/novelctl.py --slug global-descent --mode autopilot translate 140-150

# Translate (Strict — score ≥ 90 required)
python tools/novelctl.py --slug global-descent --mode strict translate 139

# Draft (preview, no file write)
python tools/novelctl.py --slug global-descent --mode draft translate 139

# Force re-translate (backup existing, restore on fail)
python tools/novelctl.py --slug global-descent --mode safe --force translate 139
```

## Validation

```bash
# Validate without translating
python tools/novelctl.py --slug global-descent validate 139

# Preflight check (source + config + API)
python tools/novelctl.py --slug global-descent preflight 140-150

# Repair (mechanical only, no LLM)
python tools/novelctl.py --slug global-descent repair 139
```

## Data Management

```bash
# Rebuild chapters.json + search index
python tools/novelctl.py --slug global-descent rebuild

# Show summary report
python tools/novelctl.py --slug global-descent report

# Schema validation
python tools/validate_data.py --novel global-descent
python tools/validate_data.py --all
```

## Running the Reader

```bash
# Local-only
cd reader && npm start

# LAN mode (requires ADMIN_TOKEN)
ADMIN_TOKEN=your-secret HOST=0.0.0.0 npm start

# Dev mode (auto-restart on changes)
npm run dev
```

## Quality Checks

```bash
# Full quality check (no server needed)
python tools/check_all.py

# JS syntax only
npm --prefix reader run check
```

## Common Flags

| Flag | Effect |
|------|--------|
| `--slug <name>` | Target novel (default: global-descent) |
| `--mode safe` | Stop on any failure (default) |
| `--mode autopilot` | Skip failed, continue to next |
| `--mode strict` | Score ≥ 90 gate |
| `--mode draft` | Dry run, no file write |
| `--force` | Re-translate even if .th.json exists |

## Anti-Patterns (don't do these)

- ❌ Don't call `translate.py` directly — use `novelctl.py`
- ❌ Don't use `hermes chat -q` for translation — use HTTP direct
- ❌ Don't change model from deepseek-v4-flash
- ❌ Don't put API keys in code or .env
- ❌ Don't use `git add -A` (root = C:\ — timeout)
