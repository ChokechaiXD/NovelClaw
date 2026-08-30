# -*- coding: utf-8 -*-
import json, os, re
BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")
def txt(p): return p.get("text","") if isinstance(p,dict) else str(p)

# 1. source footer "*Source: ch N*"
print("===== SOURCE FOOTER check (last 3 paras of a few) =====")
no_footer = []
for i in list(range(1,40))+[100,150,211,212]:
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    ps = [txt(p) for p in th["paragraphs"]]
    foot = [p for p in ps if "*Source: ch" in p]
    if not foot: no_footer.append(i)
print("chapters WITHOUT '*Source: ch N*' footer:", no_footer[:60], "count", len(no_footer))

# full count
no_footer_all = []
for i in range(1,213):
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    ps = [txt(p) for p in th["paragraphs"]]
    if not any("*Source: ch" in p for p in ps): no_footer_all.append(i)
print("all without footer:", no_footer_all)

# 2. -ๆ doubling rule
doub = 0
samples = []
for i in range(1,213):
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    for ln,p in enumerate(th["paragraphs"],1):
        s = txt(p)
        for m in re.finditer(r'[\u0e00-\u0e7f]+ๆ', s):
            doub += 1
            if len(samples) < 12: samples.append((i,ln,s[:100]))
print("\n===== -ๆ doubling total:", doub)
for s in samples: print(" ", s)

# 3. รู้สึกว่า/คิดว่า/เชื่อว่า filter words
fw = {}
for i in range(1,213):
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    sall = "\n".join(txt(p) for p in th["paragraphs"])
    for w in ["รู้สึกว่า","คิดว่า","เชื่อว่า"]:
        fw[w] = fw.get(w,0) + sall.count(w)
print("\n===== filter words:", fw)

# 4. title translated?
print("\n===== TITLE untranslated (has CJK in title.translated) =====")
for i in range(1,213):
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    t = th.get("title",{}).get("translated","")
    if re.search(r'[\u4e00-\u9fff]', t):
        print(f"ch{i}: {t}")
