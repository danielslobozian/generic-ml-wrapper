# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the tags a user puts on jobs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


class JobTagStorePort(ABC):
    """Read and change which tags each job carries.

    A tag is the user's own grouping -- a sprint, an epic -- and a job can carry several.
    Adding a tag a job already has, or removing one it does not, changes nothing.
    """

    @abstractmethod
    def tags_by_job(self) -> dict[str, tuple[str, ...]]:
        """Return every tagged job's tags, each sorted; untagged jobs are absent."""

    @abstractmethod
    def add(self, job: str, tags: Iterable[str]) -> None:
        """Put ``tags`` on ``job``, keeping the ones it already has.

        Args:
            job: The job to tag.
            tags: Validated, lowercased tag names.
        """

    @abstractmethod
    def remove(self, job: str, tags: Iterable[str]) -> None:
        """Take ``tags`` off ``job``.

        Args:
            job: The job to untag.
            tags: Validated, lowercased tag names.
        """
