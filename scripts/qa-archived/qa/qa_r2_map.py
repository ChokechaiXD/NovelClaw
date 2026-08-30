# -*- coding: utf-8 -*-
"""Map leaked TH lines to their best-matching CN source line (longest CJK-substring overlap)."""
import json, re, io, sys
sys.stdout.reconfigure(encoding="utf-8")

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = BASE + "/chapters"
han = re.compile(r'[\u4e00-\u9fff]')

def texts(path):
    j = json.load(io.open(path, encoding="utf-8"))
    p = j["paragraphs"]
    return [t if isinstance(t, str) else t.get("text", "") for t in p]

def overlap(a, b):
    sa = set(han.findall(a))
    sb = set(han.findall(b))
    return len(sa & sb)

for n in [1, 81, 155]:
    th = texts(f"{CH}/{n:04d}.th.json")
    cn = texts(f"{CH}/{n:04d}.cn.json")
    print(f"\n========== CH {n}: leaked TH -> best CN ==========")
    for i, t in enumerate(th, 1):
        if not han.search(t):
            continue
        best = max(range(len(cn)), key=lambda k: overlap(t, cn[k]))
        print(f"\n[TH L{i}] {t}")
        print(f"[CN L{best+1}] {cn[best]}")
