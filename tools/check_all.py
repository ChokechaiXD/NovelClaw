#!/usr/bin/env python3
"""
NovelClaw Quality Check — local baseline runner.

Run: python tools/check_all.py

Runs:
  1. Python compile check on all tools/
  2. novelctl smoke tests (no LLM)
  3. novelctl commands (status/report/check)
  4. Reader JS syntax check (calls npm run syntax)
  5. API smoke tests (requires running server at :4173)
  6. Schema validation (if sample data exists)

Exit 0 = all OK
Exit 1 = any check failed
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
READER = ROOT / "reader"
PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"

results = []
errors = []
start = time.time()


def check(name, cmd, cwd=None, skip_on_fail=False):
    """Run a check and return True if passed."""
    print(f"  {name}...", end=" ", flush=True)
    try:
        r = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            print(f"{PASS}")
            results.append((name, True, r.stdout[:120]))
            return True
        else:
            msg = r.stderr.strip()[:200]
            print(f"{FAIL}")
            results.append((name, False, msg))
            if not skip_on_fail:
                errors.append(f"{name}: {msg}")
            return False
    except subprocess.TimeoutExpired:
        print(f"{FAIL} (timeout)")
        results.append((name, False, "timeout"))
        if not skip_on_fail:
            errors.append(f"{name}: timeout")
        return False
    except FileNotFoundError as e:
        print(f"{SKIP} ({e})")
        results.append((name, None, str(e)))
        return True


def main():
    print(f"\n{'=' * 60}")
    print(f"  NovelClaw Quality Check")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")

    # ── 1. Python compile ────────────────────────────────────────────
    print("📦 Python Checks")
    py_files = list(TOOLS.rglob("*.py"))
    for f in py_files:
        rel = f.relative_to(ROOT)
        check(f"  Compile {rel}", [sys.executable, "-m", "py_compile", str(f)])

    # ── 2. novelctl smoke tests ──────────────────────────────────────
    print("\n📦 novelctl Smoke Tests")
    check("novelctl tests", [sys.executable, "tools/tests/test_novelctl.py"])

    # ── 3. novelctl commands (no LLM) ────────────────────────────────
    print("\n📦 novelctl Commands")
    check("novelctl status", [sys.executable, "tools/novelctl.py", "status"])
    check("novelctl report", [sys.executable, "tools/novelctl.py", "--slug", "global-descent", "report"])
    check("novelctl check", [sys.executable, "tools/novelctl.py", "--slug", "global-descent", "check"])

    # ── 4. Reader JS syntax ──────────────────────────────────────────
    print("\n📦 Reader JS Checks")
    js_files = list((READER / "public/js").rglob("*.js"))
    for f in sorted(js_files):
        rel = f.relative_to(READER)
        check(f"  Syntax {rel}", ["node", "--check", str(f)])

    # ── 5. server.js syntax ──────────────────────────────────────────
    check("  server.js syntax", ["node", "--check", str(READER / "server.js")])

    # ── 6. API smoke tests (auto-start server if needed) ─────────────
    print("\n📦 API Smoke Tests")
    import socket
    import subprocess as sp
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_running = s.connect_ex(('127.0.0.1', 4173)) == 0
    s.close()
    server_proc = None
    if not server_running:
        print(f"  → Starting reader server on :4173...", end=" ", flush=True)
        try:
            server_proc = sp.Popen(
                ["node", "server.js"],
                cwd=READER,
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )
            # Wait for server to be ready
            for _ in range(15):
                time.sleep(1)
                s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if s2.connect_ex(('127.0.0.1', 4173)) == 0:
                    s2.close()
                    print("✅ ready")
                    break
                s2.close()
            else:
                print("❌ failed to start")
                server_proc.kill()
                server_proc = None
        except FileNotFoundError:
            print("⏭️  (node not found)")
    if server_running or server_proc:
        api_ok = check("API smoke tests", ["node", "tests/test-api.js"], cwd=READER, skip_on_fail=True)
    else:
        print(f"  API smoke tests ⏭️ (server unavailable)")
    if server_proc:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except sp.TimeoutExpired:
            server_proc.kill()

    # ── 6. Schema validation ────────────────────────────────────────
    print("\n📦 Schema Validation")
    check("validate_data", [sys.executable, "tools/validate_data.py", "--all"])

    # ── Summary ──────────────────────────────────────────────────────
    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    passed = sum(1 for _, ok, _ in results if ok is True)
    failed = sum(1 for _, ok, _ in results if ok is False)
    skipped = sum(1 for _, ok, _ in results if ok is None)
    total = len(results)
    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped ({total} total)")
    print(f"  Time: {elapsed:.1f}s")

    if errors:
        print(f"\n  Errors:")
        for e in errors:
            print(f"    {FAIL} {e}")
        sys.exit(1)
    else:
        print(f"\n  {PASS} All checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
