# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The CheckForUpdate use case: a cached, rate-limited PyPI version check."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.check_for_update import CheckForUpdate
from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

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


class CheckForUpdateUseCase(CheckForUpdate):
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
        cache_path: Path,
    ) -> None:
        """Wire the use case to its version source, cache file, and clock.

        Args:
            checker: Reads the package's latest published version.
            current_version: The running gmlw version (``__version__``).
            package: The distribution name to check (``"generic-ml-wrapper"``).
            enabled: Resolves ``[update] check`` -- ``False`` short-circuits before
                touching the cache file or the network.
            clock: Returns the current time (injected for deterministic tests).
            cache_path: Where the last-checked timestamp and version are cached.
        """
        self._checker = checker
        self._current_version = current_version
        self._package = package
        self._enabled = enabled
        self._clock = clock
        self._cache_path = cache_path

    def execute(self) -> str | None:
        """Return a newer version, checking PyPI at most once per cache TTL.

        Returns:
            The newer version string, or ``None`` when up to date, the check is off,
            or a fresh check couldn't complete this launch.
        """
        if not self._enabled():
            return None
        now = self._clock()
        cached = self._read_cache()
        if cached is not None and now - cached[0] < _TTL:
            latest = cached[1]
        else:
            latest = self._checker.latest_version(self._package)
            if latest is None:
                return None
            self._write_cache(now, latest)
        return latest if self._is_newer(latest) else None

    def _is_newer(self, latest: str) -> bool:
        """Return whether ``latest`` is a newer version than the one running."""
        latest_parsed = _parse_version(latest)
        current_parsed = _parse_version(self._current_version)
        if latest_parsed is None or current_parsed is None:
            return False
        return latest_parsed > current_parsed

    def _read_cache(self) -> tuple[datetime, str] | None:
        """Return ``(checked_at, latest)`` from the cache file, or ``None`` if unusable.

        A missing or malformed cache is the ordinary first-run state, not a fault
        worth logging -- only a failed *write* (below) is, since that is the case
        that would otherwise silently keep re-checking every launch.
        """
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            checked_at = datetime.fromisoformat(data["checked_at"])
            latest = data["latest"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if not isinstance(latest, str) or not latest:
            return None
        return checked_at, latest

    def _write_cache(self, checked_at: datetime, latest: str) -> None:
        """Best-effort write of the cache file; a write failure is logged, not raised."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps({"checked_at": checked_at.isoformat(), "latest": latest}),
                encoding="utf-8",
            )
        except OSError as error:
            log.debug(i18n.t("log.update_cache_not_recorded", error=error))
