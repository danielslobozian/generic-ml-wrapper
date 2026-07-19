# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One usage-driven, suppressible tip for the exit receipt — the feature-reveal channel.

Progressive disclosure: rather than dump every capability up front, the exit receipt reveals
one tip at a time, each shown only once. Which tips have been shown is tracked in a small
state file; ``[hints] show = false`` turns them off entirely. Best-effort — a state-file
error never breaks the receipt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.common import config, paths
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer

# The tips, in reveal order. Each is (stable id, catalogue key). The id is what's recorded
# as seen, so reordering or rewording a tip never re-shows an already-seen one.
TIPS: tuple[tuple[str, str], ...] = (
    ("resume", "hint.resume"),
    ("cost", "hint.cost"),
    ("persona", "hint.persona"),
    ("config", "hint.config"),
)


def _read_seen() -> set[str]:
    """Return the set of tip ids already shown (empty on any read error)."""
    try:
        text = (paths.STATE / "hints-seen").read_text(encoding="utf-8")
    except OSError:
        return set()
    return {line.strip() for line in text.splitlines() if line.strip()}


def _mark_seen(hint_id: str) -> None:
    """Record ``hint_id`` as shown (best-effort; a write error is logged, not raised)."""
    try:
        paths.STATE.mkdir(parents=True, exist_ok=True)
        with (paths.STATE / "hints-seen").open("a", encoding="utf-8") as handle:
            handle.write(f"{hint_id}\n")
    except OSError as error:
        log.debug(f"could not record hint {hint_id!r} as seen: {error}")


def next_hint(loc: Localizer) -> str | None:
    """Return the next unseen tip's text (marking it seen), or ``None``.

    Args:
        loc: The localiser to render the tip through.

    Returns:
        The localised tip, or ``None`` when hints are off or every tip has been shown.
    """
    if not config.hints_show():
        return None
    seen = _read_seen()
    for hint_id, key in TIPS:
        if hint_id not in seen:
            _mark_seen(hint_id)
            return loc.t(key)
    return None
