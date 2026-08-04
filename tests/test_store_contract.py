# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The startup handshake between the code's expectations and the shipped lineage.

The two halves of the store are versioned by one number: the schema the code is written
against, and the migrations that build it. If the lineage falls short, every later read
and write goes through a mapping the tables do not match, so the check runs before the
first command does anything.

The realistic way to reach that state is packaging — the ``.sql`` files not making it
into the installed package — which is why failing loudly beats quietly creating an empty
database and reporting success.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.adapter.outbound.store.sqlite_store_migration import SqliteStoreMigration
from generic_ml_wrapper.application.domain.model.store_contract_outdated_error import (
    StoreContractOutdatedError,
)
from generic_ml_wrapper.application.port.outbound.store_migration import (
    CURRENT_SCHEMA_VERSION,
    StoreMigrationPort,
)

if TYPE_CHECKING:
    from pathlib import Path


class _Lineage(StoreMigrationPort):
    """A migration that reaches whatever version the test says it reaches."""

    def __init__(self, reaches: int) -> None:
        self._reaches = reaches

    def implemented_version(self) -> int:
        return self._reaches

    def migrate_to_current(self) -> None:
        """Never called: the handshake fails before anything is migrated."""


def test_a_lineage_that_cannot_reach_the_required_version_stops_the_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_store_migration", lambda: _Lineage(CURRENT_SCHEMA_VERSION - 1))

    exit_code = app.main(["jobs"])

    assert exit_code == 1
    error_text = capsys.readouterr().err
    assert "incomplete" in error_text  # phrased for a person, not a traceback
    assert "Traceback" not in error_text


def test_the_shipped_lineage_satisfies_the_handshake(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The real files, unpatched: this is the test that fails if a migration is added
    # without bumping the version the code requires, or vice versa.
    assert app.main(["jobs"]) == 0
    assert "incomplete" not in capsys.readouterr().err


def test_an_empty_lineage_reaches_no_version(tmp_path: Path) -> None:
    # What a packaging failure looks like from the runner's side: the directory is there
    # and holds nothing, so it can build no version at all.
    empty = tmp_path / "migrations"
    empty.mkdir()
    migration = SqliteStoreMigration(
        lambda: sqlite3.connect(tmp_path / "ledger.db"), tmp_path, migrations_dir=empty
    )

    assert migration.implemented_version() == 0


def test_the_error_names_both_versions() -> None:
    error = StoreContractOutdatedError(2, 4)
    assert error.implemented == 2
    assert error.required == 4
