#!/usr/bin/env python3
"""
novelclaw.py — NovelClaw Translation CLI

สายพานการผลิตนิยายแปล — เรียบง่าย เป็นเส้นตรง คุณภาพสูง

Usage:
    novelclaw translate 130                    # แปลตอน 130
    novelclaw translate 130-150                # แปลช่วง
    novelclaw translate 130 --mock             # ทดสอบ (ไม่เรียก LLM)
    novelclaw translate 130 --from jp          # แปลจากญี่ปุ่น
    novelclaw translate 130 --model gemma-4-31b-it:free
    novelclaw status                           # เช็คสถานะ
    novelclaw config                           # ดู provider ปัจจุบัน
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_TOOLS_DIR = _PROJECT_ROOT / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

from pipeline import translate_one  # noqa: E402


# ── Commands ──────────────────────────────────────────────────────────


def cmd_translate(args: list[str]) -> None:
    """novelclaw translate <range> [--mock] [--from cn|jp|kr|en] [--model <model>] [--dry-run]"""
    import argparse

    ap = argparse.ArgumentParser(prog="novelclaw translate")
    ap.add_argument("range", help="Chapter number or range (130 or 130-150)")
    ap.add_argument("--mock", action="store_true", help="Mock translation (no LLM)")
    ap.add_argument("--dry-run", action="store_true", help="Show source only")
    ap.add_argument("--from", dest="source_lang", default="cn", help="Source language")
    ap.add_argument("--model", default=None, help="Override model")
    ap.add_argument("--provider", default=None, help="Override provider")
    ap.add_argument("--json", action="store_true", help="JSON output")

    parsed = ap.parse_args(args)

    # Parse range
    if "-" in parsed.range:
        a, b = map(int, parsed.range.split("-"))
        ch_nums = list(range(a, b + 1))
    else:
        ch_nums = [int(parsed.range)]

    if parsed.json:
        for ch in ch_nums:
            result = translate_one(
                ch_num=ch,
                source_lang=parsed.source_lang,
                dry_run=parsed.dry_run,
                mock=parsed.mock,
                model_override=parsed.model,
                provider_override=parsed.provider,
            )
            print(json.dumps(result, ensure_ascii=False))
    else:
        total = len(ch_nums)
        for i, ch in enumerate(ch_nums):
            print(f"\n[{i+1}/{total}] → แปลตอน {ch}..." if total > 1 else f"\n→ แปลตอน {ch}...")
            result = translate_one(
                ch_num=ch,
                source_lang=parsed.source_lang,
                dry_run=parsed.dry_run,
                mock=parsed.mock,
                model_override=parsed.model,
                provider_override=parsed.provider,
            )

            if result["status"] == "ok":
                ratio_str = ", ".join(f"{t}:{p}%" for t, p in result.get("types", {}).items())
                print(f"  ✅ ตอน {ch}: {result['paragraphs']} ย่อหน้า ({ratio_str})")
                print(f"     {result['provider']}:{result['model']}")
            elif result["status"] == "dry_run":
                print(f"  📄 แหล่ง {result['source_chars']} ตัวอักษร")
                print(f"     ตัวอย่าง: {result['source_preview'][:100]}...")
            else:
                print(f"  ❌ ตอน {ch} FAILED: {result['reason']}")

        success = sum(1 for ch in ch_nums if translate_one(ch_num=ch, dry_run=True, mock=True)["status"] != "failed")
        print(f"\n完毕! {total} ตอน")


def cmd_status(args: list[str]) -> None:
    """novelclaw status — แสดงสถานะนิยาย"""
    novels_dir = _PROJECT_ROOT / "novels"
    if not novels_dir.exists():
        print("❌ ไม่พบ novels/")
        return

    for slug in sorted(novels_dir.iterdir()):
        if not slug.is_dir() or slug.name.startswith("test-"):
            continue
        chapters_dir = slug / "chapters"
        if not chapters_dir.exists():
            continue

        # Count source
        source_dir = chapters_dir / "source"
        source_count = len(list(source_dir.glob("*.md"))) if source_dir.exists() else 0

        # Count translated
        th_files = list(chapters_dir.glob("*.th.json"))
        th_count = len(th_files)

        # Count cn.json
        cn_files = list(chapters_dir.glob("*.cn.json"))
        cn_count = len(cn_files)

        title = "(unspecified)"
        novel_json = slug / "novel.json"
        if novel_json.exists():
            try:
                data = json.loads(novel_json.read_text(encoding="utf-8"))
                title = data.get("translatedTitle") or data.get("title") or slug.name
            except Exception:
                pass

        pct = round(th_count / source_count * 100) if source_count > 0 else 0
        print(f"  📖 {title}")
        print(f"     แหล่ง: {source_count + cn_count} ตอน | แปลแล้ว: {th_count} ({pct}%)")


def cmd_config(args: list[str]) -> None:
    """novelclaw config — แสดง/เปลี่ยน provider config"""
    try:
        from llm_router.config_providers import get_provider_config, get_providers_list, save_provider_config
    except ImportError:
        print("❌ ไม่พบ config_providers.py")
        return

    # ถ้ามี argument → save
    if args:
        import argparse
        ap = argparse.ArgumentParser(prog="novelclaw config")
        ap.add_argument("--provider", help="Set active provider")
        ap.add_argument("--model", help="Set default model")
        parsed = ap.parse_args(args)

        if parsed.provider or parsed.model:
            save_provider_config(active=parsed.provider, default_model=parsed.model)
            print(f"✅ บันทึกแล้ว")
            if parsed.provider:
                print(f"   Provider: {parsed.provider}")
            if parsed.model:
                print(f"   Model: {parsed.model}")

    # Show current config
    cfg = get_provider_config()
    active = cfg.get("active", "?")
    model = cfg.get("default_model", "?")
    print(f"⚙️  ปัจจุบัน")
    print(f"   Provider: {active}")
    print(f"   Model: {model}")
    print()

    plist = get_providers_list()
    for p in plist:
        models = p.get("models", [])
        marker = "▶️" if p["name"] == active else "  "
        print(f"  {marker} {p['display_name']}")
        for m in models:
            mm = "→" if m.get("id") == model and p["name"] == active else "  "
            print(f"     {mm} {m.get('id', '?')} ({m.get('tier', '?')})")


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "translate":
        cmd_translate(args)
    elif command == "status":
        cmd_status(args)
    elif command == "config":
        cmd_config(args)
    elif command in ("-h", "--help"):
        print(__doc__)
    else:
        print(f"❌ ไม่รู้จักคำสั่ง '{command}'")
        print("คำสั่งที่มี: translate, status, config")
        sys.exit(1)


if __name__ == "__main__":
    main()
