# -*- coding: utf-8 -*-
import json
BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = BASE + "/chapters"
def cn(i): return json.load(open(f"{CH}/{i:04d}.cn.json",encoding="utf-8"))
def th(i): return json.load(open(f"{CH}/{i:04d}.th.json",encoding="utf-8"))

for i in [33, 143, 182, 1]:
    c = cn(i); t = th(i)
    cnp = c["paragraphs"]; thp = t["paragraphs"]
    print(f"\n{'='*60}\nCH {i}: CN {len(cnp)} paras -> TH {len(thp)} paras")
    print("CN first 8 paras (junk probe):")
    for j,p in enumerate(cnp[:8]):
        print(f"  CN[{j}]: {p[:90]}")
    print("CN last 6 paras:")
    for j,p in enumerate(cnp[-6:]):
        print(f"  CN[{len(cnp)-6+j}]: {p[:90]}")
    print("TH first 3:")
    for j,p in enumerate(thp[:3]):
        print(f"  TH[{j}]: {p[:90]}")
    print("TH last 3:")
    for j,p in enumerate(thp[-3:]):
        print(f"  TH[{len(thp)-3+j}]: {p[:90]}")
