# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The CheckForUpdate use case: a cached, rate-limited PyPI version check, or one asked for."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.update_check import UpdateCheck, is_newer
from generic_ml_wrapper.application.port.inbound.check_for_update import CheckForUpdate
from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.installation import InstallationPort
    from generic_ml_wrapper.application.port.outbound.version_check import VersionCheckPort

# How long a cached "latest" answer is trusted before checking PyPI again. Not user-
# configurable -- [update] check is the one knob, matching [hints]'s single on/off key.
_TTL = timedelta(hours=24)


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
        installation: InstallationPort,
        current_version: str,
        package: str,
        enabled: Callable[[], bool],
        clock: Callable[[], datetime],
        cache_path: Path,
    ) -> None:
        """Wire the use case to its version source, cache file, and clock.

        Args:
            checker: Reads the package's latest published version.
            installation: Finds out how the running gmlw was installed.
            current_version: The running gmlw version (``__version__``).
            package: The distribution name to check (``"generic-ml-wrapper"``).
            enabled: Resolves ``[update] check`` -- ``False`` short-circuits before
                touching the cache file or the network.
            clock: Returns the current time (injected for deterministic tests).
            cache_path: Where the last-checked timestamp and version are cached.
        """
        self._checker = checker
        self._installation = installation
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
        return latest if is_newer(latest, self._current_version) else None

    def check_now(self) -> UpdateCheck:
        """Check PyPI now, bypassing the cache and the switch; refresh the cache on success.

        Returns:
            The running and latest versions and the installation.
        """
        latest = self._checker.latest_version(self._package)
        if latest is not None:
            self._write_cache(self._clock(), latest)
        return UpdateCheck(self._current_version, latest, self._installation.inspect())

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
