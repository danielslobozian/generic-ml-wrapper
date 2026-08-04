# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when a job cannot be removed because one of its sessions is running."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class JobRunningError(DomainError, RuntimeError):
    """At least one of the job's sessions has a live client.

    The job is refused as a whole: which session is running is not asked, because the
    answer is not needed and finding it would mean listing the job's sessions and testing
    each -- with a gap between the test and the delete in which another could start. The
    shared lock every running session holds on its job answers it in one claim.
    """

    def __init__(self, job: str) -> None:
        """Name the job that has a running session.

        Args:
            job: The job being removed.
        """
        self.job = job
        super().__init__("error.job.running", job=job)
