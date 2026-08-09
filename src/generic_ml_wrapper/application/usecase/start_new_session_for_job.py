# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The StartNewSessionForJobUseCase use case: mint a session, record it, run the client."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.no_such_job_error import NoSuchJobError
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.unknown_workflow_error import UnknownWorkflowError
from generic_ml_wrapper.application.domain.service.greeting_composer import GreetingComposer
from generic_ml_wrapper.application.domain.service.session_naming import SessionNaming
from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult
from generic_ml_wrapper.application.port.inbound.start_new_session_command import (
    StartNewSessionCommand,
)
from generic_ml_wrapper.application.port.inbound.start_new_session_for_job import (
    StartNewSessionForJobUseCase,
)
from generic_ml_wrapper.application.port.outbound.cli_caller_provider import CliCallerProviderPort
from generic_ml_wrapper.application.port.outbound.credentials_store import CredentialsStorePort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.client_arguments_binder import ClientArgumentsBinder
from generic_ml_wrapper.application.usecase.launch import LaunchSequence


class StartNewSessionForJobService(StartNewSessionForJobUseCase):
    """Mint a session on an existing job, compose its context, and run the client."""

    def __init__(  # noqa: PLR0913, PLR0917  (a use case binding its full set of outbound ports)
        self,
        store: SessionStorePort,
        workflows: WorkflowSourcePort,
        callers: CliCallerProviderPort,
        uuid_factory: Callable[[], str],
        cwd_factory: Callable[[], str],
        credentials: CredentialsStorePort,
        launch: LaunchSequence,
        greeting: Callable[[], str | None],
        capability_card: Callable[[], str | None],
        client_arguments: ClientArgumentsBinder,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            store: Where the job is checked and the session recorded.
            workflows: Compiles the run's context and finds named workflows.
            callers: Resolves the client caller for the run.
            uuid_factory: Mints a client-side session uuid.
            cwd_factory: The folder this session runs in; a resume relaunches there.
            credentials: Resolves the environment a workflow run needs.
            launch: The bracketed launch sequence (hooks, metering, the client).
            greeting: Renders the host greeting, or ``None`` when the companion is off.
            capability_card: Renders the ambient "how do I ..." card, or ``None`` when
                the off-by-default card is disabled.
            client_arguments: Attaches the passthrough launch arguments.
        """
        self._store = store
        self._workflows = workflows
        self._callers = callers
        self._uuid_factory = uuid_factory
        self._cwd_factory = cwd_factory
        self._credentials = credentials
        self._launch = launch
        self._greeting = greeting
        self._capability_card = capability_card
        self._client_arguments = client_arguments

    def execute(self, command: StartNewSessionCommand) -> StartJobResult:
        """Mint a session, compose its context, record it, and run the client.

        Args:
            command: The job, the client, and what to run on it.

        Returns:
            The run's outcome: exit code, job, and the session that ran.

        Raises:
            NoSuchJobError: When the job does not exist.
            UnknownWorkflowError: When a workflow was named but is not installed.
        """
        if command.job not in self._store.jobs():
            raise NoSuchJobError("error.job.not_found", job=command.job)
        session = self._mint(command)
        run = self._client_arguments.bind(self._run_for(session), command.client_args)
        run = self._with_context(run, command.workflow)
        caller = self._callers.for_run(run)
        # Persist only once every precondition has passed, so a rejected start never
        # leaves a ghost session that burns an id and could be resumed. Whether a session
        # can be reopened is the *caller's* answer, not a property of its name: a caller
        # supplied through `[callers]` or a plugin is absent from the built-in catalog.
        self._store.record(replace(session, resumable=caller.can_resume()))
        exit_code = self._launch.run(caller, run)
        return StartJobResult(exit_code=exit_code, job=run.job, session_id=run.session_id)

    def _mint(self, command: StartNewSessionCommand) -> Session:
        """Build the session this run will record.

        Args:
            command: The request being served.

        Returns:
            An unrecorded session; ``resumable`` is settled at record time, from the caller.
        """
        return Session(
            session_id=SessionNaming().next_session_id(
                command.job, self._store.ids_for_job(command.job)
            ),
            job=command.job,
            client=command.client,
            uuid=self._uuid_factory(),
            cwd=self._cwd_factory(),
        )

    @staticmethod
    def _run_for(session: Session) -> RunContext:
        """Build the run that opens a freshly minted session.

        Args:
            session: The session about to run.

        Returns:
            A non-resuming run.
        """
        return RunContext(
            job=session.job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=False,
        )

    def _with_context(self, run: RunContext, workflow: str | None) -> RunContext:
        """Compose everything a new session opens with.

        Args:
            run: The run being prepared.
            workflow: The workflow to run, or ``None`` for the plain wrapper.

        Returns:
            The run carrying its context, kickoff and environment.
        """
        run = self._attach_workflow(run, workflow) if workflow else self._attach_baseline(run)
        return self._with_capability_card(self._with_greeting(run))

    def _with_greeting(self, run: RunContext) -> RunContext:
        """Prepend the host greeting, when the companion is on.

        Args:
            run: The run being prepared.

        Returns:
            The run with the greeting opening its context, ahead of the profile and
            workflow sections; unchanged when the companion is off or the greeting empty.
        """
        greeting = self._greeting()
        if not greeting:
            return run
        section = GreetingComposer().greeting_context(greeting)
        context = section if run.context is None else f"{section}\n\n{run.context}"
        return replace(run, context=context)

    def _with_capability_card(self, run: RunContext) -> RunContext:
        """Append the ambient capability card, when enabled.

        Args:
            run: The run being prepared.

        Returns:
            The run with the card appended after the profile and workflow context —
            reference material, not an opener. Counted against the context budget like
            any other section.
        """
        card = self._capability_card()
        if not card:
            return run
        context = card if run.context is None else f"{run.context}\n\n{card}"
        return replace(run, context=context)

    def _attach_baseline(self, run: RunContext) -> RunContext:
        """Inject the always-on baseline context (snapshot/profile/learned/persona).

        Args:
            run: The run being prepared.

        Returns:
            The run carrying the user's profile, so a session on any client inherits who
            the user is and how they work. The compiled context always carries at least
            the session snapshot, so even on a fresh install the client learns which
            environment, role and job it is in.
        """
        context = self._workflows.compile(CompileMode.DEFAULT, job=run.job)
        return run if not context else replace(run, context=context)

    def _attach_workflow(self, run: RunContext, workflow: str) -> RunContext:
        """Inject a named workflow's context, kickoff and environment.

        Args:
            run: The run being prepared.
            workflow: The workflow to run.

        Returns:
            The run carrying the workflow's compiled context.

        Raises:
            UnknownWorkflowError: When the workflow is not installed. Asked before
                anything is written, so a run named for a missing workflow leaves nothing
                behind on its way to being refused.
        """
        if self._workflows.find(workflow) is None:
            raise UnknownWorkflowError("error.workflow.unknown", name=workflow)
        self._workflows.seed()
        kickoff = (
            f"You are running the {workflow!r} workflow for {run.job}. Orient first — "
            "read your context, look at what already exists, report where things stand, "
            "then stop and wait. Do not start executing steps yet."
        )
        return replace(
            run,
            context=self._workflows.compile(CompileMode.WORKFLOW, workflow, job=run.job),
            kickoff=kickoff,
            env=tuple(self._credentials.resolve(workflow).items()),
        )
