# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the domain models' construction-time invariants."""

from __future__ import annotations

import math

import pytest

from generic_ml_wrapper.application.domain.model.client_status import ClientStatus
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage


def test_turn_usage_accepts_valid_values() -> None:
    turn = TurnUsage("JOB-1_001", 100, 20, 0.01, "Opus 4.8", timestamp=1.0, duration_s=2.5)
    assert turn.input_tokens == 100
    assert TurnUsage("JOB-1_001", 0, 0, None, None).cost_usd is None


@pytest.mark.parametrize(
    ("kwargs"),
    [
        {"input_tokens": -1},
        {"output_tokens": -5},
        {"cache_creation_tokens": -1},
        {"cache_read_tokens": -1},
        {"cost_usd": -0.01},
        {"cost_usd": math.nan},
        {"cost_usd": math.inf},
        {"timestamp": -1.0},
        {"duration_s": -0.5},
        {"duration_s": math.inf},
    ],
)
def test_turn_usage_rejects_impossible_values(kwargs: dict[str, object]) -> None:
    base = {
        "session_id": "JOB-1_001",
        "input_tokens": 1,
        "output_tokens": 1,
        "cost_usd": 0.0,
        "model": "m",
    }
    with pytest.raises(ValueError, match="must be"):
        TurnUsage(**{**base, **kwargs})  # type: ignore[arg-type]


def test_client_status_accepts_valid_and_absent() -> None:
    assert ClientStatus("m", 0, 0.0, ()).context_pct == 0
    assert ClientStatus("m", 100, 1.5, ()).context_pct == 100
    assert ClientStatus(None, None, None, ()).model is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"context_pct": -1},
        {"context_pct": 101},
        {"session_cost_usd": -0.01},
        {"session_cost_usd": math.inf},
    ],
)
def test_client_status_rejects_out_of_range(kwargs: dict[str, object]) -> None:
    base = {"model": "m", "context_pct": 50, "session_cost_usd": 1.0, "extras": ()}
    with pytest.raises(ValueError, match="must be"):
        ClientStatus(**{**base, **kwargs})  # type: ignore[arg-type]
