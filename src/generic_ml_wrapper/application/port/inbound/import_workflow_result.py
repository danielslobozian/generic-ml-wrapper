# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The result of importing a workflow."""

from __future__ import annotations

from dataclasses import dataclass

from generic_ml_wrapper.application.port.inbound.import_outcome import ImportOutcome


@dataclass(frozen=True)
class ImportWorkflowResult:
    """The result of importing a workflow.

    Attributes:
        outcome: How the import resolved.
        name: The workflow's slug.
        path: The installed workflow's folder, or the existing one when refused.
        backup: Where the displaced workflow was moved, or ``None`` when none was.
    """

    outcome: ImportOutcome
    name: str
    path: str
    backup: str | None = None
