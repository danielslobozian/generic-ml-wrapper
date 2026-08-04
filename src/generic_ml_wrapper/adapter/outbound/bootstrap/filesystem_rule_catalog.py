# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``RuleCatalogPort`` backed by the environment and role folders under ``~/.gmlw``.

Reads the same ``<axis>/<slug>/rules/*.rule.md`` files the compile path composes, but for
*browsing* rather than injection: drafts are included and flagged instead of skipped, since
the question a listing answers is "what is actually live, and what am I still sitting on?".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.axis_kind import AxisKind
from generic_ml_wrapper.application.domain.model.rule_axis import RuleAxis
from generic_ml_wrapper.application.domain.model.rule_group import RuleGroup
from generic_ml_wrapper.application.domain.model.rule_summary import RuleSummary
from generic_ml_wrapper.application.domain.service import rule_parser
from generic_ml_wrapper.application.port.outbound.rule_catalog import RuleCatalogPort

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.axis_catalog import AxisCatalogPort

_RULE_GLOB = "*.rule.md"
_SUFFIX = ".rule.md"
# Environments before roles: the place's constraints outrank the craft's preferences, and
# the browser lists them in the same order the context composes them as authoritative.
_AXES = ((RuleAxis.ENVIRONMENT, AxisKind.ENVIRONMENT), (RuleAxis.ROLE, AxisKind.ROLE))


class FilesystemRuleCatalog(RuleCatalogPort):
    """List the populated rule groups by walking each axis's slug-folders."""

    def __init__(self, home: Path, axes: AxisCatalogPort) -> None:
        """Bind the catalogue to the runtime home and the axis catalogue.

        Args:
            home: The ``~/.gmlw`` root the axis folders live under.
            axes: Supplies each axis's slugs and their human labels, so the browser and
                the config switchers name an environment or role identically.
        """
        self._home = home
        self._axes = axes

    def groups(self) -> tuple[RuleGroup, ...]:
        """Return every environment and role holding at least one rule.

        Returns:
            The populated groups, environments first, each sorted by slug.
        """
        found: list[RuleGroup] = []
        for axis, kind in _AXES:
            for selection in self._axes.list(kind):
                rules = self._rules(self._rules_dir(kind, selection.slug))
                if rules:
                    found.append(
                        RuleGroup(
                            axis=axis,
                            slug=selection.slug,
                            label=selection.label or selection.slug,
                            rules=rules,
                        )
                    )
        return tuple(found)

    def _rules_dir(self, kind: AxisKind, slug: str) -> Path:
        """The rules folder for one axis slug."""
        root = "environments" if kind is AxisKind.ENVIRONMENT else "profile/roles"
        return self._home / root / slug / "rules"

    @staticmethod
    def _rules(directory: Path) -> tuple[RuleSummary, ...]:
        """Summarise every rule in a folder, skipping any file that cannot be read."""
        if not directory.is_dir():
            return ()
        summaries: list[RuleSummary] = []
        for path in sorted(directory.glob(_RULE_GLOB)):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue  # one unreadable rule never breaks the listing
            summaries.append(
                RuleSummary(
                    slug=path.name[: -len(_SUFFIX)],
                    rule=rule_parser.field(text, "Rule"),
                    when=rule_parser.field(text, "When"),
                    strength=rule_parser.field(text, "Strength"),
                    draft=rule_parser.is_draft(text),
                    path=str(path),
                )
            )
        return tuple(summaries)
