"""progress.py — Chapter translation progress tracker.

Tracks chapter translation status in a JSON file per novel.
Prevents duplicate work, enables resume, and provides progress visibility.

Status flow:
  pending → running → done | failed

File location: .chprogress/<slug>.json
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path


PROGRESS_DIR = Path(__file__).parent.parent / ".chprogress"

# Per-slug thread locks for concurrent safety
_locks: dict[str, threading.Lock] = {}


def _get_lock(slug: str) -> threading.Lock:
    if slug not in _locks:
        _locks[slug] = threading.Lock()
    return _locks[slug]


def _get_path(slug: str = "global-descent") -> Path:
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    return PROGRESS_DIR / f"{slug}.json"


def load_progress(slug: str = "global-descent") -> dict:
    """Load progress file. Returns {ch_num_str: {status, retries, updated}}."""
    path = _get_path(slug)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            return {}
    return {}


def save_progress(state: dict, slug: str = "global-descent") -> None:
    """Save progress state to file. Thread-safe."""
    lock = _get_lock(slug)
    with lock:
        path = _get_path(slug)
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def init_progress(chapters: list[int], slug: str = "global-descent") -> dict:
    """Initialize progress for a batch of chapters. Preserves existing status."""
    existing = load_progress(slug)
    for c in chapters:
        key = str(c)
        if key not in existing:
            existing[key] = {"status": "pending", "retries": 0, "updated": None}
    save_progress(existing, slug)
    return existing


def mark_running(ch_num: int, slug: str = "global-descent", state: dict | None = None) -> dict:
    if state is None:
        state = load_progress(slug)
    state[str(ch_num)] = {"status": "running", "retries": state.get(str(ch_num), {}).get("retries", 0), "updated": datetime.now().isoformat()}
    save_progress(state, slug)
    return state


def mark_done(ch_num: int, slug: str = "global-descent", state: dict | None = None) -> dict:
    if state is None:
        state = load_progress(slug)
    state[str(ch_num)] = {"status": "done", "retries": state.get(str(ch_num), {}).get("retries", 0), "updated": datetime.now().isoformat()}
    save_progress(state, slug)
    return state


def mark_failed(ch_num: int, slug: str = "global-descent", state: dict | None = None) -> dict:
    if state is None:
        state = load_progress(slug)
    state[str(ch_num)] = {"status": "failed", "retries": state.get(str(ch_num), {}).get("retries", 0), "updated": datetime.now().isoformat()}
    save_progress(state, slug)
    return state


def get_pending(state: dict) -> list[str]:
    """Return chapter keys that still need translation."""
    return [k for k, v in state.items() if v.get("status") in ("pending", "failed")]


def get_summary(state: dict) -> dict:
    """Return progress summary counts."""
    counts = {"pending": 0, "running": 0, "done": 0, "failed": 0}
    for v in state.values():
        s = v.get("status", "pending")
        if s in counts:
            counts[s] += 1
    return counts


def clear_progress(slug: str = "global-descent") -> None:
    """Delete progress file for a novel."""
    path = _get_path(slug)
    if path.exists():
        path.unlink()
