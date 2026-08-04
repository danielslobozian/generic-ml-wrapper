# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when the store was written by a newer build than this one."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class StoreSchemaTooNewError(DomainError, RuntimeError):
    """The store is at a schema version this build does not know.

    Migrations only run forwards, so an older build meeting a newer store has nothing to
    apply and would otherwise treat it as up to date — then write through a mapping that
    no longer describes the tables. Refusing to open it is what keeps a downgrade from
    damaging the history a newer build recorded.
    """

    def __init__(self, found: int, supported: int) -> None:
        """Record the store's version and the highest this build ships.

        Args:
            found: The schema version the store is at.
            supported: The highest version this build has migrations for.
        """
        self.found = found
        self.supported = supported
        super().__init__("error.store.schema_too_new", found=found, supported=supported)
