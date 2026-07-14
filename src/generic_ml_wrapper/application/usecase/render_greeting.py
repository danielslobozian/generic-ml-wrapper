# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The RenderGreeting use case: compose the free host greeting from live facts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.service.greeting import (
    daypart,
    render_greeting,
    repo_note,
)
from generic_ml_wrapper.application.port.inbound.render_greeting import RenderGreeting

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort
    from generic_ml_wrapper.application.port.outbound.workspace import WorkspaceInspectorPort
    from generic_ml_wrapper.common.config import CompanionSettings


class RenderGreetingUseCase(RenderGreeting):
    """Fill the selected persona's greeting template from the clock, name, and git.

    Free — no tokens: it is composed locally and printed at launch, never sent to a
    model. Off (``None``) unless a persona is selected and carries a greeting.
    """

    def __init__(
        self,
        *,
        personas: PersonaSourcePort,
        companion: Callable[[], CompanionSettings],
        workspace: WorkspaceInspectorPort,
        clock: Callable[[], datetime],
        username: Callable[[], str],
    ) -> None:
        """Wire the use case to its persona source and fact providers.

        Args:
            personas: The source the selected persona (and its greeting) is read from.
            companion: Resolves the ``[companion]`` settings (selected persona, name).
            workspace: Reports the git repo/branch for the greeting's repo clause.
            clock: Returns the current local time, for the time-of-day word.
            username: Returns the OS user name, the fallback when no name is configured.
        """
        self._personas = personas
        self._companion = companion
        self._workspace = workspace
        self._clock = clock
        self._username = username

    def execute(self) -> str | None:
        """Compose the greeting, or ``None`` when the companion is off.

        Returns:
            The rendered greeting, or ``None`` when no persona is selected or the
            selected persona is unknown or has no greeting.
        """
        settings = self._companion()
        if settings.persona is None:
            return None
        persona = self._personas.get(settings.persona)
        if persona is None or not persona.greeting.strip():
            return None
        name = settings.name or self._username()
        return render_greeting(
            persona.greeting,
            name=name,
            daypart=daypart(self._clock().hour),
            repo_note=repo_note(self._workspace.inspect()),
        )
