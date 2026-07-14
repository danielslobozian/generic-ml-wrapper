# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``ClientDetectorPort`` backed by ``PATH`` lookups for each client's command."""

from __future__ import annotations

import shutil

from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort

# Client -> the command it launches, in canonical order (claude first, matching the
# built-in default). Mirrors each caller's BINARY; kept explicit to avoid importing
# the whole caller family just to detect installs.
_COMMANDS: tuple[tuple[str, str], ...] = (
    ("claude", "claude"),
    ("cursor", "cursor-agent"),
    ("codex", "codex"),
    ("vibe", "vibe"),
)


class PathClientDetector(ClientDetectorPort):
    """Detect installed clients by resolving each one's command on ``PATH``."""

    def available(self) -> list[str]:
        """Return the built-in clients whose command resolves on ``PATH``.

        Returns:
            The installed client names in canonical order (empty when none are).
        """
        return [name for name, command in _COMMANDS if shutil.which(command) is not None]
