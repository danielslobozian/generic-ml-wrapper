# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Behavioral conformance kits for the outbound storage ports (E26).

Each port gets a reusable contract -- a base class with ``make_store`` left abstract
and a set of ``test_*`` methods that assert the port's behaviour. A concrete test
subclass implements ``make_store`` for one backend and inherits the whole contract, so
the same kit runs against BOTH the shipped adapter (SQLite / filesystem) and an
in-memory reference fake. The fake therefore cannot drift from the real store
(Fowler's Contract Test), and any future backend proves itself by subclassing.

This module is pure test infrastructure -- it is not named ``test_*`` so pytest does
not collect it directly; the concrete subclasses in ``test_store_conformance.py`` are
what run. It also ships in-memory reference fakes any test can reuse.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.transcript import TranscriptCall, TranscriptPort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort

if TYPE_CHECKING:
    from pathlib import Path

# A transcript trio as read back from a store: (request, response, usage-dict).
Trio = tuple[bytes, bytes, dict[str, object]]


# --------------------------------------------------------------------------- #
# In-memory reference fakes                                                    #
# --------------------------------------------------------------------------- #


class InMemorySessionStore(SessionStorePort):
    """A dict-backed reference ``SessionStorePort`` -- append-only, per job."""

    def __init__(self) -> None:
        self._by_job: dict[str, list[Session]] = {}

    def jobs(self) -> list[str]:
        return sorted(self._by_job)

    def record(self, session: Session) -> None:
        self._by_job.setdefault(session.job, []).append(session)

    def sessions_for_job(self, job: str) -> list[Session]:
        return list(self._by_job.get(job, []))

    def ids_for_job(self, job: str) -> list[str]:
        return [session.session_id for session in self._by_job.get(job, [])]

    def latest_for_job(self, job: str) -> Session | None:
        recorded = self._by_job.get(job)
        return recorded[-1] if recorded else None


class InMemoryPerTurnStore(PerTurnMeteringPort):
    """A dict-backed reference ``PerTurnMeteringPort`` -- append-only, per job."""

    def __init__(self) -> None:
        self._by_job: dict[str, list[TurnUsage]] = {}

    def record(self, job: str, turn: TurnUsage) -> None:
        self._by_job.setdefault(job, []).append(turn)

    def turns_for_job(self, job: str) -> list[TurnUsage]:
        return list(self._by_job.get(job, []))


class InMemoryUsageStore(UsageStorePort):
    """A dict-backed reference ``UsageStorePort`` -- monotonic per session cost."""

    def __init__(self) -> None:
        self._by_job: dict[str, dict[str, float]] = {}

    def record_session_cost(self, job: str, session: str, cost_usd: float) -> None:
        costs = self._by_job.setdefault(job, {})
        costs[session] = max(costs.get(session, cost_usd), cost_usd)

    def session_costs(self, job: str) -> dict[str, float]:
        return dict(self._by_job.get(job, {}))


class InMemoryTranscriptStore(TranscriptPort):
    """A dict-backed reference ``TranscriptPort`` keyed by (job, session, seq)."""

    def __init__(self) -> None:
        self._calls: dict[tuple[str, str, int], TranscriptCall] = {}

    def record(self, call: TranscriptCall) -> None:
        self._calls[(call.job, call.session, call.call_seq)] = call

    def read_trio(self, job: str, session: str, seq: int) -> Trio:
        call = self._calls[(job, session, seq)]
        return call.request, call.response, _usage_to_dict(call.usage)


def _usage_to_dict(usage: TurnUsage | None) -> dict[str, object]:
    """The transcript usage mapping any backend persists (empty when unmetered)."""
    if usage is None:
        return {}
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation_tokens": usage.cache_creation_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cost_usd": usage.cost_usd,
        "model": usage.model,
        "timestamp": usage.timestamp,
        "duration_s": usage.duration_s,
        "turn_id": usage.turn_id,
    }


# --------------------------------------------------------------------------- #
# Conformance kits                                                            #
# --------------------------------------------------------------------------- #


