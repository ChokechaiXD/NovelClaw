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

import json
import os
import re
import sys
from pathlib import Path

try:
    from validation import (
        ALLOWED_LATIN_TOKENS,
    )
    from validation import (
        check_en_terms as _check_en_terms,
    )
    from validation import (
        check_file_for_cjk_leaks as _check_file_for_cjk_leaks,
    )

    _has_validation = True
except ImportError:
    _has_validation = False

# ── Paths ───────────────────────────────────────────────────────────────────
try:
    from constants import CHAPTERS_DIR, get_novel_root

    _has_constants = True
except ImportError:
    _has_constants = False


def resolve_novel_root(novel_slug=None):
    if novel_slug and _has_constants:
        return get_novel_root(novel_slug)
    if _has_constants:
        return CHAPTERS_DIR.rsplit("/", 1)[0]
    # Fallback: assume running from repo root
    return Path(__file__).resolve().parent.parent / "novels" / "global-descent"


# ── Patterns ────────────────────────────────────────────────────────────────
CN_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
JP_PATTERN = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
KO_PATTERN = re.compile(r"[\uac00-\ud7af\u1100-\u11ff]")

# Source artifacts that should always be stripped
SOURCE_ARTIFACTS = [
    r"求订阅",
    r"求追读",
    r"三更",
    r"月票",
    r"推荐票",
    r"GZ\b",
    r"^\s*GZ\s*$",
]

# ── EN Game Term Whitelist ──────────────────────────────────────────────────
# Terms in this list are ACCEPTABLE in Thai translation output.
# Everything else EN will be flagged as WARN.
EN_WHITELIST = {
    # Tier ratings (universal gaming notation)
    "S",
    "SS",
    "SSS",
    "SSR",
    "UR",
    "LR",
    # Common gaming abbreviations widely used in Thai gaming community
    "HP",  # พลังชีวิต — but HP is universally understood
    "MP",  # มนตร์/พลังมนตร์
    "CD",  # คูลดาวน์
    "NPC",  # ตัวละครรอง
    "PVP",  # ผู้เล่น vs ผู้เล่น
    "PVE",  # ผู้เล่น vs สภาพแวดล้อม
    "EXP",  # ประสบการณ์
    "LV",
    "LVL",  # เลเวล
    "ATK",  # โจมตี
    "DEF",  # ป้องกัน
    "DMG",  # ความเสียหาย
    "BUFF",  # เสริมพลัง
    "DEBUFF",  # ลดพลัง
    "AOE",  # โจมตีวงกว้าง
    "DPS",  # ความเสียหายต่อวินาที
    "TPS",  # ดึงความสนใจ
    "ID",  # รหัส (only in system messages like "ID: 12345")
}

# EN terms that MUST be translated (never acceptable)
EN_BLACKLIST = {
    "GZ",  # source artifact, never valid
}


def check_en_terms(text):
    """Check for EN game terms using the shared validator whitelist."""
    if _has_validation:
        return _check_en_terms(text)
    words = re.findall(r"\b[A-Za-z][A-Za-z0-9]{1,}\b", text)
    whitelisted = []
    blacklisted = []
    unknown = []
    for w in words:
        upper = w.upper()
        if upper in ALLOWED_LATIN_TOKENS:
            whitelisted.append(w)
        elif upper in EN_BLACKLIST:
            blacklisted.append(w)
        elif w.isupper() and len(w) >= 2:
            unknown.append(w)
    return whitelisted, blacklisted, unknown


