# -*- coding: utf-8 -*-
"""Diff the 3 glossary sources exactly. Read Go source as UTF-8, no re-decode."""
import json, re, io

BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
GL = BASE + "/glossary"
GO = r"C:/Users/BlankScreen/Workspace/NovelClaw/internal/translator/sanitizer.go"

def parse_go_map():
    src = io.open(GO, encoding="utf-8").read()
    start = src.index("BuiltinNovelGlossary = map[string]string{")
    end = src.index("\n}", start)
    body = src[start:end]
    d = {}
    for ln in body.splitlines():
        s = ln.strip()
        mm = re.match(r'^"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$', s)
        if mm:
            d[mm.group(1)] = mm.group(2)
    return d

def parse_md(path):
    d = {}
    for ln in io.open(path, encoding="utf-8"):
        s = ln.strip()
        if not s.startswith("|"):
            continue
        parts = [p.strip() for p in s.strip("|").split("|")]
        if len(parts) >= 2 and re.search(r'[\u4e00-\u9fff]', parts[0]):
            d[parts[0]] = parts[1]
    return d

def parse_json_glossary():
    d = {}
    for item in json.load(io.open(GL + "/glossary.json", encoding="utf-8")):
        d[item["term"]] = item.get("target", "")
    return d

def parse_yml():
    """Extract source->thai pairs from glossary.yml (flat list format)."""
    d = {}
    cur = None
    for ln in io.open(GL + "/glossary.yml", encoding="utf-8"):
        s = ln.strip()
        if s.startswith("- source:"):
            cur = s[len("- source:"):].strip().strip("'")
        elif s.startswith("thai:") and cur is not None:
            d[cur] = s[len("thai:"):].strip().strip("'")
    return d

builtin = parse_go_map()
locked = parse_md(GL + "/locked.md")
reference = parse_md(GL + "/reference.md")
gj = parse_json_glossary()
gyml = parse_yml()

print("counts  builtin=%d locked=%d reference=%d glossary.json=%d glossary.yml=%d" %
      (len(builtin), len(locked), len(reference), len(gj), len(gyml)))

print("\n=== LOCKED vs BUILTIN conflicts (code overrides locked at runtime) ===")
for term in sorted(locked):
    if term in builtin and builtin[term] != locked[term]:
        print("  %s | locked=%s | builtin=%s" % (term, locked[term], builtin[term]))

print("\n=== LOCKED vs glossary.json conflicts ===")
for term in sorted(locked):
    if term in gj and gj[term] != locked[term]:
        print("  %s | locked=%s | json=%s" % (term, locked[term], gj[term]))

print("\n=== LOCKED vs glossary.yml conflicts ===")
for term in sorted(locked):
    if term in gyml and gyml[term] != locked[term]:
        print("  %s | locked=%s | yml=%s" % (term, locked[term], gyml[term]))

print("\n=== glossary.json terms vs locked (ALL json entries) ===")
for term, v in sorted(gj.items()):
    l = locked.get(term)
    r = reference.get(term)
    flag = ""
    if l and l != v:
        flag = "  <-- CONFLICTS locked=%s" % l
    elif r and r != v:
        flag = "  <-- CONFLICTS reference=%s" % r
    print("  %s -> %s%s" % (term, v, flag))

print("\n=== builtin override terms that map to a TIER term with DIFFERENT target ===")
for term, v in sorted(builtin.items()):
    if term in locked and locked[term] != v:
        print("  LOCKED   %s -> %s (should be %s)" % (term, v, locked[term]))
    elif term in reference and reference[term] != v:
        print("  REF      %s -> %s (should be %s)" % (term, v, reference[term]))
