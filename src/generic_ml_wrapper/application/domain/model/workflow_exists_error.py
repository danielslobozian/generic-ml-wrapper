# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when a workflow with the requested name already exists."""

from __future__ import annotations


class WorkflowExistsError(ValueError):
    """Raised when a workflow with the requested name already exists."""
