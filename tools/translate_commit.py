#!/usr/bin/env python3
"""
Workflow helper for translating + committing chapters.

Standard pipeline (P'Chok's choice, 2026-06-14):
  1. Run CN check on existing chapter
  2. Auto-fix common block type issues (system_message → system, ...)
  3. Validate schema
  4. (Commit happens outside this script via `git commit`)

Usage:
  python tools/translate_commit.py check 116      # just check existing ch
  python tools/translate_commit.py fix-types 116   # auto-fix block types
  python tools/translate_commit.py commit 116 "ch 116: real translation, 263 blocks, 0 CN leak"
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "tools"))

CN = re.compile(r'[\u4e00-\u9fff]')
JP_KANA = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')


def ch_path(num):
    return REPO / "novels" / "global-descent" / "chapters" / f"{num:04d}.json"


def fix_block_types(data):
    """Auto-fix common block type issues. Returns (changed_count, fixes)."""
    fixes = []
    for i, b in enumerate(data.get('blocks', [])):
        t = b.get('type')
        text = b.get('text', '')

        # system_message → system
        if t == 'system_message':
            b['type'] = 'system'
            fixes.append((i, 'system_message → system'))

        # end_marker → end
        elif t == 'end_marker':
            b['type'] = 'end'
            fixes.append((i, 'end_marker → end'))

        # system with parenthetical = narration
        elif t == 'system' and text.startswith('(') and text.endswith(')'):
            b['type'] = 'narration'
            fixes.append((i, f'parenthetical → narration: {text[:50]}'))

        # system with standalone ... = narration
        elif t == 'system' and text == '...':
            b['type'] = 'narration'
            fixes.append((i, 'standalone ... → narration'))

    return len(fixes) > 0, fixes


def count_cn_leak(data):
    """Count CN/JP leak in narration/dialogue."""
    leaks = 0
    for b in data.get('blocks', []):
        if b.get('type') in ('narration', 'dialogue'):
            text = b.get('text', '')
            leaks += len(CN.findall(text)) + len(JP_KANA.findall(text))
    return leaks


def cmd_check(num):
    """Check existing ch: CN leak + schema."""
    path = ch_path(num)
    if not path.exists():
        print(f"❌ ch {num} not found at {path}")
        return 1

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    leak = count_cn_leak(data)
    from collections import Counter
    types = dict(Counter(b['type'] for b in data['blocks']))
    print(f"ch {num}: {len(data['blocks'])} blocks ({types})")
    print(f"  CN/JP leak: {leak}")

    # Schema
    try:
        from schema import Chapter
        ch = Chapter(**data)
        print(f"  Schema: OK")
    except Exception as e:
        print(f"  Schema: FAIL — {str(e)[:200]}")
        return 1

    return 0 if leak == 0 else 1


def cmd_fix_types(num):
    """Auto-fix block types in ch."""
    path = ch_path(num)
    if not path.exists():
        print(f"❌ ch {num} not found")
        return 1

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    changed, fixes = fix_block_types(data)
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ ch {num}: applied {len(fixes)} fix(es)")
        for i, fix in fixes[:5]:
            print(f"  block {i}: {fix}")
        if len(fixes) > 5:
            print(f"  ... +{len(fixes) - 5} more")
    else:
        print(f"✓ ch {num}: no fixes needed")
    return 0


def cmd_commit(num, message):
    """Stage ch and commit with given message (then update registry)."""
    path = ch_path(num)
    if not path.exists():
        print(f"❌ ch {num} not found")
        return 1

    # Stage
    subprocess.run(['git', 'add', str(path.relative_to(REPO))], cwd=REPO, check=True)

    # Commit
    result = subprocess.run(
        ['git', 'commit', '-m', message],
        cwd=REPO, capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ git commit failed: {result.stderr[:500]}")
        return 1

    # Update registry
    update_registry(num, message)
    return 0


def update_registry(num, message):
    """Update .translation_state.json with this ch."""
    reg_path = REPO / "novels" / "global-descent" / ".translation_state.json"

    with open(path, 'r', encoding='utf-8') if False else open(ch_path(num), 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Load existing
    if reg_path.exists():
        with open(reg_path, 'r', encoding='utf-8') as f:
            reg = json.load(f)
    else:
        reg = {
            "last_chapter": 0,
            "total_chapters": 1239,
            "last_commit": "",
            "history": [],
        }

    # Get latest git commit hash
    result = subprocess.run(
        ['git', 'rev-parse', '--short', 'HEAD'],
        cwd=REPO, capture_output=True, text=True
    )
    commit_hash = result.stdout.strip() if result.returncode == 0 else "?"

    leak = count_cn_leak(data)
    from collections import Counter
    types = dict(Counter(b['type'] for b in data['blocks']))

    entry = {
        "ch": num,
        "blocks": len(data['blocks']),
        "leak": leak,
        "commit": commit_hash,
        "message": message,
        "types": types,
    }

    reg['last_chapter'] = num
    reg['last_commit'] = commit_hash
    reg['history'].append(entry)
    # Keep last 50
    reg['history'] = reg['history'][-50:]

    with open(reg_path, 'w', encoding='utf-8') as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)

    print(f"✓ Registry updated: last_chapter={num}, commit={commit_hash}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    num = int(sys.argv[2])

    if cmd == 'check':
        sys.exit(cmd_check(num))
    elif cmd == 'fix-types':
        sys.exit(cmd_fix_types(num))
    elif cmd == 'commit':
        if len(sys.argv) < 4:
            print("commit needs: python translate_commit.py commit N 'message'")
            sys.exit(1)
        sys.exit(cmd_commit(num, sys.argv[3]))
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: check, fix-types, commit")
        sys.exit(1)


if __name__ == '__main__':
    main()
