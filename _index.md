# NovelClaw Index

Status: 🟢 Active
Last Active: 2026-06-22

## Quick Links
- [Repository](./NovelClaw/AGENTS.md) — project rules
- [[05 Templates]] — Scoring Board
- [[06 Decision Log]] — Decisions

## Active Tasks
- Translate remaining chapters (ch144+)
- ch128 source scraping (blocked by CF)

## Current Metrics
- Pipeline: v3 paragraphs (0% JSON error, 1 post-process step)
- Scorer avg: 97/100
- Provider: deepseek-v4-flash (free, ~5s/call)
- Tests: 158/158 Python, backward-compat reader

## Known Gotchas
- `git add -A` time out → use `git add <absolute-path>`
- provider config in `tools/providers/api.py`, not Hermes CLI
- No `--entities` or `--two-pass` flags needed (removed)
