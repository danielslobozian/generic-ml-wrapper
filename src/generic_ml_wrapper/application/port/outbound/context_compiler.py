# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for composing a session's operating context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.context_source import CompileMode


class ContextCompilerPort(ABC):
    """Compose what a new session is told before its first word."""

    @abstractmethod
    def compile(
        self, mode: CompileMode, job: str | None = None, attachment: str | None = None
    ) -> str:
        """Compile a run's operating context for a mode.

        The context opens with the session snapshot — the active environment, role,
        persona and job — then the activation matrix for the mode selects which
        cross-cutting sources (persona, profile, learned, company, rules) are composed
        and whether each is compressed.

        Args:
            mode: The compile mode (default/attachment).
            job: The job this session runs on, for the snapshot; ``None`` leaves the
                snapshot's ``job_name`` empty rather than omitting the block.
            attachment: An attachment's section, placed after gmlw's own groups as
                written (never compressed), or ``None``.

        Returns:
            The composed context (the snapshot, then the active sources).
        """
