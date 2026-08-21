# QA Report — Round 2 (R2)

Novel: global-descent (212 chapters, th.json set)
Date: 2026-08-18
Scope: 4 verified-open items from QA Round 2 (ch211 filter-word item already done — skipped)
Rules honored: data files only; no Go code touched (Go findings reported separately, see §5).

---

## 1) CJK leak — DONE

| Chapter | Before (CJK chars) | After |
|---------|--------------------|-------|
| ch1     | 43                 | 0     |
| ch81    | 2                  | 0     |
| ch155   | 6                  | 0     |

Method: leaked paragraphs were re-translated from the aligned CN source line
(qa_r2_apply.py carries the full old→new mapping; verified per line against the
`.cn.json` paragraph). Full-scan confirmation: **0 CJK chars across all 212 chapters**.

## 2) Glossary conflict (香江) — DONE

Source of truth: `glossary/locked.md` → 香江 = เซียนเจียง (untouched).

| Data file | Before | After |
|-----------|--------|-------|
| glossary/glossary.json | 香江 → ฮ่องกง | 香江 → เซียนเจียง |
| glossary/glossary.yml  | already เซียนเจียง | unchanged (agrees) |
| chapters (12 occurrences) | ฮ่องกง: ch1×1, ch10×4, ch20×3, ch45×1, ch122×1, ch139×1, ch212×1 | all → เซียนเจียง |
| chapters (4 occurrences) | เซียงกัง (phonetic variant of 香江): ch26×1, ch59×1, ch111×1, ch202×1 | all → เซียนเจียง |

Every occurrence was verified against its CN source line (all map to 香江; no
CN 香港 anywhere in ch1–212). Final state: **17/17 CN 香江 lines in ch1–212
render as เซียนเจียง; 0 wrong variants (ฮ่องกง/เซียงกัง) remain**.

## 3) Filter words — DONE

| Word | Before | After |
|------|--------|-------|
| รู้สึกว่า | 97 | 0 |
| คิดว่า | 112 | 0 |
| เชื่อว่า | 24 | 0 |
| ดูเหมือนว่า | 119 | 0 |
| **Total** | **352** | **0** |

Method (context-aware, not blind):
- 351 occurrences (ch211's single คิดว่า was already cleaned — that's the 352nd)
  were individually anchored to the aligned CN paragraph and classified
  (`filter_classified.json`, `filter_clean_plan.json`):
  - 210 = justified (CN source contains an explicit marker: 觉得/感到/感觉/似乎/好像/想/认为/相信 …)
  - 141 = rewrite (no CN support → rephrased to match source meaning)
  - 0 = uncertain
- Rewrites drop the ว่า particle (รู้สึกว่า→รู้สึก, ดูเหมือนว่า→ดูเหมือน, เชื่อว่า→เชื่อ)
  or use นึกว่า for คิดว่า; sampled edits re-checked against CN — no meaning drift.
- Verification: `python qa_filter_scan.py` + independent count → 0 remaining.

## 4) Re-run of QA scan — PASS on all R2 items

`python qa_full_scan.py` (212 chapters scanned):

| Check | Result |
|-------|--------|
| CJK leak | 0 chapters / 0 chars |
| Forbidden terms (ฮ่องกง) | 0 hits |
| Glossary CN-term leak (香江 etc. in TH) | none |
| Glossary wrong variant (香江→ฮ่องกง) | gone |
| Remaining `glossary_wrong` | only 3 Go-builtin conflicts — see §5 |

## 5) Go changes needed (NOT touched, per task rules)

`internal/translator/sanitizer.go` builtin glossary conflicts with locked.md —
these will keep re-injecting wrong renderings:

| sanitizer.go line | Go value | locked.md wants |
|-------------------|----------|-----------------|
| 119 | "香江": "ฮ่องกง" | เซียนเจียง |
| 55  | "敏捷": "ความว่องไว" | ความเร็ว |
| 58  | "精神": "พลังจิต" | จิตวิญญาณ |
| 109 | "大白": "ต้าไป๋" | ต้าป่าย |

First one is critical: any re-translation/repair touching 香江 will re-introduce
the forbidden ฮ่องกง unless the builtin is updated.

## 6) Out of R2 scope (pre-existing, unchanged)

- Anti-pattern words: ดังนั้น×603, เต็มไปด้วยความ×139, อย่างไรก็ตาม×148, แม้ว่า×109, ชาวอาณานิคม×1
- 40 chapters below length ratio 0.8 (CN vs TH paragraph ratio)
- 3 chapters missing end marker
- name_conflicts report noise (heuristic variant list; e.g. เซียนเจียง counted under 曹星)
