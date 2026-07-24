# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The CreateAxis use case: create a role/environment folder from a typed label."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.create_axis import (
    AxisExistsError,
    AxisLabelError,
    CreateAxis,
    CreateAxisCommand,
    CreateAxisResult,
)
from generic_ml_wrapper.common.slug import slugify

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.axis_catalog import AxisCatalogPort
    from generic_ml_wrapper.application.port.outbound.config_writer import ConfigWriterPort


class CreateAxisUseCase(CreateAxis):
    """Create a role/environment slug-folder, optionally making it the default.

    The slug is derived from the label (``slugify``), so the user types a human name and
    never a dotted key or a folder path. Creation fails fast on an empty/unusable label or
    a slug collision — an existing folder is never clobbered. Making it the default is a
    single ``profile.default_<kind>`` merge through the shared config writer.
    """

    def __init__(
        self,
        catalog: AxisCatalogPort,
        writer: ConfigWriterPort,
        config_file: Callable[[], Path],
        clock: Callable[[], datetime],
    ) -> None:
        """Wire the use case to its catalog, config writer, and clock.

        Args:
            catalog: Reads and creates the axis slug-folders.
            writer: Persists ``profile.default_<kind>`` when the axis is made default.
            config_file: Resolves the config file path (indirection for tests).
            clock: Returns "now" for the folder's ``.about.toml`` ``created`` stamp.
        """
        self._catalog = catalog
        self._writer = writer
        self._config_file = config_file
        self._clock = clock

    def execute(self, command: CreateAxisCommand) -> CreateAxisResult:
        """Create the axis folder and optionally point the default at it.

        Args:
            command: The request describing the axis, label, description, and default flag.

        Returns:
            The outcome: the axis, the derived slug, the label, and whether it was made default.

        Raises:
            AxisLabelError: If the label is empty or slugifies to nothing.
            AxisExistsError: If a folder for the derived slug already exists.
        """
        slug = slugify(command.label)
        if not slug:
            message = f"cannot derive a slug from label: {command.label!r}"
            raise AxisLabelError(message)
        if self._catalog.exists(command.kind, slug):
            message = f"{command.kind.value} already exists: {slug!r}"
            raise AxisExistsError(message)
        self._catalog.create(
            command.kind, slug, command.label, command.description, self._clock().isoformat()
        )
        if command.make_default:
            self._writer.merge(
                self._config_file(), [("profile", f"default_{command.kind.value}", slug)]
            )
        return CreateAxisResult(
            kind=command.kind, slug=slug, label=command.label, made_default=command.make_default
        )
