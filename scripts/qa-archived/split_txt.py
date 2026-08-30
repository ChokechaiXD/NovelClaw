#!/usr/bin/env python3
"""Split a full-novel TXT file into NovelClaw chapter JSON files."""
import json
import os
import re
import sys

def split_novel(txt_path, out_dir):
    """Parse TXT and write chapter JSON files."""
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Split on chapter headers: optional leading space + 第N章 + title
    pattern = re.compile(r"^(?: *)第(\d+)章[^\n]*", re.MULTILINE)
    matches = list(pattern.finditer(text))
    
    if not matches:
        print("No chapters found!")
        return

    os.makedirs(out_dir, exist_ok=True)
    
    # Skip catalog.json if exists
    written = 0
    for i, m in enumerate(matches):
        ch_num = int(m.group(1))
        # Extract title (the full line)
        start = m.start()
        end_line = text.index("\n", start) if "\n" in text[start:] else len(text)
        title = text[start:end_line].strip()
        
        # Extract content: from end of title line to start of next chapter
        content_start = end_line + 1
        if i + 1 < len(matches):
            content_end = matches[i + 1].start()
        else:
            content_end = len(text)
        
        raw_content = text[content_start:content_end].strip()
        
        # Split into paragraphs, skip empty lines
        paragraphs = []
        for line in raw_content.split("\n"):
            line = line.strip()
            if line:
                # Remove leading/trailing junk
                if any(junk in line for junk in ["69shu", "69yuedu", "69xinshu", "黄金屋", "黃金屋",
                    "请记住本书首发域名", "請記住本書首發域名", "本章完", "最新网址", "最新網址",
                    "天才一秒记住", "笔趣阁", "筆趣閣", "章节错误,点此报送", "章节缺失"]):
                    continue
                paragraphs.append(line)
        
        if not paragraphs:
            continue
        
        # Write chapter JSON
        ch_file = os.path.join(out_dir, f"{ch_num:04d}.cn.json")
        chapter_data = {
            "chapterNo": ch_num,
            "title": title,
            "paragraphs": paragraphs,
            "url": f"https://www.fantinovels.com/744298/"
        }
        
        with open(ch_file, "w", encoding="utf-8") as f:
            json.dump(chapter_data, f, ensure_ascii=False, indent=2)
        
        written += 1
        if written % 100 == 0:
            print(f"  Written {written} chapters...")
    
    print(f"Done! Wrote {written} chapter files to {out_dir}")
    return written

if __name__ == "__main__":
    txt_path = sys.argv[1] if len(sys.argv) > 1 else "novels/global-descent/full_novel_utf8.txt"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "novels/global-descent/chapters"
    split_novel(txt_path, out_dir)
