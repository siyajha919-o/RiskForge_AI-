"""
Tests for the investment optimizer's risk-reduction maths.

These exist because the efficient frontier was silently broken: reduction was
clamped with `min(x, 85)` in five places, so every budget point past a low
threshold returned exactly 85.0 and the "investment vs. risk reduction" chart —
the one artefact the brief asks for by name — was a horizontal line.

The properties asserted here are the ones that make that chart meaningful.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.optimization import InvestmentOptimizer  # noqa: E402


CEILING = 85.0


def _controls(n=40, seed=7):
    """A synthetic control catalogue shaped like investment_options.csv."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "control_id": [f"CTRL-{i:04d}" for i in range(n)],
        "control_name": [f"Control {i}" for i in range(n)],
        "annual_cost": rng.integers(20_000, 400_000, n).astype(float),
        "risk_reduction_percentage": rng.uniform(5, 40, n),
        "effectiveness_score": rng.uniform(0.05, 0.40, n),
    })


@pytest.fixture
def optimizer():
    return InvestmentOptimizer(data={}, config={"max_risk_reduction_pct": CEILING})


# --- the combination formula -------------------------------------------------

def test_reduction_is_zero_with_no_controls(optimizer):
    assert optimizer._calculate_combined_reduction(pd.DataFrame({"effectiveness_score": []})) == 0.0


def test_single_control_scales_onto_the_ceiling(optimizer):
    """One control at 0.40 gives 40% of the ceiling, not a raw 40%."""
    one = pd.DataFrame({"effectiveness_score": [0.40]})
    assert optimizer._calculate_combined_reduction(one) == pytest.approx(CEILING * 0.40)


def test_reduction_never_exceeds_the_ceiling(optimizer):
    """
    The ceiling is an asymptote, not a clamp. With overlap decay applied, even a
    very large portfolio stays below it — and, importantly, approaches it slowly
    enough that realistic portfolio sizes remain distinguishable from each other.
    """
    for n in (1, 5, 10, 20, 50, 200):
        value = optimizer._calculate_combined_reduction(
            pd.DataFrame({"effectiveness_score": [0.40] * n})
        )
        assert value < CEILING, f"{n} controls hit the ceiling"

    # 6 controls used to reach 81% under pure independence, which is what
    # collapsed the frontier. With overlap modelled it must stay well clear.
    six = optimizer._calculate_combined_reduction(
        pd.DataFrame({"effectiveness_score": [0.40] * 6})
    )
    assert six < 0.9 * CEILING, six


def test_overlap_decay_separates_realistic_portfolio_sizes(optimizer):
    """
    The regression this whole change exists for: 10 vs 20 vs 40 controls must be
    visibly different numbers. Under the old model all three were 85.00.
    """
    values = {
        n: optimizer._calculate_combined_reduction(
            pd.DataFrame({"effectiveness_score": [0.40] * n})
        )
        for n in (10, 20, 40)
    }
    assert values[20] - values[10] > 1.0, values
    assert values[40] > values[20], values


def test_reduction_is_strictly_increasing_in_control_count(optimizer):
    """This is the property the old min(x, 85) clamp destroyed."""
    values = [
        optimizer._calculate_combined_reduction(
            pd.DataFrame({"effectiveness_score": [0.30] * k})
        )
        for k in range(1, 25)
    ]
    assert all(b > a for a, b in zip(values, values[1:])), values


def test_marginal_gain_is_non_increasing(optimizer):
    """Diminishing returns: each added control buys less than the previous one."""
    values = [0.0] + [
        optimizer._calculate_combined_reduction(
            pd.DataFrame({"effectiveness_score": [0.30] * k})
        )
        for k in range(1, 25)
    ]
    deltas = [b - a for a, b in zip(values, values[1:])]
    assert all(b <= a + 1e-9 for a, b in zip(deltas, deltas[1:])), deltas


def test_per_control_effectiveness_is_clipped(optimizer):
    """A bogus 5.0 effectiveness must not blow past a 0.40 control."""
    absurd = pd.DataFrame({"effectiveness_score": [5.0]})
    capped = pd.DataFrame({"effectiveness_score": [0.40]})
    assert optimizer._calculate_combined_reduction(absurd) == pytest.approx(
        optimizer._calculate_combined_reduction(capped)
    )


def test_ceiling_is_configurable(optimizer):
    low = InvestmentOptimizer(data={}, config={"max_risk_reduction_pct": 50.0})
    frame = pd.DataFrame({"effectiveness_score": [0.40] * 10})
    assert low._calculate_combined_reduction(frame) < 50.0
    assert low._calculate_combined_reduction(frame) < optimizer._calculate_combined_reduction(frame)


# --- the knapsack and the frontier -------------------------------------------

def test_knapsack_respects_the_budget(optimizer):
    budget = 500_000
    result = optimizer.solve_knapsack(_controls(), budget)
    assert result["total_cost"] <= budget


def test_knapsack_reduction_stays_below_the_ceiling(optimizer):
    result = optimizer.solve_knapsack(_controls(), 50_000_000)
    assert result["total_value"] < CEILING


def test_frontier_is_not_flat(optimizer):
    """
    The regression guard. Before the fix this produced 85.0 at fifteen of
    sixteen budget points; a flat frontier cannot show an optimal spend zone.
    """
    controls = _controls()
    budgets = np.linspace(100_000, controls["annual_cost"].sum(), 12)
    reductions = [
        optimizer.solve_knapsack(controls, float(b))["total_value"]
        for b in budgets
    ]
    assert len(set(round(r, 4) for r in reductions)) > 1, reductions
    # Non-decreasing: more budget can never buy less reduction.
    assert all(b >= a - 1e-9 for a, b in zip(reductions, reductions[1:])), reductions
