# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when the client's own settings cannot be understood."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class ClientSettingsUnusableError(DomainError, ValueError):
    """The client's settings exist but cannot be understood, so they must not be rewritten.

    The wrapper installs its status line by amending the client's own settings. When those
    settings cannot be parsed, continuing would mean overwriting them blind and destroying
    whatever the user had configured — so the run stops instead. Where the settings are
    kept, and in what format, is the adapter's business; that they are unusable is the
    application's.
    """

    def __init__(self, source: str) -> None:
        """Record which settings could not be understood.

        Args:
            source: How the user can identify them (a path, a name — the adapter decides).
        """
        self.source = source
        super().__init__("error.client_settings.unusable", source=source)
