# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The always-on directive that turns a demanded correction into a draft rule."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.rules import DIRECTIVE_TEMPLATE


class RuleCaptureDirective:
    """Renders gmlw's own instruction to the client about where a new rule belongs."""

    def render(
        self,
        *,
        environment: str,
        role: str,
        environment_dir: str,
        role_dir: str,
        template: str,
    ) -> str:
        """Render the rule-capture directive for this session's role and environment.

        The directive is gmlw's own voice to the client, injected at the head of the
        ``rules`` context section so a demanded correction becomes a draft rule in any
        session — even one with no rules yet. It names the two concrete destinations
        rather than a general one, because at the moment a rule is born exactly one
        environment and one role are active.

        Args:
            environment: The active environment's slug.
            role: The active role's slug.
            environment_dir: The environment's rules folder, as a user-readable path.
            role_dir: The role's rules folder, as a user-readable path.
            template: The rule template's text, read from the user's templates folder so
                their edits are what the model follows.

        Returns:
            The rendered directive.
        """
        return DIRECTIVE_TEMPLATE.format(
            environment=environment,
            role=role,
            environment_dir=environment_dir,
            role_dir=role_dir,
            template=template.strip(),
        )
