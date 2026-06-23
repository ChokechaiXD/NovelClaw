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


def _ch_path(slug: str, num: int, lang: str = "th") -> Path:
    return _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.{lang}.json"


def _draft_path(slug: str, num: int) -> Path:
    return _PROJECT_ROOT / "staging" / "drafts" / slug / f"{num:04d}.th.json"


def _bak_path(slug: str, num: int) -> Path:
    return _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.th.json.bak"


def _parse_jsonl(stdout: str) -> list[dict]:
    """Parse JSONL output from translate.py --json."""
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
    """From a list of JSONL objects, pick the one matching chapter number."""
    for obj in parsed:
        if isinstance(obj, dict) and obj.get("ch") == num:
            return obj
    for obj in parsed:
        if isinstance(obj, dict) and obj.get("status"):
            return obj
    return parsed[-1] if parsed else None


def translate_single(slug: str, num: int, mode: str = "safe",
                     force: bool = False, score: bool = True) -> dict:
    """Translate a single chapter with proper error handling.

    --force: backs up existing .th.json before run, restores on any failure.
    draft:  writes to staging/drafts/ instead of canonical path.
    Returns: {ok, chapter_data, score, warnings, error, draft, backup_restored}
    """
    result = {"ok": False, "chapter_data": None, "score": None, "warnings": [],
              "error": None, "draft": mode == "draft", "backup_restored": False}

    is_draft = mode == "draft"
    thp = _ch_path(slug, num)
    bak = _bak_path(slug, num)
    had_backup = False

    # ── Force: backup existing file ──────────────────────────────────
    if force and thp.exists():
        try:
            bak.parent.mkdir(parents=True, exist_ok=True)
            if bak.exists():
                bak.unlink()
            thp.rename(bak)
            had_backup = True
        except Exception as e:
            result["error"] = f"cannot backup existing file: {e}"
            return result

    try:
        # ── Draft: use staging path ──────────────────────────────────
        if is_draft:
            draft_dir = _draft_path(slug, num).parent
            draft_dir.mkdir(parents=True, exist_ok=True)

        # ── Build translate.py args ──────────────────────────────────
        cmd = [_python(), str(_TOOLS_DIR / "translate.py"), str(num), "--json"]
        if score:
            cmd.append("--score")
        if is_draft:
            cmd.append("--dry-run")

        env = dict(os.environ)
        env["NOVEL_SLUG"] = slug

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
                cwd=str(_PROJECT_ROOT), env=env,
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

        # ── Parse JSONL output ───────────────────────────────────────
        parsed = _parse_jsonl(proc.stdout)
        chapter_output = _pick_chapter_result(parsed, num)
        if chapter_output is None:
            result["error"] = f"cannot parse translate.py output (no JSON for ch {num}): {proc.stdout[:300]}"
            return result

        # ── Draft mode: write to staging/drafts/ ─────────────────────
        if is_draft:
            draft_chapter_data = {
                "novelId": slug,
                "chapterNo": num,
                "sourceLang": "cn",
                "targetLang": "th",
                "title": {"translated": chapter_output.get("title", f"ตอนที่ {num}"), "source": ""},
                "status": "draft",
                "paragraphs": chapter_output.get("paragraphs", []),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
            dp = _draft_path(slug, num)
            dp.parent.mkdir(parents=True, exist_ok=True)
            dp.write_text(json.dumps(draft_chapter_data, ensure_ascii=False, indent=2), encoding="utf-8")
            result["ok"] = True
            result["chapter_data"] = draft_chapter_data
            result["score"] = chapter_output.get("score")
            return result

        # ── Normal mode: verify .th.json was written ─────────────────
        if not thp.exists():
            result["error"] = f"translate.py claimed success but no .th.json at {thp}\nstdout: {proc.stdout[:300]}"
            return result

        # Read back for validation
        try:
            chapter_data = json.loads(thp.read_text(encoding="utf-8"))
        except Exception as e:
            result["error"] = f"saved .th.json is invalid JSON: {e}"
            return result

        # ── Success path: delete backup if it exists ─────────────────
        if had_backup and bak.exists():
            try:
                bak.unlink()
                result["backup_restored"] = False  # backup deleted, new file is king
            except Exception:
                pass

        result["ok"] = True
        result["chapter_data"] = chapter_data
        result["score"] = chapter_output.get("score") if chapter_output else chapter_data.get("score")
        result["warnings"] = chapter_data.get("warnings", [])
        return result

    finally:
        # ── Force rollback: on any failure, restore backup ────────────
        # If we didn't return ok=True above, and had_backup, restore
        if not result.get("ok") and had_backup:
            if bak.exists():
                try:
                    thp.parent.mkdir(parents=True, exist_ok=True)
                    bak.rename(thp)
                    result["backup_restored"] = True
                    # Don't overwrite the error message — keep original reason
                    # but append restore note
                    orig_error = result.get("error", "")
                    if orig_error:
                        result["error"] = f"{orig_error} (backup restored from .bak)"
                    else:
                        result["error"] = "unknown error (backup restored from .bak)"
                except Exception as restore_err:
                    # Worst case: both files may be in bad state
                    result["error"] = (result.get("error", "unknown") +
                                       f"; additionally, backup restore also failed: {restore_err}")


def validate_single(slug: str, num: int) -> dict:
    """Run scorer on a single chapter.

    Returns: {ok: bool, score: int|None, details: list, error: str|None}
    """
    result = {"ok": False, "score": None, "details": [], "error": None}

    th_path = _ch_path(slug, num)
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
    """Rebuild chapters.json + search-index via reader Node.js module."""
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
    """Quick smoke test via the reader API."""
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
