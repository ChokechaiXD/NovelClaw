# NovelClaw

> **Cross-language web novel translation toolkit**  
> Transmittor-pipeline with validation, glossary management, multi-agent orchestration, and reader UI

NovelClaw is a production-grade translation workspace for high-fidelity literary translation (CN → TH) with entity consistency, LLM-as-Judge quality scoring, translation memory, and multi-agent orchestration. Built on the "Transmittor Principle" — preserve the author's voice, enforce mechanical purity.

---

## Architecture

```
novelclaw/
├── novels/{slug}/        ← Novel data
│   ├── chapters/         ← Translated chapters (JSON)
│   ├── glossary/         ← Tiered glossary (locked/reference/auto)
│   └── source/           ← Source chapters (CN markdown)
├── tools/                ← Python toolkit (19 modules)
│   ├── translate.py      ← Translation pipeline + all features
│   ├── extract_entities.py   ← CN entity extraction + placeholder
│   ├── cumulative_glossary.py  ← Auto-glossary discovery
│   ├── quality_scorer.py ← LLM-as-Judge scoring (4 dimensions)
│   ├── quality_report.py ← Quality report CLI
│   ├── agent_coordinator.py  ← Multi-agent orchestration (3 passes)
│   ├── translation_memory.py ← Block/chapter cache (L1 exact + L2 fuzzy)
│   ├── glossary.py       ← Glossary YAML management
│   ├── schema.py         ← Pydantic chapter schema
│   ├── validation.py     ← CJK + EN retention + completeness gates
│   ├── progress.py       ← Chapter progress tracking (resume support)
│   ├── chapter_io.py     ← Chapter file I/O
│   ├── constants.py      ← Shared constants
│   └── providers/        ← LLM provider abstraction
├── reader/               ← Web reader (Node.js/Express)
├── tests/                ← 210+ Python + 20 Node tests
├── docs/                 ← Documentation
├── pyproject.toml        ← Package config (Python >=3.11)
└── LICENSE               ← MIT
```

## Quick Start

```bash
# Install
pip install -e .[test]

# Translate a single chapter
novelclaw-translate 139

# Translate with all features
novelclaw-translate 139 --entities --auto-glossary --score --tm --passes 2 --mock-agents

# Batch translate (50 chapters, concurrent, resume-safe)
novelclaw-translate 140-190 --resume --concurrent 3 --entities --auto-glossary

# Quality report
novelclaw-quality-report 1-100 --mock --output report.md

# Translation Memory
novelclaw-tm build
novelclaw-tm stats
novelclaw-tm lookup "ข้อความ"

# Glossary
novelclaw-glossary --load
novelclaw-glossary --sync

# Run tests
python -m pytest tests/

# Start reader UI
cd reader && npm install && npm start
```

## Key Features

| Feature | CLI Flag | Description |
|---------|----------|-------------|
| **Resume** | `--resume` | Resume interrupted batch from progress file |
| **Concurrent** | `--concurrent N` | Translate N chapters in parallel (max 5) |
| **Entity Pipeline** | `--entities` | Extract CN entities → SHA-256 placeholders → translate → restore from glossary |
| **Two-Pass Analysis** | `--two-pass` | Analysis pass (summary + entities) before translation |
| **Cumulative Glossary** | `--auto-glossary` | Auto-discover new terms → append to auto.md → rebuild YAML |
| **LLM-as-Judge** | `--score` | Score translation 0-10 (fluency, accuracy, terminology, completeness) |
| **Translation Memory** | `--tm` | Block-level cache (L1 exact + L2 fuzzy Jaccard) + skip-LLM for cached chapters |
| **Multi-Agent** | `--passes 1-3` | 1=translate, 2=translate+validate, 3=translate+validate+polish |
| **Mock Agents** | `--mock-agents` | Use mock agents (no LLM calls for validate/polish) |

### Commands

| Command | Description |
|---------|-------------|
| `novelclaw-translate <ch>` | Translate chapter(s) with all features |
| `novelclaw-quality-report <range>` | Quality scoring batch report |
| `novelclaw-glossary` | Glossary YAML read/write CLI |
| `novelclaw-search <term>` | Search chapters for a term |
| `novelclaw-tm build\|stats\|lookup` | Translation memory management |

## Pipeline Architecture

```
Source Text
    │
    ▼
┌─────────────────────────────────────────┐
│  Entity Extractor (--entities)          │
│  ├── Bracket entities 《》《》【】          │
│  ├── Dialogue speakers 「」               │
│  └── Glossary cross-reference            │
└──────────────┬──────────────────────────┘
               │ (non-glossary entities → __ENT_hash__)
               ▼
┌─────────────────────────────────────────┐
│  TM Cache Check (--tm)                  │
│  ├── Source hash match → skip LLM ✅     │
│  └── Cache miss → call LLM → cache      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  LLM Translation                        │
│  (prompt + glossary + style + context)  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Entity Restore                         │
│  └── __ENT_hash__ → glossary Thai/CN     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Quality Validation                     │
│  ├── Schema (Pydantic)                  │
│  ├── Regex gates (CJK, EN, length)      │
│  └── LLM Judge (--score) — 4 dimensions │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Multi-Agent Chain (--passes 2-3)       │
│  ├── L2: Validator (entity/glossary)    │
│  └── L3: Polisher (fluency/naturalness) │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Post-Translation                       │
│  ├── TM cache update                    │
│  ├── Auto-glossary (new terms)          │
│  └── Progress save (resume support)     │
└─────────────────────────────────────────┘
```

## Test Suite

```
Python: 210+ tests (pytest)
Node:   20 tests (node:test)
Total:  230+
```

## Branches

- `main` — Primary development
- `mika/*` — Feature branches (Mika agent)

## License

MIT © 2026 P Choke & Mika
