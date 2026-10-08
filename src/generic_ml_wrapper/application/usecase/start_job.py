# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The StartJob use case: resolve a session, record it, run the client."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from generic_ml_wrapper.application.domain.model.attachment import (
    Attachment,
    AttachmentError,
    AttachmentVersion,
    find,
)
from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.identifiers import TagName
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.attachment_context import (
    attachment_kickoff,
    attachment_section,
)
from generic_ml_wrapper.application.domain.service.greeting import greeting_context
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.domain.service.session_naming import next_session_id
from generic_ml_wrapper.application.port.inbound.start_job import (
    ResumeNotSupportedError,
    StartJob,
    StartJobCommand,
    StartJobResult,
)
from generic_ml_wrapper.application.port.outbound.attachment_store import AttachmentStorePort
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerProvider
from generic_ml_wrapper.application.port.outbound.context_compiler import ContextCompilerPort
from generic_ml_wrapper.application.port.outbound.credentials_store import CredentialsStorePort
from generic_ml_wrapper.application.port.outbound.job_tag_store import JobTagStorePort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.usecase.launch import run_with_hooks
from generic_ml_wrapper.common.client_args import split as split_client_args


class StartJobUseCase(StartJob):
    """Resolve a session (new or resumed), optionally attach an attachment, run it."""

    def __init__(  # noqa: PLR0913, PLR0917  (a use case binding its full set of outbound ports)
        self,
        store: SessionStorePort,
        contexts: ContextCompilerPort,
        callers: CliCallerProvider,
        uuid_factory: Callable[[], str],
        cwd_factory: Callable[[], str],
        credentials: CredentialsStorePort,
        hooks: HookRunner,
        greeting: Callable[[], str | None],
        capability_card: Callable[[], str | None],
        tags: JobTagStorePort,
        client_args: Callable[[str], str] = lambda _client: "",
        attachments: AttachmentStorePort | None = None,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            store: Where sessions are persisted and read.
            contexts: Compiles a new session's operating context.
            callers: Resolves the client caller for a run.
            uuid_factory: Mints a client-side session uuid for new sessions.
            cwd_factory: Returns the folder a new session is launched in (persisted so a
                resume can relaunch there -- Claude resume is scoped to it).
            credentials: Resolves an attachment's credentials to export at launch.
            hooks: The lifecycle hooks bracketing the client run.
            greeting: Renders the host greeting, or ``None`` when the companion is off —
                injected into a new session's context so the client greets in-band.
            capability_card: Renders the ambient "how do I …" card, or ``None`` when the
                (off-by-default) ambient card is disabled — appended to a new session's
                context so the client can answer gmlw questions mid-session.
            tags: Where a start's ``--tag`` values are put on the job.
            client_args: Returns the configured passthrough launch arguments for a client.
                Consulted with the *run's* client, which on a resume comes from the stored
                session rather than the command — so a resumed codex session never receives
                arguments configured for claude. Defaults to none configured.
            attachments: The attachment store a session's attachment is read from, or
                ``None`` when attachments are not available.
        """
        self._store = store
        self._contexts = contexts
        self._callers = callers
        self._uuid_factory = uuid_factory
        self._cwd_factory = cwd_factory
        self._credentials = credentials
        self._hooks = hooks
        self._greeting = greeting
        self._capability_card = capability_card
        self._client_args = client_args
        self._tags = tags
        self._attachments = attachments

    def execute(self, command: StartJobCommand) -> StartJobResult:
        """Resolve the session, optionally attach an attachment, run the client.

        Args:
            command: The request describing job, client, resume, and attachment.

        Returns:
            The run's outcome: exit code, job, and the session that ran.

        Raises:
            AttachmentError: If the attachment, or that version, is not stored, or has
                changed since its import.
            AttachmentVersionError: If the requested version is not ``MAJOR.MINOR.PATCH``.
            ResumeNotSupportedError: If resume was requested for a client whose
                caller cannot resume a session.
            IdentifierError: If a requested tag is not a valid tag name.
        """
        # Checked before anything happens, so a typo in a tag never costs a session.
        tags = sorted({TagName(tag) for tag in command.tags})
        run, session = self._resolve(command)
        run = self._with_client_args(run, command.client_args)
        attached: Attachment | None = None
        if not run.resume:
            if command.attachment is not None:
                run, attached = self._attach(run, command.attachment, command.attachment_version)
            else:
                run = self._attach_baseline(run)
            if command.note:
                kickoff = (
                    command.note if run.kickoff is None else f"{run.kickoff}\n\n{command.note}"
                )
                run = replace(run, kickoff=kickoff)
            run = self._with_greeting(run)  # in-band host greeting for a fresh session
            run = self._with_capability_card(run)  # optional ambient "how do I …" card
        caller = self._callers.for_run(run)
        if run.resume and not caller.can_resume():
            # Two different refusals wear this one error. Some clients cannot resume at
            # all; others (codex) can, but only a session whose client-side id we managed
            # to learn — one that died before its first turn, or was deleted client-side,
            # has none. Say which, because the fixes are not the same.
            if run.uuid is None:
                raise ResumeNotSupportedError("error.resume.unsupported", client=run.client)
            raise ResumeNotSupportedError(
                "error.resume.lost", session_id=run.session_id, client=run.client
            )
        # Persist only once every precondition (attachment, caller, resume) has passed, so
        # a rejected start never leaves a ghost session that burns an id and could be resumed.
        if session is not None:
            # Whether a session can be reopened is the *caller's* answer, not a property
            # of its name: a caller supplied through `[callers]` or a plugin is absent
            # from the built-in catalog, and deciding from that list alone recorded every
            # such session as unresumable however capable its adapter was.
            #
            # The attachment is recorded with it: it belongs to this session, not the job, so
            # one job can carry a feature session, then a review session, then a plain one.
            self._store.record(
                replace(
                    session,
                    resumable=caller.can_resume(),
                    attachment=None if attached is None else attached.name,
                    attachment_version=None if attached is None else str(attached.version),
                    attachment_hash=None if attached is None else attached.content_hash,
                )
            )
        # After the record, so the job exists to be tagged (a resumed one already does).
        if tags:
            self._tags.add(run.job, tags)
        exit_code = run_with_hooks(caller, run, self._hooks)
        return StartJobResult(exit_code=exit_code, job=run.job, session_id=run.session_id)

    def _with_client_args(self, run: RunContext, override: str | None) -> RunContext:
        """Attach the passthrough launch arguments for this run's client.

        An explicit ``--client-args`` replaces the configured value outright rather than
        adding to it: the flag names the arguments for *this* launch, and a user who wants
        the configured ones as well can type them.

        The lookup is keyed on the run's client, which on a resume is the session's own —
        so resuming a codex session never picks up arguments configured for claude.
        """
        text = override if override is not None else self._client_args(run.client)
        tokens = split_client_args(text)
        return run if not tokens else replace(run, client_args=tokens)

    def _with_greeting(self, run: RunContext) -> RunContext:
        """Prepend the host greeting to a new session's context, when the companion is on.

        The greeting is composed locally (free, no tokens) and rendered by the client
        in-band. Prepended so it opens the session ahead of the profile/attachment context;
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
        profile/attachment context (reference material, not an opener) so the client can
        answer "how do I …" gmlw questions mid-session. Counted against the context budget
        like any other section.
        """
        card = self._capability_card()
        if not card:
            return run
        context = card if run.context is None else f"{run.context}\n\n{card}"
        return replace(run, context=context)

    def _attach_baseline(self, run: RunContext) -> RunContext:
        """Inject the always-on baseline context (snapshot/profile/learned/persona).

        A plain ``gmlw start`` (no attachment) still composes the user's profile so every
        session — on any client — inherits who the user is and how they work. The compiled
        context now always carries at least the session snapshot, so on a fresh install the
        client still learns which environment, role and job it is in even before the user
        has written a word of profile.
        """
        context = self._contexts.compile(CompileMode.DEFAULT, job=run.job)
        return run if not context else replace(run, context=context)

    def _attach(
        self, run: RunContext, name: str, version: str | None
    ) -> tuple[RunContext, Attachment]:
        """Deliver an attachment into a new session, checked against its hash first.

        Its section follows gmlw's own context, the session opens on a message naming
        it, its credentials are exported, and the store is opened to the client, since
        the attachment's other files are read from there.
        """
        store = self._attachments
        if store is None:
            raise AttachmentError("error.attachment.not_found", name=name)
        wanted = None if version is None else AttachmentVersion.parse(version)
        attachment = find(store.all(), name, wanted)
        if not store.is_intact(attachment):
            raise AttachmentError(
                "error.attachment.invalid", name=name, version=str(attachment.version)
            )
        section = attachment_section(
            attachment, str(store.folder(attachment)), store.read_main(attachment)
        )
        context = self._contexts.compile(CompileMode.ATTACHMENT, job=run.job, attachment=section)
        run = replace(
            run,
            context=context,
            kickoff=attachment_kickoff(attachment, run.job),
            env=tuple(self._credentials.resolve(name).items()),
            extra_dirs=(str(store.root()),),
        )
        return run, attachment

    def _resume_target(self, command: StartJobCommand) -> Session | None:
        """The session to resume: the named one, else the latest, else ``None`` (new session).

        A specific ``resume_session`` wins over ``resume_latest``; an unknown id falls through
        to minting a new session rather than failing.
        """
        if command.resume_session is not None:
            return next(
                (
                    s
                    for s in self._store.sessions_for_job(command.job)
                    if s.session_id == command.resume_session
                ),
                None,
            )
        if command.resume_latest:
            return self._store.latest_for_job(command.job)
        return None

    def _resumed_run(self, session: Session) -> RunContext:
        """Build the run that reopens a session -- in the folder it was launched in.

        ``cwd`` is the session's stored folder (``None`` for pre-folder sessions, which
        resume in the current directory as before). Claude's resume is scoped to that folder.
        A session that ran with an attachment gets the store opened again: its context
        still sends it to the attachment's files.
        """
        store = self._attachments
        reopened = session.attachment is not None and store is not None
        return RunContext(
            job=session.job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=True,
            cwd=session.cwd,
            extra_dirs=(str(store.root()),) if reopened and store is not None else (),
        )

    def _resolve(self, command: StartJobCommand) -> tuple[RunContext, Session | None]:
        """Mint the run (and the session to record, or ``None`` on resume) -- no write yet."""
        target = self._resume_target(command)
        if target is not None:
            return self._resumed_run(target), None
        session = Session(
            session_id=next_session_id(command.job, self._store.ids_for_job(command.job)),
            job=command.job,
            client=command.client,
            uuid=self._uuid_factory(),
            cwd=self._cwd_factory(),  # the folder this session runs in (resume relaunches here)
            # `resumable` is settled at record time, from the caller — see `execute`.
        )
        run = RunContext(
            job=session.job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=False,
        )
        return run, session
