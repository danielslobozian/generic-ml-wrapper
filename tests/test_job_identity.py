# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A job's name is its identity, and it is the only thing that identifies it.

The store holds no opinion about what a job is for. Reusing a name is not a collision but
the whole point: a job accumulates sessions and spend across everything it is used for,
which is how "what did this ticket cost me" has an answer. That holds however the sessions
arose -- a run, an authoring interview, an edit -- because none of them are a different
kind of thing.

Before this, a ``kind`` column split the same table in two and a name held by the other
kind was refused outright. The column is gone; these tests pin the behaviour that replaced
it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStoreAdapter
from generic_ml_wrapper.application.domain.model.authoring_job import AuthoringJob
from generic_ml_wrapper.application.domain.model.session import Session

if TYPE_CHECKING:
    from pathlib import Path


def _session(job: str, number: int, cwd: str = "/work") -> Session:
    return Session(
        session_id=f"{job}_{number:03d}",
        job=job,
        client="claude",
        uuid=None,
        cwd=cwd,
        resumable=True,
    )


def _store(tmp_path: Path) -> SqliteSessionStoreAdapter:
    return SqliteSessionStoreAdapter(Ledger(tmp_path / "ledger.db"))


def test_reusing_a_name_is_how_a_job_accumulates(tmp_path: Path) -> None:
    # Not a collision — the point. The same job run twice, with different workflows or
    # none, is one job, and its spend adds up under one name.
    store = _store(tmp_path)
    store.record(_session("PROJ-482", 1))
    store.record(_session("PROJ-482", 2))

    assert store.jobs() == ["PROJ-482"]
    assert store.ids_for_job("PROJ-482") == ["PROJ-482_001", "PROJ-482_002"]


def test_a_name_is_one_job_whatever_produced_its_sessions(tmp_path: Path) -> None:
    # The old model refused this outright, on the grounds that an authoring session and a
    # work session under one name were two jobs fighting over it. They are one job.
    store = _store(tmp_path)
    store.record(_session(AuthoringJob.NAME, 1))
    store.record(_session(AuthoringJob.NAME, 2, cwd="/elsewhere"))

    assert store.jobs() == [AuthoringJob.NAME]
    assert store.ids_for_job(AuthoringJob.NAME) == [
        f"{AuthoringJob.NAME}_001",
        f"{AuthoringJob.NAME}_002",
    ]


def test_jobs_with_different_names_stay_apart(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record(_session("PROJ-482", 1))
    store.record(_session(AuthoringJob.NAME, 1))

    # SQLite orders TEXT by byte value, so the uppercase name sorts before the lowercase one.
    assert store.jobs() == ["PROJ-482", AuthoringJob.NAME]
    assert store.ids_for_job("PROJ-482") == ["PROJ-482_001"]
    assert store.ids_for_job(AuthoringJob.NAME) == [f"{AuthoringJob.NAME}_001"]


def test_sessions_are_never_borrowed_from_another_job(tmp_path: Path) -> None:
    # The defect that started all of this: a lookup that ignored which job it was asked
    # about and handed back another one's history.
    store = _store(tmp_path)
    store.record(_session("PROJ-482", 1))

    assert store.sessions_for_job("PROJ-999") == []
    assert store.latest_for_job("PROJ-999") is None