class SessionStoreConformance:
    """The behavioral contract for a ``SessionStorePort``."""

    def make_store(self, tmp_path: Path) -> SessionStorePort:
        raise NotImplementedError

    def test_unknown_job_is_empty(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        assert store.sessions_for_job("JOB-9") == []
        assert store.ids_for_job("JOB-9") == []
        assert store.latest_for_job("JOB-9") is None

    def test_jobs_starts_empty(self, tmp_path: Path) -> None:
        assert self.make_store(tmp_path).jobs() == []

    def test_record_then_read_round_trip_oldest_first(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        first = Session("JOB-1_001", "JOB-1", "claude", "uuid-1")
        second = Session("JOB-1_002", "JOB-1", "claude", None)
        store.record(first)
        store.record(second)
        assert store.sessions_for_job("JOB-1") == [first, second]
        assert store.ids_for_job("JOB-1") == ["JOB-1_001", "JOB-1_002"]

    def test_latest_is_the_most_recently_recorded(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        store.record(Session("JOB-1_001", "JOB-1", "claude", None))
        newest = Session("JOB-1_002", "JOB-1", "cursor", "u-2")
        store.record(newest)
        assert store.latest_for_job("JOB-1") == newest

    def test_sessions_are_isolated_per_job(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        store.record(Session("A_001", "A", "claude", None))
        assert store.ids_for_job("B") == []
        assert store.sessions_for_job("B") == []

    def test_jobs_lists_recorded_jobs_sorted(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        store.record(Session("B_001", "B", "claude", None))
        store.record(Session("A_001", "A", "claude", None))
        assert store.jobs() == ["A", "B"]


class PerTurnMeteringConformance:
    """The behavioral contract for a ``PerTurnMeteringPort``."""

    def make_store(self, tmp_path: Path) -> PerTurnMeteringPort:
        raise NotImplementedError

    def _turn(self, session: str, **kwargs: object) -> TurnUsage:
        defaults: dict[str, object] = {"cost_usd": None, "model": None}
        defaults.update(kwargs)
        return TurnUsage(session, 1, 2, **defaults)  # type: ignore[arg-type]

    def test_unknown_job_has_no_turns(self, tmp_path: Path) -> None:
        assert self.make_store(tmp_path).turns_for_job("JOB-9") == []

    def test_record_then_read_in_order(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        first = TurnUsage("JOB-1_001", 100, 20, 0.01, "Opus 4.8", timestamp=1.0, duration_s=0.5)
        second = TurnUsage("JOB-1_001", 50, 200, None, None)
        store.record("JOB-1", first)
        store.record("JOB-1", second)
        assert store.turns_for_job("JOB-1") == [first, second]

    def test_full_fidelity_round_trip(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        turn = TurnUsage(
            "JOB-1_001",
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.25,
            model="Opus 4.8",
            cache_creation_tokens=3,
            cache_read_tokens=4,
            timestamp=1234.5,
            duration_s=6.0,
            turn_id="t-1",
        )
        store.record("JOB-1", turn)
        assert store.turns_for_job("JOB-1") == [turn]

    def test_turns_are_isolated_per_job(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        store.record("JOB-1", self._turn("JOB-1_001"))
        store.record("JOB-2", self._turn("JOB-2_001"))
        assert store.turns_for_job("JOB-1") == [self._turn("JOB-1_001")]


class UsageStoreConformance:
    """The behavioral contract for a ``UsageStorePort``."""

    def make_store(self, tmp_path: Path) -> UsageStorePort:
        raise NotImplementedError

    def test_unknown_job_has_no_costs(self, tmp_path: Path) -> None:
        assert self.make_store(tmp_path).session_costs("JOB-9") == {}

    def test_record_then_read(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        store.record_session_cost("JOB-1", "JOB-1_001", 0.10)
        store.record_session_cost("JOB-1", "JOB-1_002", 0.25)
        assert store.session_costs("JOB-1") == {"JOB-1_001": 0.10, "JOB-1_002": 0.25}

    def test_cost_is_monotonic_highest_wins(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        store.record_session_cost("JOB-1", "JOB-1_001", 0.50)
        store.record_session_cost("JOB-1", "JOB-1_001", 0.20)  # lower: ignored
        store.record_session_cost("JOB-1", "JOB-1_001", 0.90)  # higher: wins
        assert store.session_costs("JOB-1") == {"JOB-1_001": 0.90}

    def test_costs_are_isolated_per_job(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        store.record_session_cost("JOB-1", "JOB-1_001", 0.10)
        store.record_session_cost("JOB-2", "JOB-2_001", 0.20)
        assert store.session_costs("JOB-1") == {"JOB-1_001": 0.10}


class TranscriptStoreConformance:
    """The behavioral contract for a ``TranscriptPort``.

    ``TranscriptPort`` is write-only, so a backend also supplies ``read_trio`` -- how
    it reads a recorded call back (from disk, from memory) -- and the kit asserts the
    write/read round trip against it.
    """

    def make_store(self, tmp_path: Path) -> TranscriptPort:
        raise NotImplementedError

    def read_trio(
        self, store: TranscriptPort, tmp_path: Path, job: str, session: str, seq: int
    ) -> Trio:
        raise NotImplementedError

    def test_records_and_reads_the_trio(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        usage = TurnUsage("JOB-1_001", 10, 20, 0.01, "Opus 4.8", timestamp=1.0, turn_id="t1")
        store.record(
            TranscriptCall("JOB-1", "JOB-1_001", 1, b'{"prompt":"hi"}', b"data: chunk\n\n", usage)
        )
        request, response, recorded = self.read_trio(store, tmp_path, "JOB-1", "JOB-1_001", 1)
        assert request == b'{"prompt":"hi"}'
        assert response == b"data: chunk\n\n"
        assert recorded["input_tokens"] == 10
        assert recorded["cost_usd"] == 0.01
        assert recorded["model"] == "Opus 4.8"
        assert recorded["turn_id"] == "t1"

    def test_no_usage_reads_as_empty(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        store.record(TranscriptCall("JOB-1", "JOB-1_001", 2, b"req", b"resp", None))
        request, response, recorded = self.read_trio(store, tmp_path, "JOB-1", "JOB-1_001", 2)
        assert request == b"req"
        assert response == b"resp"
        assert recorded == {}

    def test_calls_are_isolated_by_sequence(self, tmp_path: Path) -> None:
        store = self.make_store(tmp_path)
        store.record(TranscriptCall("JOB-1", "JOB-1_001", 1, b"one", b"r1", None))
        store.record(TranscriptCall("JOB-1", "JOB-1_001", 2, b"two", b"r2", None))
        assert self.read_trio(store, tmp_path, "JOB-1", "JOB-1_001", 1)[0] == b"one"
        assert self.read_trio(store, tmp_path, "JOB-1", "JOB-1_001", 2)[0] == b"two"


def read_transcript_files(tmp_path: Path, job: str, session: str, seq: int) -> Trio:
    """Read a filesystem-store trio back off disk (the FS ``read_trio`` helper)."""
    directory = tmp_path / job / session
    stem = f"call_{seq:03d}"
    request = (directory / f"{stem}.in.json").read_bytes()
    response = (directory / f"{stem}.out.sse").read_bytes()
    usage: dict[str, object] = json.loads(
        (directory / f"{stem}.usage.json").read_text(encoding="utf-8")
    )
    return request, response, usage
