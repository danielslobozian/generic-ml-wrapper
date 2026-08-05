# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for settings: what may be configured, and what it is set to now."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.setting_row import SettingRow


class SettingsCatalogPort(ABC):
    """Outbound port for the settable configuration surface.

    Two things the ``config`` commands need and the application ring may not fetch for
    itself: the *schema* — which keys exist, what they accept, what they default to — and
    the *current effective values*, which depend on a file on disk. Both arrive through
    this port, so a use case never reads a config module or a path directly — including
    the question of *which* file, which is this implementation's to answer.

    Reading is deliberately tolerant: a malformed or ill-typed file falls back to defaults
    rather than raising, because a broken config must not make the tool that edits it
    unusable. Validation is the write path's job, not the read path's.
    """

    @abstractmethod
    def rows(self) -> list[SettingRow]:
        """Return every registered setting's metadata, in declaration order."""

    @abstractmethod
    def current_values(self) -> dict[str, object]:
        """Return the current effective value of every registered scalar setting.

        An absent or malformed config yields defaults rather than raising.

        Returns:
            A ``dotted.key -> value`` map covering exactly the keys :meth:`rows` reports.
        """

    @abstractmethod
    def is_table(self, key: str) -> bool:
        """Whether ``key`` addresses a table of entries rather than a single scalar.

        Args:
            key: The dotted key.

        Returns:
            ``True`` for a table-valued setting (e.g. per-client launch arguments).

        Raises:
            UnknownSettingError: If ``key`` names no registered setting.
        """

    @abstractmethod
    def coerce(self, key: str, raw: str) -> object:
        """Convert a typed-in string to the setting's declared type.

        Args:
            key: The dotted key being set.
            raw: The value as the user typed it.

        Returns:
            The coerced value, ready to persist.

        Raises:
            UnknownSettingError: If ``key`` names no registered setting.
            InvalidSettingValueError: If ``raw`` is not valid for it.
        """

    @abstractmethod
    def parse_entry(self, key: str, raw: str) -> tuple[str, str | None]:
        """Split a table entry's ``name=value`` argument into its parts.

        Args:
            key: The dotted key of the table.
            raw: The ``name=value`` text, or a bare name to clear an entry.

        Returns:
            The entry name and its value, or ``None`` to remove the entry.

        Raises:
            InvalidSettingValueError: If ``raw`` is not a well-formed entry.
        """
