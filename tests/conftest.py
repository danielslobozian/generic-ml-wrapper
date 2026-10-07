# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from generic_ml_wrapper.common import paths


@pytest.fixture(autouse=True)
def _isolate_gmlw_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect every ``~/.gmlw`` location to a temp dir so no test touches real state.

    All wrapper paths derive from ``paths.HOME``; consumers read them by attribute
    (``paths.LEDGER``), so remapping the module constants here is authoritative. Done
    dynamically over every ``Path`` constant rooted at HOME, so a path newly added to
    ``paths`` is isolated automatically without editing this fixture.
    """
    real_home = paths.HOME
    fake_home = tmp_path_factory.mktemp("gmlw-home")
    for name in dir(paths):
        value = getattr(paths, name)
        if not isinstance(value, Path):
            continue
        if value == real_home:
            monkeypatch.setattr(paths, name, fake_home)
        elif real_home in value.parents:
            monkeypatch.setattr(paths, name, fake_home / value.relative_to(real_home))
