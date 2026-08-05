# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to store one credential for a workflow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetCredentialCommand:
    """A request to store one credential for a workflow.

    Attributes:
        workflow: The workflow the credential belongs to.
        name: The environment-variable name to export at launch.
        value: The secret value, or ``None`` to ask for it. A caller that already holds
            the secret passes it; one that does not says so, rather than reading it
            itself -- asking a person for a value is an outward reach like any other, and
            a caller that did it would decide how a secret is kept off the screen.
    """

    workflow: str
    name: str
    value: str | None = None
