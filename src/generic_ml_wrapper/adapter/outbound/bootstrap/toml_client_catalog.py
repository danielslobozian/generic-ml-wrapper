# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ``ClientCatalogPort`` backed by the packaged ``resources/clients.toml``.

The catalogue is data, read once at construction. Keeping it in a resource file rather
than in source means adding or correcting a client is an edit to data — the reason the
entries left the domain in the first place.
"""

from __future__ import annotations

import tomllib
from functools import cache
from importlib import resources
from typing import Any, cast

from generic_ml_wrapper.application.domain.model.client_info import ClientInfo
from generic_ml_wrapper.application.domain.model.prerequisite import Prerequisite
from generic_ml_wrapper.application.domain.model.version_probe import VersionProbe
from generic_ml_wrapper.application.port.outbound.client_catalog import ClientCatalogPort


class TomlClientCatalogAdapter(ClientCatalogPort):
    """Reads the supported clients from the packaged catalogue file."""

    def supported(self) -> tuple[ClientInfo, ...]:
        """Return every supported client, in the file's own order."""
        return _load()

    def by_name(self, name: str) -> ClientInfo | None:
        """Return the catalogue entry for a client name, or ``None`` when unsupported."""
        return next((info for info in _load() if info.name == name), None)


@cache
def _load() -> tuple[ClientInfo, ...]:
    """Parse the packaged catalogue once per process — it is immutable, packaged data."""
    path = resources.files("generic_ml_wrapper").joinpath("resources", "clients.toml")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    prerequisites = {
        key: Prerequisite(**value) for key, value in raw.get("prerequisites", {}).items()
    }
    return tuple(
        _client(cast("dict[str, Any]", entry), prerequisites) for entry in raw.get("clients", [])
    )


def _client(entry: dict[str, Any], prerequisites: dict[str, Prerequisite]) -> ClientInfo:
    """Build one :class:`ClientInfo` from its table, resolving probes and any prerequisite."""
    probes = tuple(
        VersionProbe(**cast("dict[str, Any]", probe)) for probe in entry.pop("version_probes", [])
    )
    prereq_name = cast("str | None", entry.pop("prereq", None))
    return ClientInfo(
        **entry,
        version_probes=probes,
        prereq=prerequisites[prereq_name] if prereq_name else None,
    )
