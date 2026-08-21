# -*- coding: utf-8 -*-
"""QA Round-2 tooling: glossary conflict analysis + CJK scan + chapter fix helpers."""
import json, re, collections, sys

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = BASE + "/chapters"
GL = BASE + "/glossary"

def parse_builtin():
    src = open(r"C:/Users/BlankScreen/Workspace/NovelClaw/internal/translator/sanitizer.go", encoding="utf-8").read()
    m = re.search(r'BuiltinNovelGlossary = map\[string\]string\{', src)
    body = src[m.end():]
    end = body.index('\n}')
    body = body[:end]
    builtin = {}
    # parse `"term": "repl",` lines
    for ln in body.splitlines():
        s = ln.strip()
        if not s.startswith('"'):
            continue
        # split on `": "` (comma optional at end)
        mm = re.match(r'^"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$', s)
        if mm:
            k = mm.group(1).encode('utf-8').decode('unicode_escape')
            v = mm.group(2).encode('utf-8').decode('unicode_escape')
            builtin[k] = v
    return builtin

def parse_md(path):
    d = {}
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s.startswith('|'):
            continue
        parts = [p.strip() for p in s.strip('|').split('|')]
        if len(parts) >= 2 and re.search(r'[\u4e00-\u9fff]', parts[0]):
            d[parts[0]] = parts[1]
    return d

def parse_json_glossary():
    d = {}
    path = GL + "/glossary.json"
    for item in json.load(open(path, encoding="utf-8")):
        d[item["term"]] = item.get("target", "")
    return d

def cjk_scan():
    leaks = collections.defaultdict(list)
    for n in range(1, 213):
        th = json.load(open(f"{CH}/{n:04d}.th.json", encoding="utf-8"))
        paras = th.get("paragraphs", [])
        texts = [p if isinstance(p, str) else p.get("text", "") for p in paras]
        for i, t in enumerate(texts, 1):
            cjk = re.findall(r'[\u4e00-\u9fff]', t)
            if cjk:
                leaks[n].append((i, ''.join(cjk), t))
    return leaks

if __name__ == "__main__":
    builtin = parse_builtin()
    locked = parse_md(GL + "/locked.md")
    gj = parse_json_glossary()

    print("== builtin:", len(builtin), "locked:", len(locked), "glossary.json:", len(gj))

    # 1. locked vs builtin conflicts
    print("\n### LOCKED vs BUILTIN (sanitizer.go) conflicts — code currently WINS at runtime")
    n = 0
    for term, lth in sorted(locked.items()):
        if term in builtin and builtin[term] != lth:
            n += 1
            print(f"  {term}  locked={lth!r}  builtin={builtin[term]!r}")
    print(f"  --> {n} conflicts")

    # 2. locked vs glossary.json conflicts (json wins merge, but prompt uses json+gml)
    print("\n### LOCKED vs glossary.json conflicts")
    n = 0
    for term, lth in sorted(locked.items()):
        if term in gj and gj[term] != lth:
            n += 1
            print(f"  {term}  locked={lth!r}  json={gj[term]!r}")
    print(f"  --> {n} conflicts")

    # 3. builtin terms NOT in locked (terms code will translate to a potentially wrong target)
    print("\n### BUILTIN terms NOT present in locked.md (silent potential overrides)")
    for term, v in sorted(builtin.items()):
        if term not in locked:
            print(f"  {term} -> {v!r}")

    # 4. CJK scan
    leaks = cjk_scan()
    print("\n### CURRENT CJK LEAK (TH files, full 0001-0212)")
    total = 0
    for n in sorted(leaks):
        cnt = sum(len(t[1]) for t in leaks[n])
        total += cnt
        print(f"  ch {n}: {cnt} chars, {len(leaks[n])} lines")
    print(f"  --> total leaked chars: {total}, chapters: {len(leaks)}")
