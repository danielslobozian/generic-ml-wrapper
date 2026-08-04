# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when a configured caller cannot be provided."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class CallerUnavailableError(DomainError, ValueError):
    """A configured caller was named but cannot be provided.

    The wrapper lets a private caller be plugged in through configuration. When the
    configured one cannot be produced, the run stops rather than silently falling back to
    a different client than the user asked for. How a caller is located and produced is
    the adapter's business.
    """

    def __init__(self, reason: str) -> None:
        """Record why the caller could not be provided.

        Args:
            reason: The detail to show the user, as the provider described it.
        """
        self.reason = reason
        super().__init__("error.caller.unavailable", reason=reason)
