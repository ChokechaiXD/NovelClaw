# -*- coding: utf-8 -*-
"""Filter-word cleanup harness for global-descent (th) chapters 0001-0212.

Rules enforced (see novels/global-descent/style_rules.yml):
  - forbidden filter words: รูสึกว่า / คิดว่า / เชื่อว่า / ดูเหมือนว่า (+ similar guess-y phrases)
  - no guessing: don't add emotion/feeling/conclusion the CN source lacks

Pipeline:
  1. Per occurrence, align TH position -> CN full-text window (char fraction) to check
     whether CN actually contains a justification marker.
  2. Justified -> keep. Unjustified -> rewrite (context-aware, conservative).
  3. Emit filter_clean_plan.json + filter_clean_report.txt for review; apply edits.
"""
import json, os, re

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")

def txt(p):
    if isinstance(p, dict):
        return p.get("text", "")
    return str(p)

# ---- CN justification markers (these legitimately license a TH guess word) ----
MARKERS = {
    "รู้สึกว่า": ["觉得","感到","感觉","感觉到","意識到","意识到","察觉","察覺","心中","心里","直觉","隐隐","莫名","不由"],
    "คิดว่า": ["想","认为","以為","以为","觉得","覺得","猜想","心说","心想","暗道","思量","琢磨","盘算","估摸","寻思","考慮","考虑"],
    "เชื่อว่า": ["相信","确信","坚信","深信","认为"],
    "ดูเหมือนว่า": ["似乎","好像","仿佛","仿佛","貌似","看起来","看上去","看似","犹如","如同","像是","八成","约莫"],
}

TARGETS = list(MARKERS.keys())

def cn_window(cn_full, th_full, th_paras, wi, half=600):
    """Char-fraction alignment: map TH paragraph position to CN window."""
    th_total = max(1, len(th_full))
    start = max(0, sum(len(p) for p in th_paras[:wi-1]))
    frac = start / th_total
    c0 = int(frac * len(cn_full))
    return cn_full[c0:c0 + 2*half]

def classify(th_full_offsets, cn_full, th_paras, wi, w):
    seg = cn_window(cn_full, "\n".join(th_paras), th_paras, wi)
    hit = [m for m in MARKERS[w] if m in seg]
    return hit

data = []
kept = {'justified': 0, 'uncertain': 0, 'rewrite': 0}
for i in range(1, 213):
    thp = os.path.join(CH, f"{i:04d}.th.json")
    cnp = os.path.join(CH, f"{i:04d}.cn.json")
    if not (os.path.exists(thp) and os.path.exists(cnp)):
        continue
    th = json.load(open(thp, encoding="utf-8"))
    cn = json.load(open(cnp, encoding="utf-8"))
    th_paras = [txt(p) for p in th.get("paragraphs", [])]
    cn_full = "\n".join(txt(p) for p in cn.get("paragraphs", []))
    th_full = "\n".join(th_paras)
    for wi, p in enumerate(th_paras, 1):
        for w in TARGETS:
            if w in p:
                markers = classify(None, cn_full, th_paras, wi, w)
                stat = "justified" if markers else "rewrite"
                data.append({
                    "ch": i, "th_idx": wi, "word": w, "th": p,
                    "cn_window": cn_window(cn_full, th_full, th_paras, wi)[:500],
                    "markers": markers, "stat": stat,
                })
json.dump(data, open(r"C:/Users/BlankScreen/Workspace/NovelClaw/filter_clean_plan.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)

from collections import Counter
c = Counter(d["stat"] for d in data)
print("classified:", dict(c))
cw = Counter(d["word"] for d in data if d["stat"]=="rewrite")
print("rewrite-by-word:", dict(cw))
print("total occurrences (core-3):", len(data))
