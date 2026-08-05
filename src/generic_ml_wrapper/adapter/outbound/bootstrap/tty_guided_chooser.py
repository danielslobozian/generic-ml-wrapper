# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Offer the guided-vs-quick authoring choice on a terminal, declining otherwise."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.tty_prompt import Choice, choose_number
from generic_ml_wrapper.application.domain.model.authoring_mode import AuthoringMode
from generic_ml_wrapper.application.port.outbound.guided_chooser import GuidedChooserPort

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.service.localizer import Localizer


class TtyGuidedChooserAdapter(GuidedChooserPort):
    """Ask, at authoring start, whether to use the guided experience or the quick one.

    Presented on every interactive ``workflow new`` / ``edit`` when neither ``--guided``
    nor ``--quick`` was given. Enter picks the guided experience (creation is the part
    worth investing in); off a terminal there is no one to ask, so it declines with
    ``None`` and the caller falls back to the lean interview.
    """

    def __init__(self, i18n: Localizer) -> None:
        """Bind the chooser to a localiser for its prompt text.

        Args:
            i18n: The localiser supplying the header and the two option labels.
        """
        self._i18n = i18n

    def choose(self, i18n: Localizer | None = None) -> AuthoringMode | None:
        """Offer the choice and return the chosen mode, or ``None``.

        Args:
            i18n: The localiser for the prompt; ``None`` uses the construction-time one.

        Returns:
            The chosen :class:`AuthoringMode`; ``None`` when there is no terminal to
            prompt on, and so nobody to ask.
        """
        loc = i18n or self._i18n
        picked = choose_number(
            loc.t("guided.header"),
            [
                Choice(value=AuthoringMode.GUIDED.value, label=loc.t("guided.choice_guided")),
                Choice(value=AuthoringMode.QUICK.value, label=loc.t("guided.choice_quick")),
            ],
            loc,
            default=0,  # Enter → the guided experience
        )
        return AuthoringMode(picked) if picked is not None else None
