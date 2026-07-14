# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The NewWorkflow use case: author a workflow via the create-workflow interview."""

from __future__ import annotations

from collections.abc import Callable

from generic_ml_wrapper.application.domain.model.identifiers import IdentifierError, WorkflowName
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.session_naming import next_session_id
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflow,
    NewWorkflowCommand,
    WorkflowExistsError,
    WorkflowNameError,
)
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerProvider
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort

_META = "create-workflow"
_RESERVED = frozenset({_META, "_common"})


class NewWorkflowUseCase(NewWorkflow):
    """Create a workflow folder and run the create-workflow authoring session."""

    def __init__(
        self,
        workflows: WorkflowSourcePort,
        store: SessionStorePort,
        callers: CliCallerProvider,
        uuid_factory: Callable[[], str],
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            workflows: Seeds, checks, creates, and compiles workflows.
            store: Records the authoring session.
            callers: Resolves the client caller for the run.
            uuid_factory: Mints a client-side session uuid.
        """
        self._workflows = workflows
        self._store = store
        self._callers = callers
        self._uuid_factory = uuid_factory

    def execute(self, command: NewWorkflowCommand) -> int:
        """Run the authoring session for a new workflow.

        Args:
            command: The request describing the workflow name and client.

        Returns:
            The client's exit code.

        Raises:
            WorkflowNameError: If the name is invalid or reserved.
            WorkflowExistsError: If a workflow with that name already exists.
        """
        name = command.name
        try:
            WorkflowName(name)
        except IdentifierError as error:
            raise WorkflowNameError(str(error)) from error
        if name in _RESERVED:
            message = f"reserved workflow name: {name!r}"
            raise WorkflowNameError(message)
        self._workflows.seed()
        if self._workflows.exists(name):
            message = f"workflow already exists: {name!r}"
            raise WorkflowExistsError(message)

        folder = self._workflows.create(name)
        # The authoring session's store is rooted apart from real work jobs (the
        # composition root injects the authoring root), so the job is just the
        # workflow name — no prefix, no folder-name collision with a real job.
        job = name
        session = Session(
            session_id=next_session_id(job, self._store.ids_for_job(job)),
            job=job,
            client=command.client,
            uuid=self._uuid_factory(),
        )
        self._store.record(session)

        run = RunContext(
            job=job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=False,
            cwd=folder,
            context=self._workflows.compile(_META),
            kickoff=(
                f"You are creating a new workflow named {name!r}. Your working "
                f"directory is its folder ({folder}); write the new workflow.md there. "
                "Follow the create-workflow steps: interview me, then draft and save "
                "the workflow. Start by asking what this workflow is for."
            ),
        )
        caller = self._callers.for_run(run)
        caller.start_metering()
        try:
            return caller.start_client()
        finally:
            caller.end_metering()
