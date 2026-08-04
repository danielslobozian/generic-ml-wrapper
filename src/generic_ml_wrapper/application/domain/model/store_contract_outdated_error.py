# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when the shipped migrations cannot reach the schema this build needs."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class StoreContractOutdatedError(DomainError, RuntimeError):
    """The code expects a schema the shipped migrations do not build.

    The two halves of the store are the code that reads it and the lineage that shapes
    it, and they are versioned by the same number for a reason. If the lineage falls
    short, every read and write afterwards goes through a mapping the tables do not
    match — so the check runs before the first command does anything, not after.

    In practice this means the migration files did not reach the installed package.
    """

    def __init__(self, implemented: int, required: int) -> None:
        """Record what the lineage reaches and what the code expects.

        Args:
            implemented: The highest version the available migration files reach.
            required: The version this build's code is written against.
        """
        self.implemented = implemented
        self.required = required
        super().__init__(
            "error.store.contract_outdated", implemented=implemented, required=required
        )
