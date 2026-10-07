# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the MigrateLayout use case: resolves the active environment, then migrates."""

from generic_ml_wrapper.application.domain.model.migration import MigrationReport
from generic_ml_wrapper.application.port.outbound.layout_migrator import LayoutMigratorPort
from generic_ml_wrapper.application.usecase.migrate_layout import MigrateLayoutUseCase


class _RecordingMigrator(LayoutMigratorPort):
    def __init__(self) -> None:
        self.environment: str | None = None

    def migrate(self, environment: str) -> MigrationReport:
        self.environment = environment
        return MigrationReport(environment=environment, moved=["co.md"])


def test_migrates_into_the_resolved_active_environment() -> None:
    migrator = _RecordingMigrator()
    report = MigrateLayoutUseCase(migrator, environment=lambda: "acme").execute()
    assert migrator.environment == "acme"  # the resolver's value is what gets migrated into
    assert report.environment == "acme"
    assert report.moved == ["co.md"]


def test_resolver_is_read_at_call_time() -> None:
    # The env is resolved lazily (init writes it before this runs), not bound at construction.
    box = {"env": "work"}
    use_case = MigrateLayoutUseCase(_RecordingMigrator(), environment=lambda: box["env"])
    box["env"] = "personal"
    assert use_case.execute().environment == "personal"
