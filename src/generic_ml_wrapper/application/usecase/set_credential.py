# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The SetCredential use case: store a workflow credential."""

from __future__ import annotations

from generic_ml_wrapper.application.port.inbound.set_credential import (
    SetCredential,
    SetCredentialCommand,
)
from generic_ml_wrapper.application.port.outbound.credentials_store import CredentialsStorePort


class SetCredentialUseCase(SetCredential):
    """Store a workflow credential via the credentials store."""

    def __init__(self, store: CredentialsStorePort) -> None:
        """Wire the use case to the credentials store.

        Args:
            store: Where the credential is persisted.
        """
        self._store = store

    def execute(self, command: SetCredentialCommand) -> None:
        """Store the credential described by the command."""
        self._store.set(command.workflow, command.name, command.value)
