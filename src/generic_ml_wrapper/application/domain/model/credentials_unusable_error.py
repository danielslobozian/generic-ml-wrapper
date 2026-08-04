# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when the stored credentials cannot be understood."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class CredentialsUnusableError(DomainError, ValueError):
    """The stored credentials exist but cannot be understood, so they must not be rewritten.

    Rewriting them would read the corruption as "no secrets" and destroy every one, so the
    run stops instead. Where they are stored is the adapter's business.
    """

    def __init__(self, source: str) -> None:
        """Record which credentials could not be understood.

        Args:
            source: How the user can identify them (a path, a name — the adapter decides).
        """
        self.source = source
        super().__init__("error.credentials.unusable", source=source)
