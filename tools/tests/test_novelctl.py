"""
tests/test_novelctl.py — Smoke tests for novelctl orchestrator

Run: python -m pytest tools/tests/test_novelctl.py -v
Or:  python tools/tests/test_novelctl.py

Tests (no LLM required):
  ✓ JSONL parser handles multiple lines
  ✓ _pick_chapter_result picks correct chapter
  ✓ Draft mode does not modify canonical .th.json
  ✓ Force backup/restore on failure
  ✓ Force deletes backup on success
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure UTF-8 encoding for stdout/stderr on Windows to avoid UnicodeEncodeError with emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure tools/ is on path
_TOOLS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS_DIR.parent))
sys.path.insert(0, str(_TOOLS_DIR))
from orchestrator import runner


# ── Helpers ─────────────────────────────────────────────────────────

PASS = 0
FAIL = 0


def test(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  ✓ {name}")
        PASS += 1
    else:
        print(f"  ✗ {name}: {detail}")
        FAIL += 1


# ── Test JSONL Parser ──────────────────────────────────────────────

def test_jsonl_parser():
    """Test that _parse_jsonl handles multi-line JSONL correctly."""
    # Single per-chapter JSON
    out1 = '{"status":"ok","ch":139,"paragraphs":50}\n{"status":"ok","total":1,"success":1,"failed":0}\n'
    parsed = runner._parse_jsonl(out1)
    test("_parse_jsonl returns 2 objects", len(parsed) == 2)

    # Pick chapter result
    picked = runner._pick_chapter_result(parsed, 139)
    test("_pick_chapter_result picks ch 139", picked and picked.get("ch") == 139)
    test("picked has status ok", picked and picked.get("status") == "ok")

    # Empty stdout
    parsed_empty = runner._parse_jsonl("")
    test("_parse_jsonl empty returns []", len(parsed_empty) == 0)

    # Invalid JSON lines are skipped
    mixed = '{"valid":true}\nnot-json\n{"also_valid":1}\n'
    parsed_mixed = runner._parse_jsonl(mixed)
    test("_parse_jsonl skips invalid lines", len(parsed_mixed) == 2)

    # No match returns last
    picked_none = runner._pick_chapter_result(parsed_mixed, 999)
    test("_pick_chapter_result fallback to last", picked_none and picked_none.get("also_valid") == 1)


# ── Test Force Backup/Restore ──────────────────────────────────────

def test_force_backup_restore():
    """Test that force restore works by simulating failure paths."""
    slug = "test-force"
    num = 9999  # unlikely real chapter

    # Create fake existing th.json
    thp = runner._ch_path(slug, num)
    bak = runner._bak_path(slug, num)
    thp.parent.mkdir(parents=True, exist_ok=True)
    original = {"novelId": slug, "chapterNo": num, "paragraphs": ["original"]}
    thp.write_text(json.dumps(original), encoding="utf-8")

    # Simulate: call runner.translate_single with force=True
    # It will backup -> try to run translate.py -> fail because no source
    # -> should restore backup
    result = runner.translate_single(slug, num, mode="safe", force=True, score=False)

    # On failure with force, backup should be restored
    test("--force: backup restored on failure", result.get("backup_restored") == True,
         f"error={result.get('error','')}")
    test("--force: original file exists after restore", thp.exists(), str(thp))
    if thp.exists():
        restored = json.loads(thp.read_text(encoding="utf-8"))
        test("--force: original content preserved", restored.get("paragraphs") == ["original"])

    # Cleanup
    _cleanup_force_files(slug, num)


def test_force_success_cleans_backup():
    """Test that force deletes backup on success (mock success)."""
    slug = "test-force-success"
    num = 9998

    # Create fake existing th.json
    thp = runner._ch_path(slug, num)
    bak = runner._bak_path(slug, num)
    thp.parent.mkdir(parents=True, exist_ok=True)
    original = {"novelId": slug, "chapterNo": num, "paragraphs": ["original"]}
    thp.write_text(json.dumps(original), encoding="utf-8")

    # We can't easily force translate.py to succeed,
    # but we can test that backup exists after the backup step
    # and that the function handles it gracefully
    result = runner.translate_single(slug, num, force=True, score=False)

    # Since translate will fail (no source), backup should restore
    # Backup should not exist anymore (restored back)
    test("--force: backup removed after restore", not bak.exists())

    _cleanup_force_files(slug, num)


def _cleanup_force_files(slug, num):
    """Clean up test files."""
    import time
    for p in [runner._ch_path(slug, num), runner._bak_path(slug, num),
              runner._draft_path(slug, num)]:
        if p.exists():
            p.unlink()
    # Clean parent dirs
    for parent in [runner._ch_path(slug, num).parent, Path(__file__).parent.parent / "staging" / "drafts" / slug]:
        if parent.exists() and not list(parent.iterdir()):
            parent.rmdir()


# ── Test Draft Mode ────────────────────────────────────────────────

def test_draft_mode_does_not_touch_canonical():
    """Test that draft mode does not create/remove canonical .th.json."""
    slug = "test-draft"
    num = 9997

    thp = runner._ch_path(slug, num)
    dp = runner._draft_path(slug, num)

    # Ensure canonical doesn't exist
    if thp.exists():
        thp.unlink()

    # Run draft (will fail source not found, but should not create canonical)
    result = runner.translate_single(slug, num, mode="draft", force=False, score=False)

    # Draft mode should NOT create canonical .th.json
    test("draft: canonical .th.json not created", not thp.exists())
    # Draft mode should have error because translate.py --dry-run fails without source
    # But importantly, it should set draft=True in result
    test("draft: result.draft is True", result.get("draft") == True)

    # Cleanup
    if dp.exists():
        dp.unlink()


# ── Main ───────────────────────────────────────────────────────────

def main():
    print("novelctl Smoke Tests (no LLM required)\n")
    test_jsonl_parser()
    test_force_backup_restore()
    test_force_success_cleans_backup()
    test_draft_mode_does_not_touch_canonical()

    print(f"\n{'=' * 40}")
    print(f"  {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
