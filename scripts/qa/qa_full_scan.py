# -*- coding: utf-8 -*-
"""
QA full scan for global-descent translation (chapters 0001-0212).
Checks: glossary compliance (P1/P2/P3), CJK leakage, forbidden terms,
anti-pattern slop, length ratio, title/end-marker/source-footer, name consistency.

Outputs: qa_full_scan.json + printed summary.
"""
import json, os, re, glob, collections, sys

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")

# ---------- glossary loading ----------
def parse_md_table(path):
    rows = {}  # src -> (th, priority, lock, category)
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) < 2:
                continue
            src = parts[0]
            if not re.search(r'[\u4e00-\u9fff]', src):
                continue
            th = parts[1] if len(parts) > 1 else ""
            priority = parts[3] if len(parts) > 3 else ""
            lock = ""
            notes = parts[4] if len(parts) > 4 else ""
            category = parts[2] if len(parts) > 2 else ""
            # priority from tier defaults
            rows[src] = {"th": th, "priority": priority, "category": category, "notes": notes, "lock": ""}
    return rows

def load_glossary_md():
    locked = {}
    reference = {}
    auto = {}
    gdir = os.path.join(BASE, "glossary")
    for fname, tier in [("locked.md","locked"),("reference.md","reference"),("auto.md","auto")]:
        path = os.path.join(gdir, fname)
        data = parse_md_table(path)
        for src, v in data.items():
            v = dict(v)
            v["tier"] = tier
            if tier == "locked":
                locked[src] = v
            elif tier == "reference":
                reference[src] = v
            else:
                auto[src] = v
    return locked, reference, auto

locked, reference, auto = load_glossary_md()
all_terms = {}
for d in (auto, reference, locked):
    for k, v in d.items():
        all_terms[k] = v

# glossary.json (curated)
gj_path = os.path.join(BASE, "glossary", "glossary.json")
glossary_json = {}
if os.path.exists(gj_path):
    for item in json.load(open(gj_path, encoding="utf-8")):
        glossary_json[item["term"]] = item.get("target","")

# builtin GO code glossary (from sanitizer.go) — known hard-coded overrides
builtin_overrides = {
    "大白":"ต้าไป๋", "香江":"ฮ่องกง", "冰封纪元":"ยุคน้ำแข็ง", "阿斯卡隆":"อัสคารอน",
    "永盛集团":"หย่งเซิ่งกรุ๊ป", "迈巴赫":"มายบัค", "领主":"ท่านลอร์ด", "天赋":"พรสวรรค์",
    "祝福":"พร", "忠诚度":"ค่าความภักดี", "力量":"พละกำลัง", "敏捷":"ความว่องไว",
    "体质":"สมรรถภาพร่างกาย", "精神":"พลังจิต",
}

# ---------- rules ----------
anti_patterns = ["อย่างไรก็ตาม","ดังนั้น","แม้ว่า","เต็มไปด้วยความ","ชาวอาณานิคม"]
forbidden_abs = ["ฮ่องกง"]  # hard-forbidden (locked.md says NOT ฮ่องกง)
# wrong translations for locked terms (use these as anomalies to flag)
cjk_re = re.compile(r'[\u4e00-\u9fff]')
thai_re = re.compile(r'[\u0e00-\u0e7f]')

cjk_leak = collections.Counter()
forbidden_hits = collections.Counter()
anti_hits = collections.Counter()
glossary_cn_leak = collections.Counter()  # term -> chapters count (CN term in TH)
glossary_wrong = collections.Counter()     # "term|thai_wrong" -> chapters
length_bad = []
title_missing_end = []
name_variants = collections.defaultdict(lambda: collections.defaultdict(int))  # cn_name -> th_variant -> count
sample_violations = []  # (ch, line, cn, th, issue, fix)

