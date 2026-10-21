# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The WhatsNew use case: the packaged changelog, and which of it the user has seen."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.service.changelog import notes_since, parse_changelog
from generic_ml_wrapper.application.port.inbound.whats_new import WhatsNew
from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.domain.model.release_note import ReleaseNote
    from generic_ml_wrapper.application.port.outbound.release_notes import ReleaseNotesPort


class WhatsNewUseCase(WhatsNew):
    """Read the release notes, and remember in a small state file the last version shown."""

    def __init__(self, *, source: ReleaseNotesPort, current_version: str, state_path: Path) -> None:
        """Wire the use case to the changelog and the record of what was shown.

        Args:
            source: Reads the changelog that ships with gmlw.
            current_version: The running gmlw version (``__version__``).
            state_path: Where the last version whose notes were shown is recorded.
        """
        self._source = source
        self._current_version = current_version
        self._state_path = state_path

    def all(self) -> tuple[ReleaseNote, ...]:
        """Every release's notes, newest first."""
        text = self._source.read()
        return () if text is None else parse_changelog(text)

    def take_unseen(self) -> tuple[ReleaseNote, ...]:
        """The releases since the last shown, recorded as shown; none on the first call."""
        seen = self._read_seen()
        if seen == self._current_version:
            return ()
        self._write_seen()
        return () if seen is None else notes_since(self.all(), seen, self._current_version)

    def _read_seen(self) -> str | None:
        """The last version shown; ``None`` before the first record, or when unreadable."""
        try:
            seen = json.loads(self._state_path.read_text(encoding="utf-8"))["seen"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return seen if isinstance(seen, str) and seen else None

    def _write_seen(self) -> None:
        """Best-effort record of the running version as shown; a failure is logged."""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps({"seen": self._current_version}), encoding="utf-8"
            )
        except OSError as error:
            log.debug(i18n.t("log.whats_new_not_recorded", error=error))
