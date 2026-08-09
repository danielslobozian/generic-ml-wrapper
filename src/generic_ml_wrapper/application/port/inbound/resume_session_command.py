# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to reopen a session that has already run."""

from __future__ import annotations

from dataclasses import dataclass

from generic_ml_wrapper.application.domain.model.session import Session


@dataclass(frozen=True)
class ResumeSessionCommand:
    """A request to reopen a session that has already run.

    Attributes:
        session: The session to reopen, as the job aggregate handed it back. It carries
            its own client and its own folder, so neither is asked for here.
        client_args: Passthrough launch arguments replacing whatever is configured for
            the session's client; ``None`` uses the configured value.
    """

    session: Session
    client_args: str | None = None
