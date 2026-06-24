#!/usr/bin/env python3
"""compare_chapters.py — Compare old vs new translation quality.

Usage:
    python compare_chapters.py 1

Reads from novels/global-descent/chapters/0001.th.json (old)
and staging/drafts/global-descent/0001.th.json (new).
"""

import json, re, sys
from pathlib import Path

NUM = int(sys.argv[1]) if len(sys.argv) > 1 else 1
NOVEL = "global-descent"
OLD = Path(f"novels/{NOVEL}/chapters/{NUM:04d}.th.json")
DRAFT = Path(f"staging/drafts/{NOVEL}/{NUM:04d}.th.json")
SOURCE = Path(f"novels/{NOVEL}/chapters/{NUM:04d}.cn.json")

def load(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

old = load(OLD)
new = load(DRAFT)
src = load(SOURCE)

print(f"╒════════════════════════════════════════════════════╕")
print(f"│  Chapter {NUM:04d} — {NOVEL}")
if old and "model" in old:
    print(f"│  Old model: {old.get('model')}")
    print(f"│  Old provider: {old.get('provider')}")
if new and "model" in new:
    print(f"│  New model: {new.get('model')}")
    print(f"│  New provider: {new.get('provider')}")
print(f"╘════════════════════════════════════════════════════╛")
print()

print("══════════ 1. STATS ══════════")
for label, d in [("Old (DeepSeek)", old), ("New (Gemma)", new), ("Source (CN)", src)]:
    if not d:
        print(f"  {label}: N/A")
        continue
    paras = d.get("paragraphs", [])
    non_end = [p for p in paras if p not in ("(จบบท)", "(End)", "（終）", "(끝)")]
    chars = sum(len(p) for p in non_end)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", " ".join(non_end)))
    en_words = len(re.findall(r"\b[A-Za-z]{3,}\b", " ".join(non_end)))
    has_marker = paras[-1] if paras else "?"
    print(f"  {label}")
    print(f"    Paragraphs: {len(paras)} ({len(non_end)} non-end)")
    print(f"    Characters: {chars}")
    print(f"    CJK chars: {cjk}")
    print(f"    EN words: {en_words}")
    print(f"    End marker: {has_marker}")

print()
print("══════════ 2. OPENING (first 3 paragraphs) ══════════")
if old:
    print(f"  OLD: {old['paragraphs'][:3]}")
if new:
    print(f"  NEW: {new['paragraphs'][:3]}")

print()
print("══════════ 3. CLOSING (last 3 paragraphs) ══════════")
if old:
    print(f"  OLD: {old['paragraphs'][-3:]}")
if new:
    print(f"  NEW: {new['paragraphs'][-3:]}")

print()
print("══════════ 4. KEY DIFFERENCES ══════════")
if old and new:
    o_texts = [p for p in old["paragraphs"] if p not in ("(จบบท)",)]
    n_texts = [p for p in new["paragraphs"] if p not in ("(จบบท)",)]

    # CJK comparison
    o_cjk = sum(1 for p in o_texts if re.search(r"[\u4e00-\u9fff]", p))
    n_cjk = sum(1 for p in n_texts if re.search(r"[\u4e00-\u9fff]", p))
    print(f"  Paragraphs with CJK: Old={o_cjk}, New={n_cjk}")

    # EN blacklist words
    EN_BL = {"recruiting", "level", "boss", "damage", "skill", "quest",
             "dungeon", "party", "guild", "shield", "weapon", "attack"}
    def count_en(paras):
        return sum(1 for p in paras for w in re.findall(r"\b[a-zA-Z]{3,}\b", p) if w.lower() in EN_BL)
    print(f"  EN blacklist: Old={count_en(o_texts)}, New={count_en(n_texts)}")

    # Speaker detection (para with "")
    def count_dialogue(paras):
        return sum(1 for p in paras if re.search(r'["\u201c\u201d]', p))
    print(f"  Dialogue paras: Old={count_dialogue(o_texts)}, New={count_dialogue(n_texts)}")

    # System messages 【】
    def count_system(paras):
        return sum(1 for p in paras if "【" in p)
    print(f"  System msg 【】: Old={count_system(o_texts)}, New={count_system(n_texts)}")

    # Average sentence length
    def avg_len(paras):
        paras = [p for p in paras if p.strip()]
        return sum(len(p) for p in paras) / max(1, len(paras))
    print(f"  Avg para length: Old={avg_len(o_texts):.1f}, New={avg_len(n_texts):.1f}")

print()
print("══════════ 5. SPECIFIC PARAGRAPH COMPARISON ══════════")
if old and new:
    import difflib
    for i in range(min(5, len(o_texts), len(n_texts))):
        if o_texts[i] != n_texts[i]:
            print(f"  Para {i}:")
            print(f"    OLD: {o_texts[i][:120]}")
            print(f"    NEW: {n_texts[i][:120]}")
            print()
