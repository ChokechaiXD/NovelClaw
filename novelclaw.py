#!/usr/bin/env python3
"""
novelclaw.py — NovelClaw Translation CLI

สายพานการผลิตนิยายแปล — เรียบง่าย เป็นเส้นตรง คุณภาพสูง

Usage:
    novelclaw translate 130                    # แปลตอน 130
    novelclaw translate 130-150                # แปลช่วง batch
    novelclaw translate 130 --mock             # ทดสอบ (ไม่เรียก LLM)
    novelclaw translate 130 --from jp          # แปลจากญี่ปุ่น
    novelclaw translate 130 --model gemma-4-31b-it:free
    novelclaw translate 130-150 --sequential   # batch sequential mode

    novelclaw judge 130                        # ตรวจคุณภาพตอนที่แปลแล้ว
    novelclaw judge 130-135                    # ตรวจเป็นช่วง

    novelclaw status                           # เช็คสถานะ
    novelclaw config                           # ดู/เปลี่ยน provider
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_TOOLS_DIR = _PROJECT_ROOT / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

from pipeline import translate_one, judge_translation, read_source, clean_source  # noqa: E402
from scorer import score_chapter, report as score_report  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────


def _parse_range(range_str: str) -> list[int]:
    """Parse '130' or '130-150' to list of chapter numbers."""
    if "-" in range_str:
        a, b = map(int, range_str.split("-"))
        return list(range(a, b + 1))
    return [int(range_str)]


# ── TRANSLATE ──────────────────────────────────────────────────────────


def cmd_translate(args: list[str]) -> None:
    """novelclaw translate <range> [options]"""
    import argparse

    ap = argparse.ArgumentParser(prog="novelclaw translate")
    ap.add_argument("range", help="Chapter number or range (130 or 130-150)")
    ap.add_argument("--mock", action="store_true", help="Mock translation (no LLM)")
    ap.add_argument("--dry-run", action="store_true", help="Show source only")
    ap.add_argument("--from", dest="source_lang", default="cn", help="Source language")
    ap.add_argument("--model", default=None, help="Override model")
    ap.add_argument("--provider", default=None, help="Override provider")
    ap.add_argument("--sequential", action="store_true", help="Sequential batch (default for single)")
    ap.add_argument("--parallel", type=int, default=0, const=3, nargs="?",
                    help="Parallel batch with N workers (default 3)")
    ap.add_argument("--retry", type=int, default=0, help="Retry failed chapters up to N times")
    ap.add_argument("--json", action="store_true", help="JSON output")

    parsed = ap.parse_args(args)
    ch_nums = _parse_range(parsed.range)
    is_batch = len(ch_nums) > 1

    if parsed.json:
        for ch in ch_nums:
            result = translate_one(
                ch_num=ch, source_lang=parsed.source_lang,
                dry_run=parsed.dry_run, mock=parsed.mock,
                model_override=parsed.model, provider_override=parsed.provider,
            )
            print(json.dumps(result, ensure_ascii=False))
        return

    if is_batch:
        print(f"⚡ Batch: {len(ch_nums)} ตอน ({ch_nums[0]}-{ch_nums[-1]})")

    if parsed.parallel and parsed.parallel > 0 and is_batch:
        _cmd_translate_parallel(ch_nums, parsed)
        return

    # Sequential (default)
    success = 0
    failed = 0
    total = len(ch_nums)

    for i, ch in enumerate(ch_nums):
        label = f"[{i+1}/{total}]" if is_batch else ""
        print(f"\n{label} → แปลตอน {ch}..." if label else f"\n→ แปลตอน {ch}...")

        # Retry loop
        for attempt in range(max(1, parsed.retry + 1)):
            result = translate_one(
                ch_num=ch, source_lang=parsed.source_lang,
                dry_run=parsed.dry_run, mock=parsed.mock,
                model_override=parsed.model, provider_override=parsed.provider,
            )

            if result["status"] == "ok":
                ratio_str = ", ".join(f"{t}:{p}%" for t, p in result.get("types", {}).items())
                print(f"  ✅ ตอน {ch}: {result['paragraphs']} ย่อหน้า ({ratio_str})")
                print(f"     คะแนน: {result['score']}")
                if result.get("judge") and result["judge"] != "(mock)":
                    print(f"     Judge: {result['judge'][:120]}")
                if result.get("discovery") and result["discovery"] != "none":
                    print(f"     📖 {result['discovery']}")
                print(f"     {result['provider']}:{result['model']}")
                success += 1
                break
            elif result["status"] == "dry_run":
                print(f"  📄 แหล่ง {result['source_chars']} ตัวอักษร")
                print(f"     ตัวอย่าง: {result['source_preview'][:100]}...")
                break
            else:
                if attempt < parsed.retry:
                    print(f"  ⚠️  ตอน {ch} ล้มเหลว (ครั้งที่ {attempt+1}): {result['reason'][:80]}")
                    print(f"     กำลังลองใหม่...")
                    time.sleep(2)
                else:
                    print(f"  ❌ ตอน {ch} FAILED: {result['reason'][:120]}")
                    failed += 1

    if is_batch:
        print(f"\n完毕! {success} ผ่าน, {failed} ล้มเหลว จาก {total} ตอน")


def _cmd_translate_parallel(ch_nums: list[int], parsed) -> None:
    """Parallel batch translation."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    n_workers = min(parsed.parallel, len(ch_nums))
    print(f"   ขนาน {n_workers} worker\n")

    with ThreadPoolExecutor(max_workers=n_workers) as exec:
        fut_map = {
            exec.submit(
                translate_one,
                ch_num=ch,
                source_lang=parsed.source_lang,
                model_override=parsed.model,
                provider_override=parsed.provider,
            ): ch
            for ch in ch_nums
        }

        results = {}
        for fut in as_completed(fut_map):
            ch = fut_map[fut]
            try:
                results[ch] = fut.result()
            except Exception as e:
                results[ch] = {"status": "failed", "ch": ch, "reason": str(e)[:120]}

    for ch in sorted(results.keys()):
        r = results[ch]
        if r["status"] == "ok":
            print(f"  ✅ ตอน {ch}: {r['paragraphs']} ย่อหน้า — คะแนน: {r['score']}")
        else:
            print(f"  ❌ ตอน {ch}: {r.get('reason', '?')[:80]}")


