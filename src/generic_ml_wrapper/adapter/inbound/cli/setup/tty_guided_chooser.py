# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Offer the guided-vs-quick authoring choice on a terminal, declining otherwise."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.cli.setup.tty_prompt import Choice, choose_number
from generic_ml_wrapper.application.domain.model.authoring_mode import AuthoringMode

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
        MessageSourceAccessor,
    )


class TtyGuidedChooser:
    """Ask, at authoring start, whether to use the guided experience or the quick one.

    Presented on every interactive ``workflow new`` / ``edit`` when neither ``--guided``
    nor ``--quick`` was given. Enter picks the guided experience (creation is the part
    worth investing in); off a terminal there is no one to ask, so it declines with
    ``None`` and the caller falls back to the lean interview.
    """

    def __init__(self, message_source: MessageSourceAccessor) -> None:
        """Bind the chooser to a message source for its prompt text.

        Args:
            message_source: The message source supplying the header and the two option labels.
        """
        self._message_source = message_source

    def choose(
        self, modes: list[AuthoringMode], message_source: MessageSourceAccessor | None = None
    ) -> AuthoringMode | None:
        """Offer the modes and return the chosen one, or ``None``.

        Which modes exist is the application's answer, not this widget's -- it used to
        name GUIDED and QUICK itself, which is knowledge a terminal has no business
        holding and no way to keep current. Each mode's label comes from its own code, so
        a third one needs a catalogue entry and nothing else.

        Args:
            modes: The offered modes, in the order they should be presented.
            message_source: The message source for the prompt; ``None`` uses the
                construction-time one.

        Returns:
            The chosen :class:`AuthoringMode`; ``None`` when there is no terminal to
            prompt on, and so nobody to ask.
        """
        message_source = message_source or self._message_source
        picked = choose_number(
            message_source.get_message("guided.header"),
            [
                Choice(
                    value=mode.value,
                    label=message_source.get_message(f"guided.choice_{mode.value}"),
                )
                for mode in modes
            ],
            message_source,
            default=0,  # Enter → the first offered mode
        )
        return AuthoringMode(picked) if picked is not None else None
