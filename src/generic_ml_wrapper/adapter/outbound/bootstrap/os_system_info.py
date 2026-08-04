# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``SystemInfoPort`` over the operating system this process is running on."""

from __future__ import annotations

import getpass
import platform

from generic_ml_wrapper.application.port.outbound.system_info import SystemInfoPort


class OsSystemInfo(SystemInfoPort):
    """Answer from the host: the account name, and the platform's name."""

    def username(self) -> str:
        """Return the account name, or an empty string if the host will not say.

        ``getuser`` consults the environment before the password database, and raises
        rather than guessing when neither answers -- which happens in containers with no
        passwd entry. An empty string is a better answer than a crash for something only
        used to address the user by name.
        """
        try:
            return getpass.getuser()
        except (OSError, KeyError):
            return ""

    def platform_name(self) -> str:
        """Return the platform's name as the client catalogue spells it."""
        return platform.system()