# ── JUDGE ──────────────────────────────────────────────────────────────


def cmd_judge(args: list[str]) -> None:
    """novelclaw judge <range> — ตรวจคุณภาพตอนที่แปลแล้ว"""
    import argparse

    ap = argparse.ArgumentParser(prog="novelclaw judge")
    ap.add_argument("range", help="Chapter number or range")
    ap.add_argument("--model", default=None, help="Judge model override")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--slug", default="global-descent", help="Novel slug")

    parsed = ap.parse_args(args)
    ch_nums = _parse_range(parsed.range)

    for ch in sorted(ch_nums):
        ch_path = _PROJECT_ROOT / "novels" / parsed.slug / "chapters" / f"{ch:04d}.th.json"
        if not ch_path.exists():
            print(f"  ❌ ตอน {ch}: .th.json ไม่พบ")
            continue

        data = json.loads(ch_path.read_text(encoding="utf-8"))
        source_text = read_source(ch, parsed.slug)
        if source_text:
            source_text = clean_source(source_text)
        paragraphs = data.get("paragraphs", [])

        # Score (no LLM)
        sr = score_chapter(paragraphs, len(source_text) if source_text else 0)
        score_output = score_report(sr)

        # Judge (LLM)
        jr = judge_translation(paragraphs, source_text or "", model=parsed.model)

        if parsed.json:
            print(json.dumps({
                "ch": ch,
                "score": sr.weighted_total,
                "passed": sr.passed,
                "dimensions": {d.name: round(d.score * 100) for d in sr.dimensions},
                "judge_ok": jr.get("ok", False),
                "judge_feedback": jr.get("feedback", ""),
            }, ensure_ascii=False))
        else:
            print(f"\n─── ตรวจตอน {ch} ───")
            print(score_output)
            if jr.get("ok"):
                print(f"\n🧠 LLM Judge: {jr['feedback'][:300]}")
            else:
                print(f"\n⚠️  Judge error: {jr.get('feedback', '?')}")


