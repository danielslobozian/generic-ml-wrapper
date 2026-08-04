# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when the store's own schema version cannot be read unambiguously."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class StoreCorruptError(DomainError, RuntimeError):
    """The store cannot say which schema version it is at.

    The version tracker is built to hold exactly one row. More than one means something
    wrote it that should not have, and there is no safe way to pick between them: guess
    low and a migration re-runs against tables that already exist, guess high and this
    build writes through a mapping the tables do not match. Failing here is the only
    answer that cannot silently damage the history.
    """

    def __init__(self, rows: int) -> None:
        """Record how many version rows were found.

        Args:
            rows: The number of rows in the version tracker; anything but one is a fault.
        """
        self.rows = rows
        super().__init__("error.store.corrupt", rows=rows)
