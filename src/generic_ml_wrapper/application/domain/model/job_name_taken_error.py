# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when a job name is already in use for different work."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class JobNameTakenError(DomainError, ValueError):
    """The name already belongs to a job of another kind.

    A job's name is its identity: one name, one job, and the kind is information about it
    rather than part of who it is. Two jobs may therefore never share a name — reusing one
    *within* a kind is not a collision but the point, since a job accumulates sessions and
    spend across everything it is used for. Reusing one across kinds is, and the user is
    told rather than silently handed the other job's history.
    """

    def __init__(self, job: str, kind: str, existing_kind: str) -> None:
        """Record the contested name and the two kinds contesting it.

        Args:
            job: The job name that is already taken.
            kind: The kind of work that asked for it.
            existing_kind: The kind of the job that already holds it.
        """
        self.job = job
        self.kind = kind
        self.existing_kind = existing_kind
        super().__init__("error.job.name_taken", job=job, kind=kind, existing_kind=existing_kind)
