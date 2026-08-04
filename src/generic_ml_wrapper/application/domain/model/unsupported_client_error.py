# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when a run names a client nothing can launch."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class UnsupportedClientError(DomainError, ValueError):
    """The run names a client with no configured override and no built-in support."""

    def __init__(self, client: str) -> None:
        """Record the client that cannot be launched.

        Args:
            client: The gmlw client id the run asked for.
        """
        self.client = client
        super().__init__("error.client.unsupported", client=client)
