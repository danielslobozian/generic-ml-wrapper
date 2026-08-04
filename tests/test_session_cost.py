# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SessionCost value object.

The schema carries no ``CHECK`` constraints by decision -- protecting the data is the
domain's job, and a store written around rather than through it fails on the way back in.
That decision is only sound if the value that reaches the store has been checked, which is
what this type is for and what these tests pin.
"""

from __future__ import annotations

import math

import pytest

from generic_ml_wrapper.application.domain.model.session_cost import SessionCost


def test_a_cost_carries_its_session_and_amount() -> None:
    cost = SessionCost("JOB-1_001", 1.25)

    assert cost.session_id == "JOB-1_001"
    assert cost.cost_usd == 1.25


def test_zero_is_a_real_cost() -> None:
    assert SessionCost("JOB-1_001", 0.0).cost_usd == 0.0


def test_a_cost_with_no_session_is_refused() -> None:
    with pytest.raises(ValueError, match="session_id must not be empty"):
        SessionCost("", 1.0)


def test_a_negative_cost_is_refused() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        SessionCost("JOB-1_001", -0.01)


@pytest.mark.parametrize("amount", [math.inf, -math.inf, math.nan])
def test_a_cost_that_is_not_a_finite_number_is_refused(amount: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        SessionCost("JOB-1_001", amount)


def test_two_costs_of_the_same_session_and_amount_are_equal() -> None:
    assert SessionCost("JOB-1_001", 1.25) == SessionCost("JOB-1_001", 1.25)
