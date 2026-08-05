# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``BuildInfoPort`` over the module a packaged build leaves behind.

The build writes a small module into the distribution carrying its identifier. A source
checkout that was never packaged simply does not have it, so its absence is the answer
rather than an error -- which is why the import is attempted rather than declared.
"""

from __future__ import annotations

import importlib

from generic_ml_wrapper.application.port.outbound.build_info import BuildInfoPort

_MODULE = "generic_ml_wrapper._build_info"
_ATTRIBUTE = "BUILD_ID"


class ModuleBuildInfoAdapter(BuildInfoPort):
    """Read the build stamp from the module the packaging step writes."""

    def build_id(self) -> str | None:
        """Return the stamp, or ``None`` when the module is not there."""
        try:
            stamped = importlib.import_module(_MODULE)
        except ModuleNotFoundError:
            return None
        found = getattr(stamped, _ATTRIBUTE, None)
        return found if isinstance(found, str) else "unknown"
