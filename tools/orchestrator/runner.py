"""Runner — execute translate, validate, rebuild with job checkpoint."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from orchestrator.subprocess_runner import run_cmd

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
    draft_moved = False  # Track if draft moved a file out of canonical path

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
        # ── Build translate.py args — NO --dry-run for draft ──────────
        # Draft mode: call LLM normally (translate.py writes canonical),
        # then we MOV it to staging/drafts/ after success.
        # This ensures draft is a real translation preview, not a context dump.
        cmd = [_python(), str(_TOOLS_DIR / "translate.py"), str(num), "--json"]
        if score:
            cmd.append("--score")

        env = dict(os.environ)
        env["NOVEL_SLUG"] = slug

        cr = run_cmd(cmd, timeout=300, cwd=str(_PROJECT_ROOT), env=env)

        if cr.timed_out:
            result["error"] = "translate.py timeout (300s)"
            return result
        if not cr.ok:
            result["error"] = f"translate.py exit {cr.returncode}: {cr.stderr[:500]}"
            return result

        # ── Parse JSONL output ───────────────────────────────────────
        parsed = _parse_jsonl(cr.stdout)
        chapter_output = _pick_chapter_result(parsed, num)
        if chapter_output is None:
            result["error"] = f"cannot parse translate.py output (no JSON for ch {num}): {cr.stdout[:300]}"
            return result

        # ── Draft mode: move from canonical to staging/drafts/ ────────
        if is_draft:
            if thp.exists():
                dp = _draft_path(slug, num)
                dp.parent.mkdir(parents=True, exist_ok=True)
                # Read back what was written, save to draft path
                try:
                    draft_data = json.loads(thp.read_text(encoding="utf-8"))
                    draft_data["status"] = "draft"
                    dp.write_text(json.dumps(draft_data, ensure_ascii=False, indent=2), encoding="utf-8")
                    # Remove canonical file — draft should not leave artifacts
                    thp.unlink()
                    draft_moved = True
                except Exception as e:
                    result["error"] = f"draft write failed: {e}"
                    return result
            else:
                # translate.py may write to stdout JSON but not save (if --dry-run was used internally)
                # Build from parsed output
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
                draft_moved = True

            result["ok"] = True
            # Read draft result regardless of which path was taken
            dp_check = _draft_path(slug, num)
            if dp_check.exists():
                result["chapter_data"] = json.loads(dp_check.read_text(encoding="utf-8"))
            else:
                result["chapter_data"] = {"status": "draft", "chapterNo": num}
            result["score"] = chapter_output.get("score") if chapter_output else None
            return result

        # ── Normal mode: verify .th.json was written ─────────────────
        if not thp.exists():
            result["error"] = f"translate.py claimed success but no .th.json at {thp}\\nstdout: {cr.stdout[:300]}"
            return result

        # Read back for validation
        try:
            chapter_data = json.loads(thp.read_text(encoding="utf-8"))
        except Exception as e:
            result["error"] = f"saved .th.json is invalid JSON: {e}"
            return result

        # ── Schema validation gate (redundant safety) ─────────────────
        try:
            from jsonschema import Draft7Validator, FormatChecker
            schema_path = _TOOLS_DIR / "schema" / "chapter.schema.json"
            if schema_path.exists():
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                validator = Draft7Validator(schema, format_checker=FormatChecker())
                errs = sorted(validator.iter_errors(chapter_data), key=lambda e: e.path)
                if errs:
                    if had_backup and bak.exists():
                        thp.write_bytes(bak.read_bytes())
                        result["backup_restored"] = True
                    msgs = [f"[{' → '.join(str(p) for p in e.path)}] {e.message}" for e in errs]
                    result["error"] = "Schema validation failed:\n" + "\n".join(msgs)
                    return result
        except ImportError:
            pass

        # ── Glossary validation gate ──────────────────────────────
        try:
            paragraph_text = "\n".join(
                p for p in chapter_data.get("paragraphs", [])
                if p not in ("(จบบท)", "(End)", "（終）", "(끝)")
            )
            from glossary import validate_translation
            gv = validate_translation(paragraph_text, slug)
            if not gv.ok:
                result["glossary_warnings"] = [f'Missing term: {m["source"]} → {m["thai"]} ({m["category"]})' for m in gv.missing_terms]
                result["warnings"] = result.get("warnings", []) + result["glossary_warnings"]
        except ImportError:
            pass

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
                    if thp.exists():
                        thp.unlink()  # Remove failed translation before restore
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

    if not th_path.exists():
        result["error"] = f"ไม่พบไฟล์ {th_path}"
        return result

    # ── Schema validation gate ──────────────────────────────────────
    try:
        import json
        from jsonschema import Draft7Validator, FormatChecker

        schema_path = _TOOLS_DIR / "schema" / "chapter.schema.json"
        if schema_path.exists():
            data = json.loads(th_path.read_text(encoding="utf-8"))
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            validator = Draft7Validator(schema, format_checker=FormatChecker())
            errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
            if errors:
                err_msgs = [f"[{' → '.join(str(p) for p in e.path)}] {e.message}" for e in errors]
                result["error"] = f"Schema validation failed:\n" + "\n".join(err_msgs)
                result["ok"] = False
                result["score"] = 0
                return result
    except ImportError:
        pass  # jsonschema not installed — skip gate
    except json.JSONDecodeError as e:
        result["error"] = f"Invalid JSON: {e}"
        return result

    src_path = _PROJECT_ROOT / "novels" / slug / "chapters" / f"{num:04d}.cn.json"
    
    # If source is JSON, extract paragraph text for proper comparison
    if src_path.exists():
        try:
            src_data = json.loads(src_path.read_text(encoding="utf-8"))
            src_paras = src_data.get("paragraphs", [])
            if src_paras:
                # Write extracted text to a temp file for scorer to use
                import tempfile
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", encoding="utf-8", delete=False
                )
                tmp.write("\n".join(src_paras))
                tmp.close()
                src_text_path = tmp.name
            else:
                src_text_path = src_path
        except (json.JSONDecodeError, Exception):
            src_text_path = src_path
    else:
        src_text_path = src_path

    cmd = [
        _python(), str(_TOOLS_DIR / "scorer.py"),
        str(th_path),
    ]
    if src_path.exists():
        cmd += ["--source", str(src_text_path)]

    cr = run_cmd(cmd, timeout=30, cwd=str(_PROJECT_ROOT))
    if not cr.ok and not cr.stdout:
        result["error"] = cr.error or "scorer.py failed"
        return result

    import re
    stdout = cr.stdout
    score_match = re.search(r"(\d{1,3})\s*/\s*100", stdout)
    score_val = int(score_match.group(1)) if score_match else None

    details = []
    for line in stdout.split("\n"):
        stripped = line.strip()
        if stripped and ("⚠" in stripped or "✗" in stripped or "✅" in stripped or "fail" in stripped.lower()):
            details.append(stripped)

    # Validation "ok" means we successfully ran scorer and got a result.
    # scorer.py exits code 1 when quality fails (e.g. Script Purity 50/100
    # due to 1 Latin leak), but the run itself is valid.
    # Use score_val presence as the real signal, not just exit code.
    result["ok"] = score_val is not None or cr.ok
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
    cr = run_cmd(["node", "-e", script], timeout=30, cwd=str(reader_dir))

    if not cr.ok:
        result["error"] = cr.stderr[:500]
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
