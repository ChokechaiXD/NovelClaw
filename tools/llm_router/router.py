"""
LLM Router — fallback chain orchestrator.

Core function: call_profile() takes a profile name + prompt, 
tries each model in the chain until one succeeds.

Flow per model call:
  1. Health check (circuit breaker)
  2. Call provider
  3. Validate output (per profile rules)
  4. If pass → record_success, return result
  5. If fail → record_failure, try next model
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_profile
from .providers import call_provider
from .health import get_health
from .validators import validate_translate_response

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs" / "llm-router"


class RouterConfig:
    """Configuration for a single router call."""

    def __init__(
        self,
        profile: str = "translate",
        prompt: str = "",
        system: str | None = None,
        job_id: str | None = None,
        log_outputs: bool = True,
    ):
        self.profile = profile
        self.prompt = prompt
        self.system = system
        self.job_id = job_id or f"job-{int(time.time())}"
        self.log_outputs = log_outputs


class RouterResult:
    """Result of a router call."""

    def __init__(self):
        self.ok: bool = False
        self.text: str = ""
        self.provider: str = ""
        self.model: str = ""
        self.elapsed_sec: float = 0
        self.attempts: list[dict] = []
        self.error: str = ""
        self.log_path: str = ""

    def __repr__(self) -> str:
        if self.ok:
            return f"RouterResult(✅ {self.provider}:{self.model}, {len(self.text)} chars, {self.elapsed_sec:.1f}s)"
        return f"RouterResult(❌ {self.error[:80]})"


def _make_job_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + f"-{int(time.time() % 1000):03d}"


def call_profile(
    profile: str = "translate",
    prompt: str = "",
    system: str | None = None,
    job_id: str | None = None,
    log_outputs: bool = True,
) -> RouterResult:
    """Execute a profile's fallback chain.

    Tries each model in profile chain until one:
      - passes health check (not in cooldown)
      - responds without HTTP/network error
      - passes output validation

    Returns RouterResult with full attempt log.
    """
    result = RouterResult()
    result.job_id = job_id or _make_job_id()
    start = time.time()

    # Validate profile exists
    try:
        chain = get_profile(profile)
    except KeyError as e:
        result.error = str(e)
        return result

    health = get_health()

    for step_idx, entry in enumerate(chain):
        provider = entry["provider"]
        model = entry["model"]
        timeout = entry.get("timeout_sec", 90)
        max_tokens = entry.get("max_tokens", 4096)
        temperature = entry.get("temperature", 0.3)

        # 1. Health check
        if not health.is_available(provider, model):
            remaining = health.cooldown_remaining(provider, model)
            msg = f"{provider}:{model} in cooldown ({remaining:.0f}s remaining)"
            result.attempts.append({
                "step": step_idx,
                "provider": provider,
                "model": model,
                "status": "cooldown",
                "error": msg,
                "elapsed_sec": 0,
            })
            continue

        # 2. Call provider
        attempt_start = time.time()
        try:
            text = call_provider(
                provider_name=provider,
                prompt=prompt,
                system=system,
                model=model,
                timeout_sec=timeout,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            elapsed = time.time() - attempt_start
            health.record_failure(provider, model)
            result.attempts.append({
                "step": step_idx,
                "provider": provider,
                "model": model,
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "elapsed_sec": round(elapsed, 2),
            })
            continue

        elapsed = time.time() - attempt_start

        # 3. Validate output (translate profile only for now)
        if profile in ("translate", "polish"):
            vr = validate_translate_response(text)
            if not vr.ok:
                health.record_failure(provider, model)
                result.attempts.append({
                    "step": step_idx,
                    "provider": provider,
                    "model": model,
                    "status": "validation_fail",
                    "error": vr.reason,
                    "details": vr.details,
                    "elapsed_sec": round(elapsed, 2),
                })
                continue

        # 4. Success
        health.record_success(provider, model)
        result.ok = True
        result.text = text
        result.provider = provider
        result.model = model
        result.elapsed_sec = round(elapsed, 1)
        result.attempts.append({
            "step": step_idx,
            "provider": provider,
            "model": model,
            "status": "success",
            "elapsed_sec": round(elapsed, 2),
        })
        break

    # If we exhausted all models
    if not result.ok:
        result.error = (
            f"All {len(chain)} models in profile '{profile}' failed. "
            f"Last attempts: {[a.get('error', '?') for a in result.attempts[-3:]]}"
        )

    total_elapsed = time.time() - start

    # 5. Log
    if log_outputs:
        result.log_path = _write_log(result, profile, total_elapsed)

    return result


def _write_log(result: RouterResult, profile: str, total_elapsed: float) -> str:
    """Write router log entry."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = _LOG_DIR / date_str / f"{result.job_id}.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "job_id": result.job_id,
        "profile": profile,
        "ok": result.ok,
        "provider": result.provider,
        "model": result.model,
        "text_length": len(result.text),
        "total_elapsed_sec": round(total_elapsed, 2),
        "attempts": result.attempts,
        "error": result.error or None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log_path.write_text(
        json.dumps(entry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(log_path)


def call_with_fallback(
    prompt: str,
    system: str | None = None,
    profile: str = "translate",
    fallback_profiles: list[str] | None = None,
) -> RouterResult:
    """Call with primary profile, fallback to other profiles on total failure.

    E.g. if 'translate' profile fully fails, try 'validate' profile as emergency.
    """
    result = call_profile(profile=profile, prompt=prompt, system=system)
    if result.ok:
        return result

    if fallback_profiles:
        for fb_profile in fallback_profiles:
            print(f"  ⚠ Router: primary '{profile}' failed → trying fallback profile '{fb_profile}'")
            result = call_profile(profile=fb_profile, prompt=prompt, system=system)
            if result.ok:
                return result

    return result
