"""Tests: ScorerHistory adaptive threshold (Phase 3)."""
import pytest
from scorer import ScorerHistory


def test_history_starts_at_default():
    h = ScorerHistory()
    assert h.effective_threshold == 85.0


def test_history_requires_3_before_adjusting():
    h = ScorerHistory()
    h.update(92.0)
    assert h.effective_threshold == 85.0
    h.update(88.0)
    assert h.effective_threshold == 85.0


def test_history_adjusts_after_3_chapters():
    h = ScorerHistory()
    for s in [92, 88, 95]:
        h.update(s)
    t = h.effective_threshold
    # mean=91.67, variance ~8.22, std ~2.87 → 91.67 - 1.5*2.87 = 87.37
    assert 86.0 < t < 89.0, f"expected ~87.4 got {t}"


def test_history_clamps_to_85():
    """Ensure threshold never drops below 85.0 even with outliers."""
    h = ScorerHistory()
    for s in [90, 87, 93, 30, 88]:  # 30 is outlier
        h.update(s)
    t = h.effective_threshold
    assert t >= 85.0, f"clamped to {t}"


def test_history_stabilizes_with_more_data():
    h = ScorerHistory()
    scores = [90, 87, 93, 85, 88, 92, 86]
    thresholds = []
    for s in scores:
        h.update(s)
        if len(h.scores) >= 3:
            thresholds.append(h.effective_threshold)
    # After 7 chapters threshold should be stable
    assert 84.0 < thresholds[-1] < 90.0
    # First adjustment should be higher than later ones (outliers pull down)
    assert thresholds[0] >= thresholds[-1] - 1.0


def test_history_round_trip():
    h = ScorerHistory()
    for s in [91, 89, 94, 86, 90]:
        h.update(s)
    t1 = h.effective_threshold
    assert t1 != 85.0  # adjusted

    # Simulate reset with same scores
    h2 = ScorerHistory()
    for s in [85, 100, 100]:  # perfect scores but variance is large
        h2.update(s)
    # mean=95, std=7.07 → 95 - 1.5*7.07 = 84.4 → clamped to 85
    assert h2.effective_threshold == 85.0


def test_history_update_returns_none():
    """update() has no return value — called for side effect."""
    h = ScorerHistory()
    assert h.update(90.0) is None
