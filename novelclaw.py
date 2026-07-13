#!/usr/bin/env python3
"""
novelclaw.py — NovelClaw Translation CLI

สายพานการผลิตนิยายแปล — เรียบง่าย เป็นเส้นตรง คุณภาพสูง

Usage:
    novelclaw translate 130                    # แปลตอน 130
    novelclaw translate 130-150                # แปลช่วง batch
    novelclaw translate 130 --mock             # ทดสอบ (ไม่เรียก LLM)
    novelclaw translate 130 --from jp          # แปลจากญี่ปุ่น
    novelclaw translate 130 --model gemma-4-26b-a4b-it:free
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


def _json_progress(event: str, data: dict, *, timestamp: bool = True) -> None:
    """Write structured progress to stderr as JSON lines.

    Humans read stdout. Machines read stderr.
    Use 2>progress.jsonl to capture, or 2>/dev/null to hide.

    Event types: job_start, chapter_start, chapter_done, chapter_fail, job_done
    """
    payload = {"event": event, **data}
    if timestamp:
        payload["ts"] = time.time()
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)


def _cli_config_default(key: str) -> str:
    """Read default value from novelclaw.config.yaml, return "" if not found."""
    cfg_path = _PROJECT_ROOT / "novelclaw.config.yaml"
    if not cfg_path.exists():
        return ""
    try:
        import yaml
        with open(cfg_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return str(data.get(key, ""))
    except Exception:
        return ""


_CONFIG_SCHEMA = {
    "provider": {"type": str, "required": True},
    "model": {"type": str, "required": True},
    "discovery_model": {"type": str, "default": ""},
    "temperature": {"type": float, "min": 0.0, "max": 2.0, "default": 0.28},
    "max_tokens": {"type": int, "min": 256, "max": 32768, "default": 4096},
    "timeout_sec": {"type": int, "min": 10, "max": 600, "default": 120},
    "parallel_workers": {"type": int, "min": 1, "max": 8, "default": 1},
    "prompt_profile": {"type": str, "default": ""},
    "sequential": {"type": bool, "default": False},
    "judge_enabled": {"type": bool, "default": True},
    "judge_threshold": {"type": float, "min": 0.0, "max": 100.0, "default": 85.0},
    "glossary_discovery": {"type": bool, "default": True},
    "fallback_provider": {"type": str, "default": "custom"},
    "fallback_model": {"type": str, "default": ""},
    "skip_chapters": {"type": list, "default": []},
}




def _save_runtime_config(**updates: str) -> None:
    """Update novelclaw.config.yaml, the runtime config source."""
    import yaml

    cfg_path = _PROJECT_ROOT / "novelclaw.config.yaml"
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    if not isinstance(data, dict):
        data = {}
    for key, value in updates.items():
        if value is not None:
            data[key] = value
    atomic_write_text(cfg_path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

    # ponytail: clear both config caches after local writes; add a shared config module if more writers appear.
    try:
        from pipeline_llm import _load_central_config
        _load_central_config.cache_clear()
    except Exception:
        pass
    try:
        from llm_router.config_providers import clear_provider_config_cache
        clear_provider_config_cache()
    except Exception:
        pass

def _validate_config() -> list[str]:
    """Validate novelclaw.config.yaml against schema + provider catalog. Returns list of errors."""
    import yaml
    cfg_path = _PROJECT_ROOT / "novelclaw.config.yaml"
    if not cfg_path.exists():
        return ["novelclaw.config.yaml not found — using defaults"]

    try:
        with open(cfg_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        return [f"Config parse error: {e}"]

    errors: list[str] = []
    for key, schema in _CONFIG_SCHEMA.items():
        val = data.get(key)
        if val is None:
            if schema.get("required"):
                errors.append(f"Missing required key: '{key}'")
            continue
        expected = schema["type"]
        try:
            expected(val)
        except (ValueError, TypeError):
            errors.append(f"'{key}' should be {expected.__name__}, got {type(val).__name__}")

    # Validate provider/model exist in catalog
    from llm_router.config_admin import get_providers_list
    providers = get_providers_list()
    available_models = {}
    for p in providers:
        available_models[p["name"]] = {m["id"] for m in p.get("models", [])}

    provider = data.get("provider")
    model = data.get("model")
    discovery = data.get("discovery_model")

    # Provider validation: allow if in catalog OR if it's a custom/local endpoint
    if provider and provider not in available_models:
        # Not an error — could be custom/local endpoint
        pass  # Optional: add warning logic if desired
    if provider and model and model not in available_models.get(provider, set()):
        errors.append(f"Model '{model}' not found under provider '{provider}'")

    if provider and discovery and discovery not in available_models.get(provider, set()):
        errors.append(f"Warning: Discovery model '{discovery}' not in catalog for provider '{provider}'")

    return errors
_TOOLS_DIR = _PROJECT_ROOT / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

from atomic_io import atomic_write_json, atomic_write_text  # noqa: E402
from pipeline import translate_one, judge_translation, read_source, clean_source  # noqa: E402
from scorer import ScorerHistory, score_chapter, report as score_report  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────


def _parse_range(range_str: str) -> list[int]:
    """Parse '130' or '130-150' to list of chapter numbers."""
    if "-" in range_str:
        a, b = map(int, range_str.split("-"))
        return list(range(a, b + 1))
    return [int(range_str)]


def _default_parallel_workers() -> int:
    raw = os.environ.get("NOVELCLAW_DEFAULT_PARALLEL", "3").strip()
    try:
        workers = int(raw)
    except ValueError:
        workers = 3
    return max(0, min(workers, 10))


# ── TRANSLATE ──────────────────────────────────────────────────────────


def cmd_translate(args: list[str]) -> None:
    """novelclaw translate <range> [options]"""
    import argparse

    ap = argparse.ArgumentParser(prog="novelclaw translate")
    ap.add_argument("range", help="Chapter number or range (130 or 130-150)")
    ap.add_argument("--slug", default=os.environ.get("NOVEL_SLUG", "global-descent"), help="Novel slug")
    ap.add_argument("--mock", action="store_true", help="Mock translation (no LLM)")
    ap.add_argument("--dry-run", action="store_true", help="Show source only")
    ap.add_argument("--from", dest="source_lang", default="auto", help="Source language or auto")
    ap.add_argument("--to", dest="target_lang", default="th", help="Target language")
    ap.add_argument("--model", default=None, help="Override model")
    ap.add_argument("--provider", default=None, help="Override provider")
    ap.add_argument("--profile", default=_cli_config_default("prompt_profile"), help="Prompt profile (default: omni)")
    ap.add_argument("--sequential", action="store_true", help="Force sequential batch mode")
    ap.add_argument("--parallel", type=int, default=_default_parallel_workers(), const=3, nargs="?",
                    help="Parallel batch with N workers (default: NOVELCLAW_DEFAULT_PARALLEL or 3)")
    ap.add_argument("--retry", type=int, default=2, help="Retry failed chapters up to N times")
    ap.add_argument("--json", action="store_true", help="JSON output")

    parsed = ap.parse_args(args)
    if parsed.sequential:
        parsed.parallel = 0
    ch_nums = _parse_range(parsed.range)
    is_batch = len(ch_nums) > 1

    # Apply skip-list
    import yaml
    cfg = yaml.safe_load((_PROJECT_ROOT / "novelclaw.config.yaml").read_text(encoding="utf-8")) or {}
    if isinstance(cfg.get("skip_chapters"), list):
        skip_set = set(cfg["skip_chapters"])
        orig = len(ch_nums)
        ch_nums = [c for c in ch_nums if c not in skip_set]
        if len(ch_nums) < orig:
            print(f"   ข้าม {orig - len(ch_nums)} ตอนจาก skip-list")

    if parsed.parallel and parsed.parallel > 0 and is_batch:
        _cmd_translate_parallel(ch_nums, parsed)
        return

    if parsed.json:
        scorer_history = ScorerHistory()
        for ch in ch_nums:
            result = translate_one(
                ch_num=ch, slug=parsed.slug,
                source_lang=parsed.source_lang, target_lang=parsed.target_lang,
                dry_run=parsed.dry_run, mock=parsed.mock,
                model_override=parsed.model, provider_override=parsed.provider,
                prompt_profile=parsed.profile,
                scorer_history=scorer_history,
            )
            print(json.dumps(result, ensure_ascii=False))
        return

    if is_batch:
        _json_progress("batch_start", {"chapters": ch_nums, "total": len(ch_nums)})

    # Sequential (default)
    scorer_history = ScorerHistory()
    success = 0
    failed = 0
    total = len(ch_nums)

    for i, ch in enumerate(ch_nums):
        label = f"[{i+1}/{total}]" if is_batch else ""
        print(f"\n{label} → แปลตอน {ch}..." if label else f"\n→ แปลตอน {ch}...")
        _json_progress("chapter_start", {"ch": ch, "i": i+1, "total": total})

        # Retry loop
        for attempt in range(max(1, parsed.retry + 1)):
            result = translate_one(
                ch_num=ch, slug=parsed.slug,
                source_lang=parsed.source_lang, target_lang=parsed.target_lang,
                dry_run=parsed.dry_run, mock=parsed.mock,
                model_override=parsed.model, provider_override=parsed.provider,
                prompt_profile=parsed.profile,
                scorer_history=scorer_history,
            )

            if result["status"] in {"ok", "needs_review"}:
                ratio_str = ", ".join(f"{t}:{p}%" for t, p in result.get("types", {}).items())
                marker = "⚠️" if result["status"] == "needs_review" else "✅"
                print(f"  {marker} ตอน {ch}: {result['paragraphs']} ย่อหน้า ({ratio_str})")
                print(f"     คะแนน: {result['score']}")
                if result.get("reason"):
                    print(f"     Reason: {result['reason'][:120]}")
                if result.get("judge") and result["judge"] != "(mock)":
                    print(f"     Judge: {result['judge'][:120]}")
                if result.get("discovery") and result["discovery"] != "none":
                    print(f"     📖 {result['discovery']}")
                print(f"     {result['provider']}:{result['model']}")
                _json_progress("chapter_done", {"ch": ch, "result": result})
                success += 1
                break
            elif result["status"] == "dry_run":
                print(f"  📄 แหล่ง {result['source_chars']} ตัวอักษร")
                print(f"     ตัวอย่าง: {result['source_preview'][:100]}...")
                _json_progress("chapter_done", {"ch": ch, "result": result})
                break
            else:
                if attempt < parsed.retry:
                    print(f"  ⚠️  ตอน {ch} ล้มเหลว (ครั้งที่ {attempt+1}): {result['reason'][:80]}")
                    print("     กำลังลองใหม่...")
                    _json_progress("chapter_retry", {"ch": ch, "attempt": attempt+1, "reason": result.get("reason","")})
                    time.sleep(2)
                else:
                    print(f"  ❌ ตอน {ch} FAILED: {result['reason'][:120]}")
                    failed += 1

    if is_batch:
        _json_progress("batch_done", {"success": success, "failed": failed, "total": total})
        print(f"\n完毕! {success} ผ่าน, {failed} ล้มเหลว จาก {total} ตอน")


def _cmd_translate_parallel(ch_nums: list[int], parsed) -> None:
    """Parallel batch translation."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    n_workers = min(parsed.parallel, len(ch_nums))
    if not parsed.json:
        print(f"   ขนาน {n_workers} worker\n")

    scorer_history = ScorerHistory()

    def run_chapter(ch: int) -> dict:
        last_result = None
        for attempt in range(max(1, parsed.retry + 1)):
            _json_progress("chapter_start", {"ch": ch})
            result = translate_one(
                ch_num=ch,
                slug=parsed.slug,
                source_lang=parsed.source_lang,
                target_lang=parsed.target_lang,
                dry_run=parsed.dry_run,
                mock=parsed.mock,
                model_override=parsed.model,
                provider_override=parsed.provider,
                prompt_profile=parsed.profile,
                scorer_history=scorer_history,
            )
            last_result = result
            if result.get("status") in {"ok", "dry_run", "needs_review"}:
                _json_progress("chapter_done", {"ch": ch, "status": result.get("status")})
                return result
            if attempt < parsed.retry:
                time.sleep(2)
        return last_result or {"status": "failed", "ch": ch, "reason": "no result"}

    with ThreadPoolExecutor(max_workers=n_workers) as exec:
        fut_map = {
            exec.submit(run_chapter, ch): ch
            for ch in ch_nums
        }

        results = {}
        for fut in as_completed(fut_map):
            ch = fut_map[fut]
            try:
                results[ch] = fut.result()
            except Exception as e:
                results[ch] = {"status": "failed", "ch": ch, "reason": str(e)[:120]}
            if parsed.json:
                print(json.dumps(results[ch], ensure_ascii=False), flush=True)

    if parsed.json:
        return

    for ch in sorted(results.keys()):
        r = results[ch]
        if r["status"] == "ok":
            print(f"  OK ตอน {ch}: {r['paragraphs']} ย่อหน้า - คะแนน: {r['score']}")
        elif r["status"] == "dry_run":
            print(f"  DRY RUN ตอน {ch}: แหล่ง {r.get('source_chars', 0)} ตัวอักษร")
        elif r["status"] == "needs_review":
            print(f"  REVIEW ตอน {ch}: ต้องตรวจคุณภาพ - คะแนน: {r.get('score', '?')}")
        else:
            print(f"  FAIL ตอน {ch}: {r.get('reason', '?')[:80]}")


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
    """novelclaw status — แสดงสถานะ + drift report (--report)"""
    import argparse
    ap = argparse.ArgumentParser(prog="novelclaw status")
    ap.add_argument("--report", action="store_true", help="Show structure drift report")
    parsed = ap.parse_args(args)

    from pipeline_llm import get_active_config

    novels_dir = _PROJECT_ROOT / "novels"
    if not novels_dir.exists():
        print("❌ ไม่พบ novels/")
        return

    # Show active runtime config
    cfg = get_active_config()
    print(f"⚙️  Translate: {cfg.get('provider_name', '?')} / {cfg.get('model', '?')}")
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

        if parsed.report:
            # Quick drift check: compare structure between source and translated
            for cn_file in cn_files:
                th_file = cn_file.with_suffix(".th.json")
                if not th_file.exists():
                    continue
                th_data = json.loads(th_file.read_text(encoding="utf-8"))
                if not isinstance(th_data, list) or len(th_data) == 0:
                    continue
                if cn_file.exists():
                    src = json.loads(cn_file.read_text(encoding="utf-8"))
                    if isinstance(src, list):
                        src_count = len([p for p in src if isinstance(p, dict) and p.get("type") == "paragraph"])
                        th_count_p = len(th_data)
                        if th_count_p != src_count:
                            print(f"     ⚠️  {cn_file.stem}: โครงสร้างเปลี่ยน {src_count}→{th_count_p}")


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
    ap.add_argument("--validate", action="store_true", help="Validate novelclaw.config.yaml and exit")
    parsed = ap.parse_args(args)

    if parsed.validate:
        errors = _validate_config()
        if errors:
            for err in errors:
                print(f"❌ {err}")
            raise SystemExit(1)
        print("✅ config OK")
        return

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
        atomic_write_json(llm_path, data, ensure_ascii=False, indent=2)
        print(f"✅ ตั้งค่า API key สำหรับ {provider_name} แล้ว")
        return

    if parsed.provider or parsed.model or parsed.discovery_model:
        _save_runtime_config(
            provider=parsed.provider,
            model=parsed.model,
            discovery_model=parsed.discovery_model,
        )
        print("✅ บันทึกแล้ว")

    from llm_router.config_providers import get_providers_list
    from pipeline_llm import get_active_config
    cfg = get_active_config()
    active = cfg.get("provider_name", "?")
    model = cfg.get("model", "?")
    disc = cfg.get("discovery_model", "—")
    print("⚙️  ปัจจุบัน")
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


