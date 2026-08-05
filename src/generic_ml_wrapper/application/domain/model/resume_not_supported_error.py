# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when resuming is requested for a client that cannot resume (e.g. codex)."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class ResumeNotSupportedError(DomainError, ValueError):
    """Raised when resuming is requested for a client that cannot resume (e.g. codex)."""
