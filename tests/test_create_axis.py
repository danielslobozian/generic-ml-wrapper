# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the CreateAxis use case (fake catalog + fake config writer)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from generic_ml_wrapper.application.domain.model.axis import AxisKind, AxisSelection
from generic_ml_wrapper.application.port.inbound.create_axis import (
    AxisExistsError,
    AxisLabelError,
    CreateAxisCommand,
)
from generic_ml_wrapper.application.port.outbound.axis_catalog import AxisCatalogPort
from generic_ml_wrapper.application.port.outbound.config_writer import ConfigWriterPort
from generic_ml_wrapper.application.usecase.create_axis import CreateAxisUseCase

_CONFIG = Path("/scratch/config.toml")
_WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


class _FakeCatalog(AxisCatalogPort):
    def __init__(self) -> None:
        self.created: list[tuple[AxisKind, str, str, str, str]] = []
        self._existing: set[tuple[AxisKind, str]] = set()

    def seed(self, kind: AxisKind, slug: str) -> None:
        self._existing.add((kind, slug))

    def list(self, kind: AxisKind) -> list[AxisSelection]:
        return []

    def exists(self, kind: AxisKind, slug: str) -> bool:
        return (kind, slug) in self._existing

    def create(self, kind: AxisKind, slug: str, label: str, description: str, created: str) -> None:
        self.created.append((kind, slug, label, description, created))
        self._existing.add((kind, slug))


class _FakeWriter(ConfigWriterPort):
    def __init__(self) -> None:
        self.merges: list[tuple[Path, list[tuple[str, str, object | None]]]] = []

    def merge(
        self, path: Path, entries: Sequence[tuple[str, str, object | None]]
    ) -> tuple[str, ...]:
        self.merges.append((path, list(entries)))
        return ()


def _use_case(catalog: _FakeCatalog, writer: _FakeWriter) -> CreateAxisUseCase:
    return CreateAxisUseCase(
        catalog=catalog, writer=writer, config_file=lambda: _CONFIG, clock=lambda: _WHEN
    )


def test_creates_the_folder_with_a_slug_derived_from_the_label() -> None:
    catalog, writer = _FakeCatalog(), _FakeWriter()
    result = _use_case(catalog, writer).execute(
        CreateAxisCommand(kind=AxisKind.ENVIRONMENT, label="Client Project", description="the gig")
    )
    assert result.slug == "client-project"
    assert result.label == "Client Project"
    assert result.made_default is False
    assert catalog.created == [
        (AxisKind.ENVIRONMENT, "client-project", "Client Project", "the gig", _WHEN.isoformat())
    ]
    assert writer.merges == []  # not made default


def test_make_default_writes_the_profile_key_for_the_kind() -> None:
    catalog, writer = _FakeCatalog(), _FakeWriter()
    result = _use_case(catalog, writer).execute(
        CreateAxisCommand(kind=AxisKind.ROLE, label="Code Reviewer", make_default=True)
    )
    assert result.made_default is True
    assert writer.merges == [(_CONFIG, [("profile", "default_role", "code-reviewer")])]


def test_empty_or_unusable_label_raises() -> None:
    use_case = _use_case(_FakeCatalog(), _FakeWriter())
    with pytest.raises(AxisLabelError):
        use_case.execute(CreateAxisCommand(kind=AxisKind.ROLE, label="  !!!  "))


def test_existing_slug_raises_and_does_not_create() -> None:
    catalog, writer = _FakeCatalog(), _FakeWriter()
    catalog.seed(AxisKind.ENVIRONMENT, "work")
    with pytest.raises(AxisExistsError):
        _use_case(catalog, writer).execute(
            CreateAxisCommand(kind=AxisKind.ENVIRONMENT, label="Work")
        )
    assert catalog.created == []  # never clobbered
