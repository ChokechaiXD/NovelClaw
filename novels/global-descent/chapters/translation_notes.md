# Translation Notes & Glossary Deviations Log

This document records term adjustments, glossary drifts, and translation notes starting from Chapter 131 to maintain consistency and prepare for future batch refactoring.

---

## 1. Character Name Drifts

| Chinese Term | Standard Pinyin / Glossary Lock | Used in Ch. 137 | Used in Ch. 138 | Action / Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| `大白` | **ต้าป่าย** (Mammoth pet) | ต้าป่า (Typo) | **ต้าป่าย** | Keep using `ต้าป่าย` (glossary-locked). Need to patch Ch. 137 to change `ต้าป่า` -> `ต้าป่าย`. |
| `兰倩倩` | **หลันเชี่ยนเชี่ยน** | เลี่ยนเชียนเชียน | **เลี่ยนเชียนเชียน** | To avoid reader confusion, we kept `เลี่ยนเชียนเชียน` in Ch. 138. Once ready, batch replace all occurrences in the codebase. |
| `布隆` | **บรูน** (Short name for Braum) | บรูน | **บรูน** | `布隆` is short for `布洛特·硫磺石` (บรูนท์·ซัลเฟอร์สโตน). Spelled `บรูน` in chapter content blocks. |

---

## 2. Terminology & Monster Translations (Ch. 138)

- `游猎者` (Yuliezhe) -> **นักล่า** (Hunters/Raiders).
- `游猎者斥候` -> **นักล่าลาดตระเวน** (Hunter Scout).
- `游猎者弓箭手` -> **พลธนูนักล่า** (Hunter Archer).
- `游猎者黑袍祭司` -> **นักบวชชุดดำของกลุ่มนักล่า** (Hunter Black-robed Priest).
- `训练有素的游猎者杀手` -> **มือสังหารนักล่าที่ได้รับการฝึกฝนมาอย่างดี** (Trained Hunter Assassin).

---

## 3. Schema & Validation Notes

- **System Block vs Narration**: `要害攻击！` (Critical hit / Vital attack) does not have brackets in Chinese source. Translating it as a `system` block without `【` and `】` triggers Pydantic schema validation failure. We translated it as a `narration` block (`"text": "โจมตีจุดสำคัญ!"`) to remain faithful to the source formatting while passing the schema validator.
