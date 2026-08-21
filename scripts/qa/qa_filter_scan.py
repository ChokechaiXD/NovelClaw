# -*- coding: utf-8 -*-
"""Count filter words in TH chapters, align to CN, dump occurrences for review."""
import json, os, re, sys, collections

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")

def txt(p):
    if isinstance(p, dict):
        return p.get("text", "")
    return str(p)

WORDS = ["รู้สึกว่า", "คิดว่า", "เชื่อว่า", "ดูเหมือนว่า", "รู้สึกเหมือนว่า",
         "รู้สึกเหมือน", "ดูเหมือน", "เหมือนกับว่า", "ราวกับว่า", "เหมือนว่า"]

# count per word across all chapters
total = collections.Counter()
occ = []  # (ch, th_idx, word, th_text, cn_full_paras)
merged = 0
for i in range(1, 213):
    thp = os.path.join(CH, f"{i:04d}.th.json")
    cnp = os.path.join(CH, f"{i:04d}.cn.json")
    if not (os.path.exists(thp) and os.path.exists(cnp)):
        continue
    th = json.load(open(thp, encoding="utf-8"))
    cn = json.load(open(cnp, encoding="utf-8"))
    th_paras = [txt(p) for p in th.get("paragraphs", [])]
    cn_paras = [txt(p) for p in cn.get("paragraphs", [])]
    if len(th_paras) != len(cn_paras):
        merged += 1
    for wi, p in enumerate(th_paras, 1):
        for w in WORDS:
            c = p.count(w)
            if c:
                total[w] += c
                occ.append((i, wi, w, p, cn_paras))

print("=== FILTER WORD COUNTS (th, ch1-212) ===")
for w in WORDS:
    if total[w]:
        print(f"  {w}: {total[w]}")
print("TOTAL core-4 (รู้สึกว่า/คิดว่า/เชื่อว่า/ดูเหมือนว่า):",
      sum(total[x] for x in ["รู้สึกว่า", "คิดว่า", "เชื่อว่า", "ดูเหมือนว่า"]))
print("TOTAL all:", sum(total.values()))
print("chapters where len(th)!=len(cn):", merged)

# dump occurrences grouped for review
with open(os.path.join(BASE, "..", "filter_occ.json"), "w", encoding="utf-8") as f:
    out = []
    for ch, wi, w, p, cn_paras in occ:
        out.append({"ch": ch, "th_idx": wi, "word": w, "th": p, "cn_paras": cn_paras})
    json.dump(out, f, ensure_ascii=False, indent=1)

print("\n=== OCCURRENCES BY CHAPTER ===")
by_ch = collections.OrderedDict()
for ch, wi, w, p, _ in occ:
    by_ch.setdefault(ch, []).append((wi, w, p))
for ch in sorted(by_ch):
    print(f"\n--- ch {ch} ({len(by_ch[ch])} hits) ---")
    for wi, w, p in by_ch[ch]:
        print(f"  L{wi} [{w}] {p[:160]}")
print(f"\nTOTAL occurrences listed: {len(occ)}")
