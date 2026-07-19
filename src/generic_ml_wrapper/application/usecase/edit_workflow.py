# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The EditWorkflow use case: open an existing workflow in an authoring session."""

from __future__ import annotations

from collections.abc import Callable

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.identifiers import IdentifierError, WorkflowName
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.domain.service.session_naming import next_session_id
from generic_ml_wrapper.application.port.inbound.edit_workflow import (
    EditWorkflow,
    EditWorkflowCommand,
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.new_workflow import WorkflowNameError
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerProvider
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.launch import run_with_hooks

# The create-workflow meta drives the authoring session (for editing as for creating); its
# name and the shared partial are reserved and cannot themselves be edited.
_META = "create-workflow"
_RESERVED = frozenset({_META, "_common"})


class EditWorkflowUseCase(EditWorkflow):
    """Open an existing workflow's folder and run the authoring session against it."""

    def __init__(
        self,
        workflows: WorkflowSourcePort,
        store: SessionStorePort,
        callers: CliCallerProvider,
        uuid_factory: Callable[[], str],
        hooks: HookRunner,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            workflows: Seeds, checks, and locates workflows (never creates here).
            store: Records the authoring session.
            callers: Resolves the client caller for the run.
            uuid_factory: Mints a client-side session uuid.
            hooks: The lifecycle hooks bracketing the authoring client run.
        """
        self._workflows = workflows
        self._store = store
        self._callers = callers
        self._uuid_factory = uuid_factory
        self._hooks = hooks

    def execute(self, command: EditWorkflowCommand) -> int:
        """Run the authoring session against an existing workflow.

        Args:
            command: The request describing the workflow name and client.

        Returns:
            The client's exit code.

        Raises:
            WorkflowNameError: If the name is invalid or reserved.
            WorkflowNotFoundError: If no workflow with that name exists.
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
        if not self._workflows.exists(name):
            message = f"unknown workflow: {name!r}"
            raise WorkflowNotFoundError(message)

        folder = self._workflows.folder(name)  # the existing folder — never (re)created
        # The authoring store is rooted apart from real work jobs (composition injects the
        # authoring root), so the job is just the workflow name.
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
            context=self._workflows.compile(CompileMode.AUTHORING, _META),
            kickoff=(
                f"You are editing the existing workflow {name!r}. Your working directory "
                f"is its folder ({folder}); its current workflow.md is there. Read it "
                "first, then ask me what I want to change before editing. Do not rewrite "
                "it from scratch — amend it."
            ),
        )
        caller = self._callers.for_run(run)
        return run_with_hooks(caller, run, self._hooks)
