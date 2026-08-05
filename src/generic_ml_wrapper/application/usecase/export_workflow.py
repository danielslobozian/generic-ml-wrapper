# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ExportWorkflowUseCase use case: pack a workflow for sharing."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.workflow_name import WorkflowName
from generic_ml_wrapper.application.port.inbound.edit_workflow import WorkflowNotFoundError
from generic_ml_wrapper.application.port.inbound.export_workflow import ExportWorkflowUseCase
from generic_ml_wrapper.application.port.inbound.new_workflow import WorkflowNameError

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.workflow_archive import WorkflowArchivePort
    from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort

_RESERVED = frozenset({"create-workflow", "_common"})


class ExportWorkflowService(ExportWorkflowUseCase):
    """Pack a workflow folder into an archive through the archive port."""

    def __init__(self, workflows: WorkflowSourcePort, archive: WorkflowArchivePort) -> None:
        """Wire the use case to the workflow source and the archive.

        Args:
            workflows: Resolves and checks the workflow's folder.
            archive: Packs the folder, and decides what a shared workflow consists of.
        """
        self._workflows = workflows
        self._archive = archive

    def execute(self, name: str) -> str:
        """Export a workflow, returning the path to the archive written."""
        try:
            WorkflowName(name)
        except IdentifierError as error:
            raise WorkflowNameError(error.catalogue_key, **error.params) from error
        if name in _RESERVED:
            raise WorkflowNameError("error.workflow.reserved_name", name=name)
        # No seeding here. What seeding installs is the shared base and the
        # meta-workflow, both rejected as reserved above, so it could never change the
        # answer below -- it only wrote to the user's home on the way to a refusal.
        if self._workflows.find(name) is None:
            raise WorkflowNotFoundError("error.workflow.not_found", name=name)
        return str(self._archive.pack(Path(self._workflows.folder(name)), name))
