from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


@dataclass
class _ProviderState:
    semaphore: threading.BoundedSemaphore
    lock: threading.Lock
    last_started_at: float = 0.0


class ProviderRateLimiter:
    """Thread-local process guard for outbound LLM provider calls."""

    def __init__(self, max_concurrent: int, min_interval_ms: int = 0) -> None:
        self.max_concurrent = max(1, int(max_concurrent))
        self.min_interval = max(0, int(min_interval_ms)) / 1000.0
        self._states: dict[str, _ProviderState] = {}
        self._states_lock = threading.Lock()

    def _state_for(self, provider: str) -> _ProviderState:
        key = (provider or "default").strip().lower() or "default"
        with self._states_lock:
            state = self._states.get(key)
            if state is None:
                state = _ProviderState(
                    semaphore=threading.BoundedSemaphore(self.max_concurrent),
                    lock=threading.Lock(),
                )
                self._states[key] = state
            return state

    @contextmanager
    def acquire(self, provider: str) -> Iterator[None]:
        state = self._state_for(provider)
        state.semaphore.acquire()
        try:
            if self.min_interval > 0:
                with state.lock:
                    now = time.monotonic()
                    wait_for = self.min_interval - (now - state.last_started_at)
                    if wait_for > 0:
                        time.sleep(wait_for)
                    state.last_started_at = time.monotonic()
            yield
        finally:
            state.semaphore.release()


def build_default_rate_limiter() -> ProviderRateLimiter:
    return ProviderRateLimiter(
        max_concurrent=_env_int("NOVELCLAW_LLM_MAX_CONCURRENT", 3, minimum=1, maximum=10),
        min_interval_ms=_env_int("NOVELCLAW_LLM_MIN_INTERVAL_MS", 250, minimum=0, maximum=60_000),
    )


_DEFAULT_LIMITER = build_default_rate_limiter()


@contextmanager
def limit_llm_call(provider: str) -> Iterator[None]:
    with _DEFAULT_LIMITER.acquire(provider):
        yield
