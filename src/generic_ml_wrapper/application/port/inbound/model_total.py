# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A model's totals across the job."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelTotal:
    """A model's totals across the job.

    Attributes:
        model: The model's name.
        calls: How many turns this model served.
        input_tokens: Total fresh prompt tokens.
        output_tokens: Total completion tokens.
        cache_tokens: Total cache prompt tokens.
        duration_s: Total duration, in seconds.
    """

    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_tokens: int
    duration_s: float
