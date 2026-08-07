# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when an environment already holds the code derived from the label."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class EnvironmentCodeAlreadyExistsError(DomainError, ValueError):
    """Raised when an environment already holds the code derived from the label.

    The collision is on the code, not on the text: two different labels can reduce to the
    same code, so the user can type something they have never typed before and still hit
    an existing environment.
    """
