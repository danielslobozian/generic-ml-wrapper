# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SPIKE: the launch banner derives its version and client list (no drift)."""

from __future__ import annotations

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.tui.banner import boxed_banner
from generic_ml_wrapper.application.domain.model import client_catalog


def test_banner_shows_derived_version_and_every_client() -> None:
    banner = boxed_banner()
    assert f"v{__version__}" in banner
    for info in client_catalog.SUPPORTED:
        assert info.name in banner


def test_banner_is_a_closed_box_with_aligned_rows() -> None:
    lines = boxed_banner().splitlines()
    assert lines[0].startswith("╭")
    assert lines[0].endswith("╮")
    assert lines[-1].startswith("╰")
    assert lines[-1].endswith("╯")
    # Every row is the same visual width, so the frame is straight.
    assert len({len(line) for line in lines}) == 1
