# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``ClientVersionPort`` backed by ``<binary> --version`` and first-party HTTP channels.

Zero third-party dependencies: the installed version comes from a short, timed
subprocess call; the latest version from :mod:`urllib` GETs against the catalog's
version probes. Every path is wrapped so a failure (offline, timeout, unexpected body,
missing client) degrades to ``None`` — a version check never raises.

The body parsing is factored into pure module-level functions (:func:`extract`,
:func:`parse_version`) so it can be unit-tested against fixture strings without a
network or a real client.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.application.port.outbound.client_version import ClientVersionPort

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_catalog import ClientInfo, VersionProbe

# A version token: a dotted number run plus any build/date suffix. Matches semver
# (``2.1.215``) and Cursor's date-hash (``2026.07.16-899851b``) alike.
_VERSION = re.compile(r"(\d+\.\d+(?:\.\d+)?[\w.\-]*)")

_HTTP_TIMEOUT_S = 6.0
_VERSION_TIMEOUT_S = 5.0
# GitHub's API rejects requests with no User-Agent; the others don't care.
_HEADERS = {"User-Agent": "generic-ml-wrapper", "Accept": "*/*"}


def parse_version(text: str | None) -> str | None:
    """Return the first version-shaped token in ``text``, or ``None``.

    Args:
        text: Any string (``--version`` output, an endpoint body, a git tag).

    Returns:
        The matched version, or ``None`` when nothing version-shaped is present.
    """
    if not text:
        return None
    match = _VERSION.search(text)
    return match.group(1) if match else None


def _numeric(version: str) -> tuple[int, ...]:
    """The version's leading numeric components as an int tuple (``2.1.215`` → ``(2,1,215)``)."""
    return tuple(int(part) for part in re.findall(r"\d+", version))


def outdated(installed: str, latest: str) -> bool:
    """Whether ``installed`` is strictly older than ``latest``.

    Compares numeric components so a build that is *ahead* of the published channel
    (e.g. a Claude Code install newer than the stable manifest) is never flagged, and an
    equal version never is. When either string carries no comparable number, returns
    ``False`` — an uncertain check should not nag.

    Args:
        installed: The locally reported version.
        latest: The latest published version.

    Returns:
        ``True`` only when ``installed`` is confidently behind ``latest``.
    """
    if installed == latest:
        return False
    here, there = _numeric(installed), _numeric(latest)
    if not here or not there:
        return False
    width = max(len(here), len(there))
    here += (0,) * (width - len(here))
    there += (0,) * (width - len(there))
    return here < there


def _dig(obj: object, dotted: str) -> object:
    """Walk a dotted path (``"info.version"``) into nested mappings; raise on a miss."""
    cursor: object = obj
    for key in dotted.split("."):
        if not isinstance(cursor, dict):
            raise KeyError(dotted)
        cursor = cast("dict[str, object]", cursor)[key]
    return cursor


def extract(probe: VersionProbe, body: str) -> str | None:
    """Pull a version out of a fetched ``body`` per the probe's ``kind``.

    Args:
        probe: The probe describing how to read the body.
        body: The raw response body.

    Returns:
        The parsed version, or ``None`` when the body does not carry one.
    """
    if probe.kind == "json":
        raw = str(_dig(json.loads(body), probe.selector))
    elif probe.kind == "regex":
        match = re.search(probe.selector, body)
        raw = match.group(1) if match else ""
    else:  # "text": the whole body is the version string
        raw = body.strip()
    if probe.strip_prefix and raw.startswith(probe.strip_prefix):
        raw = raw[len(probe.strip_prefix) :]
    return parse_version(raw)


class HttpClientVersions(ClientVersionPort):
    """Read installed versions from the local binary and latest ones over HTTP."""

    def installed(self, info: ClientInfo) -> str | None:
        """Run ``<binary> --version`` (briefly) and parse the version it prints.

        Args:
            info: The catalog entry (binary and version flag).

        Returns:
            The parsed installed version, or ``None`` on any failure.
        """
        try:
            result = subprocess.run(  # noqa: S603  (binary from the trusted catalog)
                [info.binary, info.version_flag],
                capture_output=True,
                text=True,
                timeout=_VERSION_TIMEOUT_S,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        # Some clients print the version to stderr; consider both streams.
        return parse_version(f"{result.stdout}\n{result.stderr}")

    def latest(self, info: ClientInfo) -> str | None:
        """Try each version probe in order; return the first version found.

        Args:
            info: The catalog entry (its ordered version probes).

        Returns:
            The latest version, or ``None`` when every probe fails.
        """
        for probe in info.version_probes:
            body = self._fetch(probe.url)
            if body is None:
                continue
            try:
                version = extract(probe, body)
            except (KeyError, ValueError, TypeError, IndexError):
                continue
            if version:
                return version
        return None

    def _fetch(self, url: str) -> str | None:
        """GET ``url`` with a short timeout, returning the decoded body or ``None``."""
        request = urllib.request.Request(url, headers=_HEADERS)  # noqa: S310  (https catalog URLs)
        try:
            with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_S) as response:  # noqa: S310
                return response.read().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            return None
