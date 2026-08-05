# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when a draft asked for by key does not exist, or none is resumable."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class NoSuchDraftError(DomainError, ValueError):
    """Raised when a draft asked for by key does not exist, or none is resumable."""
