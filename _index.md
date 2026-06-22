# NovelClaw Index

Status: 🟢 Active
Last Active: 2026-06-22

## Quick Links
- [Repository](./NovelClaw/AGENTS.md) — project rules
- [[05 Templates]] — Scoring Board
- [[06 Decision Log]] — Decisions

## Active Tasks
- Translate ch42-138 to reach 100% score
- Speaker field improvement (LLM limitation)
- ch128 source scraping (blocked by CF)

## Current Metrics
- Scorer avg: 91/100
- Pass/Fail: 69/1 (128 no source)
- Provider: deepseek-v4-flash (free, ~5s/call)

## Known Gotchas
- `git add -A` time out → use `git add <absolute-path>`
- provider config in `tools/providers/api.py`, not Hermes CLI
- `--entities` flag not needed for translation (DeepSeek understands CN)
