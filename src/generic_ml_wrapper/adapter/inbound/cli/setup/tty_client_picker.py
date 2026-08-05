# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Choosing the default client at a terminal — and refusing to go on without one.

gmlw does not install anything. It used to: it printed the command, offered to run it,
ran it, then polled ``PATH`` until the binary appeared. That was two jobs in one
conversation, and the second one was somebody else's. It also could not work reliably —
a process cannot see a ``PATH`` its own shell gained after it started, so an install into
a directory that was not already searched is invisible however long you wait.

So: if a client is installed, pick one. If none is, say so, show the commands that would
install one, and stop without writing anything. The user starts again afterwards, in a
terminal that can see what they installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.cli.setup.tty_prompt import Choice, choose_number, emit

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.cli.setup.message_source import MessageSource
    from generic_ml_wrapper.application.domain.model.client_info import ClientInfo
    from generic_ml_wrapper.application.port.inbound.listed_client import ListedClient


def choose_client(clients: list[ListedClient], loc: MessageSource) -> str | None:
    """Offer the installed clients and return the chosen one.

    Args:
        clients: Every supported client with its installed-ness and version.
        loc: Renders the prompts.

    Returns:
        The chosen client's name, or ``None`` when nothing is installed or the user
        declined. A lone installed client is taken without asking — and said out loud,
        because choosing silently is what generates support questions.
    """
    installed = [client for client in clients if client.installed]
    if not installed:
        return None
    if len(installed) == 1:
        only = installed[0]
        emit(loc.t("init.client.only_one", client=only.display))
        return only.name
    choices = [
        Choice(value=client.name, label=client.display, description=client.version or "")
        for client in installed
    ]
    return choose_number(loc.t("init.client.header"), choices, loc, default=0)


def report_no_client(supported: tuple[ClientInfo, ...], system: str, loc: MessageSource) -> None:
    """Tell the user nothing is installed, and how to install something.

    Args:
        supported: Every client gmlw supports, in canonical order.
        system: The OS name, so each command is the right one for this machine.
        loc: Renders the message.
    """
    emit(loc.t("init.client.none_installed"))
    for info in supported:
        emit(f"  {info.display}: {info.install_for(system)}")
    emit(loc.t("init.client.install_then_relaunch"))
