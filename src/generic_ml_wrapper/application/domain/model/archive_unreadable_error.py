# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when the archive is missing, not a zip, or holds no workflow."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class ArchiveUnreadableError(DomainError, ValueError):
    """Raised when the archive is missing, not a zip, or holds no workflow."""
