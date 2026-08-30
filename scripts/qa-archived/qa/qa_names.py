# -*- coding: utf-8 -*-
"""Targeted verification: name consistency + length ratio + end markers + specific terms."""
import json, os, re, glob, collections

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")

def parse_md_table(path):
    rows = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"): continue
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) < 2: continue
            src = parts[0]
            if not re.search(r'[\u4e00-\u9fff]', src): continue
            rows[src] = parts[1]
    return rows

locked = parse_md_table(os.path.join(BASE, "glossary", "locked.md"))
reference = parse_md_table(os.path.join(BASE, "glossary", "reference.md"))
auto = parse_md_table(os.path.join(BASE, "glossary", "auto.md"))

# candidate TH variants to detect (exact)
variants = {
    "曹星": ["เฉาซิง", "เฉา"],  # ตัวเอก
    "阿星": ["อาซิง"],
    "柳慕雪": ["หลิวมู่เสวี่ย"],
    "大白": ["ต้าป่าย", "ต้าไป๋"],  # mammoth
    "阿薩姆": ["อาซัม"],
    "安德鲁": ["แอนดรูว์", "แอนดรู"],
    "蕾妮丝·鹰眼": ["เลนนิส ฮอว์อาย", "เรนนี่", "เลนนิส"],
    "茱莉叶特": ["จูลี่เอท", "จูเลียต", "จูเลียต"],
    "布洛特·硫磺石": ["บรูนท์", "โบรท", "บลอท"],
    "伊勒娜": ["อิเลน่า", "อีลิน่า", "เอเลน่า"],
    "妮芙": ["นีฟ"],
    "莎拉": ["ซาร่า"],
    "陳江": ["เฉินเจียง"],
    "吴家辉": ["อู๋เจียฮุย"],
    "阿法纳西": ["อาฟานาซี"],
    "曹一": ["เฉาอี้"],
    "曹二": ["เฉาเอ้อร์"],
    "香江": ["เซียนเจียง", "ฮ่องกง"],
    "冰封纪元": ["มหายุคน้ำแข็ง", "ยุคน้ำแข็ง"],
    "阿斯卡隆": ["อัสคาลอน", "อัสคารอน"],
    "永盛集团": ["กลุ่มหย่งเซิ่ง", "หย่งเซิ่งกรุ๊ป", "กลุ่มย่งเสิง"],
    "迈巴赫": ["มายบัค", "เมอร์เซเดส-เบนซ์"],
    "精神": ["จิตวิญญาณ", "พลังจิต", "ปัญญา"],
    "敏捷": ["ความเร็ว", "ความว่องไว"],
    "力量": ["กำลัง", "พละกำลัง"],
}

def paras_to_text(ps):
    out = []
    for p in ps:
        if isinstance(p, dict): out.append(p.get("text",""))
        else: out.append(str(p))
    return out

name_count = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(int)))
chapters_with = collections.defaultdict(set)
length_bad = []
missing_end = []
for i in range(1, 213):
    thf = os.path.join(CH, f"{i:04d}.th.json")
    cnf = os.path.join(CH, f"{i:04d}.cn.json")
    if not os.path.exists(thf) or not os.path.exists(cnf): continue
    th = json.load(open(thf, encoding="utf-8"))
    cn = json.load(open(cnf, encoding="utf-8"))
    thp = paras_to_text(th["paragraphs"])
    cnp = paras_to_text(cn["paragraphs"])
    th_full = "\n".join(thp)
    cn_full = "\n".join(cnp)
    ratio = len(thp) / max(1, len(cnp))
    if ratio < 0.8: length_bad.append((i, len(cnp), len(thp), round(ratio,2)))
    if thp and "(จบบท)" not in thp[-1]: missing_end.append(i)
    for src, vs in variants.items():
        # only track if source term actually in CN
        if src in cn_full:
            for v in vs:
                if v in th_full:
                    name_count[src][v][i] += th_full.count(v)

print("=== END MARKER MISSING (last para no (จบบท)) ===")
print(missing_end[:60], "total:", len(missing_end))

print("\n=== LENGTH RATIO < 0.8 (possible skipping/truncation) ===")
print("count:", len(length_bad))
for r in length_bad: print(r)

print("\n=== PER-TERM VARIANT USAGE ===")
for src in variants:
    vs = name_count.get(src, {})
    if not vs: continue
    total = {v: sum(chs.values()) for v, chs in vs.items()}
    if any(k > 0 for k in total.values()) and (len(total) > 1 or list(total.values())[0] < 3):
        print(f"  {src}: {total}")

print("\n=== SPECIFIC: 大白 variants per chapter ===")
for v, chs in name_count.get("大白", {}).items():
    print(f"   {v}: {sorted(chs)}")

print("\n=== SPECIFIC: 香江 variants per chapter ===")
for v, chs in name_count.get("香江", {}).items():
    print(f"   {v}: {sorted(chs)[:40]}")

print("\n=== SPECIFIC: 精神 variants per chapter (first 30) ===")
for v, chs in name_count.get("精神", {}).items():
    print(f"   {v}: {sorted(chs)[:40]}")

print("\n=== SPECIFIC: 敏捷/力量 variants ===")
for term in ["敏捷","力量"]:
    for v, chs in name_count.get(term, {}).items():
        print(f"   {term} {v}: {sorted(chs)[:40]}")
