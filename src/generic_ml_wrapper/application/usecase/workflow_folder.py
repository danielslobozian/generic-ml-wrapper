# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Locating the folder of a workflow that may be edited."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.workflow_name import WorkflowName
from generic_ml_wrapper.application.domain.model.workflow_name_error import WorkflowNameError
from generic_ml_wrapper.application.domain.model.workflow_not_found_error import (
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort

# The create-workflow meta drives the authoring session (for editing as for creating); its
# name and the shared partial are reserved and cannot themselves be edited.
META = "create-workflow"
RESERVED = frozenset({META, "_common"})


def folder_for_editing(workflows: WorkflowSourcePort, name: str) -> str:
    """Return the folder of a workflow that may be edited.

    Nothing is seeded on the way: everything seeding installs is rejected as reserved
    here anyway.

    Args:
        workflows: Where workflows are found.
        name: The workflow to locate.

    Returns:
        Its existing folder, never a created one.

    Raises:
        WorkflowNameError: When the name is not a valid identifier, or names one of the
            reserved workflows that drive authoring itself.
        WorkflowNotFoundError: When no workflow of that name exists.
    """
    try:
        WorkflowName(name)
    except IdentifierError as error:
        raise WorkflowNameError(error.catalogue_key, **error.params) from error
    if name in RESERVED:
        raise WorkflowNameError("error.workflow.reserved_name", name=name)
    if workflows.find(name) is None:
        raise WorkflowNotFoundError("error.workflow.not_found", name=name)
    return workflows.folder(name)
