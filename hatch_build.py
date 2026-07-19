# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Hatchling build hook: stamp a build id into the wheel.

Writes ``src/generic_ml_wrapper/_build_info.py`` (git-ignored, force-included via
``[tool.hatch.build.targets.wheel] artifacts``) at build time so ``gmlw --version``
can report the build date. A source checkout that was never built has no
``_build_info`` module and reports a plain ``(source, unbuilt)`` version instead.

Only the build timestamp is stamped: a git sha was deliberately dropped because it is
captured at build time and every distributed artifact (PyPI wheel/sdist) is built without
a ``.git`` checkout, so it was ``unknown`` exactly where provenance would matter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class BuildInfoHook(BuildHookInterface):
    """Write ``_build_info.py`` with a UTC build timestamp."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:  # noqa: ARG002
        """Stamp the build-info module before the wheel's files are collected."""
        root = Path(self.root)
        build_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = root / "src" / "generic_ml_wrapper" / "_build_info.py"
        target.write_text(
            "# SPDX-FileCopyrightText: 2026 Daniel Slobozian\n"
            "# SPDX-License-Identifier: Apache-2.0\n"
            '"""Generated at build time by hatch_build.py -- do not edit or commit."""\n\n'
            f'BUILD_ID = "{build_id}"\n',
            encoding="utf-8",
        )