# ── SCRAPE (deprecated) ───────────────────────────────────────────
#
# scraper.py was removed. This command is kept as a stub to give
# a clear error message instead of an ImportError.


def cmd_scrape(args: list[str]) -> None:
    """novelclaw scrape — removed. Use third-party tools to download source files."""
    print("⚠️  คำสั่ง scrape ถูกลบออกแล้ว")
    print("   Scraper functionality was removed in the prompt-profile refactor.")
    print("   Place source files manually in novels/<slug>/<ch>.cn.json instead.")
    print("   For批量 download, use external tools (e.g., wget + custom script).")


# ── IMPORT SOURCE ───────────────────────────────────────────────────────


def _import_sources_main():
    """Load the importer only when an import command is used."""
    from tools.import_sources import main as import_sources_main

    return import_sources_main


def cmd_import_url(args: list[str]) -> None:
    """novelclaw import-url <url> [options] — import source chapters from a TOC URL."""
    import argparse

    import_sources_main = _import_sources_main()

    ap = argparse.ArgumentParser(prog="novelclaw import-url")
    ap.add_argument("url", help="Novel TOC URL")
    ap.add_argument("--slug", default="preview", help="Novel slug")
    ap.add_argument("--site", default="auto", help="Adapter id or auto")
    ap.add_argument("--range", dest="range_text", default=None, help="Chapter range, e.g. 1-20 or 1,3-5")
    ap.add_argument("--force", action="store_true", help="Overwrite existing source chapters")
    ap.add_argument("--preview", action="store_true", help="Preview only")
    parsed = ap.parse_args(args)

    delegated = ["preview" if parsed.preview else "run", parsed.url, "--site", parsed.site]
    if not parsed.preview:
        delegated += ["--slug", parsed.slug]
        if parsed.range_text:
            delegated += ["--range", parsed.range_text]
        if parsed.force:
            delegated.append("--force")
    raise SystemExit(import_sources_main(delegated))


def cmd_import_sites(args: list[str]) -> None:
    """novelclaw import-sites — list supported source import adapters."""
    import_sources_main = _import_sources_main()
    raise SystemExit(import_sources_main(["sites", *args]))


# ── Main ──────────────────────────────────────────────────────────────


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    # Validate config on every CLI invocation
    config_errors = _validate_config()
    if len(sys.argv) >= 2 and sys.argv[1] not in ("-h", "--help"):
        for err in config_errors:
            print(f"⚠️  {err}", file=sys.stderr)

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
    elif command == "import-url":
        cmd_import_url(args)
    elif command == "import-sites":
        cmd_import_sites(args)
    elif command in ("-h", "--help"):
        print(__doc__)
    else:
        print(f"❌ ไม่รู้จักคำสั่ง '{command}'")
        print("คำสั่งที่มี: translate, judge, status, config, scrape, import-url, import-sites")
        sys.exit(1)


if __name__ == "__main__":
    main()
