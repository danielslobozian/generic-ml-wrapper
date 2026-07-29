# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Split a configured argument string into the tokens a client is launched with.

The string is opaque to gmlw: whatever the user wrote is handed to their client
verbatim. Only the splitting is ours, and it has one platform wrinkle worth naming
(see :func:`split`).
"""

from __future__ import annotations

import os
import shlex

from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.log import log

# POSIX-mode splitting treats a backslash as an escape, so a Windows path
# (``--add-dir C:\work``) would arrive with its separators eaten. Windows keeps the
# quotes inside the tokens instead, which is what ``subprocess`` re-quotes correctly
# there anyway.
_POSIX = os.name != "nt"


def split(text: str) -> tuple[str, ...]:
    """Split an argument string into launch tokens.

    Args:
        text: The raw argument string, as configured or typed.

    Returns:
        The tokens, or an empty tuple when the string is blank or unparseable.

        An unbalanced quote is the user's typo, and it must not take down the launch —
        but it must not pass unmentioned either: dropping the arguments silently would
        start the client without the flags the user asked for and look like success.
    """
    if not text or not text.strip():
        return ()
    try:
        return tuple(shlex.split(text, posix=_POSIX))
    except ValueError as error:
        log.warning(
            i18n.t("log.client_args_unparseable", args=text, error=error),
            key="log.client_args_unparseable",
        )
        return ()
