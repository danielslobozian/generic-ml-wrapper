# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for putting tags on a job and taking them off."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class TagJobs(ABC):
    """Change which tags a job carries.

    Each operation takes raw tag names, validates them all before changing anything, and
    returns the job's tags as they now stand, sorted.
    """

    @abstractmethod
    def add(self, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        """Put ``tags`` on ``job``, keeping the ones it has.

        Raises:
            NoSuchJobError: If the job has no recorded activity.
            IdentifierError: If any tag is not a valid tag name.
        """

    @abstractmethod
    def remove(self, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        """Take ``tags`` off ``job``; a tag it does not carry is ignored.

        Raises:
            NoSuchJobError: If the job has no recorded activity.
            IdentifierError: If any tag is not a valid tag name.
        """

    @abstractmethod
    def replace(self, job: str, tags: Sequence[str]) -> tuple[str, ...]:
        """Make ``tags`` exactly the job's tags (none clears them).

        Raises:
            NoSuchJobError: If the job has no recorded activity.
            IdentifierError: If any tag is not a valid tag name.
        """
