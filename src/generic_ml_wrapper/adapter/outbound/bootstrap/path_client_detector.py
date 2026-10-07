# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``ClientDetectorPort`` backed by ``PATH`` lookups for each client's command."""

from __future__ import annotations

import shutil

from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort


class PathClientDetector(ClientDetectorPort):
    """Detect installed clients by resolving each one's command on ``PATH``."""

    def available(self) -> list[str]:
        """Return the built-in clients whose command resolves on ``PATH``.

        Returns:
            The installed client names in canonical order (empty when none are).
        """
        return [
            info.name for info in client_catalog.SUPPORTED if shutil.which(info.binary) is not None
        ]
