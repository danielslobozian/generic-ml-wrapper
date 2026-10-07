# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for putting tags on jobs and taking them off."""

from __future__ import annotations

import pytest
from _conformance import InMemoryJobTagStore, InMemorySessionStore

from generic_ml_wrapper.application.domain.model.identifiers import IdentifierError
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.inbound.delete_sessions import NoSuchJobError
from generic_ml_wrapper.application.usecase.tag_jobs import TagJobsUseCase


def _use_case() -> tuple[TagJobsUseCase, InMemoryJobTagStore]:
    store = InMemorySessionStore()
    store.record(Session("PAY-1_001", "PAY-1", "claude", None))
    tags = InMemoryJobTagStore()
    return TagJobsUseCase(store, tags), tags


def test_adding_keeps_what_the_job_had_and_folds_case() -> None:
    use_case, _ = _use_case()
    use_case.add("PAY-1", ["sprint-41"])
    assert use_case.add("PAY-1", ["Sprint-42", "payments", "sprint-42"]) == (
        "payments",
        "sprint-41",
        "sprint-42",
    )


def test_removing_takes_off_only_what_is_named() -> None:
    use_case, _ = _use_case()
    use_case.add("PAY-1", ["sprint-41", "sprint-42"])
    assert use_case.remove("PAY-1", ["sprint-41"]) == ("sprint-42",)


def test_replacing_makes_the_tags_exactly_what_was_given() -> None:
    use_case, _ = _use_case()
    use_case.add("PAY-1", ["sprint-41", "payments"])
    assert use_case.replace("PAY-1", ["sprint-42", "payments"]) == ("payments", "sprint-42")
    assert use_case.replace("PAY-1", []) == ()


def test_an_unknown_job_is_refused() -> None:
    use_case, tags = _use_case()
    with pytest.raises(NoSuchJobError):
        use_case.add("ghost", ["sprint-42"])
    assert tags.tags_by_job() == {}


def test_one_invalid_tag_changes_nothing() -> None:
    # Validated as a whole before anything is written, like a delete batch.
    use_case, tags = _use_case()
    with pytest.raises(IdentifierError):
        use_case.add("PAY-1", ["sprint-42", "not a tag"])
    assert tags.tags_by_job() == {}
