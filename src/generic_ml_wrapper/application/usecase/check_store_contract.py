# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The CheckStoreContractUseCase use case: the build and its migrations must agree."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.store_contract_outdated_error import (
    StoreContractOutdatedError,
)
from generic_ml_wrapper.application.port.inbound.check_store_contract import (
    CheckStoreContractUseCase,
)
from generic_ml_wrapper.application.port.outbound.store_migration import CURRENT_SCHEMA_VERSION

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.store_migration import StoreMigrationPort


class CheckStoreContractService(CheckStoreContractUseCase):
    """Compare what this build requires against what its migrations can deliver."""

    def __init__(self, migration: StoreMigrationPort) -> None:
        """Wire the use case to the migration whose reach it checks.

        Args:
            migration: Reports the highest version its lineage can bring a store to.
        """
        self._migration = migration

    def execute(self) -> None:
        """Raise when the shipped lineage stops short of the version this build needs.

        Raises:
            StoreContractOutdatedError: If the two disagree.
        """
        implemented = self._migration.implemented_version()
        if implemented < CURRENT_SCHEMA_VERSION:
            raise StoreContractOutdatedError(implemented, CURRENT_SCHEMA_VERSION)
