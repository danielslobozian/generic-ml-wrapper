# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One client a launch could actually run on, right now."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchClient:
    """One client a launch could actually run on, right now.

    Deliberately smaller than
    :class:`~generic_ml_wrapper.application.port.inbound.list_clients.ListedClient`: no
    version. Reading a version means running ``<binary> --version`` per installed client,
    and a chooser that sits between "start this job" and the job starting cannot afford
    several subprocesses -- nor does the question need them.

    Attributes:
        name: The gmlw client id (e.g. ``claude``) -- what a launch is keyed on.
        display: The human-readable name; the id itself for a configured caller that has
            no catalog entry.
        is_default: Whether this is the configured default.
        custom: Whether it comes from a ``[callers]`` entry -- either a caller supplied for
            a name gmlw does not ship, or one replacing a built-in.
    """

    name: str
    display: str
    is_default: bool
    custom: bool = False
