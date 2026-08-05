# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for reading which run a launched client belongs to."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.run_handoff import RunHandoff


class RunHandoffPort(ABC):
    """Report the run a client the wrapper launched was told it belongs to.

    The other half of a seam the caller adapters already write: a launch announces the job,
    the session and the client to the process it starts, and this reads that announcement
    back when the client calls in. How the announcement travels -- environment, a file, a
    socket -- is the implementation's business and nobody else's.
    """

    @abstractmethod
    def current(self) -> RunHandoff:
        """Return the run this process was told it belongs to.

        Returns:
            The handoff; every field is ``None`` when there was no launch to speak of.
        """
