# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The RenderVersionUseCase use case: name this build in one line."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper import __version__
from generic_ml_wrapper.application.port.inbound.render_version import RenderVersionUseCase

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.build_info import BuildInfoPort

_UNBUILT = "source, unbuilt"


class RenderVersionService(RenderVersionUseCase):
    """Compose the version line from the running version and the build stamp."""

    def __init__(self, build_info: BuildInfoPort) -> None:
        """Wire the use case to where the build stamp comes from.

        Args:
            build_info: Reports the stamp, or ``None`` for an unbuilt checkout.
        """
        self._build_info = build_info

    def execute(self) -> str:
        """Return ``gmlw <version> (build <id>)``, or the unbuilt form.

        Returns:
            One line, no trailing newline.
        """
        stamp = self._build_info.build_id()
        detail = _UNBUILT if stamp is None else f"build {stamp}"
        return f"gmlw {__version__} ({detail})"
