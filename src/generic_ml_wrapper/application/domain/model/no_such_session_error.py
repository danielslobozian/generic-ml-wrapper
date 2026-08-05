# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when the named session is not recorded for its job."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class NoSuchSessionError(DomainError, ValueError):
    """Raised when the named session is not recorded for its job."""
