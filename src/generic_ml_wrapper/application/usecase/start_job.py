# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The StartJob use case: resolve a session, record it, run the client."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.session_naming import next_session_id
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJob,
    StartJobCommand,
    UnknownWorkflowError,
)
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerProvider
from generic_ml_wrapper.application.port.outbound.credentials_store import CredentialsStorePort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort


class StartJobUseCase(StartJob):
    """Resolve a session (new or resumed), optionally attach a workflow, run it."""

    def __init__(
        self,
        store: SessionStorePort,
        workflows: WorkflowSourcePort,
        callers: CliCallerProvider,
        uuid_factory: Callable[[], str],
        credentials: CredentialsStorePort,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            store: Where sessions are persisted and read.
            workflows: Seeds, checks, and compiles workflows.
            callers: Resolves the client caller for a run.
            uuid_factory: Mints a client-side session uuid for new sessions.
            credentials: Resolves a workflow's credentials to export at launch.
        """
        self._store = store
        self._workflows = workflows
        self._callers = callers
        self._uuid_factory = uuid_factory
        self._credentials = credentials

    def execute(self, command: StartJobCommand) -> int:
        """Resolve the session, optionally inject a workflow, run the client.

        Args:
            command: The request describing job, client, resume, and workflow.

        Returns:
            The client's exit code.

        Raises:
            UnknownWorkflowError: If a workflow was requested but does not exist.
            ResumeNotSupportedError: If resume was requested for a client whose
                caller cannot resume a session.
        """
        run, session = self._resolve(command)
        if not run.resume:
            if command.workflow is not None:
                run = self._attach_workflow(run, command.workflow)
            else:
                run = self._attach_baseline(run)
        caller = self._callers.for_run(run)
        if run.resume and not caller.can_resume():
            message = f"session resume not supported on {run.client}"
            raise ResumeNotSupportedError(message)
        # Persist only once every precondition (workflow, caller, resume) has passed, so
        # a rejected start never leaves a ghost session that burns an id and could be resumed.
        if session is not None:
            self._store.record(session)
        caller.start_metering()
        try:
            return caller.start_client()
        finally:
            caller.end_metering()

    def _attach_baseline(self, run: RunContext) -> RunContext:
        """Inject the always-on baseline context (profile/learned/persona) on a plain run.

        A plain ``gmlw start`` (no workflow) still composes the user's profile so every
        session — on any client — inherits who the user is and how they work. Left
        untouched when the baseline is empty, so nothing is written for a fresh install.
        """
        context = self._workflows.compile(CompileMode.DEFAULT)
        return run if not context else replace(run, context=context)

    def _attach_workflow(self, run: RunContext, workflow: str) -> RunContext:
        self._workflows.seed()
        if not self._workflows.exists(workflow):
            message = f"unknown workflow: {workflow!r}"
            raise UnknownWorkflowError(message)
        kickoff = (
            f"You are running the {workflow!r} workflow for {run.job}. Orient first — "
            "read your context, look at what already exists, report where things stand, "
            "then stop and wait. Do not start executing steps yet."
        )
        return replace(
            run,
            context=self._workflows.compile(CompileMode.WORKFLOW, workflow),
            kickoff=kickoff,
            env=tuple(self._credentials.resolve(workflow).items()),
        )

    def _resolve(self, command: StartJobCommand) -> tuple[RunContext, Session | None]:
        """Mint the run (and the session to record, or ``None`` on resume) -- no write yet."""
        if command.resume_latest:
            latest = self._store.latest_for_job(command.job)
            if latest is not None:
                resumed = RunContext(
                    job=latest.job,
                    session_id=latest.session_id,
                    client=latest.client,
                    uuid=latest.uuid,
                    resume=True,
                )
                return resumed, None
        session = Session(
            session_id=next_session_id(command.job, self._store.ids_for_job(command.job)),
            job=command.job,
            client=command.client,
            uuid=self._uuid_factory(),
        )
        run = RunContext(
            job=session.job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=False,
        )
        return run, session
