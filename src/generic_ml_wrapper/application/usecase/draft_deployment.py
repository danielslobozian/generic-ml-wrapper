# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Settling an authoring draft once its session has ended."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.slug import Slug
from generic_ml_wrapper.application.domain.model.workflow_name import WorkflowName
from generic_ml_wrapper.application.domain.model.workflow_name_error import WorkflowNameError
from generic_ml_wrapper.application.port.inbound.create_workflow_result import CreateWorkflowResult
from generic_ml_wrapper.application.port.inbound.workflow_outcome import WorkflowOutcome
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.workflow_folder import RESERVED


def validate_workflow_name(name: str) -> None:
    """Reject an invalid or reserved workflow name.

    Args:
        name: The candidate slug.

    Raises:
        WorkflowNameError: When the name is not a usable identifier.
    """
    try:
        WorkflowName(name)
    except IdentifierError as error:
        raise WorkflowNameError(error.catalogue_key, **error.params) from error
    if name in RESERVED:
        raise WorkflowNameError("error.workflow.reserved_name", name=name)


def settle_draft(
    workflows: WorkflowSourcePort,
    clock: Callable[[], datetime],
    exit_code: int,
    draft: str,
) -> CreateWorkflowResult:
    """Deploy the draft if the session settled it and declared it finished.

    The slug comes from the label the session chose, the same way a role's or an
    environment's does — the author names the workflow in words and never has to think in
    kebab-case. An older interview that wrote a bare name instead still works: that name
    is taken as both slug and label.

    Args:
        workflows: Reads the draft marker and deploys the folder.
        clock: Returns "now" for the deployed folder's recorded creation time.
        exit_code: What the authoring session returned.
        draft: The draft folder.

    Returns:
        The outcome. A missing or unfinished marker, a label that slugifies to nothing,
        or a slug already taken each leaves the draft in place so nothing is lost; only a
        finished, valid, free slug is deployed.
    """
    marker = workflows.read_draft_marker(draft)
    label = marker.label or marker.name
    if not marker.finished or label is None:
        return CreateWorkflowResult(exit_code, WorkflowOutcome.INCOMPLETE, marker.name, draft)
    slug = Slug.of(label).value if marker.label else label
    try:
        validate_workflow_name(slug)
    except WorkflowNameError:  # the label yielded nothing usable — keep the draft
        return CreateWorkflowResult(exit_code, WorkflowOutcome.INCOMPLETE, slug or label, draft)
    if workflows.find(slug) is not None:
        return CreateWorkflowResult(exit_code, WorkflowOutcome.COLLISION, slug, draft)
    deployed = workflows.deploy_draft(draft, slug, label, marker.description, clock().isoformat())
    return CreateWorkflowResult(exit_code, WorkflowOutcome.DEPLOYED, slug, deployed)
