"""Translator router — backend selection with session stickiness.

Routes all LLM calls through consolidated backends.
Provides session stickiness: same session_id → same backend/model.

Usage:
    from translator.router import new_session, route

    session = new_session("translate_fast")
    result = route(session, prompt, system=system)

    # Next call with same session → same backend (session_sticky=True)
    result2 = route(session, prompt2)
"""

import time
from datetime import datetime, timezone
from pathlib import Path

from translator.backends import OpenModelBackend, OpenRouterBackend
from translator.policy import get_chain, ProfileChain


# ── Session tracking ──────────────────────────────────────────────────

class RouterSession:
    """Tracks a translation session for backend stickiness.

    Once a backend succeeds, subsequent calls with the same session
    use the same backend (unless it's in cooldown).
    """
    def __init__(self, profile: str, session_id: str | None = None):
        self.profile = profile
        self.session_id = session_id or f"s-{int(time.time())}"
        self.chain = get_chain(profile)
        self.active_backend: str | None = None  # "openrouter" etc.
        self.active_model: str | None = None
        self.last_ok_at: float = 0

    def __repr__(self) -> str:
        return (f"RouterSession({self.profile}, "
                f"active={self.active_backend}:{self.active_model})")


# ── Result ────────────────────────────────────────────────────────────

class RouterResult:
    """Result of a routed LLM call."""
    def __init__(self):
        self.ok: bool = False
        self.text: str = ""
        self.provider: str = ""
        self.model: str = ""
        self.elapsed_sec: float = 0
        self.error: str = ""

    def __repr__(self) -> str:
        if self.ok:
            return f"RouterResult(✅ {self.provider}:{self.model}, {len(self.text)} chars)"
        return f"RouterResult(❌ {self.error[:80]})"


# ── Session management ────────────────────────────────────────────────

def new_session(profile: str = "translate_fast",
                session_id: str | None = None) -> RouterSession:
    """Create a new routing session.

    Args:
        profile: Profile name (translate_fast, translate_quality, judge, validate)
        session_id: Optional session ID for resume/restore

    Returns:
        RouterSession with chain loaded.
    """
    return RouterSession(profile=profile, session_id=session_id)


# ── Route function ────────────────────────────────────────────────────

def _build_backend(backend_name: str, model: str):
    """Factory: create a backend instance from name + model."""
    backends = {
        "openmodel": OpenModelBackend,
        "openrouter": OpenRouterBackend,
    }
    cls = backends.get(backend_name)
    if cls is None:
        raise ValueError(f"Unknown backend '{backend_name}'")
    if cls == OpenModelBackend:
        return cls(model_override=model)
    return cls(model=model)


def route(session: RouterSession, prompt: str,
          system: str | None = None, **kwargs) -> RouterResult:
    """Route a translation call through the session's fallback chain.

    Args:
        session: RouterSession from new_session()
        prompt: User text to send
        system: System prompt (optional)
        **kwargs: Overrides (timeout_sec, max_tokens, temperature)

    Returns:
        RouterResult with full details.
    """
    result = RouterResult()
    start = time.time()

    # Build ordered list of backends to try
    backends_to_try = []

    # If session has an active backend and session_sticky=True, try it first
    if session.chain.session_sticky and session.active_backend:
        backends_to_try.append(
            (session.active_backend, session.active_model)
        )

    # Then the primary
    p = session.chain.primary
    if not backends_to_try or p.model != session.active_model:
        backends_to_try.insert(0, (p.backend, p.model))

    # Then fallbacks
    for fb in session.chain.fallbacks:
        if not any(b[0] == fb.backend and b[1] == fb.model
                   for b in backends_to_try):
            backends_to_try.append((fb.backend, fb.model))

    # Try each backend
    last_error = None
    for backend_name, model in backends_to_try:
        try:
            bk = _build_backend(backend_name, model)
            text = bk.translate(prompt, system=system, **kwargs)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            continue

        # Success — update session
        session.active_backend = backend_name
        session.active_model = model
        session.last_ok_at = time.time()

        elapsed = time.time() - start
        result.ok = True
        result.text = text
        result.provider = backend_name
        result.model = model
        result.elapsed_sec = round(elapsed, 1)
        return result

    # All backends failed
    elapsed = time.time() - start
    result.elapsed_sec = round(elapsed, 1)
    result.error = (f"All {len(backends_to_try)} backends failed. "
                    f"Last: {last_error}")
    return result
