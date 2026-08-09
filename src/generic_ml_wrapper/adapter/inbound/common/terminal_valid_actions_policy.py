# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys

from generic_ml_wrapper.adapter.inbound.common.view.terminal_action_verdict import (
    TerminalActionVerdict,
)

HANDOVER_COMMANDS = frozenset({"start", "run"})
HANDOVER_WORKFLOW_ACTIONS = frozenset({"new", "edit", "resume"})
WORKFLOW_COMMAND = "workflow"
NOT_INTERACTIVE_MESSAGE_CODE = "main.not_interactive"


class TerminalValidActionsPolicy:
    @staticmethod
    def check(arguments: list[str]) -> TerminalActionVerdict:
        """Decide whether the requested action is allowed in the terminal it was asked in.

        Args:
            arguments: The launch arguments with the program name already stripped, so an
                empty list means the user asked for the application itself.

        Returns:
            A refusal carrying the message code to show, or an allowance carrying none.
        """
        if (
            not TerminalValidActionsPolicy.is_interactive()
            and TerminalValidActionsPolicy.needs_the_terminal(arguments)
        ):
            return TerminalActionVerdict(allowed=False, message_code=NOT_INTERACTIVE_MESSAGE_CODE)

        return TerminalActionVerdict(allowed=True)

    @staticmethod
    def is_interactive() -> bool:
        """Whether a person is present.

        Returns:
            ``True`` only when both ends are a terminal — either one redirected means the
            output is going somewhere no keystroke can answer.
        """
        return sys.stdin.isatty() and sys.stdout.isatty()

    @staticmethod
    def needs_the_terminal(arguments: list[str]) -> bool:
        """Whether the requested command takes the terminal over.

        Returns:
            ``True`` for the menu and for anything that hands the screen to a client,
            which between them are the actions a pipe cannot serve.
        """
        if not arguments:
            return True
        if arguments[0] in HANDOVER_COMMANDS:
            return True
        return arguments[0] == WORKFLOW_COMMAND and TerminalValidActionsPolicy.is_handover_workflow(
            arguments
        )

    @staticmethod
    def is_handover_workflow(arguments: list[str]) -> bool:
        """Whether a ``workflow`` command names one of the actions that opens a session.

        Returns:
            ``True`` for the authoring verbs; ``False`` for the ones that only read or
            move files.
        """
        return len(arguments) > 1 and arguments[1] in HANDOVER_WORKFLOW_ACTIONS
