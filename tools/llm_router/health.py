"""
LLM Router Health — circuit breaker with per-model cooldown tracking.
"""

import json
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_HEALTH_PATH = _PROJECT_ROOT / "logs" / "llm-router" / "health.json"


class HealthTracker:
    """Tracks model health for circuit breaker.

    State per model_key ("provider:model"):
      - failure_count: int
      - last_failure: float (timestamp)
      - cooldown_until: float (timestamp) — no more attempts until this time
      - success_count: int
      - last_success: float (timestamp)

    Cooldown periods (exponential):
      1st failure → 30s
      2nd failure → 60s
      3rd failure → 300s (5 min)
      4+  failure → 900s (15 min)

    Reset on success.
    """

    def __init__(self, health_path: str | None = None):
        self._path = Path(health_path) if health_path else _HEALTH_PATH
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def key(self, provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def record_success(self, provider: str, model: str) -> None:
        k = self.key(provider, model)
        now = time.time()
        self._data[k] = {
            "failure_count": 0,
            "last_success": now,
            "cooldown_until": 0,
            "last_failure": self._data.get(k, {}).get("last_failure", 0),
        }
        self._save()

    def record_failure(self, provider: str, model: str) -> None:
        k = self.key(provider, model)
        now = time.time()
        entry = self._data.get(k, {"failure_count": 0})
        entry["failure_count"] = entry.get("failure_count", 0) + 1
        entry["last_failure"] = now
        entry["last_success"] = entry.get("last_success", 0)

        # Exponential cooldown
        failures = entry["failure_count"]
        if failures <= 1:
            cooldown = 30
        elif failures == 2:
            cooldown = 60
        elif failures == 3:
            cooldown = 300
        else:
            cooldown = 900
        entry["cooldown_until"] = now + cooldown

        self._data[k] = entry
        self._save()

    def is_available(self, provider: str, model: str) -> bool:
        """Check if model is available (not in cooldown)."""
        k = self.key(provider, model)
        entry = self._data.get(k)
        if entry is None:
            return True
        cooldown_until = entry.get("cooldown_until", 0)
        return time.time() >= cooldown_until

    def cooldown_remaining(self, provider: str, model: str) -> float:
        """Seconds remaining in cooldown. 0 = available."""
        k = self.key(provider, model)
        entry = self._data.get(k)
        if entry is None:
            return 0
        remaining = entry.get("cooldown_until", 0) - time.time()
        return max(0, remaining)

    def status(self, provider: str, model: str) -> str:
        """Human-readable status."""
        if self.is_available(provider, model):
            return "available"
        remaining = self.cooldown_remaining(provider, model)
        return f"cooldown ({remaining:.0f}s remaining)"


# Global singleton
_health = HealthTracker()


def get_health() -> HealthTracker:
    return _health


def reset_health() -> None:
    """Clear all health data (for testing)."""
    global _health
    _health = HealthTracker()
    if _health._path.exists():
        _health._path.unlink(missing_ok=True)
