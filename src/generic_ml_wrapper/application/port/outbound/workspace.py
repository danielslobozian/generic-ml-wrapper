# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for inspecting the working environment."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model.workspace import Workspace


class WorkspaceInspectorPort(ABC):
    """Report the run's working environment (folder and git state).

    This is client-agnostic: the wrapper computes these facts itself rather than
    reading them from a client's payload, so every client's status line carries
    them identically.
    """

    @abstractmethod
    def inspect(self) -> Workspace:
        """Inspect the current working environment.

        Returns:
            The working directory and git state (fields the environment does not
            provide are ``None``; ``dirty`` is ``0`` when clean or unknown).
        """
