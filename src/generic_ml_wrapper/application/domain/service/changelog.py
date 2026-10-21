# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Read a Keep-a-Changelog file into its releases, and pick the ones a user has not seen."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.release_note import ReleaseNote
from generic_ml_wrapper.application.domain.model.update_check import parse_version

if TYPE_CHECKING:
    from collections.abc import Sequence

# A release's heading: ``## [0.12.1] - 2026-10-11``, or ``## [Unreleased]``.
_HEADING = re.compile(r"^## \[(?P<version>[^\]]+)\](?:\s+-\s+(?P<date>\S+))?\s*$")
# The link definitions closing the file: ``[0.12.1]: https://…``.
_LINK = re.compile(r"^\[[^\]]+\]:\s+\S+\s*$")


def parse_changelog(text: str) -> tuple[ReleaseNote, ...]:
    """The releases of a changelog, newest first as written; one with no entry is left out.

    Everything above the first release heading (the title, the preamble) and the link
    definitions at the bottom are not part of any release.

    Args:
        text: The changelog's Markdown.

    Returns:
        Each release that has something to say.
    """
    notes: list[ReleaseNote] = []
    heading: re.Match[str] | None = None
    body: list[str] = []
    for line in [*text.splitlines(), "## [end]"]:
        match = _HEADING.match(line)
        if match is None:
            if heading is not None and not _LINK.match(line):
                body.append(line)
            continue
        entry = "\n".join(body).strip()
        if heading is not None and entry:
            notes.append(ReleaseNote(heading["version"], heading["date"], entry))
        heading, body = match, []
    return tuple(notes)


def notes_since(notes: Sequence[ReleaseNote], seen: str, current: str) -> tuple[ReleaseNote, ...]:
    """The releases after ``seen``, up to and including ``current``.

    What a user who last saw ``seen`` has not read yet. ``Unreleased`` is never among them:
    it is not a release anyone upgraded to.

    Args:
        notes: The changelog's releases.
        seen: The last version whose notes were shown.
        current: The running version.

    Returns:
        Those releases, in the changelog's order.
    """
    after, upto = parse_version(seen), parse_version(current)
    if after is None or upto is None:
        return ()
    return tuple(
        note
        for note in notes
        if (version := parse_version(note.version)) is not None and after < version <= upto
    )
