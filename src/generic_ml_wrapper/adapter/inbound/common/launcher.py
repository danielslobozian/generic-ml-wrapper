# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys

from generic_ml_wrapper.adapter.inbound.common.renderer import (
    format_client_guidance,
    render_launch_location,
)
from generic_ml_wrapper.application.wiring.composition import (
    build_check_client_ready,
    build_check_launch_location,
)


def preflight_client(client: str) -> bool:
    """Check the client can launch, printing install or login guidance when it cannot.

    Returns:
        ``True`` to go ahead. ``False`` means guidance has already been written to stderr
        and the caller should stop without printing anything further.
    """
    readiness = build_check_client_ready().execute(client)
    if readiness.ready:
        return True
    print(format_client_guidance(readiness), file=sys.stderr)
    return False


def preflight_cwd() -> bool:
    """Check this folder still exists, printing guidance when it does not.

    Returns:
        ``True`` to go ahead; ``False`` after guidance has been written to stderr.
    """
    return render_launch_location(build_check_launch_location().execute())


def preflight_resume_cwd(cwd: str | None) -> bool:
    """Check a resumed session's recorded folder still exists.

    Args:
        cwd: ``None`` for a session recorded before folders were tracked, which always
            passes.

    Returns:
        ``True`` to go ahead; ``False`` after guidance has been written to stderr.
    """
    return render_launch_location(build_check_launch_location().execute(cwd))
