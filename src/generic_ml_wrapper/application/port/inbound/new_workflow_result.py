# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The result of an authoring session."""

from __future__ import annotations

from dataclasses import dataclass

from generic_ml_wrapper.application.port.inbound.workflow_outcome import WorkflowOutcome


@dataclass(frozen=True)
class NewWorkflowResult:
    """The result of an authoring session.

    Attributes:
        exit_code: The authoring client's exit code.
        outcome: How the draft resolved (deployed / collision / incomplete).
        name: The workflow name the session settled on, or ``None`` if it named none.
        draft_path: The draft folder — the deployed location on success, or where the
            kept draft still lives on a collision or an incomplete run.
    """

    exit_code: int
    outcome: WorkflowOutcome
    name: str | None
    draft_path: str
