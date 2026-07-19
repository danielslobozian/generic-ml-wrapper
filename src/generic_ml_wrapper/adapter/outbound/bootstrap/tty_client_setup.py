# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``ClientSetupPort`` that talks the default-client choice through on a terminal.

The forced init's client step. Where the old chooser silently took a lone install and
dead-ended when nothing was found, this always converses:

* lists every installed client with its version — flagging an *old* install and
  offering the one-line update;
* lets the user switch, or install a different client;
* on an install it prints the OS-specific command (copied to the clipboard when a
  clipboard tool is present), offers to run it *for* the user or let them run it
  themselves, then polls ``PATH`` until the client appears;
* handles a prerequisite first (``uv`` for Vibe) when it is missing.

All input/output goes through :mod:`tty_prompt`, so a non-TTY run declines cleanly to
the first installed client (or ``None``) and never blocks automation. The install
runner, clipboard, version reader, PATH probe, and sleep are all injected, so the whole
conversation is testable without a network, a real install, or a real wait.
"""

from __future__ import annotations

import platform
import shutil
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.http_client_versions import outdated
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_prompt import Choice, choose_number, emit
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.port.outbound.client_setup import ClientSetupPort

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_catalog import ClientInfo, Prerequisite
    from generic_ml_wrapper.application.port.outbound.client_version import ClientVersionPort
    from generic_ml_wrapper.application.port.outbound.clipboard import ClipboardPort
    from generic_ml_wrapper.application.port.outbound.command_runner import CommandRunnerPort
    from generic_ml_wrapper.common.i18n import Localizer

# Sentinel option value: "install a client other than the ones already here".
_INSTALL = "\x00install"


def _on_path(binary: str) -> bool:
    """Whether ``binary`` resolves on ``PATH`` (the default presence probe)."""
    return shutil.which(binary) is not None


class TtyClientSetup(ClientSetupPort):
    """Guide the default-client choice, install, and update at an interactive terminal."""

    def __init__(  # noqa: PLR0913  (small injected collaborators, all defaulted)
        self,
        i18n: Localizer,
        *,
        version: ClientVersionPort,
        runner: CommandRunnerPort,
        clipboard: ClipboardPort,
        present: Callable[[str], bool] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        system: str | None = None,
        poll_interval_s: float = 2.0,
        poll_attempts: int = 5,
    ) -> None:
        """Wire the conversation to its collaborators and pacing.

        Args:
            i18n: The default localiser for the prompts.
            version: Reads installed and latest versions (best-effort).
            runner: Runs an install/update command when the user asks gmlw to.
            clipboard: Copies a command to the clipboard (best-effort).
            present: Predicate for "this binary is on PATH" (defaults to ``shutil.which``).
            sleep: Pauses between install-verification polls (defaults to ``time.sleep``).
            system: The ``platform.system()`` value for OS-specific commands.
            poll_interval_s: Seconds between verification polls.
            poll_attempts: Automatic polls before offering a manual re-check.
        """
        self._i18n = i18n
        self._version = version
        self._runner = runner
        self._clipboard = clipboard
        self._present = present or _on_path
        self._sleep = sleep
        self._system = system or platform.system()
        self._interval = poll_interval_s
        self._attempts = poll_attempts

    def choose(self, found: list[str], i18n: Localizer | None = None) -> str | None:
        """Run the conversation and return the settled default client (or ``None``).

        Args:
            found: Installed clients in canonical order (possibly empty).
            i18n: The localiser to use; ``None`` falls back to the construction-time one.

        Returns:
            The chosen client, or ``None`` when nothing is installed and no install
            completed. On a non-TTY run, the first installed client (or ``None``).
        """
        loc = i18n or self._i18n
        picked = self._pick(found, loc)
        if picked is None:  # non-TTY, declined, or EOF — fall back to a lone default
            return found[0] if found else None
        if picked == _INSTALL:
            return self._install_flow(found, loc)
        self._maybe_update(picked, loc)
        return picked

    def _pick(self, found: list[str], loc: Localizer) -> str | None:
        """Offer the installed clients (with versions) plus an "install another" option."""
        choices = [
            Choice(
                value=name,
                label=info.display,
                description=self._version_note(info, loc),
            )
            for name in found
            if (info := client_catalog.by_name(name)) is not None
        ]
        choices.append(Choice(value=_INSTALL, label=loc.t("init.client.menu_install")))
        return choose_number(loc.t("init.client.header"), choices, loc, default=0)

    def _version_note(self, info: ClientInfo, loc: Localizer) -> str:
        """Describe an installed client: up to date, an update available, or unknown."""
        installed = self._version.installed(info)
        latest = self._version.latest(info)
        if installed and latest and outdated(installed, latest):
            return loc.t("init.client.note_update", installed=installed, latest=latest)
        if installed:
            return loc.t("init.client.note_current", version=installed)
        return loc.t("init.client.note_installed")

    def _maybe_update(self, name: str, loc: Localizer) -> None:
        """When a chosen client is behind its latest, offer to run the update command."""
        info = client_catalog.by_name(name)
        if info is None:
            return
        installed = self._version.installed(info)
        latest = self._version.latest(info)
        if not (installed and latest and outdated(installed, latest)):
            return
        command = info.update_for(self._system)
        prompt = loc.t(
            "init.client.offer_update", display=info.display, installed=installed, latest=latest
        )
        choice = choose_number(
            prompt,
            [
                Choice(value="update", label=loc.t("init.client.update_now", command=command)),
                Choice(value="keep", label=loc.t("init.client.keep", version=installed)),
            ],
            loc,
            default=1,  # default: keep what's installed
        )
        if choice == "update":
            self._run(command, loc)

    def _install_flow(self, found: list[str], loc: Localizer) -> str | None:
        """Pick a client to install, satisfy any prerequisite, guide it, and verify."""
        target = self._pick_target(loc)
        if target is None:
            return found[0] if found else None
        if target.prereq is not None and not self._present(target.prereq.binary):
            self._guide_prereq(target.prereq, loc)
        installed = self._guide(
            target.display, target.install_for(self._system), target.binary, target.login, loc
        )
        if installed or self._present(target.binary):
            return target.name
        return found[0] if found else None

    def _pick_target(self, loc: Localizer) -> ClientInfo | None:
        """Offer every supported client (with its paid-plan framing) to install."""
        choices = [
            Choice(value=info.name, label=info.display, description=info.subscription)
            for info in client_catalog.SUPPORTED
        ]
        name = choose_number(loc.t("init.install.header"), choices, loc, skippable=True)
        return client_catalog.by_name(name) if name else None

    def _guide_prereq(self, prereq: Prerequisite, loc: Localizer) -> None:
        """Guide installing a missing prerequisite (e.g. uv) before the client itself."""
        emit(loc.t("init.prereq.needed", display=prereq.display))
        self._guide(prereq.display, prereq.install_for(self._system), prereq.binary, None, loc)

    def _guide(
        self, display: str, command: str, binary: str, login: str | None, loc: Localizer
    ) -> bool:
        """Show the install command, offer to run it, and verify the binary appears.

        Returns:
            ``True`` when the binary is on PATH afterwards, ``False`` otherwise.
        """
        emit(loc.t("init.install.command", display=display), "", f"    {command}", "")
        if login:
            emit(loc.t("init.install.login_hint", login=login))
        if self._clipboard.copy(command):
            emit(loc.t("init.install.copied"))
        action = choose_number(
            loc.t("init.install.action", display=display),
            [
                Choice(value="run", label=loc.t("init.install.run_for_you")),
                Choice(value="self", label=loc.t("init.install.self")),
                Choice(value="skip", label=loc.t("init.install.skip")),
            ],
            loc,
            default=1,  # default: I'll run it myself
        )
        if action is None or action == "skip":
            return self._present(binary)
        if action == "run":
            self._run(command, loc)
        return self._verify(binary, display, loc)

    def _verify(self, binary: str, display: str, loc: Localizer) -> bool:
        """Poll PATH for ``binary``; after a few tries, offer a manual re-check or skip."""
        for _ in range(self._attempts):
            if self._present(binary):
                emit(loc.t("init.install.success", display=display))
                return True
            emit(loc.t("init.install.waiting", display=display))
            self._sleep(self._interval)
        if self._present(binary):
            emit(loc.t("init.install.success", display=display))
            return True
        again = choose_number(
            loc.t("init.install.recheck_header", display=display),
            [
                Choice(value="again", label=loc.t("init.install.recheck")),
                Choice(value="skip", label=loc.t("init.install.skip")),
            ],
            loc,
            default=0,
        )
        if again == "again":
            return self._verify(binary, display, loc)
        emit(loc.t("init.install.gaveup", display=display))
        return False

    def _run(self, command: str, loc: Localizer) -> None:
        """Run a command via the injected runner and narrate a non-zero exit."""
        emit(loc.t("init.install.running", command=command))
        code = self._runner.run(command)
        if code != 0:
            emit(loc.t("init.install.run_failed", code=code))
