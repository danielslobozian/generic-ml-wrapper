# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the clients a launch can choose between, right now."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchClient:
    """One client a launch could run on.

    Deliberately smaller than
    :class:`~generic_ml_wrapper.application.port.inbound.list_clients.ClientStatus`: no
    version. Reading a version means running ``<binary> --version`` per installed client,
    and a chooser that sits between "start this job" and the job starting cannot afford
    several subprocesses -- nor does the question need them. Whether a client is *there*
    is a ``PATH`` lookup.

    Attributes:
        name: The gmlw client id (e.g. ``claude``) -- what a launch is keyed on.
        display: The human-readable name.
        installed: Whether the client's binary is on ``PATH``.
        is_default: Whether this is the configured default.
    """

    name: str
    display: str
    installed: bool
    is_default: bool


class ListLaunchClients(ABC):
    """List the clients a launch can be pointed at, and say which one is the default."""

    @abstractmethod
    def execute(self) -> list[LaunchClient]:
        """List the supported clients for a launch chooser.

        Returns:
            One entry per supported client, in catalog order.
        """
