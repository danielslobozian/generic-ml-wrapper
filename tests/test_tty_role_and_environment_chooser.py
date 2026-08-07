# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the role and environment steps of init: a menu, plus "type your own"."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.cli.setup import (
    tty_environment_chooser,
    tty_prompt,
    tty_role_chooser,
)
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_environment_chooser import (
    TtyEnvironmentChooser,
)
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_role_chooser import TtyRoleChooser
from generic_ml_wrapper.application.domain.model.role import Role
from generic_ml_wrapper.application.port.outbound.role_examples_repository import (
    RoleExamplesRepositoryPort,
)
from generic_ml_wrapper.application.usecase.list_role_examples import ListRoleExamplesService
from generic_ml_wrapper.application.wiring.composition import (
    build_list_environment_examples,
    build_list_role_examples,
)
from generic_ml_wrapper.application.wiring.localization import load_localizer

if TYPE_CHECKING:
    import pytest


class _Tty(io.StringIO):
    """A StringIO that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


def _wire(monkeypatch: pytest.MonkeyPatch, *, stdin: str, tty: bool = True) -> io.StringIO:
    """Point the menu primitive and both choosers at a scripted stdin + captured stderr."""
    stdin_stream: io.StringIO = _Tty(stdin) if tty else io.StringIO(stdin)
    err: io.StringIO = _Tty() if tty else io.StringIO()
    for module in (tty_prompt, tty_role_chooser, tty_environment_chooser):
        monkeypatch.setattr(module.sys, "stdin", stdin_stream)
        monkeypatch.setattr(module.sys, "stderr", err)
    return err


def _environments() -> TtyEnvironmentChooser:
    return TtyEnvironmentChooser(load_localizer("en"), build_list_environment_examples())


def _roles() -> TtyRoleChooser:
    return TtyRoleChooser(load_localizer("en"), build_list_role_examples())


def test_picking_an_example_returns_its_code_and_rendered_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, stdin="1\n")  # the first environment example is "work"
    chosen = _environments().choose("work", load_localizer("en"))
    assert (chosen.code, chosen.label) == ("work", "Work")


def test_picking_a_role_example_returns_its_code_and_rendered_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, stdin="1\n")  # the first role example is "software-engineer"
    chosen = _roles().choose("default", load_localizer("en"))
    assert (chosen.code, chosen.label) == ("software-engineer", "Software engineer")


def test_type_your_own_codes_the_answer_and_echoes_it(monkeypatch: pytest.MonkeyPatch) -> None:
    # 4 examples + "type your own" = option 5; then a free-text French answer.
    err = _wire(monkeypatch, stdin="5\nÉquipe Produit\n")
    chosen = _environments().choose("work", load_localizer("en"))
    assert chosen.code == "equipe-produit"  # accents stripped, kebab-cased
    assert chosen.label == "Équipe Produit"  # the human wording is kept as the label
    assert "equipe-produit" in err.getvalue()  # the code is echoed back


def test_non_tty_declines_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n", tty=False)
    chosen = _environments().choose("work", load_localizer("en"))
    assert (chosen.code, chosen.label, chosen.description) == ("work", "work", "work")


def test_empty_typed_answer_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="5\n\n")  # choose "type your own", then an empty line
    assert _environments().choose("work", load_localizer("en")).code == "work"


def test_a_label_with_nothing_codeable_falls_back_rather_than_refusing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Setup cannot be skipped, so an uncodable answer keeps the default instead of raising.
    _wire(monkeypatch, stdin="5\n!!!\n")
    assert _environments().choose("work", load_localizer("en")).code == "work"


def test_no_offered_examples_still_allows_typing_your_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, stdin="1\nMy Own Role\n")  # the only option is "type your own"
    chooser = TtyRoleChooser(load_localizer("en"), ListRoleExamplesService(_NoExamples()))
    assert chooser.choose("default", load_localizer("en")).code == "my-own-role"


class _NoExamples(RoleExamplesRepositoryPort):
    """A role examples repository with nothing packaged."""

    def find_all(self) -> tuple[Role, ...]:
        return ()
