# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for best-effort folder birth time."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.file_creation_time import FileCreationTime

if TYPE_CHECKING:
    from pathlib import Path


def test_created_ms_returns_a_positive_stamp_for_an_existing_folder(tmp_path: Path) -> None:
    folder = tmp_path / "env"
    folder.mkdir()
    assert FileCreationTime().of(folder) > 0


def test_created_ms_is_zero_for_a_missing_path(tmp_path: Path) -> None:
    assert FileCreationTime().of(tmp_path / "nope") == 0
