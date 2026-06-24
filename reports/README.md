# Reports

## Structure

```
reports/
├── perf/         — Performance benchmarks (render time, search latency)
├── model-bench/  — OpenRouter model comparison (latency, quality, cost)
└── api/          — API route health checks, endpoint tests
```

## How to generate

- **perf/reader-render.md**: `node reader/tests/perf-render.js` (benchmarks paragraph render)
- **model-bench/openrouter-language.md**: `python tools/novelctl.py bench 5`
- **api/route-health.md**: `node reader/tests/test-api.js` (API smoke test output) or `python tools/check_all.py`
