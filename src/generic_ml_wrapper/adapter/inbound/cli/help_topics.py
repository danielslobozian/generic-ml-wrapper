# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``gmlw help <topic>`` — short explainers for the core concepts, from the catalogue.

Progressive disclosure: the bare index lists *what* the commands are; these topics explain
the *concepts behind* them (job vs workflow, start vs run, personas, cost). Each topic's
summary and body live in the i18n catalogue, so the help speaks the active language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer

# The topics, in display order. Each name maps to catalogue keys ``help.<name>.summary``
# (the one-line listing) and ``help.<name>.body`` (the full explainer).
TOPICS: tuple[str, ...] = ("job-vs-workflow", "start-vs-run", "personas", "cost")


def _key(topic: str) -> str:
    """Return the catalogue key stem for a topic (dashes → underscores)."""
    return topic.replace("-", "_")


def render_topic_list(loc: Localizer) -> str:
    """Render the list of help topics with their one-line summaries.

    Args:
        loc: The localiser to render through.

    Returns:
        The listing text (no trailing newline).
    """
    width = max(len(topic) for topic in TOPICS)
    lines = [loc.t("help.header"), ""]
    for topic in TOPICS:
        summary = loc.t(f"help.{_key(topic)}.summary")
        lines.append(loc.t("help.topic_line", topic=f"{topic:<{width}}", summary=summary))
    lines += ["", loc.t("help.footer")]
    return "\n".join(lines)


def render_topic(loc: Localizer, topic: str) -> str | None:
    """Render one topic's explainer, or ``None`` when the topic is unknown.

    Args:
        loc: The localiser to render through.
        topic: The requested topic name.

    Returns:
        The topic body, or ``None`` if ``topic`` is not a known topic.
    """
    if topic not in TOPICS:
        return None
    return loc.t(f"help.{_key(topic)}.body")
