# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Resolve the caller to use for a given run."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerPort


class CliCallerProviderPort(ABC):
    """Resolve the caller to use for a given run."""

    @abstractmethod
    def for_run(self, run: RunContext) -> CliCallerPort:
        """Return the caller instance for a run.

        Args:
            run: The run to launch.

        Returns:
            A caller bound to the run.
        """
