# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Offer the guided-vs-quick authoring choice on a terminal, declining otherwise."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.tty_prompt import Choice, choose_number

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer

GUIDED = "guided"
QUICK = "quick"


class TtyGuidedChooser:
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

    def choose(self, i18n: Localizer | None = None) -> str | None:
        """Offer the choice and return ``"guided"``, ``"quick"``, or ``None``.

        Args:
            i18n: The localiser for the prompt; ``None`` uses the construction-time one.

        Returns:
            ``"guided"`` or ``"quick"``; ``None`` when there is no terminal to prompt on.
        """
        loc = i18n or self._i18n
        return choose_number(
            loc.t("guided.header"),
            [
                Choice(value=GUIDED, label=loc.t("guided.choice_guided")),
                Choice(value=QUICK, label=loc.t("guided.choice_quick")),
            ],
            loc,
            default=0,  # Enter → the guided experience
        )
