# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Load an external ``CliCallerPort`` class from a config spec, at runtime."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.caller_unavailable_error import (
    CallerUnavailableError,
)
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerPort
from generic_ml_wrapper.application.wiring.spec_loader import SpecLoader, SpecLoadError


def load_caller_class(spec: str) -> type[CliCallerPort]:
    """Resolve a ``"module:Class"`` or ``"/path/to/file.py:Class"`` spec to a class.

    The spec lets a private metering caller be plugged in via config without ever
    living in this repo.

    Args:
        spec: The import spec, ``"<module-or-path>:<ClassName>"``.

    Returns:
        The referenced ``CliCallerPort`` subclass.

    Raises:
        CallerUnavailableError: If the spec is malformed, cannot be imported, or does not
            name a ``CliCallerPort`` subclass.
    """
    try:
        return SpecLoader().load_class(spec, CliCallerPort)
    except SpecLoadError as error:
        raise CallerUnavailableError(str(error)) from error
