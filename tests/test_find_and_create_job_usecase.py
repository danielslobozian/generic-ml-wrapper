# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Finding a job and creating one, against the in-memory reference store."""

import pytest
from _conformance import InMemorySessionStore

from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.no_such_job_error import NoSuchJobError
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.inbound.create_job_command import CreateJobCommand
from generic_ml_wrapper.application.port.inbound.find_job_query import FindJobQuery
from generic_ml_wrapper.application.usecase.create_job import CreateJobService
from generic_ml_wrapper.application.usecase.find_job import FindJobService


def test_finding_a_job_returns_its_sessions_oldest_first() -> None:
    store = InMemorySessionStore()
    store.record(Session("alpha_001", "alpha", "claude", None))
    store.record(Session("alpha_002", "alpha", "cursor", None))

    job = FindJobService(store).execute(FindJobQuery(job="alpha"))

    assert [session.session_id for session in job.sessions] == ["alpha_001", "alpha_002"]
    assert job.latest_session().session_id == "alpha_002"


def test_finding_an_unknown_job_refuses() -> None:
    with pytest.raises(NoSuchJobError) as raised:
        FindJobService(InMemorySessionStore()).execute(FindJobQuery(job="nope"))
    assert raised.value.catalogue_key == "error.job.not_found"


def test_a_created_job_is_found_and_has_no_sessions() -> None:
    store = InMemorySessionStore()
    CreateJobService(store).execute(CreateJobCommand(job="alpha"))

    job = FindJobService(store).execute(FindJobQuery(job="alpha"))

    assert job.sessions == ()


def test_creating_a_job_that_exists_returns_it_with_its_sessions() -> None:
    # The start path creates before starting; a second create must not disturb what is there.
    store = InMemorySessionStore()
    store.record(Session("alpha_001", "alpha", "claude", None))

    job = CreateJobService(store).execute(CreateJobCommand(job="alpha"))

    assert [session.session_id for session in job.sessions] == ["alpha_001"]


def test_creating_a_job_with_an_unusable_name_refuses() -> None:
    with pytest.raises(IdentifierError):
        CreateJobService(InMemorySessionStore()).execute(CreateJobCommand(job="../escape"))
