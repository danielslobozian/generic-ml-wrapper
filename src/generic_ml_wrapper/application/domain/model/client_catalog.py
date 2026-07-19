# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The catalog of supported clients: how to install, update, log in, and version-check.

The single source of truth for the built-in clients — the PATH command each one
launches (used to detect installs), the OS-specific install/update guidance shown at
setup, the login step, and the first-party sources that report the latest published
version (so an old install can be flagged). Edit an entry here when a vendor changes a
command; the guided setup and the launch preflight both read from it.

All URLs below are the vendors' own release channels, confirmed against each project's
official install script or package registry. Each client carries an ordered list of
:class:`VersionProbe`s — a primary channel and a changelog/registry fallback — tried in
order until one yields a version.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VersionProbe:
    """One first-party way to read a client's latest published version.

    Attributes:
        kind: How to read the fetched body — ``"text"`` (the whole body, a bare
            version string), ``"json"`` (a dotted path into the parsed JSON), or
            ``"regex"`` (the first capture group of ``selector``).
        url: The endpoint to GET.
        selector: The dotted JSON path (``kind="json"``) or the regex with one capture
            group (``kind="regex"``); ignored for ``"text"``.
        strip_prefix: A leading token to drop from the extracted value (e.g. ``"rust-v"``
            or ``"v"`` on a git tag).
    """

    kind: str
    url: str
    selector: str = ""
    strip_prefix: str = ""


@dataclass(frozen=True)
class Prerequisite:
    """A tool a client's install path needs first (e.g. ``uv`` for Vibe).

    Attributes:
        binary: The executable to detect on ``PATH``.
        display: The human-readable name.
        install_unix: The install command on macOS / Linux.
        install_windows: The install command on Windows.
    """

    binary: str
    display: str
    install_unix: str
    install_windows: str

    def install_for(self, system: str) -> str:
        """Return the install command for an OS (``platform.system()`` value)."""
        return self.install_windows if system == "Windows" else self.install_unix


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
        login: How to authenticate once installed.
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


# ``uv`` is Astral's Python tool installer. gmlw itself may have arrived via pip / pipx,
# so uv is not guaranteed to be present even though the user is running gmlw — Vibe's
# only supported install path needs it, so the guided setup offers it first when absent.
UV = Prerequisite(
    binary="uv",
    display="uv",
    install_unix="curl -LsSf https://astral.sh/uv/install.sh | sh",
    install_windows=(
        'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    ),
)


CLAUDE = ClientInfo(
    name="claude",
    binary="claude",
    display="Claude Code",
    subscription="Claude Pro / Max / Team / Enterprise",
    # The native installer is Anthropic's recommended path (npm is now deprecated); it
    # needs only curl and self-updates in the background.
    install_unix="curl -fsSL https://claude.ai/install.sh | bash",
    install_windows="irm https://claude.ai/install.ps1 | iex",
    login="claude   (first run opens a browser)",
    update="claude update",
    version_probes=(
        # The stable channel the native installer and `claude update` target.
        VersionProbe(kind="text", url="https://downloads.claude.ai/claude-code-releases/stable"),
        VersionProbe(
            kind="regex",
            url="https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md",
            selector=r"(?m)^#+\s*([0-9]+\.[0-9]+\.[0-9]+)",
        ),
    ),
)
CURSOR = ClientInfo(
    name="cursor",
    binary="cursor-agent",
    display="Cursor CLI",
    subscription="Cursor Pro / Business",
    install_unix="curl https://cursor.com/install -fsS | bash",
    install_windows="irm 'https://cursor.com/install?win32=true' | iex",
    login="cursor-agent login",
    update="cursor-agent update",
    version_probes=(
        # Cursor embeds the current version in its own install script's download URL.
        VersionProbe(
            kind="regex",
            url="https://cursor.com/install",
            selector=r"lab/([^/\"'\s]+)/",
        ),
        VersionProbe(
            kind="json",
            url="https://formulae.brew.sh/api/cask/cursor-cli.json",
            selector="version",
        ),
    ),
)
CODEX = ClientInfo(
    name="codex",
    binary="codex",
    display="OpenAI Codex CLI",
    subscription="ChatGPT Plus / Pro / Team (or an API key)",
    install_unix="curl -fsSL https://chatgpt.com/codex/install.sh | sh",
    install_windows=(
        'powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"'
    ),
    login="codex login   (ChatGPT account or API key)",
    # No dedicated updater subcommand; re-running the native installer upgrades in place.
    version_probes=(
        VersionProbe(
            kind="json",
            url="https://registry.npmjs.org/@openai/codex/latest",
            selector="version",
        ),
        VersionProbe(
            kind="json",
            url="https://api.github.com/repos/openai/codex/releases/latest",
            selector="tag_name",
            strip_prefix="rust-v",
        ),
    ),
)
VIBE = ClientInfo(
    name="vibe",
    binary="vibe",
    display="Mistral Vibe",
    subscription="Mistral La Plateforme / Le Chat Pro",
    install_unix="uv tool install mistral-vibe",
    install_windows="uv tool install mistral-vibe",
    login="vibe   (first run opens the setup wizard; or set MISTRAL_API_KEY)",
    update="uv tool upgrade mistral-vibe",
    prereq=UV,
    version_probes=(
        VersionProbe(
            kind="json",
            url="https://pypi.org/pypi/mistral-vibe/json",
            selector="info.version",
        ),
        VersionProbe(
            kind="json",
            url="https://api.github.com/repos/mistralai/mistral-vibe/releases/latest",
            selector="tag_name",
            strip_prefix="v",
        ),
    ),
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
