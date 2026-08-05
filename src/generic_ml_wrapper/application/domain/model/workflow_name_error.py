# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when a workflow name is invalid or reserved."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class WorkflowNameError(DomainError, ValueError):
    """Raised when a workflow name is invalid or reserved."""
