# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when a resume was asked for and the workflow has no reopenable session."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class NoEditToResumeError(DomainError, ValueError):
    """Raised when a resume was asked for and the workflow has no reopenable session."""
