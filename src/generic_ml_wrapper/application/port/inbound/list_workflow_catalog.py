# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing workflows with the words behind their slugs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.workflow import Workflow


class ListWorkflowCatalogUseCase(ABC):
    """List the runnable workflows with their labels and descriptions."""

    @abstractmethod
    def execute(self) -> list[Workflow]:
        """List the workflows, sorted by slug.

        The richer counterpart to ``ListWorkflowsUseCase``, which returns bare slugs for the
        pickers that only need something to launch.

        Returns:
            The workflows (empty if none exist).
        """
