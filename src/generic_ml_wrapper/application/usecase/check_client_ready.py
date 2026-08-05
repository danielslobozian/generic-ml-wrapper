# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The CheckClientReady use case: is the resolved client launchable?"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.check_client_ready import (
    CheckClientReady,
    ClientReadiness,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.client_catalog import ClientCatalogPort
    from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
    from generic_ml_wrapper.application.port.outbound.system_info import SystemInfoPort


class CheckClientReadyUseCase(CheckClientReady):
    """Resolve readiness from the caller overrides and the installed clients.

    A client with a ``[callers]`` override is trusted as ready — the override is
    arbitrary code whose dependencies the wrapper cannot know. A supported built-in
    is ready only when its command is on ``PATH``. Anything else is not ready.
    """

    def __init__(
        self,
        *,
        overrides: dict[str, str],
        detector: ClientDetectorPort,
        catalog: ClientCatalogPort,
        system: SystemInfoPort,
    ) -> None:
        """Wire the use case to the config overrides and the install detector.

        Args:
            overrides: The ``[callers]`` client-to-spec overrides.
            detector: Reports which supported clients are installed.
            catalog: The supported clients and their facts.
            system: Names the platform, so the install commands can be resolved here.
        """
        self._overrides = overrides
        self._detector = detector
        self._catalog = catalog
        self._system = system

    def execute(self, client: str) -> ClientReadiness:
        """Report whether ``client`` can launch, with guidance when it cannot.

        Args:
            client: The resolved client name.

        Returns:
            The readiness verdict.
        """
        installed = tuple(self._detector.available())
        if client in self._overrides:  # a custom caller — trust it, do not gate on PATH
            return ClientReadiness(client=client, ready=True, missing=None, installed=installed)
        info = self._catalog.by_name(client)
        ready = info is not None and client in installed
        missing = None if ready else info
        system = self._system.platform_name()
        return ClientReadiness(
            client=client,
            ready=ready,
            missing=missing,
            installed=installed,
            install_command=None if missing is None else missing.install_for(system),
            catalogue_install_commands=tuple(
                (entry.name, entry.install_for(system)) for entry in self._catalog.supported()
            ),
        )
