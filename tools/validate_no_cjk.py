#!/usr/bin/env python3
"""
validate_no_cjk.py — CJK leakage checker for NovelClaw translations.

Checks translated chapter JSON files for:
1. CN (Chinese) character leakage — FAIL
2. JP (Japanese) character leakage — FAIL
3. EN game term leakage — WARN (configurable whitelist)

Usage:
    python tools/validate_no_cjk.py                    # check last translated
    python tools/validate_no_cjk.py 72                 # check specific chapter
    python tools/validate_no_cjk.py --all              # check all chapters
    python tools/validate_no_cjk.py --novel global-descent --all
    python tools/validate_no_cjk.py --strip            # strip donor-thanks blocks
    python tools/validate_no_cjk.py --fix-en           # auto-fix EN terms using whitelist
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    from constants import CHAPTERS_DIR, get_novel_root
    _has_constants = True
except ImportError:
    _has_constants = False

ALLOWED_LATIN_TOKENS: set[str] | None = None
check_en_terms = None
check_file_for_cjk_leaks = None

try:
    from validation import ALLOWED_LATIN_TOKENS as _shared_tokens  # noqa: E402
    from validation import check_en_terms as _shared_en             # noqa: E402
    from validation import check_file_for_cjk_leaks as _shared_file # noqa: E402
    ALLOWED_LATIN_TOKENS = _shared_tokens
    check_en_terms = _shared_en
    check_file_for_cjk_leaks = _shared_file
    _has_validation = True
except ImportError:
    _has_validation = False
    # ponytail: minimal inline fallback — keep only what standalone CLI needs
    ALLOWED_LATIN_TOKENS = {
        "HP", "MP", "EXP", "SSS", "SSR", "UR", "SP", "ID", "VIP",
        "S", "SS", "LR", "CD", "NPC", "PVP", "PVE",
        "LV", "LVL", "ATK", "DEF", "DMG", "BUFF", "DEBUFF",
        "AOE", "DPS", "TPS",
    }

    def check_en_terms(text):  # type: ignore
        words = re.findall(r"\b[A-Za-z][A-Za-z0-9]{1,}\b", text)
        whitelisted, blacklisted, unknown = [], [], []
        for w in words:
            upper = w.upper()
            if upper in ALLOWED_LATIN_TOKENS:
                whitelisted.append(w)
            elif upper == "GZ":
                blacklisted.append(w)
            elif w.isupper() and len(w) >= 2:
                unknown.append(w)
        return whitelisted, blacklisted, unknown

    def check_file_for_cjk_leaks(filepath):  # type: ignore
        issues = []
        with Path(filepath).open(encoding="utf-8") as f:
            data = json.load(f)
        blocks = data.get("blocks", [])
        for i, block in enumerate(blocks):
            text = block.get("text", "")
            btype = block.get("type", "?")
            cn = re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]", text)
            if cn:
                issues.append({"block": i + 1, "type": btype, "severity": "FAIL", "kind": "CN",
                               "detail": f"CN chars: {''.join(cn[:5])}", "text": text[:80]})
            jp = re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", text)
            if jp:
                issues.append({"block": i + 1, "type": btype, "severity": "FAIL", "kind": "JP",
                               "detail": f"JP chars: {''.join(jp[:5])}", "text": text[:80]})
            ko = re.findall(r"[\uac00-\ud7af\u1100-\u11ff]", text)
            if ko:
                issues.append({"block": i + 1, "type": btype, "severity": "FAIL", "kind": "KO",
                               "detail": f"KO chars: {''.join(ko[:5])}", "text": text[:80]})
            for pat in (r"求订阅", r"求追读", r"三更", r"月票", r"推荐票", r"GZ\b", r"^\s*GZ\s*$"):
                if re.search(pat, text):
                    issues.append({"block": i + 1, "type": btype, "severity": "FAIL",
                                   "kind": "ARTIFACT", "detail": f"Source artifact: {pat}", "text": text[:80]})
            _, bl, unk = check_en_terms(text)
            for w in bl:
                issues.append({"block": i + 1, "type": btype, "severity": "FAIL",
                               "kind": "EN_BLACKLIST", "detail": f"Blacklisted EN: {w}", "text": text[:80]})
            for w in unk:
                issues.append({"block": i + 1, "type": btype, "severity": "WARN", "kind": "EN_UNKNOWN",
                               "detail": f"Unknown EN term: {w}", "text": text[:80]})
        return issues


# ── Paths ───────────────────────────────────────────────────────────────────
def resolve_novel_root(novel_slug=None):
    if novel_slug and _has_constants:
        return get_novel_root(novel_slug)
    if _has_constants:
        return CHAPTERS_DIR.rsplit("/", 1)[0]
    return Path(__file__).resolve().parent.parent / "novels" / "global-descent"


def main():
    parser = argparse.ArgumentParser(description="CJK leakage checker")
    parser.add_argument("chapter", nargs="?", type=int, help="Chapter number to check")
    parser.add_argument("--all", action="store_true", help="Check all chapters")
    parser.add_argument("--novel", type=str, default=os.environ.get("NOVEL_SLUG", "global-descent"),
                        help="Novel slug. Uses $NOVEL_SLUG env var or 'global-descent'.")
    parser.add_argument("--strip", action="store_true", help="Strip donor-thanks blocks")
    parser.add_argument("--fix-en", action="store_true", help="Auto-fix EN terms")
    args = parser.parse_args()

    root = resolve_novel_root(args.novel)
    chapters_dir = Path(root) / "chapters"

    if args.all:
        files = sorted(
            [f.name for f in chapters_dir.iterdir() if f.suffix == ".json" and f.name[0].isdigit()]
        )
    elif args.chapter:
        files = [f"{args.chapter:04d}.json"]
    else:
        progress_file = Path(root) / "progress.md"
        if progress_file.exists():
            content = progress_file.read_text(encoding="utf-8")
            m = re.search(r"Last translated:\s*ch\s*(\d+)", content)
            if m:
                files = [f"{int(m.group(1)):04d}.json"]
            else:
                print("Cannot detect last translated chapter. Use --all or specify chapter number.")
                sys.exit(1)
        else:
            print("No progress.md found. Use --all or specify chapter number.")
            sys.exit(1)

    total_fail = total_warn = files_with_issues = 0
    for fname in files:
        fpath = chapters_dir / fname
        if not fpath.exists():
            continue
        issues = check_file_for_cjk_leaks(str(fpath))
        fails = [i for i in issues if i["severity"] == "FAIL"]
        warns = [i for i in issues if i["severity"] == "WARN"]
        if fails or warns:
            files_with_issues += 1
            total_fail += len(fails)
            total_warn += len(warns)
            print(f"\n{'=' * 60}")
            print(f"  {fname}: {len(fails)} FAIL, {len(warns)} WARN")
            print(f"{'=' * 60}")
            for issue in fails:
                print(f"  ✗ Block {issue['block']} ({issue['type']}): {issue['detail']}")
                print(f"    {issue['text']}")
            for issue in warns:
                print(f"  ⚠ Block {issue['block']} ({issue['type']}): {issue['detail']}")

    print(f"\n{'=' * 60}")
    print(f"Summary: {files_with_issues} files with issues")
    print(f"  FAIL: {total_fail}")
    print(f"  WARN: {total_warn}")
    if total_fail > 0:
        sys.exit(1)
    else:
        print("\n✅ All clean (CN/JP/ARTIFACT). WARN items are EN terms to review.")
        sys.exit(0)


if __name__ == "__main__":
    main()
