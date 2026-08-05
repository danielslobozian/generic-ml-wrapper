# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when a label is empty or slugifies to nothing usable."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class AxisLabelError(DomainError, ValueError):
    """Raised when a label is empty or slugifies to nothing usable."""
