# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for when each job was last worked on."""

from __future__ import annotations

from abc import ABC, abstractmethod


class JobActivityPort(ABC):
    """Read when each job's latest metered turn happened."""

    @abstractmethod
    def last_turn_by_job(self) -> dict[str, float]:
        """Each job's latest recorded turn, epoch seconds; jobs without a timed turn are absent."""
