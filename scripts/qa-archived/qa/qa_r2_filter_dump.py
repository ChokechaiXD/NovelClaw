# -*- coding: utf-8 -*-
"""Print all filter-word occurrences paired with aligned CN context for manual review."""
import json, io, sys
sys.stdout.reconfigure(encoding="utf-8")
occ = json.load(io.open(r"C:/Users/BlankScreen/Workspace/NovelClaw/r2_filter_occ.json", encoding="utf-8"))
for i, o in enumerate(occ, 1):
    print(f"--- {i}. ch{o['ch']} L{o['idx']} [{o['w']}] ---")
    print("TH:", o["th"])
    print("CN:", o["cn"][:200])
