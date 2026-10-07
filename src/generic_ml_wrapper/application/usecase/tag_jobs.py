# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The TagJobs use case: put tags on a recorded job, or take them off."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.identifiers import TagName
from generic_ml_wrapper.application.port.inbound.delete_sessions import NoSuchJobError
from generic_ml_wrapper.application.port.inbound.tag_jobs import TagJobs

if TYPE_CHECKING:
    from collections.abc import Sequence

    from generic_ml_wrapper.application.port.outbound.job_tag_store import JobTagStorePort
    from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort


class TagJobsUseCase(TagJobs):
    """Validate, then change a job's tags through the tag store."""

    def __init__(self, store: SessionStorePort, tags: JobTagStorePort) -> None:
        """Wire the use case to the jobs it may tag and where tags are kept.

        Args:
            store: Which jobs exist -- only a job with recorded activity can be tagged,
                the same jobs ``gmlw jobs`` lists.
            tags: Where the tags are read and written.
        """
        self._store = store
        self._tags = tags

    def add(self, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        """Put ``tags`` on ``job``, keeping the ones it has."""
        names = self._validate(job, tags)
        self._tags.add(job, names)
        return self._current(job)

    def remove(self, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        """Take ``tags`` off ``job``."""
        names = self._validate(job, tags)
        self._tags.remove(job, names)
        return self._current(job)

    def replace(self, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        """Make ``tags`` exactly the job's tags."""
        wanted = set(self._validate(job, tags))
        held = set(self._current(job))
        self._tags.remove(job, sorted(held - wanted))
        self._tags.add(job, sorted(wanted - held))
        return self._current(job)

    def _validate(self, job: str, tags: Sequence[str]) -> list[str]:
        """Check the job exists and every tag is valid, before anything is written."""
        if job not in self._store.jobs():
            raise NoSuchJobError("error.job.not_found", job=job)
        return sorted({TagName(tag) for tag in tags})

    def _current(self, job: str) -> tuple[str, ...]:
        return self._tags.tags_by_job().get(job, ())
