"""Build cn.json for ALL chapters from source .md files.
Cleans artifacts, splits paragraphs, creates cn.json for any chapter missing one."""
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(r'C:\Users\BlankScreen\Workspace\Projects\NovelClaw\novels\global-descent\chapters')
SRC = BASE / 'source'

# ── Cleaning rules ──────────────────────────────────────────────────────

HEADER_RE = re.compile(r'^#\s*第\d+章')  # "# 第12章"
TITLE_RE = re.compile(r'^第\d+章\s')      # "第12章 霜狼戰士，出動！"
THANKS_RE = re.compile(r'^(感谢[书書]友|感謝[书書]友|謝謝?各位|推薦?票|月票|打赏|打賞)')
END_RE = re.compile(r'\(本章完\)|（本章完）')
PUNCT_ONLY_RE = re.compile(r'^[\s\u3000\.\,\!\?\。\，\！\？\…\⋯\～\~\·]+$')

def is_artifacts_line(stripped: str) -> bool:
    """Check if a line is scraping/HTML/metadata artifact."""
    if not stripped:
        return True
    if len(stripped) <= 1 and not stripped.isalpha():
        return True
    if stripped.startswith('#'):
        return True
    if stripped.startswith('<'):
        return True
    if PUNCT_ONLY_RE.match(stripped):
        return True
    # Thank-you / voting sections at end of chapter
    if THANKS_RE.match(stripped):
        return True
    if any(kw in stripped for kw in ['推薦票', '推荐票', '月票', '打赏', '打賞', '點幣', '追讀', '追读']):
        return True
    if re.match(r'^\d+张月票', stripped):
        return True
    if re.match(r'^感谢.*的\d+张月票', stripped):
        return True
    if re.match(r'^感谢.*打赏', stripped):
        return True
    if re.match(r'^感谢各位书友', stripped):
        return True
    return False

def clean_source(text: str) -> list[str]:
    """Clean source .md text and return paragraphs."""
    lines = text.split('\n')
    
    # Remove header/title lines
    filtered = []
    for line in lines:
        stripped = line.strip()
        if HEADER_RE.match(stripped):
            continue
        if TITLE_RE.match(stripped):
            # Extract the actual title part after "第X章 "
            title_text = re.sub(r'^第\d+章\s*', '', stripped)
            if title_text:
                filtered.append(title_text)
            continue
        if is_artifacts_line(stripped):
            continue
        filtered.append(stripped)
    
    # Combine into paragraphs (split on double newlines or natural breaks)
    # First pass: group by paragraph breaks
    raw_paras = []
    current = []
    for line in filtered:
        if not line.strip():
            if current:
                raw_paras.append(''.join(current))
                current = []
        else:
            current.append(line)
    if current:
        raw_paras.append(''.join(current))
    
    # Second pass: clean each paragraph
    cleaned = []
    for p in raw_paras:
        p = p.strip()
        if not p:
            continue
        # Remove end marker "(本章完)" if it's a standalone paragraph
        if END_RE.match(p):
            continue  # Skip - will be added by assembler
        # If end marker is embedded, remove it
        p = END_RE.sub('', p).strip()
        if p:
            cleaned.append(p)
    
    # If too few paragraphs (< 3), try splitting by line
    if len(cleaned) < 3 and len(filtered) > 3:
        cleaned = [l for l in filtered if l and len(l) > 10]
        if not cleaned:
            cleaned = [l for l in filtered if l]
    
    return cleaned if cleaned else [text.strip()]


# ── Main ─────────────────────────────────────────────────────────────────

now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')

existing_cn = set()
for f in BASE.glob('*.cn.json'):
    m = re.match(r'(\d+)\.cn\.json', f.name)
    if m:
        existing_cn.add(int(m.group(1)))

existing_th = set()
for f in BASE.glob('*.th.json'):
    m = re.match(r'(\d+)\.th\.json', f.name)
    if m:
        existing_th.add(int(m.group(1)))

print(f'Source .md files: {len(list(SRC.glob("*.md")))}')
print(f'Existing cn.json: {len(existing_cn)} (chapters: {sorted(existing_cn)[:5]}...{sorted(existing_cn)[-5:]})')
print(f'Existing th.json: {len(existing_th)}')
print()

# Build cn.json for ALL chapters (including existing — to clean them)
# Focus on chapters that DON'T have cn.json yet
need_cn = set()
for ch in range(1, 1240):
    md_path = SRC / f'{ch:04d}.md'
    cn_path = BASE / f'{ch:04d}.cn.json'
    
    if not md_path.exists():
        continue
    
    # Always create if missing, OR if the existing one has only 1 paragraph (uncleaned)
    needs_update = False
    if ch not in existing_cn:
        need_cn.add(ch)
        continue  # We'll batch process below
    
    # Check if existing cn.json is just 1 big paragraph (uncleaned)
    try:
        with open(cn_path, encoding="utf-8") as f:
            d = json.load(f)
        paras = d.get('paragraphs', [])
        if len(paras) == 1 and len(paras[0]) > 500:
            need_cn.add(ch)  # Needs re-clean
    except:
        need_cn.add(ch)

print(f'Chapters needing cn.json creation/refresh: {len(need_cn)}')
if need_cn:
    print(f'  Range: {min(need_cn)} - {max(need_cn)}')

# Batch process
created = 0
errors = []
for ch in sorted(need_cn):
    md_path = SRC / f'{ch:04d}.md'
    cn_path = BASE / f'{ch:04d}.cn.json'
    
    try:
        raw_text = md_path.read_text(encoding='utf-8')
        paragraphs = clean_source(raw_text)
        
        # Extract title
        title_match = re.search(r'第(\d+)章\s*(.*?)$', raw_text.split('\n')[0] if raw_text.split('\n')[0].startswith('#') else '', re.MULTILINE)
        if not title_match:
            title_match = re.search(r'^第(\d+)章\s*(.*?)$', raw_text, re.MULTILINE)
        
        title_source = f'第{ch}章'
        title_text = ''
        if title_match:
            title_text = title_match.group(2).strip()
            if title_text:
                title_source = f'第{ch}章 {title_text}'
        
        cn_data = {
            "novelId": "global-descent",
            "chapterNo": ch,
            "sourceLang": "cn",
            "targetLang": "cn",
            "title": {
                "source": title_source,
                "translated": f"ตอนที่ {ch}"
            },
            "status": "source",
            "paragraphs": paragraphs,
            "updatedAt": now
        }
        
        cn_path.write_text(json.dumps(cn_data, ensure_ascii=False, indent=2), encoding='utf-8')
        created += 1
        
        if created % 100 == 0:
            print(f'  Progress: {created}/{len(need_cn)}')
            
    except Exception as e:
        errors.append(f'Ch {ch}: {e}')

print(f'\n=== RESULT ===')
print(f'Created/updated cn.json: {created}')
print(f'Errors: {len(errors)}')
if errors:
    for e in errors[:10]:
        print(f'  {e}')

# Verify
verified = len(list(BASE.glob('*.cn.json')))
print(f'\nTotal cn.json on disk: {verified}')
print(f'Total th.json on disk: {len(list(BASE.glob("*.th.json")))}')
