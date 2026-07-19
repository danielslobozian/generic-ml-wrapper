# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""generic-ml-wrapper: a wrapper around an ML coding CLI.

You enter it at a job, it mints a named, resumable session on the client, and
optionally drives it through a workflow. This is the package root; the walking
skeleton exposes only the version and a minimal entry point. See ``docs/DESIGN.md``
for the architecture the use cases will fill in.
"""

from __future__ import annotations

__version__ = "0.6.0"
