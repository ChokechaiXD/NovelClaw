#!/usr/bin/env python3
"""
NovelClaw Workspace Sanitizer & Bug Detector
Scans translated chapter files for:
  - JSON structural errors
  - Schema version compliance (must be v2)
  - Missing chapter numbers
  - Chinese/Japanese/Korean character leakage

Usage:
    python tools/sanitize_workspace.py

Exit codes:
    0 = clean
    1 = errors found
"""

import json
import os
import re
import validate_chapter as vc
import sys


def check_cjk(text):
    """Check for Chinese/Japanese/Korean character leakage."""
    return vc.CJK_PATTERN.findall(text)

def sanitize_workspace():
    print("=" * 60)
    print(" NOVELCLAW WORKSPACE SANITIZER & BUG DETECTOR")
    print("=" * 60)

    novel_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'novels')
    if not os.path.exists(novel_dir):
        print(f"[!] Error: '{novel_dir}' directory not found.")
        sys.exit(1)

    errors_found = 0
    warnings_found = 0
    total_files_checked = 0

    for slug in sorted(os.listdir(novel_dir)):
        slug_path = os.path.join(novel_dir, slug)
        if not os.path.isdir(slug_path):
            continue

        chapters_dir = os.path.join(slug_path, "chapters")
        if not os.path.exists(chapters_dir):
            print(f"[-] No chapters directory found for novel: {slug}")
            continue

        print(f"\n[*] Auditing chapters for: {slug}...")

        chapter_files = sorted(
            [f for f in os.listdir(chapters_dir) if f.endswith('.json')],
            key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0
        )

        for filename in chapter_files:
            file_path = os.path.join(chapters_dir, filename)
            total_files_checked += 1

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 1. Verify Schema Version
                schema_ver = data.get("schema_version")
                if schema_ver != 2:
                    print(f"    [ERR] {filename}: Inconsistent schema version ({schema_ver}). Expected 2.")
                    errors_found += 1

                # 2. Verify Chapter Title
                title = data.get("title", "")
                if not title.startswith("ตอนที่"):
                    print(f"    [WARN] {filename}: Title '{title}' does not follow 'ตอนที่ N' convention.")
                    warnings_found += 1

                # 3. Check for CJK Character Leakage
                blocks = data.get("blocks", [])
                for idx, block in enumerate(blocks):
                    block_type = block.get("type", "unknown")
                    block_text = block.get("text", "")
                    cjk_leaks = check_cjk(block_text)
                    if cjk_leaks:
                        sample = ''.join(cjk_leaks[:5])
                        print(f"    [ERR] {filename} (Block #{idx} [{block_type}]): CJK leakage: {sample}...")
                        errors_found += 1

                # 4. Check for Empty Content Blocks
                if not blocks:
                    print(f"    [WARN] {filename}: Chapter contains no translation blocks.")
                    warnings_found += 1

            except json.JSONDecodeError:
                print(f"    [ERR] {filename}: Invalid JSON format (parsing failed).")
                errors_found += 1
            except Exception as e:
                print(f"    [ERR] {filename}: Unexpected error: {str(e)}")
                errors_found += 1

    print("\n" + "=" * 60)
    print(" AUDIT RESULT SUMMARY:")
    print(f"  - Total Chapter Files Checked : {total_files_checked}")
    print(f"  - Total Errors Found (Blocked): {errors_found}")
    print(f"  - Total Warnings (Optimizable): {warnings_found}")
    print("=" * 60)

    if errors_found > 0:
        print("[!] Workspace SANITIZATION FAILED. Clean up errors before committing!")
        sys.exit(1)
    else:
        print("[+] Workspace is CLEAN & SANITIZED. Ready for production usage.")
        sys.exit(0)


if __name__ == "__main__":
    sanitize_workspace()
