# -*- coding: utf-8 -*-
import json, os, re, glob
BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")
cjk = re.compile(r'[\u4e00-\u9fff]')
def txt(p):
    return p.get("text","") if isinstance(p,dict) else str(p)

# 1. CJK leak content
print("===== CJK LEAK CONTENT =====")
for i in range(1,213):
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    for ln,p in enumerate(th["paragraphs"],1):
        s = txt(p)
        m = cjk.findall(s)
        if m:
            n = cjk.search(s)
            print(f"ch{i} L{ln} [{len(m)} CJK]: ...{s[max(0,n.start()-40):n.start()+40]}...")

# 2. 安德鲁 both spellings
print("\n===== 安德鲁 spelling split =====")
for i in range(1,213):
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    for ln,p in enumerate(th["paragraphs"],1):
        s = txt(p)
        if "แอนดรู" in s and "แอนดรูว์" not in s:
            print(f"ch{i} L{ln}: ...{s[max(0,s.find('แอนดรู')-30):s.find('แอนดรู')+30]}...")

# 3. game name / company / car
print("\n===== GAME NAME 冰封纪元 variants =====")
for i in range(1,213):
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    s = "\n".join(txt(p) for p in th["paragraphs"])
    for v in ["มหายุคน้ำแข็ง","ยุคน้ำแข็ง"]:
        if v in s:
            for ln,p in enumerate(th["paragraphs"],1):
                if v in txt(p):
                    print(f"ch{i} L{ln} ({v}): ...{txt(p)[:90]}...")
                    break
            break

print("\n===== 永盛集团 variants =====")
for i in range(1,213):
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    s = "\n".join(txt(p) for p in th["paragraphs"])
    for v in ["หย่งเซิ่ง","ย่งเสิง","กลุ่มหย่งเส่ง"]:
        if v in s:
            for ln,p in enumerate(th["paragraphs"],1):
                if v in txt(p):
                    print(f"ch{i} L{ln} ({v}): ...{txt(p)[:110]}...")
                    break

print("\n===== 迈巴赫 variants =====")
for i in range(1,213):
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    s = "\n".join(txt(p) for p in th["paragraphs"])
    for v in ["มายบัค","เมอร์เซเดส","เบนซ์"]:
        if v in s:
            for ln,p in enumerate(th["paragraphs"],1):
                if v in txt(p):
                    print(f"ch{i} L{ln} ({v}): ...{txt(p)[:110]}...")
                    break

# 4. truncation suspects ch33,107,143 - first & last paras
print("\n===== TRUNCATION SUSPECTS (first+last) =====")
for i in [33,107,143,182,208]:
    cn = json.load(open(os.path.join(CH,f"{i:04d}.cn.json"),encoding="utf-8"))
    th = json.load(open(os.path.join(CH,f"{i:04d}.th.json"),encoding="utf-8"))
    cnp=[txt(p) for p in cn["paragraphs"]]; thp=[txt(p) for p in th["paragraphs"]]
    print(f"\n--- ch{i}: CN {len(cnp)} paras, TH {len(thp)} paras ---")
    print("CN first:", cnp[1][:100] if len(cnp)>1 else cnp[0][:100])
    print("TH first:", thp[1][:100] if len(thp)>1 else "")
    print("CN last :", cnp[-1][:100])
    print("TH last :", thp[-1][:100])
