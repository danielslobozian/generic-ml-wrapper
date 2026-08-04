# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A job's name is its identity: one name, one job, whatever kind of work it is.

The kind — work, or authoring a workflow — is information *about* a job, not part of who
it is. Two jobs may therefore never share a name. Reusing a name within a kind is not a
collision but the whole point: a job accumulates sessions and spend across everything it
is used for, which is how "what did this ticket cost me" has an answer.

Before this was enforced the two kinds shared one row. Recording a work session and an
authoring session under one name left the authoring job absent from its own listing while
both kinds' sessions showed through either one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.application.domain.model.job_name_taken_error import JobNameTakenError
from generic_ml_wrapper.application.domain.model.session import Session

if TYPE_CHECKING:
    from pathlib import Path

_AUTHORING_JOB = "create-workflow"  # the fixed job every authoring session is recorded under


def _session(job: str, number: int) -> Session:
    return Session(
        session_id=f"{job}_{number:03d}",
        job=job,
        client="claude",
        uuid=None,
        cwd="/work",
        resumable=True,
    )


def _stores(tmp_path: Path) -> tuple[SqliteSessionStore, SqliteSessionStore]:
    ledger = Ledger(tmp_path / "ledger.db")
    return SqliteSessionStore(ledger, "work"), SqliteSessionStore(ledger, "authoring")


def test_a_name_held_by_the_other_kind_is_refused(tmp_path: Path) -> None:
    work, authoring = _stores(tmp_path)
    work.record(_session(_AUTHORING_JOB, 1))

    with pytest.raises(JobNameTakenError) as caught:
        authoring.record(_session(_AUTHORING_JOB, 2))

    assert caught.value.job == _AUTHORING_JOB
    assert caught.value.existing_kind == "work"


def test_the_refusal_is_symmetric(tmp_path: Path) -> None:
    work, authoring = _stores(tmp_path)
    authoring.record(_session("shared", 1))
    with pytest.raises(JobNameTakenError):
        work.record(_session("shared", 2))


def test_a_refused_session_leaves_the_existing_job_untouched(tmp_path: Path) -> None:
    # The reason this matters: the old behaviour did not merely allow the clash, it hid
    # the loser. The authoring job vanished from its own listing and both kinds' sessions
    # showed through either one.
    work, authoring = _stores(tmp_path)
    work.record(_session(_AUTHORING_JOB, 1))
    with pytest.raises(JobNameTakenError):
        authoring.record(_session(_AUTHORING_JOB, 2))

    assert work.jobs() == [_AUTHORING_JOB]
    assert authoring.jobs() == []
    assert work.ids_for_job(_AUTHORING_JOB) == [f"{_AUTHORING_JOB}_001"]


def test_reusing_a_name_within_one_kind_is_how_a_job_accumulates(tmp_path: Path) -> None:
    # Not a collision — the point. The same job run twice, with different workflows or
    # none, is one job, and its spend adds up under one name.
    work, _ = _stores(tmp_path)
    work.record(_session("PROJ-482", 1))
    work.record(_session("PROJ-482", 2))

    assert work.jobs() == ["PROJ-482"]
    assert work.ids_for_job("PROJ-482") == ["PROJ-482_001", "PROJ-482_002"]


def test_each_kind_keeps_its_own_jobs_when_the_names_differ(tmp_path: Path) -> None:
    work, authoring = _stores(tmp_path)
    work.record(_session("PROJ-482", 1))
    authoring.record(_session(_AUTHORING_JOB, 1))

    assert work.jobs() == ["PROJ-482"]
    assert authoring.jobs() == [_AUTHORING_JOB]
    assert work.ids_for_job(_AUTHORING_JOB) == []
    assert authoring.ids_for_job("PROJ-482") == []
