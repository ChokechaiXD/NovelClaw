from __future__ import annotations

import threading
import time

from llm_rate_limit import ProviderRateLimiter


def test_provider_rate_limiter_caps_concurrent_calls_per_provider():
    limiter = ProviderRateLimiter(max_concurrent=2, min_interval_ms=0)
    active = 0
    max_seen = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal active, max_seen
        with limiter.acquire("openrouter"):
            with lock:
                active += 1
                max_seen = max(max_seen, active)
            time.sleep(0.02)
            with lock:
                active -= 1

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert max_seen == 2


def test_provider_rate_limiter_isolates_provider_buckets():
    limiter = ProviderRateLimiter(max_concurrent=1, min_interval_ms=0)
    entered: list[str] = []
    release_alpha = threading.Event()

    def alpha() -> None:
        with limiter.acquire("alpha"):
            entered.append("alpha")
            release_alpha.wait(timeout=1)

    thread = threading.Thread(target=alpha)
    thread.start()
    while entered != ["alpha"]:
        time.sleep(0.001)

    with limiter.acquire("beta"):
        entered.append("beta")

    release_alpha.set()
    thread.join(timeout=1)

    assert entered == ["alpha", "beta"]


def test_provider_rate_limiter_spaces_start_times_for_same_provider():
    limiter = ProviderRateLimiter(max_concurrent=2, min_interval_ms=100)
    starts: list[float] = []

    def worker() -> None:
        with limiter.acquire("openrouter"):
            starts.append(time.monotonic())

    first = threading.Thread(target=worker)
    second = threading.Thread(target=worker)
    first.start()
    second.start()
    first.join()
    second.join()

    starts.sort()
    assert starts[1] - starts[0] >= 0.05
