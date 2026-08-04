# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Run the storage-port conformance kits against every backend (E26).

Each port's contract (defined in ``_conformance``) runs twice: once against the
shipped adapter and once against the in-memory reference fake. Passing both proves
the adapter meets the port contract AND that the fake cannot drift from it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from _conformance import (
    InMemoryPerTurnStore,
    InMemorySessionStore,
    InMemoryTranscriptStore,
    InMemoryUsageStore,
    PerTurnMeteringConformance,
    SessionStoreConformance,
    TranscriptStoreConformance,
    Trio,
    UsageStoreConformance,
    read_transcript_files,
)

from generic_ml_wrapper.adapter.outbound.store.filesystem_transcript_store import (
    FilesystemTranscriptStore,
)
from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import SqlitePerTurnStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStore
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort

if TYPE_CHECKING:
    from pathlib import Path


# -- SessionStorePort ------------------------------------------------------- #


class TestSqliteSessionStore(SessionStoreConformance):
    def make_store(self, tmp_path: Path) -> SessionStorePort:
        return SqliteSessionStore(Ledger(tmp_path / "ledger.db"))


class TestInMemorySessionStore(SessionStoreConformance):
    def make_store(self, tmp_path: Path) -> SessionStorePort:
        return InMemorySessionStore()


def _record_sessions(tmp_path: Path, job: str, *sessions: str) -> None:
    """Persist the sessions a turn or a cost will be recorded against.

    The ledger's tables reference each other, so a turn or a cost cannot be written for a
    session that was never recorded. In a real run the session is persisted before the
    client that produces either is launched; here it has to be said out loud.
    """
    store = SqliteSessionStore(Ledger(tmp_path / "ledger.db"))
    for session in sessions:
        store.record(Session(session, job, "claude", None))


# -- PerTurnMeteringPort ---------------------------------------------------- #


class TestSqlitePerTurnStore(PerTurnMeteringConformance):
    def make_store(self, tmp_path: Path) -> PerTurnMeteringPort:
        return SqlitePerTurnStore(Ledger(tmp_path / "ledger.db"))

    def seed_sessions(self, tmp_path: Path, job: str, *sessions: str) -> None:
        _record_sessions(tmp_path, job, *sessions)


class TestInMemoryPerTurnStore(PerTurnMeteringConformance):
    def make_store(self, tmp_path: Path) -> PerTurnMeteringPort:
        return InMemoryPerTurnStore()


# -- UsageStorePort --------------------------------------------------------- #


class TestSqliteUsageStore(UsageStoreConformance):
    def make_store(self, tmp_path: Path) -> UsageStorePort:
        return SqliteUsageStore(Ledger(tmp_path / "ledger.db"))

    def seed_sessions(self, tmp_path: Path, job: str, *sessions: str) -> None:
        _record_sessions(tmp_path, job, *sessions)


class TestInMemoryUsageStore(UsageStoreConformance):
    def make_store(self, tmp_path: Path) -> UsageStorePort:
        return InMemoryUsageStore()


# -- TranscriptPort --------------------------------------------------------- #


class TestFilesystemTranscriptStore(TranscriptStoreConformance):
    def make_store(self, tmp_path: Path) -> TranscriptPort:
        return FilesystemTranscriptStore(tmp_path)

    def read_trio(
        self, store: TranscriptPort, tmp_path: Path, job: str, session: str, seq: int
    ) -> Trio:
        return read_transcript_files(tmp_path, job, session, seq)


class TestInMemoryTranscriptStore(TranscriptStoreConformance):
    def make_store(self, tmp_path: Path) -> TranscriptPort:
        return InMemoryTranscriptStore()

    def read_trio(
        self, store: TranscriptPort, tmp_path: Path, job: str, session: str, seq: int
    ) -> Trio:
        assert isinstance(store, InMemoryTranscriptStore)
        return store.read_trio(job, session, seq)
