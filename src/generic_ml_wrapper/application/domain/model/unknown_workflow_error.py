# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when a requested workflow does not exist."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class UnknownWorkflowError(DomainError, ValueError):
    """Raised when a requested workflow does not exist."""
