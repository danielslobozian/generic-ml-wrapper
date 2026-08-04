# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when a string is not a valid identifier of its kind."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class IdentifierError(DomainError, ValueError):
    """Raised when a string is not a valid identifier of its kind."""
