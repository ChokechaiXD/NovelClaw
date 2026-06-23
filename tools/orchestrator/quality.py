"""Needs review queue + audit log for translation pipeline."""

import json
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_NEEDS_DIR = _PROJECT_ROOT / "jobs" / "needs_review"
_LOGS_DIR = _PROJECT_ROOT / "logs" / "translate"


def needs_review_path(slug: str, num: int) -> Path:
    return _NEEDS_DIR / f"{slug}-{num:04d}.json"


def audit_dir(slug: str, num: int) -> Path:
    return _LOGS_DIR / slug / f"{num:04d}"


def write_needs_review(slug: str, num: int, reason: str, score: int | None = None,
                       mode: str = "safe", fix_command: str | None = None):
    """Write a needs_review entry for a failed chapter."""
    _NEEDS_DIR.mkdir(parents=True, exist_ok=True)
    if fix_command is None:
        if score is not None and score < 70:
            fix_command = f"python tools/novelctl.py translate {num} --mode strict --force --slug {slug}"
        else:
            fix_command = f"python tools/novelctl.py repair {num} --slug {slug}"
    entry = {
        "chapter": num,
        "slug": slug,
        "reason": reason,
        "score": score,
        "mode": mode,
        "suggestedCommand": fix_command,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    p = needs_review_path(slug, num)
    p.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def remove_needs_review(slug: str, num: int):
    """Remove a needs_review entry (when chapter is fixed)."""
    p = needs_review_path(slug, num)
    if p.exists():
        p.unlink(missing_ok=True)


def list_needs_review(slug: str | None = None) -> list[dict]:
    """List all needs_review entries, optionally filtered by slug."""
    if not _NEEDS_DIR.exists():
        return []
    entries = []
    for p in sorted(_NEEDS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if slug and not p.name.startswith(slug):
            continue
        try:
            entry = json.loads(p.read_text(encoding="utf-8"))
            entries.append(entry)
        except Exception:
            pass
    return entries


def write_audit_log(slug: str, num: int, command: str, mode: str,
                    stdout: str = "", stderr: str = "",
                    parsed_jsonl: list[dict] | None = None,
                    chapter_data: dict | None = None,
                    validation_result: dict | None = None,
                    result: dict | None = None):
    """Write per-chapter audit log."""
    d = audit_dir(slug, num)
    d.mkdir(parents=True, exist_ok=True)

    # Save raw stdout
    if stdout:
        (d / "stdout.txt").write_text(stdout[:100000], encoding="utf-8")
    if stderr:
        (d / "stderr.txt").write_text(stderr[:100000], encoding="utf-8")

    # Save parsed JSONL
    if parsed_jsonl:
        (d / "parsed.jsonl").write_text(
            "\n".join(json.dumps(o, ensure_ascii=False) for o in parsed_jsonl),
            encoding="utf-8"
        )

    # Save chapter data
    if chapter_data:
        (d / "chapter.json").write_text(
            json.dumps(chapter_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # Save validation report
    if validation_result:
        (d / "validation.json").write_text(
            json.dumps(validation_result, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # Save report
    report = {
        "command": command,
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }
    (d / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def audit_exists(slug: str, num: int) -> bool:
    """Check if audit log exists for a chapter."""
    return (audit_dir(slug, num) / "report.json").exists()


def count_needs_review(slug: str | None = None) -> int:
    """Count needs_review entries."""
    return len(list_needs_review(slug))
