# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The learned notebook: the user-owned, portable store the client mirrors into.

"Learned" is what the AI notices about how the user works. Each client keeps its own
private memory of that — but siloed, and lost the moment the user switches tool. gmlw
turns it into an *indication*: a shared notebook the user owns (a plain file under
``profile/me``), composed into every client's context (see the ``me.learned`` source),
so what one tool learns, they all inherit. This module holds the two invariants of that
system — the notebook's shape and the directive that asks the client to write to it.
"""

from __future__ import annotations

# The two headings the notebook is organised under. The heading is the polarity: a
# note's home says whether it is something to carry or something to avoid — no schema.
POSITIVE_HEADING = "## What follows you"
NEGATIVE_HEADING = "## What to avoid"

# Seeded once into ``profile/me/learned.md``. A human-facing header (this is the user's
# file) plus the two empty sections the client appends to.
NOTEBOOK_TEMPLATE = f"""\
# Learned

What your AI tools notice about how you work — kept in your own file and shared across
every tool, so what one learns, they all inherit. Yours to read, edit, or trim.

{POSITIVE_HEADING}

{NEGATIVE_HEADING}
"""

# Injected as the head of the ``me.learned`` context section (gmlw's voice to the client).
# Folds in the field's guidance: durable facts only, one self-contained line, no one-offs,
# secrets, or the assistant's own suggestions; negatives are first-class; supersede on
# reversal; the file is the user's to edit. The path is the fixed ``~/.gmlw`` location.
# Implicitly concatenated so the source wraps while the injected text flows.
CAPTURE_DIRECTIVE = (
    "The user keeps a portable notebook of how they work at "
    "~/.gmlw/profile/me/learned.md. gmlw reads it into every AI tool they use, so "
    "whatever is written there follows them across Claude, Cursor, codex, and the rest "
    "— it is theirs, not any one tool's."
    "\n\n"
    "When you learn something durable about how this user works — a preference, a "
    "convention, a standing decision, a way they like things done — append a short, "
    f'plain-language line under "{POSITIVE_HEADING}". Record the negatives too, under '
    f'"{NEGATIVE_HEADING}": what they have asked you not to do, and what they have '
    "declined to keep — those are as valuable as the positives, and no tool usually "
    "keeps them."
    "\n\n"
    "Keep each note to one self-contained line, in their words. Only durable facts "
    "about the user, added with clear intent — not one-off task details, not secrets, "
    "not your own suggestions. If something here is now wrong, correct or remove that "
    "line rather than piling on a contradiction. It is the user's file: they can edit "
    "or delete anything."
)
