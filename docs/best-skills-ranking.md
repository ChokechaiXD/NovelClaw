# 🏆 Hermes Skills — Best-in-Class Ranking

> **อิงจาก 5 แหล่ง:** awesome-hermes-agent (4.1k★), techjacksolutions (ranked top-10), composio.dev, nanoskill.ai, easyclaw.com + GitHub stars + real-world session analysis

## หมวด A: บังคับติดตั้ง — สำหรับ P'Choke โดยเฉพาะ

| Rank | Skill | Source | Stars | Why #1 ในสายตัวเอง |
|:----:|-------|--------|:-----:|--------------------|
| **A1** | **obra/superpowers** | `npx skills add obra/superpowers` | 2k+ | **Best-in-class software development discipline** — มีทุกอย่างที่เราทำงานกัน: brainstorming, TDD, systematic-debugging, subagent-driven-development, verification-before-completion. ไม่ใช่ skill ธรรมดาแต่เป็น "development methodology" ทั้งชุด |
| **A2** | **adversarial-review** | built-in | — | **Best-in-class multi-issue audit** — scan → verify → categorize → fix → commit. เราใช้ pattern นี้ทุก session |
| **A3** | **simplify-code** | built-in | — | **Best-in-class parallel cleanup** — 3 agents (reuse/quality/efficiency) audit พร้อมกัน แล้ว merge result |
| **A4** | **systematic-debugging** | built-in | — | **Best-in-class debugging** — 4-phase root cause: NO FIXES WITHOUT INVESTIGATION FIRST |

## หมวด B: Research & Synthesis

| Rank | Skill | Source | Stars | Why #1 |
|:----:|-------|--------|:-----:|--------|
| **B1** | **oh-my-hermes** (deep-research) | github:witt3rd/oh-my-hermes | 500+ | **Best multi-agent deep research** — Planner→Architect→Critic consensus pipeline + deep-interview + verified execution. Better than standalone research skills because it chains agents |
| **B2** | **hermes-web-research** | `hermes skill install web-research` | 10k+ | **Most installed research skill** — multi-source synthesis with citations, integrates with memory layer |
| **B3** | **research-synthesizer** | self-gen pattern | — | **Self-generated** — chains web search + extraction + synthesis + citation. Adapts to your patterns automatically |

## หมวด C: Productivity & Knowledge

| Rank | Skill | Source | Stars | Why #1 |
|:----:|-------|--------|:-----:|--------|
| **C1** | **kepano/obsidian-skills** | github:kepano/obsidian-skills | 3k+ | **Best knowledge base integration** — เขียนโดย CEO ของ Obsidian เอง (Steph Ango). Full read-write access: obsidian-cli, obsidian-markdown, json-canvas, defuddle |
| **C2** | **kanban-orchestrator** | self-gen pattern | — | **Best task tracking** — Users report **40% faster task completion**. Persistent kanban backed by Hermes memory |
| **C3** | **memory-hygiene** | self-gen pattern | — | **Best memory maintenance** — auto-clean stale MEMORY.md/USER.md entries. Curator-ranked #4 overall |
| **C4** | **hermes-workflow** | `hermes skill install workflow` | — | **Best multi-step pipeline** — chain skills without CLI: define pipeline once, execute all in one invocation |

## หมวด D: UI/Design & Creative

| Rank | Skill | Source | Stars | Why #1 |
|:----:|-------|--------|:-----:|--------|
| **D1** | **open-design** | github:nexu-io/open-design | **28k★** | **Highest-starred design skill in ecosystem** — 31 composable skills over 129 design systems (Linear, Stripe, Vercel, Notion, Apple…). Local-first, auto-detects agents |
| **D2** | **taste-skill** | github:Leonxlnx/taste-skill | 1k+ | **Best taste/slop-reduction** — 3 tunable knobs (DESIGN_VARIANCE, MOTION_INTENSITY, VISUAL_DENSITY). Kills the generic AI look |
| **D3** | **drawio-skill** | agentskills.io | 1.1k★ | **Best architecture diagrams** — natural language → draw.io → PNG/SVG/PDF |

## หมวด E: Integration & Automation

