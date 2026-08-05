# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when the workflow to edit does not exist."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class WorkflowNotFoundError(DomainError, ValueError):
    """Raised when the workflow to edit does not exist."""
