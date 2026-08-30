# -*- coding: utf-8 -*-
"""Classify filter-word occurrences: justified (CN has marker) vs unjustified."""
import json, os, re, collections

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")

def txt(p):
    if isinstance(p, dict):
        return p.get("text", "")
    return str(p)

# core 4 forbidden filter words per new rule
WORDS = ["รู้สึกว่า", "คิดว่า", "เชื่อว่า", "ดูเหมือนว่า"]

# marker sets that justify each word (CN source actually contains the meaning)
FEEL = ["觉得", "感到", "感觉", "意识到", "意識到", "察觉", "察覺", "心里", "心中", "直觉", "隐隐", "不由自主", "莫名"]
THINK = ["想", "认为", "以為", "以为", "觉得", "覺得", "考虑", "猜想", "估摸", "琢磨", "猜测", "心说", "心想", "暗道", "思量", "寻思"]
BELIEVE = ["相信", "确信", "坚信", "深信", "认为", "觉得"]
SEEM = ["似乎", "好像", "仿佛", "貌似", "看起来", "看上去", "看似", "犹如", "如同", "像是", "估摸着", "八成", "约莫"]

MARK = {
    "รู้สึกว่า": FEEL,
    "คิดว่า": THINK,
    "เชื่อว่า": BELIEVE,
    "ดูเหมือนว่า": SEEM,
}

def anchor_cn(th_paras, cn_paras, th_idx):
    """Return CN paragraph best positioned for the TH paragraph, by cumulative fraction."""
    if not cn_paras:
        return "", 0
    th_total = sum(len(p) for p in th_paras) or 1
    upto = sum(len(p) for p in th_paras[:th_idx-1])
    frac_before = upto / th_total
    upto2 = sum(len(p) for p in th_paras[:th_idx])
    frac_after = upto2 / th_total
    cn_total = sum(len(p) for p in cn_paras) or 1
    # find first cn para whose cumulative end >= frac_before
    best = 0
    cum = 0
    for j, p in enumerate(cn_paras):
        cum += len(p)
        if cum / cn_total >= frac_before:
            best = j
            break
    return cn_paras[best], best

occ = []
stats = collections.Counter()
for i in range(1, 213):
    thp = os.path.join(CH, f"{i:04d}.th.json")
    cnp = os.path.join(CH, f"{i:04d}.cn.json")
    if not (os.path.exists(thp) and os.path.exists(cnp)):
        continue
    th = json.load(open(thp, encoding="utf-8"))
    cn = json.load(open(cnp, encoding="utf-8"))
    th_paras = [txt(p) for p in th.get("paragraphs", [])]
    cn_paras = [txt(p) for p in cn.get("paragraphs", [])]
    for wi, p in enumerate(th_paras, 1):
        for w in WORDS:
            if w in p:
                cn_txt, cn_idx = anchor_cn(th_paras, cn_paras, wi)
                stat = "unjustified"
                if cn_txt:
                    hit = [m for m in MARK[w] if m in cn_txt]
                    if hit:
                        stat = "justified"
                stats[stat] += 1
                occ.append({"ch": i, "th_idx": wi, "word": w, "th": p,
                            "cn": cn_txt[:300], "stat": stat, "markers": hit if cn_txt else []})

print("=== CLASSIFICATION ===")
print(dict(stats))
by_word = collections.defaultdict(collections.Counter)
for o in occ:
    by_word[o["word"]][o["stat"]] += 1
for w in WORDS:
    print(f"  {w}: {dict(by_word[w])}")

json.dump(occ, open(os.path.join(BASE, "..", "filter_classified.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("wrote filter_classified.json, total occ:", len(occ))