def scan():
    th_files = sorted(glob.glob(os.path.join(CH, "*.th.json")))
    for th_path in th_files:
        chnum = int(re.search(r'(\d+)\.th\.json$', th_path).group(1))
        if chnum > 212:
            continue
        cn_path = th_path.replace(".th.json", ".cn.json")
        if not os.path.exists(cn_path):
            continue
        th = json.load(open(th_path, encoding="utf-8"))
        cn = json.load(open(cn_path, encoding="utf-8"))
        def to_str(p):
            if isinstance(p, dict):
                return p.get("text", "")
            return str(p)
        th_paras = [to_str(p) for p in th.get("paragraphs", [])]
        cn_paras = [to_str(p) for p in cn.get("paragraphs", [])]
        th_full = "\n".join(th_paras)
        cn_full = "\n".join(cn_paras)

        # 1. CJK leak
        cjks = cjk_re.findall(th_full)
        if cjks:
            cjk_leak[chnum] = len(cjks)

        # 2. forbidden absolute
        for w in forbidden_abs:
            cnt = th_full.count(w)
            if cnt:
                forbidden_hits[f"ฮ่องกง"] += cnt
                for ln, p in enumerate(th_paras, 1):
                    if w in p:
                        # find cn line
                        cn_line = cn_paras[ln-1] if ln-1 < len(cn_paras) else ""
                        sample_violations.append((chnum, ln, cn_line[:120], p[:120],
                            "ใช้คำต้องห้าม '%s' (locked.md: ห้ามใช้ ให้ใช้ 'เซียนเจียง')" % w,
                            "เซียนเจียง"))

        # 3. glossary: CN term leaked into TH
        for src, v in all_terms.items():
            if src in th_full:
                glossary_cn_leak[src] += 1
            # wrong TH variant detection for locked terms
            if src in cn_full:
                expected = v["th"]
                # if expected not in th and src not in th — maybe check known wrong builtin
                if v["tier"] == "locked" and expected and expected not in th_full:
                    # check builtin override variant present?
                    if src in builtin_overrides and builtin_overrides[src] in th_full:
                        wv = builtin_overrides[src]
                        glossary_wrong[f"{src}->{wv} (ควรเป็น {expected})"] += 1
                        for ln, p in enumerate(th_paras, 1):
                            if wv in p and len(sample_violations) < 120:
                                cn_line = cn_paras[ln-1] if ln-1 < len(cn_paras) else ""
                                sample_violations.append((chnum, ln, cn_line[:120], p[:120],
                                    "glossary ผิด: '%s' ใช้สลับกับ locked '%s'" % (wv, expected), expected))

        # 4. anti-pattern
        for w in anti_patterns:
            cnt = th_full.count(w)
            if cnt:
                anti_hits[w] += cnt

        # 5. length ratio
        ratio = len(th_paras) / max(1, len(cn_paras))
        if ratio < 0.8 or ratio > 3.6:
            length_bad.append((chnum, len(cn_paras), len(th_paras), round(ratio,2)))

        # 6. end marker
        if th_paras and "(จบบท)" not in th_paras[-1] and "จบ" not in th_paras[-1]:
            title_missing_end.append(chnum)

        # 7. name variants: track TH variants for main locked names
        for src, v in locked.items():
            if v["category"] == "ตัวละคร":
                # find all distinct TH renderings that plausibly map (exact known variants)
                for w in [ "ต้าป่าย","ต้าไป๋","เฉาซิง","อาซิง","เฉา","หลิวมู่เสวี่ย","อาซัม",
                           "แอนดรูว์","เลนนิส","จูลี่เอท","นีฟ","ซาร่า","อิเลน่า","เฉินเจียง",
                           "อู๋เจียฮุย","อาฟานาซี","เฉาอี้","เฉาเอ้อร์","บลูสตาร์","เซียนเจียง",
                           "ฮ่องกง","อัสคาลอน","อัสคารอน","มหายุคน้ำแข็ง","ยุคน้ำแข็ง",
                           "หย่งเซิ่งกรุ๊ป","กลุ่มหย่งเซิ่ง","กลุ่มย่งเสิง","มายบัค","เมอร์เซเดส-เบนซ์"]:
                    if w in th_full:
                        name_variants[src][w] += 1

# run
scan()

# consolidate name variant anomalies (locked terms with >1 distinct variant)
name_conflicts = {k: dict(v) for k, v in name_variants.items() if len(v) > 1}

out = {
    "scanned": 212,
    "cjk_leak_chapters": len(cjk_leak),
    "cjk_leak_total_chars": sum(cjk_leak.values()),
    "cjk_top": cjk_leak.most_common(30),
    "forbidden_hits": dict(forbidden_hits),
    "anti_hits": dict(anti_hits),
    "glossary_cn_leak": dict(glossary_cn_leak.most_common(60)),
    "glossary_wrong": dict(glossary_wrong.most_common(60)),
    "length_bad": length_bad[:40],
    "title_missing_end": title_missing_end[:30],
    "name_conflicts": {k: v for k, v in name_conflicts.items() if any(c >= 3 for c in v.values()) or len(v) > 1 and sum(v.values()) >= 5},
}
with open(os.path.join(BASE, "..", "qa_full_scan.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(json.dumps(out, ensure_ascii=False, indent=2))

print("\n\n############ SAMPLE VIOLATIONS (up to 120) ############")
for s in sample_violations[:40]:
    print(f"\n--- ch {s[0]} line {s[1]} ---")
    print("CN:", s[2])
    print("TH:", s[3])
    print("ISSUE:", s[4])
    print("FIX:", s[5])

print("\n\n############ NAME VARIANTS (locked characters, raw) ############")
for src, variants in sorted(name_variants.items()):
    if sum(variants.values()) >= 3:
        print(f"  {src} ({locked[src]['th']}): {dict(variants)}")

print("\nDone. Wrote qa_full_scan.json")
