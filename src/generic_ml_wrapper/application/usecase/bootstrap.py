# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Bootstrap use case: ensure the runtime layout exists."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.bootstrap import Bootstrap
from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.errors import DomainError
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort
    from generic_ml_wrapper.application.usecase.install_provided_attachments import (
        InstallProvidedAttachmentsUseCase,
    )


class BootstrapUseCase(Bootstrap):
    """Ensure the runtime layout by delegating to a layout seeder."""

    def __init__(
        self,
        seeder: LayoutSeederPort,
        attachments: InstallProvidedAttachmentsUseCase | None = None,
    ) -> None:
        """Wire the use case to its outbound seeder.

        Args:
            seeder: The seeder that creates missing directories and the config.
            attachments: Imports the attachments gmlw ships with, or ``None``.
        """
        self._seeder = seeder
        self._attachments = attachments

    def execute(self) -> None:
        """Ensure the runtime layout exists (idempotent, missing-only)."""
        self._seeder.ensure()
        if self._attachments is None:
            return
        try:
            self._attachments.execute()
        except (DomainError, OSError) as error:
            # A provided attachment that cannot be imported must not stop gmlw: it is
            # missing from the store until the cause is fixed, and the log says why.
            reason = error.localized(i18n.active()) if isinstance(error, DomainError) else error
            log.warning(i18n.t("log.provided_attachment_failed", error=reason))
