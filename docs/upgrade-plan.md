# NovelClaw Translation Pipeline — Comprehensive Upgrade Plan

## Current State Assessment

```
Pipeline:   tools/translate.py (840 LOC)
Validation: tools/validation.py (347 LOC) — regex-based, no scoring
Glossary:   locked.md + auto.md → build_yaml.py → prompt injection  
CLI:        8 flags, sequential-only, no resume
Context:    3 previous chapters summary (weak continuity)
Quality:    Length ratio + CJK/EN regex gates only
Cost:       No TM caching, no RAG, no concurrency
Tests:      123 Python + 20 Node (functional only)
```

## Architecture Gaps vs Industry Best Practices

| Dimension | NovelClaw Current | Industry (2025-2026) |
|-----------|-------------------|----------------------|
| Entity Consistency | Glossary-only prompt injection | Placeholder pipeline (SHA-256 → translate → restore) |
| Translation Memory | None | RAG vector search + sentence embedding |
| Quality Gate | Regex-only (CJK/EN/length) | LLM-as-judge scoring + COMET/XCOMET |
| Context Continuity | 3-chapter summary (loose) | Two-pass analysis → summary → translate |
| Batch Efficiency | Sequential, no resume | Parallel agents + resume |
| Error Recovery | Fail fast | Retry with backoff + circuit breaker |
| Cost Optimization | None | TM cache → RAG → skip LLM for similar blocks |

---

## 5-Dimension Strategy

### 🎯 A. Quality — 0 drift, 0 hallucination, 0 CJK leak

| Improvement | Technique | Source | Impact |
|-------------|-----------|--------|--------|
| A1 | Entity Placeholder Pipeline | NovelTrans | Prevents "John"→"จอห์นนี่" cross-chapter |
| A2 | Two-Pass Translation | ai-novel-translation | Better context than 3-ch summary |
| A3 | LLM-as-Judge Validator | TransAgents, TACTIC | Catches fluency drift regex can't |
| A4 | Genre-Matched Prompts | NovelTrans | Battle/mystery/daily = different tones |
| A5 | Multi-Agent: Translator + Polish | TACTIC | Second pass improves naturalness |

### ⚡ B. Speed — minimize wall-clock time

| Improvement | Technique | Source | Impact |
|-------------|-----------|--------|--------|
| B1 | Resume Support | ai-novel-translation | No re-translation on crash |
| B2 | Concurrent Batch | NovelTrans | 3-5x faster batch translate |
| B3 | Smart Prompt Caching | Custom | Block-level hashing → skip duplicate context |
| B4 | Streaming Parse | Custom | Progressive block validation |

### 💰 C. Cost — minimize LLM tokens

| Improvement | Technique | Source | Impact |
|-------------|-----------|--------|--------|
| C1 | RAG Translation Memory | NovelTrans | Skip LLM for cosine ≥ 0.85 blocks |
| C2 | Prompt Size Optimization | Custom | Trim glossary to chapter-relevant terms only ✅ DONE |
| C3 | Conditional Context | Custom | Don't inject style/format on repeat calls |
| C4 | Caching Layer | NovelTrans L1 | Exact-match cache skips LLM entirely |

### 🎯 D. Accuracy — right terms, right tone, right every time

| Improvement | Technique | Source | Impact |
|-------------|-----------|--------|--------|
| D1 | Continuity Summary Pass | ai-novel-translation | Extract chapter summary + new terms before translate |
| D2 | Cumulative Glossary | ai-novel-translation | New terms auto-added per-chapter |
| D3 | Entity Cross-Chapter Audit | Custom | Scan all 1239 chapters for entity drift → report |
| D4 | Quality Score Threshold | COMET/XCOMET | Auto-flag chapters below 0.85 for review |

### 🛡️ E. Stability — never lose work, always verify

| Improvement | Technique | Source | Impact |
|-------------|-----------|--------|--------|
| E1 | Chapter Lock File | Custom | .chprogress file prevents partial writes |
| E2 | Retry with Exponential Backoff | NovelTrans | Transient LLM failures auto-recover |
| E3 | Checkpoint Save | Custom | After every 10 chapters → save state |
| E4 | Comprehensive Test Suite | Custom | All new features + regression gates |

