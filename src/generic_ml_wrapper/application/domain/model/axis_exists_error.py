# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when a folder for the derived slug already exists."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class AxisExistsError(DomainError, ValueError):
    """Raised when a folder for the derived slug already exists."""
