# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Build the opening message that points a fileless-prompt agent at its context.

Clients without a system-prompt flag (cursor-agent, codex) receive their compiled
operating context by being told, in the opening message, to read a file first.
"""

from __future__ import annotations


def read_first_opening(context_path: str, kickoff: str | None = None) -> str:
    """Build an opening message telling the agent to read its context file first.

    Args:
        context_path: The path to the compiled operating-context file.
        kickoff: An opening user message to append after the instruction, or ``None``.

    Returns:
        The opening message.
    """
    preamble = (
        f"Your operating context for this session is in the file:\n{context_path}\n"
        "Read that file in full FIRST — it is your instructions, profile, rules, and "
        "the workflow steps — then proceed as it says."
    )
    return f"{preamble}\n\n{kickoff}" if kickoff else preamble
