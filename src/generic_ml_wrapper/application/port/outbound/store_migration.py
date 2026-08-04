# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for evolving the ledger to the schema this build expects.

Migration is a contract rather than a private detail of the store, for the same reason
`Flyway <https://www.red-gate.com/products/flyway/>`_ and Liquibase are contracts in a
Java service: what a build can persist is a fact about the build, checked once at
startup, not something discovered halfway through a write.

The check is one integer, for the whole store, verified before anything is served.
:data:`CURRENT_SCHEMA_VERSION` is what this build requires; an implementation reports
what it can actually deliver through :meth:`StoreMigrationPort.implemented_version`,
and a lower answer is refused at boot rather than allowed to write through a mapping
that no longer matches the tables.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

#: The schema version this build requires the ledger to be at. Bumped by every
#: migration that changes the persisted model; the migration files are the lineage that
#: reaches it, and each one is numbered for the version it brings a store *to*.
CURRENT_SCHEMA_VERSION = 6


class StoreMigrationPort(ABC):
    """Outbound port for bringing the ledger up to the schema this build expects."""

    @abstractmethod
    def implemented_version(self) -> int:
        """Return the highest schema version this implementation can migrate a store to.

        Compared at startup against :data:`CURRENT_SCHEMA_VERSION`; a lower answer means
        the code and the tables disagree, and the wrapper refuses to serve.

        Returns:
            The highest version this implementation ships migrations for.
        """

    @abstractmethod
    def migrate_to_current(self) -> None:
        """Bring the store to :meth:`implemented_version`, idempotently.

        A no-op when the store is already current, so it is safe to call on every
        startup rather than guarded by a caller that has to know whether it is needed.

        Raises:
            MigrationFailedError: If a migration failed; it was rolled back and the
                store is left at the last version that applied cleanly.
            StoreCorruptError: If the store's version cannot be read unambiguously.
            StoreSchemaTooNewError: If the store was written by a newer build.
        """
