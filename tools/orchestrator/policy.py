"""
Quality policy — threshold configs for translate/validate modes.

Usage:
    from orchestrator.policy import get_policy

    policy = get_policy("safe")
    if score >= policy["pass_score"]: ...
"""

from __future__ import annotations

from typing import TypedDict


class ModePolicy(TypedDict):
    pass_score: int
    repair_score: int
    stop_on_fail: bool


QUALITY_POLICY: dict[str, ModePolicy] = {
    "safe": {
        "pass_score": 70,
        "repair_score": 60,
        "stop_on_fail": True,
    },
    "strict": {
        "pass_score": 85,
        "repair_score": 75,
        "stop_on_fail": True,
    },
    "autopilot": {
        "pass_score": 70,
        "repair_score": 60,
        "stop_on_fail": False,
    },
    "draft": {
        "pass_score": 0,  # draft skips validation entirely
        "repair_score": 0,
        "stop_on_fail": False,
    },
}

VALID_MODES = list(QUALITY_POLICY.keys())


def get_policy(mode: str) -> ModePolicy:
    """Get quality thresholds for the given mode."""
    if mode not in QUALITY_POLICY:
        raise KeyError(
            f"Unknown mode '{mode}'. "
            f"Valid modes: {', '.join(VALID_MODES)}"
        )
    return QUALITY_POLICY[mode]


def list_modes() -> list[str]:
    return VALID_MODES
