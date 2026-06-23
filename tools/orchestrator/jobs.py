"""Job state machine — created → preflight → running → validating → repairing → saving → rebuilding → testing → done/failed/needs_review."""

import json
from datetime import datetime, timezone
from pathlib import Path

_JOBS_DIR = Path(__file__).resolve().parent.parent.parent / "jobs"

VALID_STATES = [
    "created", "preflight", "queued", "running",
    "validating", "repairing", "saving", "rebuilding", "testing",
    "done", "failed", "needs_review",
]


class Job:
    """Immutable(ish) job state — read/write as JSON on disk."""

    def __init__(self, data: dict):
        self.data = data

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def slug(self) -> str:
        return self.data.get("slug", "global-descent")

    @property
    def state(self) -> str:
        return self.data.get("state", "created")

    @property
    def chapters(self) -> list[int]:
        return self.data.get("chapters", [])

    @property
    def done(self) -> list[int]:
        return self.data.get("done", [])

    @property
    def failed(self) -> list[dict]:
        return self.data.get("failed", [])

    @property
    def current(self) -> int | None:
        return self.data.get("current")

    @property
    def mode(self) -> str:
        return self.data.get("mode", "safe")

    @property
    def pending(self) -> list[int]:
        done_set = set(self.done)
        failed_set = set(f["chapter"] for f in self.failed)
        return [c for c in self.chapters if c not in done_set and c not in failed_set]

    def to_dict(self) -> dict:
        return dict(self.data)

    # ── Mutators (return new Job) ──────────────────────────────────

    def copy(self, **overrides) -> "Job":
        d = dict(self.data)
        d.update(overrides)
        d["updatedAt"] = datetime.now(timezone.utc).isoformat()
        return Job(d)

    # ── Disk I/O ───────────────────────────────────────────────────

    def save(self):
        target = _active_dir() / f"{self.id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def archive(self, target_state: str = "done"):
        src = _active_dir() / f"{self.id}.json"
        if not src.exists():
            return
        dst_dir = _JOBS_DIR / target_state
        dst_dir.mkdir(parents=True, exist_ok=True)
        self.copy(state=target_state).save_to(dst_dir / f"{self.id}.json")
        src.unlink(missing_ok=True)

    def save_to(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")


def _active_dir() -> Path:
    return _JOBS_DIR / "active"


def create(slug: str, chapters: list[int], mode: str = "safe", force: bool = False) -> Job:
    """Create a new job."""
    now = datetime.now(timezone.utc)
    job_id = f"translate-{now.strftime('%Y%m%d-%H%M%S')}"
    data = {
        "id": job_id,
        "slug": slug,
        "mode": mode,
        "force": force,
        "state": "created",
        "chapters": sorted(set(chapters)),
        "current": None,
        "done": [],
        "failed": [],
        "needs_review": [],
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
    }
    job = Job(data)
    job.save()
    return job


def load(job_id: str) -> Job | None:
    """Load a job by ID."""
    for sub in ("active", "done", "failed"):
        p = _JOBS_DIR / sub / f"{job_id}.json"
        if p.exists():
            return Job(json.loads(p.read_text(encoding="utf-8")))
    return None


def load_active() -> list[Job]:
    """Load all active jobs, newest first."""
    d = _active_dir()
    if not d.exists():
        return []
    jobs = []
    for p in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.suffix == ".json":
            try:
                jobs.append(Job(json.loads(p.read_text(encoding="utf-8"))))
            except Exception:
                pass
    return jobs


def load_latest(slug: str | None = None) -> Job | None:
    """Load the latest active job, optionally filtered by slug."""
    active = load_active()
    if slug:
        active = [j for j in active if j.slug == slug]
    return active[0] if active else None


def get_state_summary(job: Job) -> str:
    """Short one-line summary of a job."""
    total = len(job.chapters)
    done_n = len(job.done)
    failed_n = len(job.failed)
    pending_n = len(job.pending)
    pct = int((done_n / total) * 100) if total else 0
    return f"{job.id} | {job.state} | {done_n}/{total} done ({pct}%) | {failed_n} failed | {pending_n} pending"
