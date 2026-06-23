"""migrate_json.py — Migrate chapter data to per-language canonical JSON format.

Usage: python tools/migrate_json.py [--slug NAME] [--all]

Creates/updates:
  novels/{slug}/novel.json               — novel metadata (canonical)
  novels/{slug}/chapters.json            — chapter index (fast-path for listing)
  novels/{slug}/chapters/index.json      — backward-compat chapter index
  novels/{slug}/chapters/{num}.th.json   — Thai translation per chapter
  novels/{slug}/chapters/{num}.cn.json   — Chinese source per chapter

Run idempotently. Source files under chapters/source/*.md are used for cn.json.
"""

from pathlib import Path
import json, re

NOVELS_DIR = Path(__file__).resolve().parent.parent / "novels"

def get_source_paragraphs(slug: str, num: int):
    """Extract paragraphs from source markdown file."""
    sp = NOVELS_DIR / slug / "chapters" / "source" / f"{num:04d}.md"
    if not sp.exists(): return [], f"\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 {num}"
    raw = sp.read_text("utf-8")
    m = re.match(r"^#\s+(.+?)\r?\n", raw)
    title = m[1].strip() if m else f"\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 {num}"
    body = raw[m.end():].strip() if m else raw.strip()
    return [p.strip() for p in body.split("\n") if p.strip()], title

def migrate_novel(slug: str):
    cd = NOVELS_DIR / slug / "chapters"
    if not cd.exists(): return
    th_files = sorted(cd.glob("*.th.json"))
    
    # Create/update novel.json from meta.md
    md = NOVELS_DIR / slug / "meta.md"
    meta = {"slug": slug, "title": slug, "sourceLang": "cn", "targetLang": "th", "totalChapters": 0, "description": ""}
    if md.exists():
        raw = md.read_text("utf-8")
        m = re.match(r"^---\s*\n([\s\S]*?)\n---", raw)
        if m:
            for line in m[1].split("\n"):
                kv = re.match(r"^(\w[\w_]*):\s*(.+?)\s*$", line)
                if kv: meta[kv[1].replace("source_lang","sourceLang").replace("target_lang","targetLang").replace("total_chapters","totalChapters")] = kv[2].replace("'","").replace('"',"")
        desc, in_desc = [], False
        for line in raw.split("\n"):
            if in_desc:
                if line.startswith("## "): break
                desc.append(line.strip())
            elif line == "## Description": in_desc = True
        meta["description"] = "\n".join(desc).strip()
    
    (NOVELS_DIR / slug / "novel.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    
    # Build chapter index
    chapters = []
    for f in th_files:
        try:
            d = json.loads(f.read_text("utf-8"))
            chapters.append({"num": d["chapterNo"], "title": d.get("title",{}).get("translated",f"\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 {d['chapterNo']}"), "status": d.get("status","translated")})
        except: pass
    
    # Add source-only chapters
    cn_files = {int(f.stem.replace(".cn","")) for f in cd.glob("*.cn.json")}
    for num in sorted(cn_files):
        if not any(c["num"] == num for c in chapters):
            try:
                d = json.loads((cd / f"{num:04d}.cn.json").read_text("utf-8"))
                chapters.append({"num": num, "title": d.get("title",{}).get("source",f"\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48 {num}"), "status": "source_only"})
            except: pass
    
    chapters.sort(key=lambda c: c["num"])
    
    (NOVELS_DIR / slug / "chapters.json").write_text(json.dumps({"slug": slug, "totalChapters": len(chapters), "chapters": chapters}, ensure_ascii=False, indent=2), "utf-8")
    
    # Backward-compat index.json
    idx = [{"num": c["num"], "title": c["title"], "isTranslated": c["status"] != "source_only"} for c in chapters]
    (cd / "index.json").write_text(json.dumps({"slug": slug, "chapters": idx}, ensure_ascii=False, indent=2), "utf-8")
    
    return len(chapters)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate novels to per-language JSON format")
    parser.add_argument("--slug", help="Specific novel slug (default: all)")
    args = parser.parse_args()
    slugs = [args.slug] if args.slug else [d.name for d in sorted(NOVELS_DIR.iterdir()) if d.is_dir()]
    for s in slugs:
        n = migrate_novel(s)
        if n: print(f"  {s}: {n} chapters")
    print("Done")