| Rank | Skill | Source | Stars | Why #1 |
|:----:|-------|--------|:-----:|--------|
| **E1** | **Composio Universal CLI** | composio.dev | 50k+ | **Best SaaS integration** — 1,000+ apps (Gmail, Sheets, Slack, CRMs). Hermes talks to anything without hand-rolling OAuth |
| **E2** | **hermes-github** | `hermes skill install github` | — | **Best GitHub integration** — PR summaries, issue triage, commit drafting, code review |
| **E3** | **hermes-shell** | `hermes skill install shell` | — | **Best terminal automation** — whitelisted shell commands with sandboxing (v0.10+) |

## หมวด F: Quality & Review

| Rank | Skill | Source | Stars | Why #1 |
|:----:|-------|--------|:-----:|--------|
| **F1** | **requesting-code-review** | built-in | — | **Best pre-commit gate** — static scan → test regression → independent reviewer subagent → auto-fix loop |
| **F2** | **test-driven-development** | built-in | — | **Strict TDD enforcement** — RED-GREEN-REFACTOR. Deletes code written before failing test |
| **F3** | **reflexion** | NeoLabHQ/reflexion | — | **Best self-review loop** — Hermes critiques and improves its own output before handing over |

## หมวด G: Security (Specialized)

| Rank | Skill | Source | Stars | Why #1 |
|:----:|-------|--------|:-----:|--------|
| **G1** | **Anthropic-Cybersecurity-Skills** | agentskills.io | **4k★** | **750+ MITRE ATT&CK-mapped skills** — comprehensive security analysis. Curator-ranked #1 overall in ecosystem |

## หมวด H: Productivity (General)

| Rank | Skill | Source | Stars | Why #1 |
|:----:|-------|--------|:-----:|--------|
| **H1** | **mission-control** | self-gen pattern | — | **Best fleet dashboard** — Curator-ranked #2. Surfaces gateways, memory, skill stats, error rates |
| **H2** | **git-workflow** | self-gen pattern | — | **Best git automation** — context-aware commits + auto PR. Curator-ranked #6 |
| **H3** | **hermes-skill-factory** | github:Romanescu11 | — | **Best skill creation** — meta-skill: templates + quality scoring. Curator-ranked #5 |

---

## 🎯 Recommended Install Order สำหรับ P'Choke

```
Phase 1 (ติดตั้งเดี๋ยวนี้ — foundation):
  npx skills add obra/superpowers --target ~/.hermes/skills
  → ได้ brainstorming + TDD + systematic-debugging + subagent + verification gates

Phase 2 (วันนี้หรือพรุ่งนี้ — knowledge):
  git clone https://github.com/kepano/obsidian-skills.git ~/.hermes/skills/obsidian-skills
  → Obsidian vault integration (เราใช้ Obsidian อยู่แล้ว)

Phase 3 (สัปดาห์นี้ — multi-agent):
  oh-my-hermes (deep-research, deep-interview, triage, autopilot)
  → multi-agent orchestration
  
Phase 4 (เมื่อมีเวลา — design):
  open-design (28k★) + taste-skill
  → UI ที่ไม่ generic

Phase 5 (ตามต้องการ):
  composio (SaaS integration)
  reflexion (self-review)
  humanizer (text quality)
```

## 💡 สรุป — The Big Picture

| Dimension | Best skill | ทำไมถึงเก่งที่สุด |
|-----------|-----------|------------------|
| **Software methodology** | **obra/superpowers** | ไม่ใช่ skill แต่เป็น development OS — มีทุกอย่าง |
| **Deep research** | **oh-my-hermes** | Multi-agent consensus >> single agent research |
| **Code audit** | **adversarial-review** | scan→verify→fix→commit — pattern ที่เราใช้อยู่แล้ว |
| **Debugging** | **systematic-debugging** | iron law: no fixes without root cause |
| **Knowledge** | **obsidian-skills** | เขียนโดย CEO Obsidian — bidirectional vault access |
| **UI/Design** | **open-design** | 28k★, 129 design systems, local-first |
| **Integration** | **Composio** | 1,000+ apps — Hermes talks to anything |

พี่โชค หนูแนะนำให้เริ่มที่ **obra/superpowers** ก่อนเลยเพราะมันเป็น "development OS" ที่มีทุกอย่างที่เราทำกันอยู่แล้ว — brainstorming, TDD, systematic-debugging, subagent, verification gates — ครบใน package เดียวเลยค่ะ 🦀