# ── STATUS ─────────────────────────────────────────────────────────────


def cmd_status(args: list[str]) -> None:
    """novelclaw status — แสดงสถานะนิยาย"""
    from llm_router.config_providers import get_provider_config

    novels_dir = _PROJECT_ROOT / "novels"
    if not novels_dir.exists():
        print("❌ ไม่พบ novels/")
        return

    # Show active config
    cfg = get_provider_config()
    print(f"⚙️  Translate: {cfg.get('active', '?')} / {cfg.get('default_model', '?')}")
    print(f"   Discovery: {cfg.get('discovery_model', '—')}")
    print()

    for slug in sorted(novels_dir.iterdir()):
        if not slug.is_dir() or slug.name.startswith("test-"):
            continue
        chapters_dir = slug / "chapters"
        if not chapters_dir.exists():
            continue

        source_dir = chapters_dir / "source"
        source_count = len(list(source_dir.glob("*.md"))) if source_dir.exists() else 0
        cn_files = list(chapters_dir.glob("*.cn.json"))
        cn_count = len(cn_files)
        th_files = list(chapters_dir.glob("*.th.json"))
        th_count = len(th_files)
        source_all = source_count + cn_count

        title = "(unspecified)"
        novel_json = slug / "novel.json"
        if novel_json.exists():
            try:
                data = json.loads(novel_json.read_text(encoding="utf-8"))
                title = data.get("translatedTitle") or data.get("title") or slug.name
            except Exception:
                pass

        pct = round(th_count / source_all * 100) if source_all > 0 else 0
        print(f"  📖 {title}")
        print(f"     แหล่ง: {source_all} ตอน | แปลแล้ว: {th_count} ({pct}%)")


# ── CONFIG ─────────────────────────────────────────────────────────────


def cmd_config(args: list[str]) -> None:
    """novelclaw config — แสดง/เปลี่ยน provider config และ API keys"""
    import argparse

    ap = argparse.ArgumentParser(prog="novelclaw config")
    ap.add_argument("--provider", help="Set active provider")
    ap.add_argument("--model", help="Set default translate model")
    ap.add_argument("--discovery-model", help="Set discovery/judge model")
    ap.add_argument("--set-key", nargs=2, metavar=("PROVIDER", "KEY"),
                    help="Set API key for provider (e.g. openrouter sk-or-...)")
    parsed = ap.parse_args(args)

    if parsed.set_key:
        provider_name, api_key = parsed.set_key
        # Write to llm.json
        llm_path = _PROJECT_ROOT / "llm.json"
        try:
            data = json.loads(llm_path.read_text(encoding="utf-8")) if llm_path.exists() else {}
        except Exception:
            data = {}

        key_map = {
            "openrouter": "openrouter_api_key",
            "openmodel": "api_key",
            "openai": "openai_api_key",
            "anthropic": "anthropic_api_key",
        }
        json_key = key_map.get(provider_name, f"{provider_name}_api_key")
        data[json_key] = api_key
        llm_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"✅ ตั้งค่า API key สำหรับ {provider_name} แล้ว")
        return

    if parsed.provider or parsed.model or parsed.discovery_model:
        try:
            from llm_router.config_providers import save_provider_config
        except ImportError:
            print("❌ ไม่พบ config_providers.py")
            return
        save_provider_config(active=parsed.provider, default_model=parsed.model)
        if parsed.discovery_model:
            text = _PROJECT_ROOT.joinpath("tools/config/providers.yaml").read_text(encoding="utf-8")
            import re
            text = re.sub(
                r"^discovery_model:.*",
                f'discovery_model: "{parsed.discovery_model}"',
                text, flags=re.MULTILINE,
            )
            _PROJECT_ROOT.joinpath("tools/config/providers.yaml").write_text(text, encoding="utf-8")
        print(f"✅ บันทึกแล้ว")

    from llm_router.config_providers import get_provider_config, get_providers_list
    cfg = get_provider_config()
    active = cfg.get("active", "?")
    model = cfg.get("default_model", "?")
    disc = cfg.get("discovery_model", "—")
    print(f"⚙️  ปัจจุบัน")
    print(f"   Provider:   {active}")
    print(f"   Translate:  {model}")
    print(f"   Discovery:  {disc}")
    print()

    plist = get_providers_list()
    for p in plist:
        models = p.get("models", [])
        marker = "▶️" if p["name"] == active else "  "
        print(f"  {marker} {p['display_name']}")
        for m in models:
            mm = "→" if m.get("id") == model and p["name"] == active else "  "
            print(f"     {mm} {m.get('id', '?')} ({m.get('tier', '?')})")


