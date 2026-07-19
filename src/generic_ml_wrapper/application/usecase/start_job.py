# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The StartJob use case: resolve a session, record it, run the client."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.greeting import greeting_context
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.domain.service.session_naming import next_session_id
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJob,
    StartJobCommand,
    StartJobResult,
    UnknownWorkflowError,
)
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerProvider
from generic_ml_wrapper.application.port.outbound.credentials_store import CredentialsStorePort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.launch import run_with_hooks


class StartJobUseCase(StartJob):
    """Resolve a session (new or resumed), optionally attach a workflow, run it."""

    def __init__(  # noqa: PLR0913  (a use case binding its full set of outbound ports)
        self,
        store: SessionStorePort,
        workflows: WorkflowSourcePort,
        callers: CliCallerProvider,
        uuid_factory: Callable[[], str],
        credentials: CredentialsStorePort,
        hooks: HookRunner,
        greeting: Callable[[], str | None],
        capability_card: Callable[[], str | None],
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            store: Where sessions are persisted and read.
            workflows: Seeds, checks, and compiles workflows.
            callers: Resolves the client caller for a run.
            uuid_factory: Mints a client-side session uuid for new sessions.
            credentials: Resolves a workflow's credentials to export at launch.
            hooks: The lifecycle hooks bracketing the client run.
            greeting: Renders the host greeting, or ``None`` when the companion is off —
                injected into a new session's context so the client greets in-band.
            capability_card: Renders the ambient "how do I …" card, or ``None`` when the
                (off-by-default) ambient card is disabled — appended to a new session's
                context so the client can answer gmlw questions mid-session.
        """
        self._store = store
        self._workflows = workflows
        self._callers = callers
        self._uuid_factory = uuid_factory
        self._credentials = credentials
        self._hooks = hooks
        self._greeting = greeting
        self._capability_card = capability_card

    def execute(self, command: StartJobCommand) -> StartJobResult:
        """Resolve the session, optionally inject a workflow, run the client.

        Args:
            command: The request describing job, client, resume, and workflow.

        Returns:
            The run's outcome: exit code, job, and the session that ran.

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
            run = self._with_greeting(run)  # in-band host greeting for a fresh session
            run = self._with_capability_card(run)  # optional ambient "how do I …" card
        caller = self._callers.for_run(run)
        if run.resume and not caller.can_resume():
            message = f"session resume not supported on {run.client}"
            raise ResumeNotSupportedError(message)
        # Persist only once every precondition (workflow, caller, resume) has passed, so
        # a rejected start never leaves a ghost session that burns an id and could be resumed.
        if session is not None:
            self._store.record(session)
        exit_code = run_with_hooks(caller, run, self._hooks)
        return StartJobResult(exit_code=exit_code, job=run.job, session_id=run.session_id)

    def _with_greeting(self, run: RunContext) -> RunContext:
        """Prepend the host greeting to a new session's context, when the companion is on.

        The greeting is composed locally (free, no tokens) and rendered by the client
        in-band. Prepended so it opens the session ahead of the profile/workflow context;
        a no-op when the companion is off (no persona) or the greeting is empty.
        """
        greeting = self._greeting()
        if not greeting:
            return run
        section = greeting_context(greeting)
        context = section if run.context is None else f"{section}\n\n{run.context}"
        return replace(run, context=context)

    def _with_capability_card(self, run: RunContext) -> RunContext:
        """Append the ambient capability card to a new session's context, when enabled.

        Off by default; when the ``[ambient]`` card is on, it is appended after the
        profile/workflow context (reference material, not an opener) so the client can
        answer "how do I …" gmlw questions mid-session. Counted against the context budget
        like any other section.
        """
        card = self._capability_card()
        if not card:
            return run
        context = card if run.context is None else f"{run.context}\n\n{card}"
        return replace(run, context=context)

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