---

## Phased Implementation Plan

### Phase 1: Foundation (Effort: ~4h)
**Goal:** Developer velocity + crash recovery

| Task | LOC | Tests | Acceptance |
|------|:---:|-------|------------|
| **1.1** Resume support — `translate.py --resume` skips existing + detects partial | +40 | 3 tests | `--resume` skips done chs |
| **1.2** Concurrent batch — `translate.py --batch 1-50 --concurrent 3` | +80 | 3 tests | 3 chs translate in parallel |
| **1.3** Chapter lock file — `.chprogress/<slug>.json` with status | +60 | 2 tests | Crash → resume → continue |
| **1.4** Retry with exponential backoff (3 retries, 2s/4s/8s) | +30 | 2 tests | Auto-recoverable failures pass |
| **1.5** CLI UX overhaul — `--from cn --to th` short flags, env defaults | +20 | existing | `novelclaw-translate 139` works |

**Test count: +10** | **Current: 123 → 133**

### Phase 2: Entity & Context (Effort: ~8h)
**Goal:** Meaningful quality leap — entity consistency + continuity

| Task | LOC | Tests | Acceptance |
|------|:---:|-------|------------|
| **2.1** Entity extraction module — `tools/extract_entities.py` CN → proper nouns | +150 | 5 tests | Entity recall ≥ 90% |
| **2.2** Placeholder pipeline — `__ENT_sha256__` sub → translate → restore | +120 | 5 tests | Same entity = same Thai across chapters |
| **2.3** Glossary integration — entity → glossary lookup → rewrite | +40 | 3 tests | glossary term overrides placeholder |
| **2.4** Two-pass analysis — Pass 1: summary + new terms → Pass 2: translate | +100 | 4 tests | Summary quality ≥ chapter comprehension |
| **2.5** Cumulative glossary — auto-save new terms per chapter → reference tier | +50 | 3 tests | New terms persist across session |
| **2.6** Entity cross-chapter audit — scan all 1239 chs for drift | +80 | 2 tests | Drift report with examples |

**Test count: +22** | **Running: 133 → 155**

### Phase 3: Quality Scoring (Effort: ~6h)
**Goal:** Beyond regex — LLM-as-Judge quality gate

| Task | LOC | Tests | Acceptance |
|------|:---:|-------|------------|
| **3.1** LLM-as-judge — prompt LLM to score 0-10 on fluency/consistency/glossary | +100 | 4 tests | Score correlates with human review |
| **3.2** AutoMQM adapter — categorize errors (accuracy/fluency/terminology/style) | +80 | 3 tests | Error categories match MQM standard |
| **3.3** Quality gate v2 — regex fast path first, LLM judge only if regex passes | +40 | 3 tests | < 2x overhead on good translations |
| **3.4** Quality report command — `novelclaw-quality-report 100-150` | +60 | 2 tests | Markdown report with scores |

**Test count: +12** | **Running: 155 → 167**

### Phase 4: Translation Memory (Effort: ~8h)
**Goal:** Cost savings + consistency across chapters

| Task | LOC | Tests | Acceptance |
|------|:---:|-------|------------|
| **4.1** Sentence embedding — `tools/embed.py` with small ONNX model | +100 | 3 tests | Embed ≤ 50ms/block |
| **4.2** Vector store — chapter block → embedding → HNSW index | +80 | 3 tests | Query ≤ 10ms |
| **4.3** RAG lookup — cosine similarity ≥ 0.85 → reuse translation | +60 | 4 tests | ≥ 10% cache hit rate on batch |
| **4.4** TM statistics — `novelclaw-tm-stats` shows savings | +30 | 1 test | Accurate cost report |

**Test count: +11** | **Running: 167 → 178**

### Phase 5: Multi-Agent (Effort: ~8h)
**Goal:** Translation + edit pass for naturalness

