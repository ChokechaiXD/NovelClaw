"""Needs review queue + audit log + quality records for translation pipeline.

Sub-modules:
- write_needs_review / list_needs_review / remove_needs_review
- write_audit_log (per-action file dump)
- write_quality_record (structured history per chapter)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_NEEDS_DIR = _PROJECT_ROOT / "jobs" / "needs_review"
_LOGS_DIR = _PROJECT_ROOT / "logs" / "translate"
_QUALITY_DIR = _PROJECT_ROOT / "jobs" / "quality"


# ═══════════════════════════════════════════════════════════════════════
# Needs Review Queue
# ═══════════════════════════════════════════════════════════════════════

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


def count_needs_review(slug: str | None = None) -> int:
    """Count needs_review entries."""
    return len(list_needs_review(slug))


# ═══════════════════════════════════════════════════════════════════════
# Audit Log (per-action file dump)
# ═══════════════════════════════════════════════════════════════════════

def write_audit_log(slug: str, num: int, command: str, mode: str,
                    stdout: str = "", stderr: str = "",
                    parsed_jsonl: list[dict] | None = None,
                    chapter_data: dict | None = None,
                    validation_result: dict | None = None,
                    result: dict | None = None):
    """Write per-chapter audit log."""
    d = audit_dir(slug, num)
    d.mkdir(parents=True, exist_ok=True)

    if stdout:
        (d / "stdout.txt").write_text(stdout[:100000], encoding="utf-8")
    if stderr:
        (d / "stderr.txt").write_text(stderr[:100000], encoding="utf-8")
    if parsed_jsonl:
        (d / "parsed.jsonl").write_text(
            "\n".join(json.dumps(o, ensure_ascii=False) for o in parsed_jsonl),
            encoding="utf-8"
        )
    if chapter_data:
        (d / "chapter.json").write_text(
            json.dumps(chapter_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    if validation_result:
        (d / "validation.json").write_text(
            json.dumps(validation_result, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
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


# ═══════════════════════════════════════════════════════════════════════
# Quality Record (structured history per chapter)
# ═══════════════════════════════════════════════════════════════════════

def quality_record_path(slug: str, num: int) -> Path:
    """Path to the quality record file for a chapter."""
    return _QUALITY_DIR / slug / f"{num:04d}.json"


def write_quality_record(
    slug: str,
    num: int,
    action: str,
    model: str = "unknown",
    provider: str = "unknown",
    score: int | None = None,
    duration_ms: int | None = None,
    mqm: dict | None = None,
    error: str | None = None,
):
    """Append a quality record for a chapter.

    Creates or appends to jobs/quality/<slug>/<num>.json.
    Each chapter gets ONE file with an array of records — append-only.

    Record fields:
      - action: "translate" | "validate" | "repair" | "judge"
      - model: model name used
      - provider: provider name
      - score: quality score (0-100)
      - duration_ms: time taken
      - mqm: MQM-style error tags { accuracy, fluency, terminology, omission }
      - error: error message if the step failed
      - timestamp: ISO 8601
    """
    _QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    (_QUALITY_DIR / slug).mkdir(parents=True, exist_ok=True)

    path = quality_record_path(slug, num)

    # Read existing records or start fresh
    records = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            records = existing.get("records", [])
        except (json.JSONDecodeError, OSError):
            records = []

    # Append new record
    record = {
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if model:
        record["model"] = model
    if provider:
        record["provider"] = provider
    if score is not None:
        record["score"] = score
    if duration_ms is not None:
        record["duration_ms"] = duration_ms
    if mqm:
        record["mqm"] = mqm
    if error:
        record["error"] = error

    records.append(record)

    # Write back
    path.write_text(
        json.dumps({"slug": slug, "num": num, "records": records},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return record


def get_quality_history(slug: str, num: int) -> list[dict]:
    """Get all quality records for a chapter. Returns empty list if none."""
    path = quality_record_path(slug, num)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("records", [])
    except (json.JSONDecodeError, OSError):
        return []


def get_all_quality_records(slug: str | None = None) -> dict[str, list[dict]]:
    """Get quality records for all chapters. Returns { slug/num: records }."""
    base = _QUALITY_DIR
    if slug:
        base = base / slug
    if not base.exists():
        return {}

    result = {}
    for f in sorted(base.rglob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            key = f"{data['slug']}/{data['num']:04d}"
            result[key] = data["records"]
        except Exception:
            pass
    return result
