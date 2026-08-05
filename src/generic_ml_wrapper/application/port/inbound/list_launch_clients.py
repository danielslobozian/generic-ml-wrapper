# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the clients a launch can choose between, right now."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchClient:
    """One client a launch could actually run on, right now.

    Deliberately smaller than
    :class:`~generic_ml_wrapper.application.port.inbound.list_clients.ClientStatus`: no
    version. Reading a version means running ``<binary> --version`` per installed client,
    and a chooser that sits between "start this job" and the job starting cannot afford
    several subprocesses -- nor does the question need them.

    Attributes:
        name: The gmlw client id (e.g. ``claude``) -- what a launch is keyed on.
        display: The human-readable name; the id itself for a configured caller that has
            no catalog entry.
        is_default: Whether this is the configured default.
        custom: Whether it comes from a ``[callers]`` entry -- either a caller supplied for
            a name gmlw does not ship, or one replacing a built-in.
    """

    name: str
    display: str
    is_default: bool
    custom: bool = False


class ListLaunchClientsUseCase(ABC):
    """List the clients a launch can be pointed at, and say which one is the default.

    "Can be pointed at" is the whole contract, and it has two halves. A built-in client
    counts only when its binary is on ``PATH`` -- offering one that is not installed is
    offering a launch that cannot happen. A ``[callers]`` entry counts unconditionally:
    the caller is whatever the user configured, gmlw does not know what it needs, and
    configuring one is already a deliberate statement that it works.
    """

    @abstractmethod
    def execute(self) -> list[LaunchClient]:
        """List the clients available to launch on.

        Returns:
            Installed built-ins in catalog order, then configured callers gmlw does not
            ship, sorted by name. Empty when nothing is available.
        """