| Task | LOC | Tests | Acceptance |
|------|:---:|-------|------------|
| **5.1** Translator agent — current `translate_one()` → agent interface | +30 | existing | Backward compatible |
| **5.2** Validator agent — second pass checks entity/glossary/fluency | +120 | 5 tests | Catches ≥ 90% of known issues |
| **5.3** Polisher agent — optional third pass for naturalness | +80 | 3 tests | Readability improvement on samples |
| **5.4** Agent coordinator — orchestrator with pass control | +60 | 3 tests | `--passes=1|2|3` flag works |

**Test count: +11** | **Running: 178 → 189**

### Phase 6: Comprehensive Tests (Effort: ~4h)
**Goal:** Regression-proof everything

| Task | LOC | Tests | Acceptance |
|------|:---:|-------|------------|
| **6.1** Entity placeholder unit tests | +60 | 5 tests | All edge cases covered |
| **6.2** Two-pass integration tests | +40 | 3 tests | Pipeline end-to-end |
| **6.3** RAG memory integration tests | +50 | 3 tests | Cache hit/miss correct |
| **6.4** Quality scorer tests (mock LLM) | +40 | 3 tests | Score boundaries correct |
| **6.5** Multi-agent mock tests | +30 | 2 tests | Agent chain works |
| **6.6** Regression suite — all existing tests still pass | +20 | — | 189 ✅ |

**Test count: +16** | **Final: 189 ✅**

---

## Architecture Diagram (After)

```
client → CLI / noveltclaw-translate 
            │
            ▼
     ┌─────────────────┐
     │  Orchestrator    │  Phase 5: Agent coordinator
     │  (agent.py)      │
     └──────┬──────────┘
            │
     ┌──────▼──────────┐         ┌──────────────────┐
     │  Resolver        │────────▶│  Entity Extractor  │  Phase 2
     │  (resume/lock)   │         │  (extract + hash)  │
     └──────┬──────────┘         └──────────────────┘
            │
     ┌──────▼──────────┐
     │  Pipeline        │
     │                  │
     │  L1: TM Cache ──▶│── Exact match? → reuse ✓
     │  L2: RAG ───────▶│── Cosine ≥ 0.85? → reuse ✓
     │  L3: Entity ────▶│── Extract → placeholder → translate → restore
     │  L4: LLM ───────▶│── Prompt + glossary → translate
     │  L5: Validate ──▶│── Regex fast → LLM judge → score
     └──────┬──────────┘
            │
     ┌──────▼──────────┐
     │  Quality Gate    │  Phase 3
     │  (scorer.py)     │
     └──────┬──────────┘
            │
     ┌──────▼──────────┐
     │  Save + Log      │
     └─────────────────┘
```

## Testing Strategy

### Unit Tests (+56 total)
```
tests/test_entity_extraction.py     — 5 tests
tests/test_placeholder_pipeline.py  — 5 tests
tests/test_two_pass.py              — 4 tests
tests/test_rag_memory.py            — 3 tests
tests/test_quality_scorer.py        — 4 tests
tests/test_agent_coordinator.py     — 3 tests
tests/test_resume_lock.py           — 2 tests
tests/test_concurrent_batch.py      — 3 tests
```

### Integration Tests (+16 total)
```
tests/test_pipeline_end_to_end.py   — 6 tests  (mock LLM)
tests/test_entity_drift_audit.py    — 3 tests  (across chapters)
tests/test_cost_savings.py          — 3 tests  (cache hit rate)
tests/test_quality_regression.py    — 4 tests  (regression gate)
```

### Regression Gates
```bash
# Before every commit
python -m pytest tests/ -q --tb=short -x    # 189 tests must pass
cd reader && node --test tests/*.test.js      # 20 reader tests must pass
```

## Key Performance Indicators (KPIs)

| KPI | Current | Target | Phase |
|-----|:-------:|:------:|:-----:|
| Batch throughput | 1 ch/min (sequential) | 3 ch/min (parallel) | P1 |
| Entity consistency | ~70% (glossary-only) | ≥ 95% (placeholder) | P2 |
| CJK leak rate | < 2% | < 0.5% | P2 |
| Cost/chapter (LLM) | 100% (no cache) | ≤ 80% (TM + RAG) | P4 |
| Quality gate false positive | ~15% (regex only) | < 5% | P3 |
| Crash recovery | Restart from ch 1 | Resume < 1s | P1 |
