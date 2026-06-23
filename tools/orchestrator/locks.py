"""File-based lock system to prevent concurrent chapter jobs."""

import os
from pathlib import Path

_LOCKS_DIR = Path(__file__).resolve().parent.parent.parent / "jobs" / "locks"


def _ensure_locks_dir():
    _LOCKS_DIR.mkdir(parents=True, exist_ok=True)


def lock_path(slug: str, num: int) -> Path:
    return _LOCKS_DIR / f"{slug}-{num:04d}.lock"


def acquire(slug: str, num: int, job_id: str) -> bool:
    """Try to acquire a lock. Returns True if acquired, False if already locked."""
    _ensure_locks_dir()
    lp = lock_path(slug, num)
    if lp.exists():
        return False
    lp.write_text(job_id, encoding="utf-8")
    return True


def release(slug: str, num: int):
    """Release a lock."""
    lp = lock_path(slug, num)
    if lp.exists():
        lp.unlink(missing_ok=True)


def release_all(slug: str):
    """Release all locks for a slug."""
    _ensure_locks_dir()
    for p in _LOCKS_DIR.glob(f"{slug}-*.lock"):
        p.unlink(missing_ok=True)


def who_holds(slug: str, num: int) -> str | None:
    """Return the job_id holding the lock, or None."""
    lp = lock_path(slug, num)
    if lp.exists():
        return lp.read_text(encoding="utf-8").strip()
    return None
