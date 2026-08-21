# -*- coding: utf-8 -*-
"""QA scan for global-descent translation quality."""
import json, os, re, glob, collections

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")

# Load glossary locked/reference terms (CN -> TH)
def load_glossary():
    locked = {}
    reference = {}
    for fname, tier in [("locked.md", "locked"), ("reference.md", "reference")]:
        path = os.path.join(BASE, "glossary", fname)
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("|") and ("---" in line or "Source" in line):
                    continue
                if line.startswith("|"):
                    parts = [p.strip() for p in line.strip("|").split("|")]
                    if len(parts) >= 2:
                        src, th = parts[0], parts[1]
                        if re.search(r'[\u4e00-\u9fff]', src):
                            if tier == "locked":
                                locked[src] = th
                            else:
                                reference[src] = th
    return locked, reference

locked, reference = load_glossary()

# anti-patterns from index.md
anti_patterns = ["อย่างไรก็ตาม", "ดังนั้น", "แม้ว่า", "เต็มไปด้วยความ", "ชาวอาณานิคม"]

# banned/error from guard rails
forbidden = ["ฮ่องกง"]

cjk_re = re.compile(r'[\u4e00-\u9fff]')
thai_re = re.compile(r'[\u0e00-\u0e7f]')

results = []
glossary_violations = collections.Counter()  # term -> count
name_inconsistency = collections.defaultdict(list)  # th name -> list of (chapter)
cn_leak_count = collections.Counter()  # chapter -> count of CJK chars in th
anti_count = collections.Counter()
forbidden_count = collections.Counter()
chapter_glossary_missing = collections.defaultdict(list)

for i in range(1, 213):
    cn_file = os.path.join(CH, f"{i:04d}.cn.json")
    th_file = os.path.join(CH, f"{i:04d}.th.json")
    if not os.path.exists(th_file):
        continue
    th = json.load(open(th_file, encoding="utf-8"))
    paras = th.get("paragraphs", [])
    full_text = "\n".join(paras)
    # 1. CJK leakage in TH text
    cjk_chars = cjk_re.findall(full_text)
    if cjk_chars:
        cn_leak_count[i] = len(cjk_chars)
    # 2. glossary violations: check if CN term appears untranslated OR wrong TH
    for src_term, target in list(locked.items()) + list(reference.items()):
        if src_term in full_text:
            glossary_violations[f"{src_term} (ยังเหลือ CN)"] += 1
            chapter_glossary_missing[i].append(src_term)
    # 3. forbidden
    for w in forbidden:
        if w in full_text:
            forbidden_count[w] += 1
    # 4. anti-pattern
    for w in anti_patterns:
        if w in full_text:
            anti_count[w] += 1
            chapter_glossary_missing[i].append(f"[anti]{w}")

# 5. name consistency: count th names usage across chapters
def extract_names():
    # collect main locked names' th forms
    names = {}
    for src, th in locked.items():
        if th and not th.startswith("{"):
            names[src] = th
    return names

locked_names = extract_names()
name_usage = collections.defaultdict(list)
for i in range(1, 213):
    th_file = os.path.join(CH, f"{i:04d}.th.json")
    if not os.path.exists(th_file):
        continue
    th = json.load(open(th_file, encoding="utf-8"))
    full_text = "\n".join(th.get("paragraphs", []))
    for src, th_name in locked_names.items():
        if th_name in full_text:
            name_usage[th_name].append(i)

print("="*60)
print("SUMMARY")
print("="*60)
print(f"Total chapters scanned: {len([f for f in glob.glob(CH+'/*.th.json')] )}")
print(f"Total chapters with CJK leakage in TH: {len(cn_leak_count)}")
total_leak = sum(cn_leak_count.values())
print(f"Total CJK chars leaked: {total_leak}")
print()
print("Top 20 chapters with most CJK leakage:")
for ch, cnt in cn_leak_count.most_common(20):
    print(f"  ch {ch}: {cnt} CJK chars")

print()
print("Glossary violations (CN term left untranslated, count of chapters):")
for term, cnt in glossary_violations.most_common(50):
    print(f"  {term}: {cnt} chapters")

print()
print("Anti-pattern slop occurrences:")
for w, cnt in anti_count.most_common():
    print(f"  {w}: {cnt}")

print()
print("Forbidden term occurrences:")
for w, cnt in forbidden_count.items():
    print(f"  {w}: {cnt}")

# name usage check
print()
print("Main locked names coverage (chapters where TH name appears):")
if name_usage:
    for name, chs in sorted(name_usage.items()):
        print(f"  {name}: {len(chs)} chapters")

# Consistency check: for each locked name, what CN appears but th missing
print()
print("Chapters with glossary missing terms:")
for ch in sorted(chapter_glossary_missing):
    print(f"  ch {ch}: {chapter_glossary_missing[ch]}")
