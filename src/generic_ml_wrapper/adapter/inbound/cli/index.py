# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The grouped capability index shown for a bare ``gmlw`` on an initialised install.

Discovery lives in the thin surface *around* a run (the wrapper cedes the screen to the
client), so a bare ``gmlw`` reveals the capabilities grouped by intent — **launch /
inspect / author** — rather than dumping the flat argparse view (still available via
``--help``). Every listing ends with a next-action footer pointing at ``gmlw help``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer

# Each group is (label_key, rows); each row is (literal command, description key). The
# commands are literal invocations (not localised); their descriptions render from the
# catalogue. Kept curated, not a mirror of every flag — that is what --help is for.
_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "index.group.launch",
        (
            ("gmlw <job>", "index.desc.job"),
            ("gmlw start <job>", "index.desc.start"),
            ("gmlw start <job> -w <workflow>", "index.desc.run_workflow"),
            ("gmlw run <workflow>", "index.desc.run"),
        ),
    ),
    (
        "index.group.inspect",
        (
            ("gmlw jobs", "index.desc.jobs"),
            ("gmlw sessions <job>", "index.desc.sessions"),
            ("gmlw export <job>", "index.desc.export"),
            ("gmlw config list", "index.desc.config"),
        ),
    ),
    (
        "index.group.author",
        (
            ("gmlw workflow new <name>", "index.desc.workflow_new"),
            ("gmlw workflow list", "index.desc.workflow_list"),
            ("gmlw persona list", "index.desc.persona"),
            ("gmlw plugins list", "index.desc.plugins"),
        ),
    ),
)


def render_index(loc: Localizer) -> str:
    """Render the grouped capability index in the active language.

    Args:
        loc: The localiser to render through.

    Returns:
        The index text (no trailing newline): a tagline, the grouped commands, and a
        next-action footer.
    """
    width = max(len(command) for _, rows in _GROUPS for command, _ in rows)
    lines = [loc.t("index.tagline"), ""]
    for label_key, rows in _GROUPS:
        lines.append(loc.t(label_key))
        lines += [
            loc.t("index.row", command=f"{command:<{width}}", description=loc.t(desc_key))
            for command, desc_key in rows
        ]
        lines.append("")
    lines.append(loc.t("index.footer"))
    return "\n".join(lines)
