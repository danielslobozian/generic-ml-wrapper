# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outcome of a run, carrying what the exit receipt needs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartJobResult:
    """The outcome of a run, carrying what the exit receipt needs.

    Attributes:
        exit_code: The client's exit code.
        job: The job the session ran on.
        session_id: The session that ran (new or resumed).
    """

    exit_code: int
    job: str
    session_id: str
