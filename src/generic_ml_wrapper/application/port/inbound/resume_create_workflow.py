# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for carrying on an unfinished create-workflow interview."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.create_workflow_result import CreateWorkflowResult
from generic_ml_wrapper.application.port.inbound.resume_create_workflow_command import (
    ResumeCreateWorkflowCommand,
)


class ResumeCreateWorkflowUseCase(ABC):
    """Reopen an unfinished draft and carry on the interview that made it."""

    @abstractmethod
    def execute(self, command: ResumeCreateWorkflowCommand) -> CreateWorkflowResult:
        """Reopen the draft.

        Args:
            command: Names the draft, or asks for the latest unfinished one.

        Returns:
            The result: the client's exit code and how the draft resolved — it may still
            end incomplete, and that is not an error.

        Raises:
            NoSuchDraftError: When the named draft is gone, nothing is resumable, the
                session behind it was never recorded, or its client cannot reopen it.
        """
