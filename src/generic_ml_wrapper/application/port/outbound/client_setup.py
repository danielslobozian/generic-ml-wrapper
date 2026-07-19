# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the guided client step of the forced init."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer


class ClientSetupPort(ABC):
    """Run the guided conversation that settles which client gmlw wraps by default.

    Unlike a bare chooser, this always talks the choice through: it shows each installed
    client with its version (flagging an old install and offering the update), lets the
    user switch, and — when none is installed or the user wants another — guides an
    install with the OS-specific command and verifies it before returning. On a non-TTY
    run it never blocks: it declines to the first installed client (or ``None``).
    """

    @abstractmethod
    def choose(self, found: list[str], i18n: Localizer | None = None) -> str | None:
        """Settle the default client, guiding an install/update as needed.

        Args:
            found: The installed clients detected, in canonical order (may be empty).
            i18n: The localiser for the conversation; ``None`` uses the built-in one.

        Returns:
            The chosen client name, or ``None`` when none is installed and the user did
            not complete an install.
        """
