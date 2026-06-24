"""Translator policy — fallback chains + quality thresholds.

Defines per-profile model chains and session stickiness rules.
Canonical config — llm_router/config.py should import from here.
"""

from dataclasses import dataclass, field


@dataclass
class BackendRef:
    """Reference to a backend + model combination."""
    backend: str       # "openrouter", "openmodel", etc.
    model: str
    timeout_sec: int = 90
    max_tokens: int = 4096
    temperature: float = 0.3


@dataclass
class ProfileChain:
    """A named profile with primary + fallback chain."""
    name: str
    primary: BackendRef
    fallbacks: list[BackendRef] = field(default_factory=list)
    session_sticky: bool = True


# ── Default fallback chains ────────────────────────────────────────────

FALLBACK_CHAINS: dict[str, ProfileChain] = {
    "translate_fast": ProfileChain(
        name="translate_fast",
        primary=BackendRef("openrouter", "google/gemma-4-26b-a4b-it:free",
                          timeout_sec=80, max_tokens=4096, temperature=0.28),
        fallbacks=[
            BackendRef("openrouter", "google/gemma-4-31b-it:free",
                      timeout_sec=100, max_tokens=4096, temperature=0.28),
            BackendRef("openrouter", "openai/gpt-oss-120b:free",
                      timeout_sec=90, max_tokens=4096, temperature=0.2),
            BackendRef("openrouter", "openrouter/free",
                      timeout_sec=75, max_tokens=2048, temperature=0.25),
        ],
    ),
    "translate_quality": ProfileChain(
        name="translate_quality",
        primary=BackendRef("openrouter", "google/gemma-4-31b-it:free",
                          timeout_sec=110, max_tokens=8192, temperature=0.25),
        fallbacks=[
            BackendRef("openrouter", "google/gemma-4-26b-a4b-it:free",
                      timeout_sec=85, max_tokens=4096, temperature=0.26),
            BackendRef("openrouter", "openai/gpt-oss-120b:free",
                      timeout_sec=90, max_tokens=4096, temperature=0.15),
            BackendRef("openrouter", "openrouter/free",
                      timeout_sec=75, max_tokens=2048, temperature=0.25),
        ],
    ),
    "judge": ProfileChain(
        name="judge",
        primary=BackendRef("openrouter", "google/gemma-4-26b-a4b-it:free",
                          timeout_sec=60, max_tokens=2048, temperature=0.1),
        fallbacks=[
            BackendRef("openrouter", "google/gemma-4-31b-it:free",
                      timeout_sec=80, max_tokens=2048, temperature=0.1),
            BackendRef("openrouter", "openrouter/free",
                      timeout_sec=60, max_tokens=1024, temperature=0.1),
        ],
    ),
    "validate": ProfileChain(
        name="validate",
        primary=BackendRef("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free",
                          timeout_sec=120, max_tokens=4096, temperature=0.05),
        fallbacks=[
            BackendRef("openrouter", "google/gemma-4-31b-it:free",
                      timeout_sec=100, max_tokens=2048, temperature=0.05),
            BackendRef("openrouter", "openrouter/free",
                      timeout_sec=75, max_tokens=1536, temperature=0.05),
        ],
    ),
}


def get_chain(profile: str) -> ProfileChain:
    """Get a profile chain by name. Raises KeyError if not found."""
    if profile not in FALLBACK_CHAINS:
        raise KeyError(f"Unknown profile '{profile}'. "
                       f"Available: {list(FALLBACK_CHAINS.keys())}")
    return FALLBACK_CHAINS[profile]


def list_profiles() -> list[str]:
    """List available profile names."""
    return list(FALLBACK_CHAINS.keys())
