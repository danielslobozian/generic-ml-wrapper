# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ToolCalls value object."""

import pytest

from generic_ml_wrapper.application.domain.model.tool_calls import ToolCalls


def test_calls_are_counted_most_called_first_then_by_name() -> None:
    calls = ToolCalls.of(["Read", "Bash", "Bash", "Agent", "Read", "Bash"])
    assert calls.counts == (("Bash", 3), ("Read", 2), ("Agent", 1))
    assert calls.total == 6


def test_calls_add_up_across_turns() -> None:
    summed = ToolCalls.summed([ToolCalls.of(["Bash"]), ToolCalls(), ToolCalls.of(["Bash", "Web"])])
    assert summed.as_dict() == {"Bash": 2, "Web": 1}


def test_a_tool_never_called_is_not_listed() -> None:
    assert ToolCalls.from_counts({"Bash": 0, "Read": 1}).counts == (("Read", 1),)
    with pytest.raises(ValueError, match="at least once"):
        ToolCalls((("Bash", 0),))
