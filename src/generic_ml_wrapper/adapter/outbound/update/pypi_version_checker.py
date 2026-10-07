# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``VersionCheckPort`` backed by PyPI's JSON API, stdlib-only."""

from __future__ import annotations

import json
import urllib.request
from typing import ClassVar

from generic_ml_wrapper.application.port.outbound.version_check import VersionCheckPort

_TIMEOUT_S = 2.0


class PypiVersionChecker(VersionCheckPort):
    """Read a package's latest version from ``pypi.org/pypi/<package>/json``.

    Every failure mode (network, timeout, an unreadable or unexpected response) is
    caught and degrades to ``None`` — this adapter must never raise, since it runs on
    the exit-receipt path of a normal session.
    """

    _EXPECTED_ERRORS: ClassVar[tuple[type[Exception], ...]] = (
        OSError,  # covers urllib's URLError/HTTPError/timeout
        ValueError,  # json.JSONDecodeError
        KeyError,
        TypeError,
    )

    def latest_version(self, package: str) -> str | None:
        """Return ``package``'s latest version on PyPI, or ``None`` on any failure.

        Args:
            package: The distribution name, e.g. ``"generic-ml-wrapper"``.

        Returns:
            The latest version string, or ``None``.
        """
        url = f"https://pypi.org/pypi/{package}/json"
        try:
            with urllib.request.urlopen(url, timeout=_TIMEOUT_S) as response:
                data = json.loads(response.read())
            version = data["info"]["version"]
        except self._EXPECTED_ERRORS:
            return None
        return version if isinstance(version, str) and version else None
