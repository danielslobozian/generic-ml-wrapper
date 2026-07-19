# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Offer the runnable workflows on a terminal, declining without one.

The pre-launch filler for ``gmlw run`` invoked with no workflow: it lists the authored
workflows and returns the picked name. Like every gmlw picker it writes to stderr, reads
from stdin, and declines (returns ``None``) whenever there is no terminal — so a piped or
scripted ``gmlw run`` never blocks and a full-argv ``gmlw run <workflow>`` never reaches
it at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.tty_prompt import Choice, choose_number

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer


class TtyWorkflowChooser:
    """Offer the runnable workflows at an interactive terminal; decline otherwise.

    An empty line (or no terminal) declines with ``None``, leaving the caller to guide
    the user toward naming a workflow explicitly.
    """

    def __init__(self, i18n: Localizer) -> None:
        """Bind the chooser to a localiser for its prompt text.

        Args:
            i18n: The localiser supplying the header and fixed prompt fragments.
        """
        self._i18n = i18n

    def choose(self, names: list[str], i18n: Localizer | None = None) -> str | None:
        """Offer ``names`` and return the chosen workflow, or ``None`` to decline.

        Args:
            names: The runnable workflow names to offer, in display order.
            i18n: The localiser for the prompt; ``None`` uses the construction-time one.

        Returns:
            The chosen workflow name, or ``None`` when skipped or there is no terminal.
        """
        loc = i18n or self._i18n
        return choose_number(
            loc.t("run.pick_header"),
            [Choice(value=name, label=name) for name in names],
            loc,
            skippable=True,
        )
