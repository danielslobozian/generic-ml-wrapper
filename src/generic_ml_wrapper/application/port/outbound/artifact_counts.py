# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""How many files a job or session holds outside the ledger."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactCounts:
    """How many files a job or session holds outside the ledger.

    Attributes:
        contexts: Compiled-context files (one per session that launched fresh).
        transcript_calls: Recorded transcript files (three per metered call, when the
            opt-in transcript is on; ``0`` when it never was).
    """

    contexts: int
    transcript_calls: int

    def __add__(self, other: ArtifactCounts) -> ArtifactCounts:
        """Sum two counts, so a job's footprint folds over its sessions'."""
        return ArtifactCounts(
            contexts=self.contexts + other.contexts,
            transcript_calls=self.transcript_calls + other.transcript_calls,
        )
