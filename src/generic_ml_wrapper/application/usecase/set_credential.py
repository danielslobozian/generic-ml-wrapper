# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The SetCredentialUseCase use case: store a workflow credential."""

from __future__ import annotations

from generic_ml_wrapper.application.port.inbound.set_credential import (
    SetCredentialCommand,
    SetCredentialUseCase,
)
from generic_ml_wrapper.application.port.outbound.credentials_store import CredentialsStorePort
from generic_ml_wrapper.application.port.outbound.secret_prompt import SecretPromptPort


class SetCredentialService(SetCredentialUseCase):
    """Store a workflow credential, asking for it when the caller did not supply it."""

    def __init__(self, store: CredentialsStorePort, prompt: SecretPromptPort) -> None:
        """Wire the use case to the credentials store and where a secret is asked for.

        Args:
            store: Where the credential is persisted.
            prompt: Asks for the secret when the command did not carry one.
        """
        self._store = store
        self._prompt = prompt

    def execute(self, command: SetCredentialCommand) -> None:
        """Store the credential, reading the secret first when none was given."""
        value = (
            command.value if command.value is not None else self._prompt.ask_secret(command.name)
        )
        self._store.set(command.workflow, command.name, value)
