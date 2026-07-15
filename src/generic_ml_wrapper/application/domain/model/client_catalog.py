# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The catalog of supported clients: their command, and how to install and log in.

The single source of truth for the built-in clients — the PATH command each one
launches (used to detect installs) and the install/login guidance shown when a
resolved client is not yet available. Edit an entry here if a vendor changes its
install command.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClientInfo:
    """One supported client and how to get it running.

    Attributes:
        name: The gmlw client id (the ``--client`` value / ``[client] default``).
        binary: The executable resolved on ``PATH`` to detect the install.
        display: The human-readable product name.
        install: The one-line install command.
        login: How to authenticate once installed.
    """

    name: str
    binary: str
    display: str
    install: str
    login: str


CLAUDE = ClientInfo(
    name="claude",
    binary="claude",
    display="Claude Code",
    install="npm install -g @anthropic-ai/claude-code",
    login="claude auth login  (first run opens a browser)",
)
CURSOR = ClientInfo(
    name="cursor",
    binary="cursor-agent",
    display="Cursor CLI",
    install="curl https://cursor.com/install -fsSL | bash",
    login="cursor-agent login",
)
CODEX = ClientInfo(
    name="codex",
    binary="codex",
    display="OpenAI Codex CLI",
    install="npm install -g @openai/codex",
    login="codex login  (ChatGPT account or API key)",
)
VIBE = ClientInfo(
    name="vibe",
    binary="vibe",
    display="Mistral Vibe",
    install="uv tool install mistral-vibe",
    login="run `vibe` to start the setup wizard  (or set MISTRAL_API_KEY)",
)

# The supported clients, in canonical order (claude first, matching the built-in default).
SUPPORTED: tuple[ClientInfo, ...] = (CLAUDE, CURSOR, CODEX, VIBE)


def by_name(name: str) -> ClientInfo | None:
    """Return the catalog entry for a client name, or ``None`` when unsupported.

    Args:
        name: The gmlw client id.

    Returns:
        The matching :class:`ClientInfo`, or ``None``.
    """
    return next((info for info in SUPPORTED if info.name == name), None)
