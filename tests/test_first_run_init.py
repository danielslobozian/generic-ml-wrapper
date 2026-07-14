# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the FirstRunInit use case: detect, choose, seed."""

from generic_ml_wrapper.application.port.inbound.first_run_init import FirstRunOutcome
from generic_ml_wrapper.application.port.outbound.client_chooser import ClientChooserPort
from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort
from generic_ml_wrapper.application.usecase.first_run_init import FirstRunInitUseCase


class _FakeDetector(ClientDetectorPort):
    def __init__(self, found: list[str]) -> None:
        self._found = found

    def available(self) -> list[str]:
        return self._found


class _RecordingSeeder(LayoutSeederPort):
    def __init__(self) -> None:
        self.calls = 0
        self.seeded_with: str | None = None

    def ensure(self, default_client: str | None = None) -> None:
        self.calls += 1
        self.seeded_with = default_client


class _FakeChooser(ClientChooserPort):
    def __init__(self, choice: str | None) -> None:
        self._choice = choice
        self.asked: list[str] | None = None

    def choose(self, candidates: list[str]) -> str | None:
        self.asked = candidates
        return self._choice


def _run(
    found: list[str], choice: str | None = None
) -> tuple[FirstRunOutcome, _FakeChooser, str | None]:
    seeder = _RecordingSeeder()
    chooser = _FakeChooser(choice)
    outcome = FirstRunInitUseCase(
        detector=_FakeDetector(found), seeder=seeder, chooser=chooser
    ).execute()
    assert seeder.calls == 1  # the layout is always seeded exactly once
    return (outcome, chooser, seeder.seeded_with)


def test_single_client_becomes_the_default_without_asking() -> None:
    outcome, chooser, seeded = _run(["cursor"])
    assert outcome.found == ["cursor"]
    assert outcome.chosen == "cursor"
    assert chooser.asked is None  # never prompted for a lone client
    assert seeded == "cursor"


def test_no_client_seeds_without_a_default() -> None:
    outcome, chooser, seeded = _run([])
    assert outcome.found == []
    assert outcome.chosen is None
    assert chooser.asked is None
    assert seeded is None  # commented template; built-in default applies


def test_several_clients_defer_to_the_chooser() -> None:
    outcome, chooser, seeded = _run(["claude", "cursor", "codex"], choice="cursor")
    assert chooser.asked == ["claude", "cursor", "codex"]
    assert outcome.chosen == "cursor"
    assert seeded == "cursor"


def test_several_clients_with_a_declined_choice_seed_no_default() -> None:
    outcome, chooser, seeded = _run(["claude", "cursor"], choice=None)
    assert chooser.asked == ["claude", "cursor"]
    assert outcome.chosen is None
    assert seeded is None  # non-interactive: never block, keep the built-in default