# ── SCRAPE ──────────────────────────────────────────────────────────────


def cmd_scrape(args: list[str]) -> None:
    """novelclaw scrape <range> [options] — ดาวน์โหลด source จากเว็บ"""
    import argparse

    ap = argparse.ArgumentParser(prog="novelclaw scrape")
    ap.add_argument("range", help="Chapter range (130 or 130-150)")
    ap.add_argument("--site", default="69shu", choices=["69shu", "uukanshu"], help="Site to scrape")
    ap.add_argument("--slug", default="global-descent", help="Novel slug")
    ap.add_argument("--novel-id", default=None, help="Site novel ID (auto from novel.json if not set)")
    ap.add_argument("--force", action="store_true", help="Re-download existing")
    ap.add_argument("--delay", type=float, default=None, help="Seconds between requests")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be scraped without downloading")

    parsed = ap.parse_args(args)
    a, b = map(int, parsed.range.split("-")) if "-" in parsed.range else (int(parsed.range), int(parsed.range))
    total = b - a + 1

    if parsed.dry_run:
        print(f"📋 จะ scrape {total} ตอน ({a}-{b})")
        print(f"   Site: {parsed.site}")
        print(f"   Slug: {parsed.slug}")
        novel_id = parsed.novel_id
        if not novel_id:
            novel_json = _PROJECT_ROOT / "novels" / parsed.slug / "novel.json"
            if novel_json.exists():
                data = json.loads(novel_json.read_text(encoding="utf-8"))
                novel_id = data.get(f"{parsed.site}_id") or data.get("id") or data.get("sourceId", "?")
        print(f"   Novel ID: {novel_id}")
        print(f"   Delay: {parsed.delay or 1}s")
        return

    from scraper import scrape_range

    print(f"📥 กำลัง scrape {total} ตอน ({a}-{b}) จาก {parsed.site}")
    results = scrape_range(
        start=a, end=b,
        slug=parsed.slug,
        novel_id=parsed.novel_id,
        site=parsed.site,
        force=parsed.force,
        incremental=not parsed.force,
        delay=parsed.delay,
    )

    ok = sum(1 for r in results if r["status"] == "ok")
    exists = sum(1 for r in results if r["status"] == "exists")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\n完毕! {ok} สำเร็จ, {exists} มีแล้ว, {failed} ล้มเหลว จาก {total} ตอน")


# ── Main ──────────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "translate":
        cmd_translate(args)
    elif command == "judge":
        cmd_judge(args)
    elif command == "status":
        cmd_status(args)
    elif command == "config":
        cmd_config(args)
    elif command == "scrape":
        cmd_scrape(args)
    elif command in ("-h", "--help"):
        print(__doc__)
    else:
        print(f"❌ ไม่รู้จักคำสั่ง '{command}'")
        print("คำสั่งที่มี: translate, judge, status, config")
        sys.exit(1)


if __name__ == "__main__":
    main()
