# -*- coding: utf-8 -*-
"""Record BEFORE state, print full leaked lines for ch1/81/155 with CN context."""
import json, re, io, sys
sys.stdout.reconfigure(encoding="utf-8")

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = BASE + "/chapters"

def th_texts(n):
    th = json.load(io.open(f"{CH}/{n:04d}.th.json", encoding="utf-8"))
    p = th["paragraphs"]
    return [t if isinstance(t, str) else t.get("text", "") for t in p]

def cn_texts(n):
    cn = json.load(io.open(f"{CH}/{n:04d}.cn.json", encoding="utf-8"))
    p = cn["paragraphs"]
    return [t if isinstance(t, str) else t.get("text", "") for t in p]

han = re.compile(r'[\u4e00-\u9fff]')
for n in [1, 81, 155]:
    ts = th_texts(n)
    cs = cn_texts(n)
    print(f"\n========== CH {n} ==========")
    for i, t in enumerate(ts, 1):
        if han.search(t):
            cn = cs[i-1] if i-1 < len(cs) else "(no CN line)"
            print(f"[L{i}] TH: {t}")
            print(f"      CN: {cn}")
