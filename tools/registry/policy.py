"""registry/policy.py — Centralized quality and routing policies.

Re-exports from canonical sources.
Single import point for all policy consumers.
"""

# ── Quality thresholds ────────────────────────────────────────────────
from orchestrator.policy import get_policy, list_modes, ModePolicy, QUALITY_POLICY  # noqa: F401

# ── Translator routing policies ───────────────────────────────────────
from translator.policy import (  # noqa: F401
    FALLBACK_CHAINS,
    get_chain,
    list_profiles,
    ProfileChain,
    BackendRef,
)