def check_file(filepath):
    """Check a single chapter JSON file using the shared validation rules."""
    if _has_validation:
        return _check_file_for_cjk_leaks(filepath)

    issues = []
    with Path(filepath).open(encoding="utf-8") as f:
        data = json.load(f)

    blocks = data.get("blocks", [])
    for i, block in enumerate(blocks):
        text = block.get("text", "")
        btype = block.get("type", "?")

        # Check CN
        cn_matches = CN_PATTERN.findall(text)
        if cn_matches:
            issues.append(
                {
                    "block": i + 1,
                    "type": btype,
                    "severity": "FAIL",
                    "kind": "CN",
                    "detail": f"CN chars: {''.join(cn_matches[:5])}",
                    "text": text[:80],
                }
            )

        # Check JP
        jp_matches = JP_PATTERN.findall(text)
        if jp_matches:
            issues.append(
                {
                    "block": i + 1,
                    "type": btype,
                    "severity": "FAIL",
                    "kind": "JP",
                    "detail": f"JP chars: {''.join(jp_matches[:5])}",
                    "text": text[:80],
                }
            )

        # Check KO
        ko_matches = KO_PATTERN.findall(text)
        if ko_matches:
            issues.append(
                {
                    "block": i + 1,
                    "type": btype,
                    "severity": "FAIL",
                    "kind": "KO",
                    "detail": f"KO chars: {''.join(ko_matches[:5])}",
                    "text": text[:80],
                }
            )

        # Check source artifacts
        for pattern in SOURCE_ARTIFACTS:
            if re.search(pattern, text):
                issues.append(
                    {
                        "block": i + 1,
                        "type": btype,
                        "severity": "FAIL",
                        "kind": "ARTIFACT",
                        "detail": f"Source artifact: {pattern}",
                        "text": text[:80],
                    }
                )

        # Check EN terms
        wl, bl, unk = check_en_terms(text)
        for w in bl:
            issues.append(
                {
                    "block": i + 1,
                    "type": btype,
                    "severity": "FAIL",
                    "kind": "EN_BLACKLIST",
                    "detail": f"Blacklisted EN: {w}",
                    "text": text[:80],
                }
            )
        for w in unk:
            issues.append(
                {
                    "block": i + 1,
                    "type": btype,
                    "severity": "WARN",
                    "kind": "EN_UNKNOWN",
                    "detail": f"Unknown EN term: {w} (add to whitelist if acceptable)",
                    "text": text[:80],
                }
            )

        # Check structural consistency: dialogue markers must match block type
        # Supports multiple quote styles: "" (Thai standard), "" (curly), 「」 (CN)
        has_dialogue_markers = (
            "「" in text or "」" in text or '"' in text or '"' in text or '"' in text or '"' in text
        )
        if has_dialogue_markers and btype != "dialogue":
            # หาว่าใช้ quote style ไฉน
            quote_style = []
            if "「" in text or "」" in text:
                quote_style.append("「」")
            if "“" in text or "”" in text:
                quote_style.append('"" (curly)')
            if '"' in text or '"' in text:
                quote_style.append('"" (straight)')
            quote_str = ", ".join(quote_style) if quote_style else "quotes"
            issues.append(
                {
                    "block": i + 1,
                    "type": btype,
                    "severity": "WARN",
                    "kind": "STRUCT_MISMATCH",
                    "detail": f"Block has {quote_str} but type is '{btype}' (expected 'dialogue')",
                    "text": text[:80],
                }
            )

        if ("【" in text or "】" in text) and btype != "system":
            issues.append(
                {
                    "block": i + 1,
                    "type": btype,
                    "severity": "WARN",
                    "kind": "STRUCT_MISMATCH",
                    "detail": f"Block has 【】 markers but type is '{btype}' (expected 'system')",
                    "text": text[:80],
                }
            )

    return issues


def main():
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="CJK leakage checker")
    parser.add_argument("chapter", nargs="?", type=int, help="Chapter number to check")
    parser.add_argument("--all", action="store_true", help="Check all chapters")
    parser.add_argument("--novel", type=str, default=os.environ.get("NOVEL_SLUG", "global-descent"), help="Novel slug. Uses $NOVEL_SLUG env var or 'global-descent'.")
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
        # Auto-detect last translated
        progress_file = Path(root) / "progress.md"
        if progress_file.exists():
            with progress_file.open(encoding="utf-8") as f:
                content = f.read()
            m = re.search(r"Last translated:\s*ch\s*(\d+)", content)
            if m:
                files = [f"{int(m.group(1)):04d}.json"]
            else:
                print("Cannot detect last translated chapter. Use --all or specify chapter number.")
                sys.exit(1)
        else:
            print("No progress.md found. Use --all or specify chapter number.")
            sys.exit(1)

    total_fail = 0
    total_warn = 0
    files_with_issues = 0

    for fname in files:
        fpath = chapters_dir / fname
        if not fpath.exists():
            continue
        issues = check_file(fpath)
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
    print(f"  Whitelisted EN terms: {', '.join(sorted(EN_WHITELIST))}")
    if total_fail > 0:
        sys.exit(1)
    else:
        print("\n✅ All clean (CN/JP/ARTIFACT). WARN items are EN terms to review.")
        sys.exit(0)


if __name__ == "__main__":
    main()
