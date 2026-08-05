# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``RunHandoffPort`` over the environment the caller adapters export.

Each caller exports ``GMLW_JOB``, ``GMLW_SESSION`` and ``GMLW_CLIENT`` into the client it
launches, so anything the client then invokes -- the status line -- inherits them. This is
the read side of that, and it lives beside the callers that write it so the two names stay
together.
"""

from __future__ import annotations

import os

from generic_ml_wrapper.application.domain.model.run_handoff import RunHandoff
from generic_ml_wrapper.application.port.outbound.run_handoff import RunHandoffPort

_JOB = "GMLW_JOB"
_SESSION = "GMLW_SESSION"
_CLIENT = "GMLW_CLIENT"


class EnvironmentRunHandoff(RunHandoffPort):
    """Read the run the launching caller announced through the environment."""

    def current(self) -> RunHandoff:
        """Return what the launch exported, with ``None`` for anything absent."""
        return RunHandoff(
            job=os.environ.get(_JOB),
            session_id=os.environ.get(_SESSION),
            client=os.environ.get(_CLIENT),
        )
