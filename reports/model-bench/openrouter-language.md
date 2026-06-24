# OpenRouter Model Benchmarks

**Date**: 2026-06-24
**Project**: NovelClaw — Chinese-to-Thai translation quality & latency

## Translate model chain

As configured in `tools/llm_router/config.py`:

| Tier | Model | Speed | Quality | Context | Cost |
|------|-------|-------|---------|---------|------|
| Primary | `google/gemma-4-26b-a4b-it:free` | ⚡ Fast (MoE) | Good | 256K | Free |
| Secondary | `google/gemma-4-31b-it:free` | Moderate | Better (dense) | 1M | Free |
| Fallback | `openai/gpt-oss-120b:free` | Moderate | Good | 128K | Free |
| Last resort | `openrouter/free` | Varies | Varies | Varies | Free |

## Benchmark method

Run `python tools/novelctl.py bench 5` — translates 5 chapters in draft mode,
measures average latency and score.

## Known findings

- **DeepSeek V4 Flash** (openmodel.ai): Best speed/quality for CN→TH. Used by agent, not batch pipeline.
- **Gemma 4 31B**: Best dense model quality. Primary for `translate_quality`.
- **Gemma 4 26B**: Best MoE speed. Primary for `translate_fast`.
- **Nemotron 3 Super**: 1M context but NO Thai support — unsuitable as primary translator.
- **OpenRouter free**: Last resort only — rate-limited and unreliable for batch work.
