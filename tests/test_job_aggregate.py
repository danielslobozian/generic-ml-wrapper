# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Job aggregate: finding a session by id, and finding the latest."""

import pytest

from generic_ml_wrapper.application.domain.model.job import Job
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.no_such_session_error import NoSuchSessionError
from generic_ml_wrapper.application.domain.model.session import Session


def _session(session_id: str, client: str = "claude") -> Session:
    return Session(session_id=session_id, job="alpha", client=client, uuid=None)


def _job(*session_ids: str) -> Job:
    return Job(job_id=JobId("alpha"), sessions=tuple(_session(s) for s in session_ids))


def test_a_job_starts_with_no_sessions() -> None:
    assert Job(job_id=JobId("alpha")).sessions == ()


def test_session_for_returns_the_named_session() -> None:
    job = _job("alpha_001", "alpha_002")
    assert job.session_for("alpha_002").session_id == "alpha_002"


def test_session_for_refuses_an_unknown_id_rather_than_minting_one() -> None:
    # The defect this replaces: a mistyped id used to fall through to a brand-new session.
    job = _job("alpha_001")
    with pytest.raises(NoSuchSessionError) as raised:
        job.session_for("alpha_009")
    assert raised.value.catalogue_key == "error.session.not_found"
    assert raised.value.params == {"session": "alpha_009", "job": "alpha"}


def test_latest_session_is_the_last_recorded_not_the_highest_named() -> None:
    # Order is the store's, oldest first; nothing re-derives it from the name.
    job = _job("alpha_009", "alpha_002")
    assert job.latest_session().session_id == "alpha_002"


def test_latest_session_refuses_a_job_that_has_never_run() -> None:
    with pytest.raises(NoSuchSessionError) as raised:
        Job(job_id=JobId("alpha")).latest_session()
    assert raised.value.catalogue_key == "error.session.none_yet"
    assert raised.value.params == {"job": "alpha"}


def test_the_aggregate_is_immutable() -> None:
    job = _job("alpha_001")
    with pytest.raises(AttributeError):
        job.job_id = JobId("beta")  # type: ignore[misc]
