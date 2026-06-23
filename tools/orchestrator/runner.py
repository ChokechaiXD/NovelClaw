"""Runner — execute translate, validate, rebuild with job checkpoint."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TOOLS_DIR = _PROJECT_ROOT / "tools"
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_TOOLS_DIR))


def _python() -> str:
    """Detect python executable."""
    return sys.executable or "python"


def translate_single(slug: str, num: int, mode: str = "safe",
                     force: bool = False, score: bool = True) -> dict:
    """Translate a single chapter, return result dict.

    Returns: {ok: bool, chapter_data: dict|None, score: int|None, warnings: list, error: str|None}
    """
    result = {"ok": False, "chapter_data": None, "score": None, "warnings": [], "error": None}

    # Build translate.py args
    cmd = [_python(), str(_TOOLS_DIR / "translate.py"), str(num), "--json"]
    if score:
        cmd.append("--score")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=300,
            cwd=str(_PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        result["error"] = "translate.py timeout (300s)"
        return result
    except Exception as e:
        result["error"] = f"translate.py failed: {e}"
        return result

    if proc.returncode != 0:
        result["error"] = f"translate.py exit {proc.returncode}: {proc.stderr[:500]}"
        return result

    # Parse JSON output from stdout
    try:
        output = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result["error"] = f"translate.py output not JSON: {proc.stdout[:200]}"
        return result

    # translate.py now writes directly to .th.json via --json flag
    # Our orchestrator needs to ensure the output goes to staging
    # Let's translate and then move the file
    th_path = _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.th.json"
    staging_path = _PROJECT_ROOT / "staging" / slug / f"{num:04d}.th.json.tmp"

    # If translate.py wrote directly, move to staging first
    if th_path.exists():
        staging_path.parent.mkdir(parents=True, exist_ok=True)
        th_path.rename(staging_path)

    # Parse the chapter data
    chapter_data = output if isinstance(output, dict) else {}

    # Extract score if available
    score_val = chapter_data.get("score") or output.get("score")

    result["ok"] = True
    result["chapter_data"] = chapter_data
    result["score"] = score_val
    result["warnings"] = chapter_data.get("warnings", [])

    return result


def validate_single(slug: str, num: int) -> dict:
    """Run scorer on a single chapter.

    Returns: {ok: bool, score: int|None, details: list, error: str|None}
    """
    result = {"ok": False, "score": None, "details": [], "error": None}

    th_path = _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.th.json"
    src_path = _PROJECT_ROOT / "novels" / slug / "chapters" / "source" / f"{num:04d}.md"

    if not th_path.exists():
        result["error"] = f"ไม่พบไฟล์ {th_path}"
        return result

    cmd = [
        _python(), str(_TOOLS_DIR / "scorer.py"),
        str(th_path),
    ]
    if src_path.exists():
        cmd += ["--source", str(src_path)]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            cwd=str(_PROJECT_ROOT),
        )
    except Exception as e:
        result["error"] = str(e)
        return result

    # Scorer outputs to stdout with score info
    stdout = proc.stdout
    stderr = proc.stderr

    # Extract score from output (scorer.py outputs "Score: N/100" or similar)
    import re
    score_match = re.search(r"(\d{1,3})\s*/\s*100", stdout)
    score_val = int(score_match.group(1)) if score_match else None

    # Collect details (warnings, errors)
    details = []
    for line in stdout.split("\n"):
        stripped = line.strip()
        if stripped and ("⚠" in stripped or "✗" in stripped or "✅" in stripped or "fail" in stripped.lower()):
            details.append(stripped)

    result["ok"] = proc.returncode == 0
    result["score"] = score_val
    result["details"] = details
    return result


def rebuild_index(slug: str) -> dict:
    """Rebuild chapters.json + search-index via reader Node.js module.

    Returns: {ok: bool, error: str|None}
    """
    result = {"ok": False, "error": None}

    # Use the Node.js chapter-repo module to rebuild
    script = f"""
    const repo = require('./lib/chapter-repo');
    repo.rebuildChaptersIndex('{slug}').then(idx => {{
        console.log('chapters.json rebuilt:', idx.chapters.length, 'chapters');
        // Also rebuild search-index.th.json
        const ss = require('./lib/search-service');
        return ss.rebuildSearchIndex('{slug}', 'th');
    }}).then(si => {{
        console.log('search-index.th.json rebuilt:', si.entries.length, 'entries');
        process.exit(0);
    }}).catch(e => {{ console.error(e); process.exit(1); }});
    """

    reader_dir = _PROJECT_ROOT / "reader"
    try:
        proc = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, timeout=30,
            cwd=str(reader_dir),
        )
    except Exception as e:
        result["error"] = str(e)
        return result

    if proc.returncode != 0:
        result["error"] = proc.stderr[:500]
        return result

    result["ok"] = True
    return result


def stage_to_final(slug: str, num: int) -> dict:
    """Move staging file to final chapters/ dir with backup.

    Returns: {ok: bool, error: str|None}
    """
    result = {"ok": False, "error": None}

    staging = _PROJECT_ROOT / "staging" / slug / f"{num:04d}.th.json.tmp"
    final = _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.th.json"

    if not staging.exists():
        result["error"] = f"staging file not found: {staging}"
        return result

    # Backup existing th.json if any
    if final.exists():
        bak = final.with_suffix(".th.json.bak")
        final.rename(bak)

    # Move staging → final
    staging.rename(final)
    result["ok"] = True
    return result


def smoke_test(slug: str, num: int) -> dict:
    """Run a quick smoke test via the reader API.

    Returns: {ok: bool, detail: str|None}
    """
    import urllib.request
    import json

    result = {"ok": False, "detail": None}

    try:
        # Test the API directly
        url = f"http://localhost:4173/api/novel/{slug}/chapter/{num}?lang=th"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            paras = len(data.get("paragraphs", []))
            if paras > 0:
                result["ok"] = True
                result["detail"] = f"loaded {paras} paragraphs"
            else:
                result["detail"] = "chapter loaded but 0 paragraphs"
    except Exception as e:
        result["detail"] = str(e)

    return result
