# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for resolving a session, a job or a file to analyses."""

import pytest
from _conformance import InMemorySessionStore

from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.session_analysis import SessionFile, SessionRecord
from generic_ml_wrapper.application.port.inbound.analyze_session import (
    NothingToAnalyzeError,
    SessionFileUnavailableError,
)
from generic_ml_wrapper.application.port.outbound.session_files import SessionFilesPort
from generic_ml_wrapper.application.usecase.analyze_session import AnalyzeSessionUseCase


class FakeFiles(SessionFilesPort):
    """Files keyed by path; a session's file is ``/<client>/<uuid>``."""

    def __init__(self, *paths: str, recent: tuple[SessionFile, ...] = ()) -> None:
        self._paths = set(paths)
        self._recent = recent

    def analyzable_clients(self) -> frozenset[str]:
        return frozenset({"claude", "codex"})

    def locate(self, client: str, uuid: str) -> str | None:
        path = f"/{client}/{uuid}"
        return path if path in self._paths else None

    def recent(self, limit: int) -> list[SessionFile]:
        return list(self._recent[:limit])

    def read(self, source: str) -> SessionRecord | None:
        if source not in self._paths:
            return None
        return SessionRecord(source.split("/")[1], source, 1.0, 2.0)


def _store(*sessions: Session) -> InMemorySessionStore:
    store = InMemorySessionStore()
    for session in sessions:
        store.record(session)
    return store


def test_a_gmlw_session_is_analysed_from_its_client_file() -> None:
    use_case = AnalyzeSessionUseCase(
        _store(Session("my_job_001", "my_job", "claude", "u-1")), FakeFiles("/claude/u-1")
    )

    (analysis,) = use_case.execute("my_job_001")

    assert (analysis.session_id, analysis.source) == ("my_job_001", "/claude/u-1")


def test_a_job_is_analysed_session_by_session_leaving_out_those_without_a_file() -> None:
    use_case = AnalyzeSessionUseCase(
        _store(
            Session("j_001", "j", "codex", None),  # never learned its id
            Session("j_002", "j", "codex", "c-2"),
            Session("j_003", "j", "cursor", "x"),  # not analysable
            Session("j_004", "j", "claude", "u-4"),
        ),
        FakeFiles("/codex/c-2", "/claude/u-4"),
    )

    assert [a.session_id for a in use_case.execute("j")] == ["j_002", "j_004"]


def test_a_session_file_outside_gmlw_is_analysed_without_a_session() -> None:
    use_case = AnalyzeSessionUseCase(_store(), FakeFiles("/codex/c-9"))

    (analysis,) = use_case.execute("/codex/c-9")

    assert (analysis.session_id, analysis.client) == (None, "codex")


def test_something_that_is_none_of_the_three_is_refused() -> None:
    use_case = AnalyzeSessionUseCase(_store(), FakeFiles())

    with pytest.raises(NothingToAnalyzeError):
        use_case.execute("nothing_here")


@pytest.mark.parametrize(
    ("session", "key"),
    [
        (Session("j_001", "j", "vibe", "v"), "analyze.error.client"),
        (Session("j_001", "j", "codex", None), "analyze.error.missing"),
        (Session("j_001", "j", "claude", "gone"), "analyze.error.missing"),
    ],
)
def test_a_session_without_a_readable_file_says_why(session: Session, key: str) -> None:
    use_case = AnalyzeSessionUseCase(_store(session), FakeFiles())

    with pytest.raises(SessionFileUnavailableError) as raised:
        use_case.execute("j_001")

    assert raised.value.catalogue_key == key


def test_a_job_with_no_readable_session_says_so() -> None:
    use_case = AnalyzeSessionUseCase(_store(Session("j_001", "j", "codex", None)), FakeFiles())

    with pytest.raises(SessionFileUnavailableError) as raised:
        use_case.execute("j")

    assert raised.value.catalogue_key == "analyze.error.job_unavailable"


def test_recent_files_are_matched_to_the_gmlw_session_that_ran_them() -> None:
    files = (
        SessionFile("claude", "/claude/u-1", 3.0, uuid="u-1"),
        SessionFile("codex", "/codex/u-1", 2.0, uuid="u-1"),  # same id, other client: no match
        SessionFile("codex", "/codex/x", 1.0),  # no id read
    )
    use_case = AnalyzeSessionUseCase(
        _store(Session("j_001", "j", "claude", "u-1")), FakeFiles(recent=files)
    )

    recent = use_case.recent(limit=2)

    assert [(r.file.source, r.session_id) for r in recent] == [
        ("/claude/u-1", "j_001"),
        ("/codex/u-1", None),
    ]
