# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What a check for a newer gmlw found: the running version, the latest, and the install."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.installation import Installation


def parse_version(value: str) -> tuple[int, ...] | None:
    """Parse a plain ``X.Y.Z`` version string into a comparable tuple, or ``None``.

    gmlw's own versions are always plain dotted integers (see ``RELEASE.md`` /
    ``bump_version.py``); an unparseable string degrades to "not newer" rather than
    raising, so a malformed or unexpected PyPI response never breaks the receipt.
    """
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return None


def is_newer(latest: str, current: str) -> bool:
    """Whether ``latest`` is a newer version than ``current``; ``False`` if either is unreadable."""
    latest_parsed = parse_version(latest)
    current_parsed = parse_version(current)
    if latest_parsed is None or current_parsed is None:
        return False
    return latest_parsed > current_parsed


@dataclass(frozen=True)
class UpdateCheck:
    """One check for a newer release.

    Attributes:
        current: The running version.
        latest: The latest published version, or ``None`` when PyPI could not be reached.
        installation: How the running gmlw was installed.
    """

    current: str
    latest: str | None
    installation: Installation

    @property
    def newer(self) -> bool:
        """Whether a newer release than the running one is out."""
        return self.latest is not None and is_newer(self.latest, self.current)

    @property
    def command(self) -> str | None:
        """The command that upgrades to the newer release; ``None`` without one."""
        if self.latest is None or not self.newer:
            return None
        return self.installation.upgrade_command(self.latest)
