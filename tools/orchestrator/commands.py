"""Command dispatch — parse args and route to handlers."""

import argparse
import sys
from pathlib import Path

# Ensure tools/ is on path
_TOOLS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS_DIR.parent))  # project root
sys.path.insert(0, str(_TOOLS_DIR))


def parse_range(range_str: str) -> list[int]:
    """Parse '139' → [139], '140-150' → [140..150], '140,142,145' → [140,142,145]."""
    if not range_str:
        return []
    nums = set()
    for part in range_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            nums.update(range(int(start.strip()), int(end.strip()) + 1))
        else:
            nums.add(int(part))
    return sorted(nums)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="novelctl",
        description="NovelClaw Job Orchestrator — safe translation pipeline control",
    )
    parser.add_argument("--slug", default="global-descent", help="Novel slug (default: global-descent)")
    parser.add_argument("--mode", choices=["safe", "autopilot", "strict", "draft"], default="safe",
                        help="Translation mode (default: safe)")
    parser.add_argument("--force", action="store_true", help="Force re-translate even if th.json exists")
    parser.add_argument("--notify", help="Delivery target (telegram, local, origin)")
    parser.add_argument("--no-score", action="store_true", help="Skip scoring")

    sub = parser.add_subparsers(dest="command", required=True)

    # translate
    t = sub.add_parser("translate", help="Translate chapters with full pipeline")
    t.add_argument("range", help="Chapter range: '139', '140-150', '140,142,145'")

    # repair
    r = sub.add_parser("repair", help="Mechanical repair without LLM")
    r.add_argument("range", help="Chapter range")

    # validate
    v = sub.add_parser("validate", help="Validate + score only")
    v.add_argument("range", help="Chapter range")

    # preflight
    p = sub.add_parser("preflight", help="Check source/config/index/API before spending tokens")
    p.add_argument("range", help="Chapter range")

    # rebuild
    sub.add_parser("rebuild", help="Rebuild chapters.json + search-index")

    # status
    sub.add_parser("status", help="Show active job queue")

    # resume
    sub.add_parser("resume", help="Resume last paused/failed job")

    # stop
    sub.add_parser("stop", help="Stop active job after current chapter")

    # report
    sub.add_parser("report", help="Summary of translated/source_only/failed")

    # check
    c = sub.add_parser("check", help="Show needs_review queue")
    c.add_argument("range", nargs="?", help="Optional chapter range: '139', '140-150'")

    return parser


def run(args: list[str] | None = None) -> dict:
    """Parse args and dispatch to command handler.

    Returns dict with: ok, message, data (optional)
    """
    parser = build_parser()
    parsed = parser.parse_args(args)

    base = {
        "slug": parsed.slug,
        "mode": parsed.mode,
        "force": parsed.force,
        "notify": parsed.notify,
    }

    cmd = parsed.command

    if cmd == "translate":
        nums = parse_range(parsed.range)
        if not nums:
            return {"ok": False, "message": "ช่วงตอนไม่ถูกต้อง", "data": base}
        return {**base, "ok": True, "command": "translate", "nums": nums}

    elif cmd == "repair":
        nums = parse_range(parsed.range)
        if not nums:
            return {"ok": False, "message": "ช่วงตอนไม่ถูกต้อง", "data": base}
        return {**base, "ok": True, "command": "repair", "nums": nums}

    elif cmd == "validate":
        nums = parse_range(parsed.range)
        if not nums:
            return {"ok": False, "message": "ช่วงตอนไม่ถูกต้อง", "data": base}
        return {**base, "ok": True, "command": "validate", "nums": nums}

    elif cmd == "preflight":
        nums = parse_range(parsed.range)
        if not nums:
            return {"ok": False, "message": "ช่วงตอนไม่ถูกต้อง", "data": base}
        return {**base, "ok": True, "command": "preflight", "nums": nums}

    elif cmd == "rebuild":
        return {**base, "ok": True, "command": "rebuild"}

    elif cmd == "status":
        return {"ok": True, "command": "status"}

    elif cmd == "resume":
        return {"ok": True, "command": "resume"}

    elif cmd == "stop":
        return {"ok": True, "command": "stop"}

    elif cmd == "report":
        return {**base, "ok": True, "command": "report"}

    elif cmd == "check":
        return {**base, "ok": True, "command": "check", "range": parsed.range}

    return {"ok": False, "message": f"Unknown command: {cmd}"}
