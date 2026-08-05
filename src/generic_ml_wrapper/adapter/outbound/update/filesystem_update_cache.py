# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``UpdateCachePort``: the last release check, as a small JSON file."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.update_check import UpdateCheck
from generic_ml_wrapper.application.port.outbound.update_cache import UpdateCachePort

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort
    from generic_ml_wrapper.application.port.outbound.localizer import LocalizerPort


class FilesystemUpdateCacheAdapter(UpdateCachePort):
    """Keep the last release check in one JSON file, and never fail the run over it.

    The file holds ``checked_at`` and ``latest``. A missing or malformed one is the
    ordinary first-run state rather than a fault worth reporting -- only a failed
    *write* is, because that is the case which would otherwise silently re-check on
    every launch with nobody able to see why.
    """

    def __init__(
        self, cache_file: Path, diagnostics: DiagnosticsPort, localizer: LocalizerPort
    ) -> None:
        """Bind the cache to its file and to where a failed write is reported.

        Args:
            cache_file: The file the last check is kept in (its folder is created).
            diagnostics: Where a failed write is reported.
            localizer: Renders that report in the language the wrapper is speaking.
        """
        self._cache_file = cache_file
        self._diagnostics = diagnostics
        self._localizer = localizer

    def last_check(self) -> UpdateCheck | None:
        """Return the recorded check, or ``None`` when there is not a usable one."""
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            checked_at = datetime.fromisoformat(data["checked_at"])
            latest = data["latest"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if not isinstance(latest, str) or not latest:
            return None
        return UpdateCheck(checked_at, latest)

    def record(self, check: UpdateCheck) -> None:
        """Write the check to the cache file; a write failure is logged, not raised."""
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._cache_file.write_text(
                json.dumps({"checked_at": check.checked_at.isoformat(), "latest": check.latest}),
                encoding="utf-8",
            )
        except OSError as error:
            self._diagnostics.debug(
                f"could not record the update check as of now: {error}",
                key="log.update_cache_not_recorded",
            )
