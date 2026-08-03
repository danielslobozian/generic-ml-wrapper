# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from generic_ml_wrapper.application.wiring.paths import paths


@pytest.fixture(autouse=True)
def _isolate_gmlw_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect every ``~/.gmlw`` location to a temp dir so no test touches real state.

    Every location is derived from the root, so moving the root moves the whole tree —
    a folder added to ``Paths`` later is isolated by this fixture without editing it.
    """
    monkeypatch.setattr(paths, "home", tmp_path_factory.mktemp("gmlw-home"))
