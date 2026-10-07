# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the available workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ListWorkflows(ABC):
    """List the runnable workflows."""

    @abstractmethod
    def execute(self) -> list[str]:
        """List the runnable workflow names.

        Returns:
            The workflow names, sorted (empty if none exist).
        """
