# Git hooks for NovelClaw

Project-level git hooks. Configure once per clone:

```bash
git config core.hooksPath .githooks
```

## pre-commit

Validates any staged `chapters/*.json` files:
- **Blocks** on schema errors (Pydantic validation)
- **Blocks** on glossary doctor errors
- **Warns** on doctor warnings (transmittor principle — detect, don't fix)
- **Succeeds** silently when no ch JSON is staged

Skips `.md` files (they use legacy markdown format).
