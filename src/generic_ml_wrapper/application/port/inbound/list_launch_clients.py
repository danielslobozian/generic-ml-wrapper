# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the clients a launch can choose between, right now."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.launch_client import LaunchClient


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
