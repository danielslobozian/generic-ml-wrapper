# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when the named job has no recorded activity."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class NoSuchJobError(DomainError, ValueError):
    """Raised when the named job has no recorded activity."""
