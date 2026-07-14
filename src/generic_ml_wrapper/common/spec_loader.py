# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Load a class from a ``"module:Class"`` / ``"/path.py:Class"`` config spec.

The generic spec loader that both the CliCaller override seam and the context
interceptor seam use to plug private code in via config without it living here.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from types import ModuleType

_T = TypeVar("_T")


class SpecLoadError(ValueError):
    """Raised when a spec cannot be resolved to a subclass of the expected base."""


def load_class(spec: str, base: type[_T]) -> type[_T]:
    """Resolve a ``"module:Class"`` or ``"/path/to/file.py:Class"`` spec to a class.

    Args:
        spec: The import spec, ``"<module-or-path>:<ClassName>"``.
        base: The base class the referenced class must subclass.

    Returns:
        The referenced subclass of ``base``.

    Raises:
        SpecLoadError: If the spec is malformed, cannot be imported, or does not
            name a subclass of ``base``.
    """
    # rpartition (last colon), not partition: a Windows file path carries a colon in
    # its drive letter (``C:\...\file.py``), so only the final colon splits the class.
    module_ref, separator, class_name = spec.rpartition(":")
    if not separator or not module_ref or not class_name:
        message = f"expected '<module-or-path>:<Class>', got {spec!r}"
        raise SpecLoadError(message)
    module = _import(module_ref, spec)
    candidate = getattr(module, class_name, None)
    if not isinstance(candidate, type) or not issubclass(candidate, base):
        message = f"{spec!r} does not name a {base.__name__} subclass"
        raise SpecLoadError(message)
    return candidate


def _import(module_ref: str, spec: str) -> ModuleType:
    if module_ref.endswith(".py"):
        location = importlib.util.spec_from_file_location(Path(module_ref).stem, module_ref)
        if location is None or location.loader is None:
            message = f"cannot load a module from {module_ref!r}"
            raise SpecLoadError(message)
        module = importlib.util.module_from_spec(location)
        location.loader.exec_module(module)
        return module
    try:
        return importlib.import_module(module_ref)
    except ImportError as error:
        message = f"cannot import {module_ref!r} from spec {spec!r}"
        raise SpecLoadError(message) from error
