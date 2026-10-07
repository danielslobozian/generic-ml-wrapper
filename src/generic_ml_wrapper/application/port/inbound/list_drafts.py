# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the unfinished authoring drafts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.draft import Draft


class ListDrafts(ABC):
    """List the authoring drafts still on disk."""

    @abstractmethod
    def execute(self) -> list[Draft]:
        """List the drafts, newest first.

        A draft is an authoring interview that never deployed. Until this listing
        existed they accumulated invisibly: the user was told the path on the way out
        and had no way to see or reopen one afterwards.

        Returns:
            The drafts, newest first (empty when there are none).
        """
