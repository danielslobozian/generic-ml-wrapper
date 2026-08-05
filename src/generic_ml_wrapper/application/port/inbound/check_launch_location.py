# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for "can a run happen here at all"."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.launch_location import LaunchLocation


class CheckLaunchLocationUseCase(ABC):
    """Report whether the folder a launch depends on is still there."""

    @abstractmethod
    def execute(self, session_folder: str | None = None) -> LaunchLocation:
        """Check where a run is about to happen.

        Args:
            session_folder: The folder a resumed session ran in, when resuming a specific
                one. ``None`` means the run happens in the current directory, which is
                checked either way -- a session recorded before folders existed resumes
                there too.

        Returns:
            The verdict, naming the missing folder when one is missing.
        """
