# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The CheckForUpdateUseCase use case: a cached, rate-limited PyPI version check."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.update_check import UpdateCheck
from generic_ml_wrapper.application.port.inbound.check_for_update import CheckForUpdateUseCase

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from generic_ml_wrapper.application.port.outbound.update_cache import UpdateCachePort
    from generic_ml_wrapper.application.port.outbound.version_check import VersionCheckPort

# How long a cached "latest" answer is trusted before checking PyPI again. Not user-
# configurable -- [update] check is the one knob, matching [hints]'s single on/off key.
_TTL = timedelta(hours=24)


def _parse_version(value: str) -> tuple[int, ...] | None:
    """Parse a plain ``X.Y.Z`` version string into a comparable tuple, or ``None``.

    gmlw's own versions are always plain dotted integers (see ``RELEASE.md`` /
    ``bump_version.py``); an unparseable string degrades to "not newer" rather than
    raising, so a malformed or unexpected PyPI response never breaks the receipt.
    """
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return None


class CheckForUpdateService(CheckForUpdateUseCase):
    """Check PyPI for a newer release, reading/writing a small local cache first.

    Free of the wrapper's own metering -- this checks gmlw's own distribution, not a
    model call. Off by ``[update] check = false``; the cache TTL means most launches
    never reach the network at all.
    """

    def __init__(  # noqa: PLR0913  (the use case's full set of injected dependencies)
        self,
        *,
        checker: VersionCheckPort,
        current_version: str,
        package: str,
        enabled: Callable[[], bool],
        clock: Callable[[], datetime],
        cache: UpdateCachePort,
    ) -> None:
        """Wire the use case to its version source, its cache, and the clock.

        Args:
            checker: Reads the package's latest published version.
            current_version: The running gmlw version (``__version__``).
            package: The distribution name to check (``"generic-ml-wrapper"``).
            enabled: Resolves ``[update] check`` -- ``False`` short-circuits before
                asking the cache or the network.
            clock: Returns the current time (injected for deterministic tests).
            cache: Remembers what the last check found, and where that is kept.
        """
        self._checker = checker
        self._current_version = current_version
        self._package = package
        self._enabled = enabled
        self._clock = clock
        self._cache = cache

    def execute(self) -> str | None:
        """Return a newer version, checking PyPI at most once per cache TTL.

        Returns:
            The newer version string, or ``None`` when up to date, the check is off,
            or a fresh check couldn't complete this launch.
        """
        if not self._enabled():
            return None
        now = self._clock()
        cached = self._cache.last_check()
        if cached is not None and now - cached.checked_at < _TTL:
            latest = cached.latest
        else:
            latest = self._checker.latest_version(self._package)
            if latest is None:
                return None
            self._cache.record(UpdateCheck(now, latest))
        return latest if self._is_newer(latest) else None

    def _is_newer(self, latest: str) -> bool:
        """Return whether ``latest`` is a newer version than the one running."""
        latest_parsed = _parse_version(latest)
        current_parsed = _parse_version(self._current_version)
        if latest_parsed is None or current_parsed is None:
            return False
        return latest_parsed > current_parsed
