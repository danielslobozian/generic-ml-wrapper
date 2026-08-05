# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for refusing to run against a store this build cannot reach."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CheckStoreContractUseCase(ABC):
    """Verify that the shipped migrations reach the schema this build writes through."""

    @abstractmethod
    def execute(self) -> None:
        """Raise if the build's code and its migration files disagree.

        The comparison is the application's to make, not the caller's: which version this
        build requires and which one the shipped lineage reaches are both facts about the
        application, and a caller that compared them itself would need to know both.

        Raises:
            StoreContractOutdatedError: If the shipped migrations stop short of the
                version this build requires. The realistic cause is packaging -- the
                migration files failing to reach the installed distribution -- which is
                exactly the case where failing at the first command beats creating an
                empty store and calling it success.
        """
