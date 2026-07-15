# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The CheckClientReady use case: is the resolved client launchable?"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.port.inbound.check_client_ready import (
    CheckClientReady,
    ClientReadiness,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort


class CheckClientReadyUseCase(CheckClientReady):
    """Resolve readiness from the caller overrides and the installed clients.

    A client with a ``[callers]`` override is trusted as ready — the override is
    arbitrary code whose dependencies the wrapper cannot know. A supported built-in
    is ready only when its command is on ``PATH``. Anything else is not ready.
    """

    def __init__(self, *, overrides: dict[str, str], detector: ClientDetectorPort) -> None:
        """Wire the use case to the config overrides and the install detector.

        Args:
            overrides: The ``[callers]`` client-to-spec overrides.
            detector: Reports which supported clients are installed.
        """
        self._overrides = overrides
        self._detector = detector

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
        info = client_catalog.by_name(client)
        ready = info is not None and client in installed
        return ClientReadiness(
            client=client,
            ready=ready,
            missing=None if ready else info,
            installed=installed,
        )
