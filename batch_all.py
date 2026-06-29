"""Batch translate ALL chapters from current state onwards.
Skips known-problematic API chapters. Restart-safe."""
import subprocess, sys, os, re, time
from pathlib import Path

ROOT = Path(r"C:\Users\BlankScreen\Workspace\NovelClaw")
LOG = ROOT / "batch_all_log.txt"

# Chapters that persistently fail API/timeout — skip for now
SKIP = {15, 16, 18, 19, 37, 97, 119, 170, 190, 192}

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

def get_saved():
    d = ROOT / "novels" / "global-descent" / "chapters"
    saved = set()
    for f in sorted(d.glob("*.th.json")):
        saved.add(int(f.name.split(".")[0]))
    return saved

saved = get_saved()
needed = sorted((set(range(1, 1240)) - saved) - SKIP)

log(f"📖 ต้องแปล: {len(needed)} ตอน (ข้าม {len(SKIP)} ตอนที่ API มีปัญหา)")

passed = 0
failed = 0
total = len(needed)
_start = time.time()

for i, ch in enumerate(needed):
    log(f"[{i+1}/{total}] ตอน {ch}...")
    try:
        r = subprocess.run(
            [sys.executable, "novelclaw.py", "translate", str(ch)],
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "PYTHONPATH": "tools"},
            cwd=str(ROOT),
        )
        out = r.stdout
        if re.search(rf"✅.*{ch}", out):
            score_m = re.search(r"คะแนน:\s*([\d.]+)", out)
            score = score_m.group(1) if score_m else "?"
            log(f"  ✅ {score}/100")
            passed += 1
        else:
            rm = re.search(r"FAILED:\s*(.+?)$", out, re.MULTILINE)
            reason = rm.group(1).strip()[:60] if rm else "unknown"
            log(f"  ❌ {reason}")
            failed += 1
    except subprocess.TimeoutExpired:
        log(f"  ⌛ TIMEOUT (300s)")
        failed += 1
    except Exception as e:
        log(f"  💥 {str(e)[:60]}")
        failed += 1

    # Progress every 100 chapters
    if (i + 1) % 100 == 0:
        elapsed_h = (time.time() - _start) / 3600
        rate = (i + 1) / elapsed_h if elapsed_h > 0 else 0
        rem = (total - i - 1) / rate if rate > 0 else 0
        log(f"📊 {i+1}/{total} | {passed}✅ {failed}❌ | {rate:.0f} ch/h | ~{rem:.0f}h remaining")

log(f"\n=== เสร็จ! {passed} ผ่าน, {failed} ล้มเหลว จาก {total} ตอน ===")
