# NovelClaw 🦊

> **Cross-language web novel translation toolkit**
> Transmittor-pipeline with validation, glossary management, and reader UI

NovelClaw is a production-grade translation workspace designed for high-fidelity literary translation across multiple source languages (CN, JP, KR, EN) and genres (Xianxia, Fantasy, Horror, Romance). Built on the "Transmittor Principle" — preserve the author's voice, enforce mechanical purity.

---

## Architecture

```
novelclaw/
├── novels/{slug}/     ← Novel data per language/genre
│   ├── chapters/      ← Translated chapters (JSON)
│   ├── glossary/      ← Locked + reference terms
│   ├── format_spec.json  ← Single source of truth for formatting rules
│   ├── style_rules.yml   ← Auto-generated from format_spec.json
│   └── style.md       ← Novel-specific voice/tone
├── tools/             ← Python toolkit (22 modules)
│   ├── translate.py   ← Translation pipeline
│   ├── validate_chapter.py  ← CJK + structure validation
│   ├── glossary.py    ← Glossary management + --sync
│   ├── dashboard.py   ← Translation progress dashboard
│   ├── batch_validate.py   ← Batch validation
│   ├── slop/          ← Anti-slop detection suite
│   └── sites/         ← Scraper configs
├── reader/            ← Web reader (Node.js/Express)
├── tests/             ← 220+ test suite
├── docs/              ← Style guides
├── PROMPT.md          ← Global AI prompt (multi-language)
├── pyproject.toml     ← Package config (Python >=3.11)
└── LICENSE            ← MIT
```

## Quick Start

```bash
# Install
pip install -e .

# Translate a chapter
python tools/translate.py --chapter 1 --novel global-descent

# Validate
python tools/validate_chapter.py 1

# Sync formatting rules (after editing format_spec.json)
python tools/glossary.py --sync

# Run tests
pip install -e .[test]
python -m pytest tests/

# Start reader UI
cd reader && npm install && npm start
```

## Key Features

- **Multi-language**: CN, JP, KR, EN → Thai (with template slots for more)
- **Multi-genre**: Xianxia, Dark Fantasy, Lovecraft (extensible)
- **Zero CJK leakage**: Automated detection in all source languages
- **Transmittor Pipeline**: 5-phase workflow (Context → Comprehension → Decomposition → Reconstruction → Correction)
- **Glossary Management**: Tiered (locked > reference > auto), with priority-based lookup
- **Anti-Slop Detection**: 4-module analysis suite
- **Format Consistency**: Single source of truth via `format_spec.json`

## Branches

- `main` — Primary development
- `gemini` — Gemini provider configuration
- `claude` — Claude provider configuration

## License

MIT © 2026 P Choke & Mika
