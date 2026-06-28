#!/usr/bin/env python3
"""Check which chapters failed"""
import glob, os

chapters_dir = r"C:\Users\BlankScreen\Workspace\NovelClaw\novels\global-descent\chapters"
files = sorted(glob.glob(os.path.join(chapters_dir, "0*.th.json")))

saved = set()
for f in files:
    basename = os.path.basename(f)
    ch = int(basename.split('.')[0])
    saved.add(ch)

failed = sorted(set(range(3, 103)) - saved)
print(f"บันทึกแล้ว: {len(saved)} ตอน")
print(f"ล้มเหลว: {len(failed)} ตอน")
print(f"ตอนที่ล้มเหลว: {failed}")
