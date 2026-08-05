# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One supported client and everything needed to get and keep it running."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.prerequisite import Prerequisite
    from generic_ml_wrapper.application.domain.model.version_probe import VersionProbe
    from generic_ml_wrapper.application.domain.service.localizer import Localizer


@dataclass(frozen=True)
class ClientInfo:
    """One supported client and everything needed to get and keep it running.

    Attributes:
        name: The gmlw client id (the ``--client`` value / ``[client] default``).
        binary: The executable resolved on ``PATH`` to detect the install.
        display: The human-readable product name.
        subscription: The paid plan that unlocks it, shown when guiding a fresh install
            (the "do you pay for …?" map).
        install_unix: The recommended install command on macOS / Linux.
        install_windows: The recommended install command on Windows.
        login: The command that authenticates once installed — a literal command, never
            prose, so it stays the same in every language.
        login_hint: Catalogue key for a short note rendered beside ``login`` (e.g. that the
            first run opens a browser), or ``""`` when the command speaks for itself. It is
            a key rather than a sentence because the catalogue is data, and data does not
            know which language it will be read in.
        resumable: Whether a session on this client can be reopened at all — the answer the
            clients listing gives the user, and its only consumer. Not the launch mechanism:
            Claude and cursor-agent are told the id we named, Codex learns the one it minted
            mid-run, and all three end up resumable; Vibe keeps no durable session, so it
            does not. Whether a *particular* session can be resumed is the caller's call
            (``CliCallerPort.can_resume``), which for Codex is answered per session.
        resume_hint: Catalogue key for the caveat on ``resumable``, or ``""`` when the yes
            is unconditional. A key, not a sentence, for the same reason as ``login_hint``.
        version_probes: Ordered first-party sources for the latest version.
        update: The dedicated upgrade command; empty means "re-run the installer".
        version_flag: The argument that prints the installed version (``--version``).
        prereq: A tool the install path needs first, or ``None``.
    """

    name: str
    binary: str
    display: str
    subscription: str
    install_unix: str
    install_windows: str
    login: str
    login_hint: str = ""
    resumable: bool = True
    resume_hint: str = ""
    version_probes: tuple[VersionProbe, ...] = field(default_factory=tuple)
    update: str = ""
    version_flag: str = "--version"
    prereq: Prerequisite | None = None

    def install_for(self, system: str) -> str:
        """Return the install command for an OS (``platform.system()`` value)."""
        return self.install_windows if system == "Windows" else self.install_unix

    def update_for(self, system: str) -> str:
        """Return the upgrade command for an OS: the dedicated updater, else the installer."""
        return self.update or self.install_for(system)

    def login_for(self, loc: Localizer) -> str:
        """Return the login command, with its localised note when it has one.

        The command itself is never translated — it is something the user types. Only the
        note beside it is prose, so only the note goes through the catalogue.

        The localiser is required rather than defaulted: the domain does not know which
        language the process is speaking, and must not go looking for it.

        Args:
            loc: The localiser to render the note through.

        Returns:
            e.g. ``claude   (first run opens a browser)``, or bare ``cursor-agent login``.
        """
        if not self.login_hint:
            return self.login
        return f"{self.login}   ({loc.t(self.login_hint)})"
