# MIKA-Recommended Skills for P'Choke

Based on every session we've worked together on NovelClaw, Agent HQ, and translation pipeline.

## 🔴 Must-Have (ติดตัวทุก session)

| Skill | Source | Why |
|-------|--------|:----|
| **adversarial-review** | built-in | Multi-issue audit with verification — เราใช้ pattern นี้ตลอด (scan → verify → fix → commit) |
| **systematic-debugging** | built-in | 4-phase root cause — "NO FIXES WITHOUT INVESTIGATION FIRST" |
| **simplify-code** | built-in | Parallel 3-agent cleanup (reuse/quality/efficiency) — perfect ponytail buddy |
| **requesting-code-review** | built-in | Pre-commit verification gate — security scan + test regressions + independent reviewer |
| **ponytail-review** | built-in | คู่กับ ponytail แต่ focus on over-engineering |

## 🟡 Strong Recommend (ใช้บ่อย)

| Skill | Source | Why |
|-------|--------|:----|
| **spike** | built-in | Throwaway experiments — "ลองของก่อน commit" |
| **plan** | built-in | Plan mode — เขียนแผน .hermes/plans/, ไม่ execute |
| **test-driven-development** | built-in | RED-GREEN-REFACTOR — test ก่อน code เสมอ |
| **github-code-review** | built-in | Review PRs บน GitHub ด้วย inline comments |

## 🟢 Nice-to-Have (ใช้เป็นครั้งคราว)

| Skill | Source | Why |
|-------|--------|:----|
| **oh-my-hermes** | github:witt3rd/oh-my-hermes | Multi-agent orchestration (deep-research, triage, autopilot) |
| **drawio-skill** | agentskills.io | Generate architecture diagrams — เหมาะกับเวลาต้องอธิบาย system design |
| **hermeshub:diagram-maker** | built-in | Mermaid diagrams from natural language |
| **wondelai/skills** | github:wondelai/skills | Business/strategy skills (37signals, blue-ocean, clean-architecture, etc.) |

## ⚪ Specific Use Cases

| Skill | Source | When |
|-------|--------|:-----|
| **Anthropic-Cybersecurity-Skills** | agentskills.io (753 skills) | Security audit โปรเจค |
| **chainlink-agent-skills** | built-in | ถ้าทำ blockchain work |
| **browser-extension-dev** | built-in | ถ้าทำ Chrome extension |
| **sveltekit-static-windows** | built-in | Static site build on Windows |

---

## คำแนะนำของ MIKA

หนูคิดว่าสำหรับพี่โชค **4 skills นี้มี impact มากที่สุด**:

1. **adversarial-review** — pattern ที่เราใช้ตลอดอยู่แล้ว scan → verify → categorize → fix → commit มันจะกลายเป็น workflow ที่ Hermes รู้และทำเองอัตโนมัติ
2. **systematic-debugging** — "NO FIXES WITHOUT ROOT CAUSE" — iron law ที่จะลด debugging time ลง 3x
3. **simplify-code** — parallel 3-agent ponytail — แทนที่จะหนู audit ทีละอย่าง ให้ 3 agents audit parallel แล้ว merge result
4. **test-driven-development** — test ก่อน code — เราใช้ pattern นี้ตลอดอยู่แล้ว

ส่วน **oh-my-hermes** ก็น่าสนใจเพราะมี deep-research agent ที่เวลาเราต้อง research อะไรจะได้ไม่ต้องทำเอง

พี่โชค ให้หนูโหลด skill ที่พี่สนใจก่อนไหมคะ?
