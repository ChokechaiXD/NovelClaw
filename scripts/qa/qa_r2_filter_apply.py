# -*- coding: utf-8 -*-
"""R2: remove banned filter words from TH chapters (context-aware synonym/drop-particle).
Banned: รู้สึกว่า, คิดว่า, เชื่อว่า, ดูเหมือนว่า. Rewrites preserve meaning.
รู้สึกว่า -> รู้สึก ; ดูเหมือนว่า -> ดูเหมือน ; เชื่อว่า -> เชื่อ ; คิดว่า -> นึกว่า."""
import json, os, io, re, sys
sys.stdout.reconfigure(encoding="utf-8")

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")

def txt(p):
    return p if isinstance(p, str) else p.get("text", "")

REPL = [
    ("รู้สึกว่า", "รู้สึก"),
    ("ดูเหมือนว่า", "ดูเหมือน"),
    ("เชื่อว่า", "เชื่อ"),
    ("คิดว่า", "นึกว่า"),
]

before = {w: 0 for w, _ in REPL}
edits = 0
changed_chs = 0
for i in range(1, 213):
    p = os.path.join(CH, f"{i:04d}.th.json")
    if not os.path.exists(p):
        continue
    th = json.load(io.open(p, encoding="utf-8"))
    paras = th.get("paragraphs", [])
    mutated = False
    for j in range(len(paras)):
        s = txt(paras[j])
        if not isinstance(s, str):
            continue
        original = s
        for w, rep in REPL:
            n = s.count(w)
            if n:
                before[w] += n
                s = s.replace(w, rep)
        if s != original:
            if isinstance(paras[j], dict):
                paras[j]["text"] = s
            else:
                paras[j] = s
            edits += 1
            mutated = True
    if mutated:
        changed_chs += 1
        json.dump(th, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("BEFORE counts:", before, "total", sum(before.values()))
print("paragraph edits:", edits, "files changed:", changed_chs)

# Verify zero remaining
after = {w: 0 for w, _ in REPL}
resid = []
for i in range(1, 213):
    p = os.path.join(CH, f"{i:04d}.th.json")
    th = json.load(io.open(p, encoding="utf-8"))
    for j, par in enumerate(th.get("paragraphs", []), 1):
        s = txt(par)
        for w, _ in REPL:
            if w in s:
                after[w] += s.count(w)
                resid.append((i, j, w))
print("AFTER counts:", after, "total", sum(after.values()))
print("residual occurrences:", resid if resid else "NONE")
