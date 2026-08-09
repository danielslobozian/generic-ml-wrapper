# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Reopening a recorded session: the session decides the client, the folder and the id."""

import os

import pytest
from test_start_job_usecase import FakeProvider, FakeSessionLock, _NoInterrupts

from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnosticsAdapter
from generic_ml_wrapper.application.domain.model.resume_not_supported_error import (
    ResumeNotSupportedError,
)
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.inbound.resume_session_command import ResumeSessionCommand
from generic_ml_wrapper.application.usecase.client_arguments_binder import ClientArgumentsBinder
from generic_ml_wrapper.application.usecase.hook_runner import HookRunner
from generic_ml_wrapper.application.usecase.launch import LaunchSequence
from generic_ml_wrapper.application.usecase.resume_session_for_job import (
    ResumeSessionForJobService,
)


def _use_case(
    provider: FakeProvider, client_args: dict[str, str] | None = None
) -> ResumeSessionForJobService:
    return ResumeSessionForJobService(
        callers=provider,
        launch=LaunchSequence(
            HookRunner((), NullDiagnosticsAdapter()),
            NullDiagnosticsAdapter(),
            FakeSessionLock(),
            _NoInterrupts(),
        ),
        client_arguments=ClientArgumentsBinder(
            configured=lambda client: (client_args or {}).get(client, ""),
            posix=os.name != "nt",
            diagnostics=NullDiagnosticsAdapter(),
        ),
    )


def test_the_session_supplies_the_client_the_folder_and_the_id() -> None:
    session = Session("JOB-1_002", "JOB-1", "cursor", "uuid-2", cwd="/work/elsewhere")
    provider = FakeProvider()

    _use_case(provider).execute(ResumeSessionCommand(session=session))

    assert provider.run is not None
    assert provider.run.resume is True
    assert provider.run.session_id == "JOB-1_002"
    assert provider.run.client == "cursor"  # not whatever the config defaults to
    assert provider.run.uuid == "uuid-2"
    assert provider.run.cwd == "/work/elsewhere"  # a resume relaunches where it ran


def test_a_pre_folder_session_resumes_in_the_current_directory() -> None:
    session = Session("JOB-1_001", "JOB-1", "claude", "uuid-1", cwd=None)
    provider = FakeProvider()

    _use_case(provider).execute(ResumeSessionCommand(session=session))

    assert provider.run is not None
    assert provider.run.cwd is None


def test_no_context_is_recomposed_on_a_resume() -> None:
    # The client still holds the conversation; re-injecting would double it.
    provider = FakeProvider()

    _use_case(provider).execute(
        ResumeSessionCommand(session=Session("JOB-1_001", "JOB-1", "claude", "uuid-1"))
    )

    assert provider.run is not None
    assert provider.run.context is None
    assert provider.run.kickoff is None


def test_a_client_that_cannot_resume_at_all_is_refused() -> None:
    provider = FakeProvider(can_resume=False)

    with pytest.raises(ResumeNotSupportedError) as raised:
        _use_case(provider).execute(
            ResumeSessionCommand(session=Session("JOB-1_001", "JOB-1", "codex", None))
        )

    assert raised.value.catalogue_key == "error.workflow.resume_unsupported"


def test_a_session_whose_client_side_id_was_never_learned_is_refused_differently() -> None:
    # Same error type, different cause: the client can resume, this session cannot.
    provider = FakeProvider(can_resume=False)

    with pytest.raises(ResumeNotSupportedError) as raised:
        _use_case(provider).execute(
            ResumeSessionCommand(session=Session("JOB-1_003", "JOB-1", "codex", "uuid-3"))
        )

    assert raised.value.catalogue_key == "error.workflow.resume_lost"


def test_the_arguments_are_the_sessions_own_clients() -> None:
    session = Session("JOB-1_002", "JOB-1", "codex", "uuid-2")
    provider = FakeProvider()

    _use_case(provider, client_args={"claude": "--claude-only", "codex": "--codex-only"}).execute(
        ResumeSessionCommand(session=session)
    )

    assert provider.run is not None
    assert provider.run.client_args == ("--codex-only",)
