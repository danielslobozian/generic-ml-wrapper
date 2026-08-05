# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for naming this build in one line."""

from __future__ import annotations

from generic_ml_wrapper import __version__
from generic_ml_wrapper.application.port.outbound.build_info import BuildInfoPort
from generic_ml_wrapper.application.usecase.render_version import RenderVersionService


class _Stamp(BuildInfoPort):
    def __init__(self, build_id: str | None) -> None:
        self._build_id = build_id

    def build_id(self) -> str | None:
        return self._build_id


def test_a_released_build_is_named_by_its_stamp() -> None:
    assert RenderVersionService(_Stamp("2026.08.04-1")).execute() == (
        f"gmlw {__version__} (build 2026.08.04-1)"
    )


def test_an_unbuilt_checkout_says_so() -> None:
    """The absence of a stamp is how a developer is told apart from a user."""
    assert RenderVersionService(_Stamp(None)).execute() == f"gmlw {__version__} (source, unbuilt)"


def test_the_line_is_one_line() -> None:
    assert "\n" not in RenderVersionService(_Stamp("x")).execute()
