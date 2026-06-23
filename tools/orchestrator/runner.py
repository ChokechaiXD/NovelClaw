"""Runner — execute translate, validate, rebuild with job checkpoint."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TOOLS_DIR = _PROJECT_ROOT / "tools"
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_TOOLS_DIR))


def _python() -> str:
    return sys.executable or "python"


def _th_path(slug: str, num: int) -> Path:
    return _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.th.json"


def _parse_jsonl(stdout: str) -> list[dict]:
    """Parse JSONL output from translate.py --json.

    translate.py may emit one JSON line per chapter, then a batch summary.
    Returns a list of all successfully parsed JSON objects.
    """
    results = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            results.append(obj)
        except json.JSONDecodeError:
            continue
    return results


def _pick_chapter_result(parsed: list[dict], num: int) -> dict | None:
    """From a list of JSONL objects, pick the one matching the chapter number."""
    for obj in parsed:
        if isinstance(obj, dict) and obj.get("ch") == num:
            return obj
    # Fallback: return first object with status
    for obj in parsed:
        if isinstance(obj, dict) and obj.get("status"):
            return obj
    # Last resort: return the last parseable object
    return parsed[-1] if parsed else None


def translate_single(slug: str, num: int, mode: str = "safe",
                     force: bool = False, score: bool = True) -> dict:
    """Translate a single chapter, return result dict.

    Returns: {ok: bool, chapter_data: dict|None, score: int|None, warnings: list, error: str|None,
              draft: bool}
    """
    result = {"ok": False, "chapter_data": None, "score": None, "warnings": [],
              "error": None, "draft": mode == "draft"}

    is_draft = mode == "draft"
    thp = _th_path(slug, num)

    # Handle --force: backup/delete existing before calling translate.py
    if force and thp.exists():
        bak = thp.with_suffix(".th.json.bak")
        try:
            if bak.exists():
                bak.unlink()
            thp.rename(bak)
        except Exception as e:
            result["error"] = f"cannot backup existing file: {e}"
            return result

    # Build translate.py args
    cmd = [_python(), str(_TOOLS_DIR / "translate.py"), str(num), "--json"]
    if score:
        cmd.append("--score")
    if is_draft:
        cmd.append("--dry-run")

    env = dict(os.environ)
    env["NOVEL_SLUG"] = slug

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=300,
            cwd=str(_PROJECT_ROOT),
            env=env,
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

    # Parse JSONL output
    parsed = _parse_jsonl(proc.stdout)
    chapter_output = _pick_chapter_result(parsed, num)

    if is_draft:
        # Draft mode: restore backup if we backed up, and report the output
        if force and bak.exists():
            if thp.exists():
                thp.unlink()
            bak.rename(thp)
        result["ok"] = True
        result["chapter_data"] = chapter_output or {}
        result["score"] = (chapter_output or {}).get("score")
        result["warnings"] = []
        return result

    # Verify output file was written
    if not thp.exists():
        result["error"] = f"translate.py claimed success but no .th.json at {thp}\nstdout: {proc.stdout[:300]}"
        return result

    # Read back the chapter data for validation
    try:
        chapter_data = json.loads(thp.read_text(encoding="utf-8"))
    except Exception as e:
        result["error"] = f"saved .th.json is invalid JSON: {e}"
        return result

    result["ok"] = True
    result["chapter_data"] = chapter_data
    result["score"] = chapter_output.get("score") if chapter_output else chapter_data.get("score")
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

    import re
    stdout = proc.stdout

    score_match = re.search(r"(\d{1,3})\s*/\s*100", stdout)
    score_val = int(score_match.group(1)) if score_match else None

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

    script = f"""
    const repo = require('./lib/chapter-repo');
    repo.rebuildChaptersIndex('{slug}').then(idx => {{
        console.log('chapters.json rebuilt:', idx.chapters.length, 'chapters');
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


def smoke_test(slug: str, num: int) -> dict:
    """Run a quick smoke test via the reader API.

    Returns: {ok: bool, detail: str|None}
    """
    import urllib.request

    result = {"ok": False, "detail": None}

    try:
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
