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

from generic_ml_wrapper.adapter.inbound.cli.setup.tty_prompt import Choice, choose_number

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
        MessageSourceAccessor,
    )


class TtyWorkflowChooser:
    """Offer the runnable workflows at an interactive terminal; decline otherwise.

    An empty line (or no terminal) declines with ``None``, leaving the caller to guide
    the user toward naming a workflow explicitly.
    """

    def __init__(self, message_source: MessageSourceAccessor) -> None:
        """Bind the chooser to a message source for its prompt text.

        Args:
            message_source: The message source supplying the header and fixed prompt fragments.
        """
        self._message_source = message_source

    def choose(
        self, names: list[str], message_source: MessageSourceAccessor | None = None
    ) -> str | None:
        """Offer ``names`` and return the chosen workflow, or ``None`` to decline.

        Args:
            names: The runnable workflow names to offer, in display order.
            message_source: The message source for the prompt; ``None`` uses the
                construction-time one.

        Returns:
            The chosen workflow name, or ``None`` when skipped or there is no terminal.
        """
        message_source = message_source or self._message_source
        return choose_number(
            message_source.get_message("run.pick_header"),
            [Choice(value=name, label=name) for name in names],
            message_source,
            skippable=True,
        )
