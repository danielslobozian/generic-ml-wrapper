# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when a schema migration failed and was rolled back."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class MigrationFailedError(DomainError, RuntimeError):
    """A migration could not be applied, and the store was left as it was.

    Each migration commits as a unit with the version bump that records it, so a failure
    leaves the store at the last version that applied cleanly rather than half-way
    between two. The history the user cares about is intact; what they cannot do is run
    this build until the cause is dealt with.
    """

    def __init__(self, version: int, reason: str) -> None:
        """Record which migration failed and why.

        Args:
            version: The schema version the failed migration was bringing the store to.
            reason: The underlying failure, for the message and the logs.
        """
        self.version = version
        self.reason = reason
        super().__init__("error.store.migration_failed", version=version, reason=reason)
