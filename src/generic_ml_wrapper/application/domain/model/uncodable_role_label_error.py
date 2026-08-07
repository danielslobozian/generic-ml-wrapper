# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when a role label leaves nothing to make a code from."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class UncodableRoleLabelError(DomainError, ValueError):
    """Raised when a role label leaves nothing to make a code from.

    Not "invalid": punctuation, spaces and accents are all fine and reduce cleanly. The
    only failure is a label whose reduction is empty — an all-symbol input, or text in a
    script that carries no ASCII at all.
    """
