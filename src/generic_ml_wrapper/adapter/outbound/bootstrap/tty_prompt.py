# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A shared terminal chooser: one numbered, optionally icon-tagged single choice.

One implementation behind every first-run picker (client, persona, …). It writes the
list to stderr and reads a line from stdin, so stdout stays clean for ``--json`` and
view output, and it declines (returns ``None``) whenever either end is not a TTY — a
piped or automated run never blocks. The fixed fragments (the pick line, the range
error) are localised through a :class:`Localizer`; the caller passes already-localised
choices, so this stays dependency-free and framework-free.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from generic_ml_wrapper.common.i18n import Localizer


@dataclass(frozen=True)
class Choice:
    """One selectable option: the value returned, its label, and optional trimmings.

    Attributes:
        value: What :func:`choose_number` returns when this option is picked.
        label: The human label shown after the number.
        icon: An optional leading glyph (emoji); rendered only when non-empty.
        description: An optional dim suffix shown after an em dash.
    """

    value: str
    label: str
    icon: str = ""
    description: str = ""


def choose_number(
    header: str,
    choices: Sequence[Choice],
    i18n: Localizer,
    *,
    default: int | None = None,
    skippable: bool = False,
) -> str | None:
    """Offer ``choices`` as a numbered list and return the picked value, or ``None``.

    Writes to ``sys.stderr`` and reads from ``sys.stdin`` (both resolved at call time),
    so a non-TTY run declines with ``None`` rather than blocking.

    Args:
        header: The already-localised question line printed above the options.
        choices: The options, in display order.
        i18n: The localiser supplying the fixed prompt fragments.
        default: Index picked on an empty line; ``None`` means empty does not default.
        skippable: When true, an empty line returns ``None`` (skip) instead.

    Returns:
        The chosen choice's ``value``; ``None`` when skipped, at end of input, or when
        there are no choices or no terminal to prompt on.
    """
    if not choices or not (sys.stdin.isatty() and sys.stderr.isatty()):
        return None
    print(header, file=sys.stderr)
    for index, choice in enumerate(choices, start=1):
        icon = f"{choice.icon}  " if choice.icon else ""
        description = f" — {choice.description}" if choice.description else ""
        print(f"  {index}) {icon}{choice.label}{description}", file=sys.stderr)
    rng = f"1-{len(choices)}"
    if skippable:
        pick = i18n.t("prompt.pick_skippable", range=rng)
    elif default is not None:
        pick = i18n.t("prompt.pick_default", range=rng, default=default + 1)
    else:
        pick = i18n.t("prompt.pick_plain", range=rng)
    while True:
        reply = _read(pick)
        if reply is None:
            return None
        reply = reply.strip()
        if not reply:
            if skippable:
                return None
            if default is not None:
                return choices[default].value
            continue
        if reply.isdigit() and 1 <= int(reply) <= len(choices):
            return choices[int(reply) - 1].value
        print("  " + i18n.t("prompt.not_in_range", reply=reply, range=rng), file=sys.stderr)


def emit(*lines: str) -> None:
    """Write already-localised narration ``lines`` to the prompt's stderr.

    Used by richer conversations (the guided client setup) to print status around the
    numbered prompts, on the same stream :func:`choose_number` writes to, so stdout
    stays clean and a non-TTY run stays silent. Skipped entirely without a terminal.

    Args:
        lines: The lines to print, each on its own row.
    """
    if not sys.stderr.isatty():
        return
    for line in lines:
        print(line, file=sys.stderr)


def _read(prompt: str) -> str | None:
    """Write ``prompt`` (no newline) to stderr and read one line from stdin.

    Returns:
        The line read, or ``None`` at end of input.
    """
    print(prompt, end="", file=sys.stderr, flush=True)
    line = sys.stdin.readline()
    return None if line == "" else line
