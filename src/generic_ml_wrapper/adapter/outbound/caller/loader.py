# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Load an external ``CliCaller`` class from a config spec, at runtime."""

from __future__ import annotations

from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller
from generic_ml_wrapper.common.spec_loader import SpecLoadError, load_class


class CallerLoadError(ValueError):
    """Raised when a caller spec cannot be resolved to a ``CliCaller`` subclass."""


def load_caller_class(spec: str) -> type[CliCaller]:
    """Resolve a ``"module:Class"`` or ``"/path/to/file.py:Class"`` spec to a class.

    The spec lets a private metering caller be plugged in via config without ever
    living in this repo.

    Args:
        spec: The import spec, ``"<module-or-path>:<ClassName>"``.

    Returns:
        The referenced ``CliCaller`` subclass.

    Raises:
        CallerLoadError: If the spec is malformed, cannot be imported, or does not
            name a ``CliCaller`` subclass.
    """
    try:
        return load_class(spec, CliCaller)
    except SpecLoadError as error:
        raise CallerLoadError(str(error)) from error
