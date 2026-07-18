# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``ClientChooserPort`` that prompts on a terminal, declining when there is none."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.tty_prompt import Choice, choose_number
from generic_ml_wrapper.application.port.outbound.client_chooser import ClientChooserPort

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer


class TtyClientChooser(ClientChooserPort):
    """Ask the user to pick a default client, but only at an interactive terminal.

    Delegates the prompt mechanics to :func:`choose_number`: the list is written to
    stderr and read from stdin, an empty line takes the first candidate, and a non-TTY
    (piped or automated) run declines with ``None`` so it never blocks.
    """

    def __init__(self, i18n: Localizer) -> None:
        """Bind the chooser to a localiser for its prompt text.

        Args:
            i18n: The localiser supplying the header and fixed prompt fragments.
        """
        self._i18n = i18n

    def choose(self, candidates: list[str], i18n: Localizer | None = None) -> str | None:
        """Prompt for a default client, defaulting to the first on an empty line.

        Args:
            candidates: The installed clients to choose among (two or more).
            i18n: The localiser for the prompt; ``None`` uses the construction-time one.

        Returns:
            The chosen client, or ``None`` when there is no terminal to prompt on.
        """
        loc = i18n or self._i18n
        return choose_number(
            loc.t("init.client.header"),
            [Choice(value=name, label=name) for name in candidates],
            loc,
            default=0,
        )
