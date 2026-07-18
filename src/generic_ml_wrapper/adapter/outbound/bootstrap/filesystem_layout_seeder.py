# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``LayoutSeederPort``: create ``~/.gmlw`` dirs and a commented config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.learned import NOTEBOOK_TEMPLATE
from generic_ml_wrapper.application.domain.model.rules import EXAMPLE_RULE
from generic_ml_wrapper.application.port.outbound.layout_seeder import (
    InitSelections,
    LayoutSeederPort,
)

if TYPE_CHECKING:
    from pathlib import Path

# The personas/ folder is seeded on demand by the persona source (packaged defaults),
# so it is not created here. Place-specific context lives under environments/<env>/ now
# (created by `initialize` for the chosen env); the old profile/company is migrated into it.
_DIRS = ("profile/me", "rules")
_ENVIRONMENTS = "environments"
# Role-scoped rules/learned live per role; init seeds the chosen role's folder (with an
# empty rules/ drop-zone mirroring the global rules/). The role is a lens over `me`.
_ROLES = "profile/roles"
_CONFIG = "config.toml"
# The learned notebook, seeded empty (header + the two sections) for the client to fill.
_LEARNED = "profile/me/learned.md"
# A draft example rule (never injected) so the user has the rule format to copy.
_EXAMPLE_RULE = "rules/example.rule.md"


# The seed for the ``[init]`` gate marker: an active ``version`` once init has run, else a
# commented block so the file parses to no ``[init]`` and the gate still forces init.
_INIT_MARKER_PLACEHOLDER = "__INIT_MARKER__"


def _init_marker_block(version: str | None) -> str:
    """Render the ``[init]`` marker: active ``version`` when init ran, else commented."""
    if not version:
        return '# [init]\n# version = "0.0.0"   # written by `gmlw init`; presence is the gate'
    return (
        "[init]\n"
        "# Recorded by `gmlw init`; its presence is the gate that you have been set up.\n"
        f'version = "{version}"'
    )


_LANGUAGE_CODE_PLACEHOLDER = "__LANGUAGE_CODE__"


def _language_line(code: str | None) -> str:
    """Render the ``[language] code`` line: active when init chose one, else commented."""
    if not code:
        return '# code = "en"'
    return f'code = "{code}"'


_DEFAULT_ROLE_PLACEHOLDER = "__DEFAULT_ROLE__"
_DEFAULT_ENVIRONMENT_PLACEHOLDER = "__DEFAULT_ENVIRONMENT__"


def _role_line(role: str | None) -> str:
    """Render the ``[profile] default_role`` line: active when chosen, else commented."""
    if not role:
        return '# default_role = "default"'
    return f'default_role = "{role}"'


def _environment_line(environment: str | None) -> str:
    """Render the ``[profile] default_environment`` line: active when chosen, else commented."""
    if not environment:
        return '# default_environment = "work"'
    return f'default_environment = "{environment}"'


# The seed for the ``[client] default`` line: the active choice picked on first run,
# else a commented placeholder so the file parses to nothing and the built-in default
# applies until edited. Substituted into ``_CONFIG_TEMPLATE`` at ``__CLIENT_DEFAULT__``.
_CLIENT_DEFAULT_PLACEHOLDER = "__CLIENT_DEFAULT__"


def _client_default_line(default_client: str | None) -> str:
    """Render the ``[client] default`` line: active when chosen, else commented."""
    if not default_client:
        return '# default = "claude"'
    return (
        "# gmlw set this on first run from the client(s) found on your PATH.\n"
        f'default = "{default_client}"'
    )


_COMPANION_NAME_PLACEHOLDER = "__COMPANION_NAME__"


def _companion_name_line(name: str | None) -> str:
    """Render the ``[companion] name`` line: active when init captured one, else commented."""
    if not name:
        return '# name = "Ada"'
    return f'name = "{name}"'


_COMPANION_PERSONA_PLACEHOLDER = "__COMPANION_PERSONA__"


def _companion_persona_line(persona: str | None) -> str:
    """Render the ``[companion] persona`` line: active when chosen, else commented."""
    if not persona:
        return '# persona = "companion"'
    return f'# gmlw set this on first run.\npersona = "{persona}"'


# Seeded once when no config exists. Every real setting but the init-chosen ones is
# commented out, so the file parses to just those choices (or, on a bootstrap write with
# nothing chosen, to nothing — keeping the built-in defaults).
_CONFIG_TEMPLATE = """\
# gmlw configuration. Every setting is optional; delete this file to fall back to
# the built-in defaults. Uncomment and edit what you need.

# Init marker. `gmlw init` writes this once; while it is absent, gmlw funnels you
# through the forced first-run setup before any command runs.
__INIT_MARKER__

[language]
# The language gmlw speaks TO YOU (onboarding now; receipts/help later). It does NOT
# force the companion's language. Supported: en | fr.
__LANGUAGE_CODE__

[profile]
# The movie-set axes chosen at init: the role you play (a lens over `me`, not a copy of
# it) and the environment the work happens in. Changeable later via the config commands.
__DEFAULT_ROLE__
__DEFAULT_ENVIRONMENT__

[client]
# The client to wrap when --client is not given.
# Built-in clients: claude | cursor | codex | vibe.
__CLIENT_DEFAULT__

# SECURITY: the [callers] and [[interceptors]] specs below name Python code that gmlw
# LOADS AND RUNS with your permissions on the next invocation. Only point them at code
# you wrote or trust -- this file is a trusted-code boundary.

[callers]
# Per-client caller overrides, loaded at runtime in place of the built-in caller.
# The value is either an importable "module:Class" / "/path/to/file.py:Class" spec, OR
# a plugin id -- a folder in ~/.gmlw/plugins/<id>/ with a plugin.toml (see: gmlw plugins
# list). The plugin id is the tidy way to plug in a private metering caller.
# cursor = "cursor-mitm"                                   # by plugin id
# cursor = "/path/to/my_cursor_caller.py:CursorCaller"     # by explicit spec

[logging]
# Diagnostic verbosity on stderr: debug | info | warning | error.
# level = "warning"

[transcript]
# Persist the request, response, and usage of each metered call under
# transcripts/<job>/<session>/ as a portable per-call trio (call_NNN.in.json /
# .out.sse / .usage.json). Default: OFF. It contains your prompts and the model's
# replies -- a local data-at-rest surface you own; nothing manages retention.
# enabled = true
# root = "/some/dir"   # optional; defaults to ~/.gmlw/transcripts

# Interceptors (0..N, ordered), each a str->str transform (InterceptorPort) bound to
# a target. Compile-time targets: "profile" | "rules" | "workflow" | "context". Wire
# targets (metered clients only): "request" (outbound body) | "response" (captured
# reply, observe-only). A target may have many; one spec may appear under several.
# The built-in MessageSizeLogger logs each message's size — put it on request and
# response to trace sizes in and out:
# [[interceptors]]
# target = "request"
# spec = "generic_ml_wrapper.adapter.outbound.interceptor.size_logger:MessageSizeLogger"
# [[interceptors]]
# target = "response"
# spec = "generic_ml_wrapper.adapter.outbound.interceptor.size_logger:MessageSizeLogger"

# Hooks (0..N, ordered), each an action (HookPort) run at a lifecycle seam bracketing the
# client run — not a content transform (that is an interceptor) but a side effect. Phases:
# "pre-launch" (after the context is compiled and the caller resolved, before the client
# starts — for per-client setup: deploy skills/rules, write MCP config, warm a cache) and
# "post-session" (after the client exits, with its exit code — for cleanup, notification,
# archival). Each spec is a "module:Class" / "/path.py:Class" or a plugin id; an optional
# client scopes the hook to one client. Best-effort: a failing hook never breaks a launch.
# The built-in SessionLogger appends a line at each seam — a template for your own hooks:
# [[hooks]]
# phase = "pre-launch"
# spec = "generic_ml_wrapper.adapter.outbound.hook.session_logger:SessionLogger"
# [[hooks]]
# phase = "post-session"
# spec = "generic_ml_wrapper.adapter.outbound.hook.session_logger:SessionLogger"
# client = "claude"   # optional; omit to run for every client

# Context packaging. On every run gmlw composes an operating context from a fixed set of
# sources; [startup] decides, per mode, which are active and which are compressed. Modes:
# default (a plain `gmlw start`), workflow (`start -w`), authoring (`workflow new`).
# Sources: me.user (profile/me/*.md), me.learned (profile/me/learned*), company
# (environments/<env>/*.md — the active [profile] default_environment), rules (rules/*.md),
# persona (the selected persona + shared floor,
# see [companion]); a workflow run also composes its base and steps. Omit all of this for the
# built-in per-mode defaults; the default-mode defaults, shown explicitly:
# [startup.default.context.me]
# user    = { activated = true,  compression = false }
# learned = { activated = true,  compression = false }
# [startup.default.context]
# company = { activated = true,  compression = false }
# rules   = { activated = true,  compression = false }
# persona = { activated = false, compression = false }
# In workflow/authoring modes base and steps are always active — only their compression
# is configurable:
# [startup.workflow.context]
# base  = { compression = false }
# steps = { compression = true }

[companion]
# The persona gmlw adopts: it voices a free host greeting at launch, and its tone is
# injected as the `persona` context source (when that source is activated above). Off
# (invisible) until set. See the choices with: gmlw persona list. Author your own by
# dropping a file in ~/.gmlw/personas/. Built-in: plain | companion | mentor | butler | terse.
# `name` is what the companion calls you (falls back to your OS user when unset).
__COMPANION_NAME__
__COMPANION_PERSONA__

[compress]
# When a source has compression = true, gmlw compresses it through generic-ml-cache
# (record/replay — the same source replays for free). The prompt is chosen by the source's
# data type; each is your IP (the repo ships none), so a source stays verbatim until a
# prompt resolves for it. Kinds: human-touch (me.user + me.learned), technical (workflow
# base + steps), rules (rules); company/persona are verbatim.
# adapter = "cursor"   # any generic-ml-cache client adapter / model / effort
# model = "gpt-5.4"
# effort = "low"
# [compress.prompts]
# A prompt file per kind, OR per specific source key (the key wins over the kind):
# human-touch = "/path/to/human-touch.md"
# technical = "/path/to/technical.md"
# rules = "/path/to/rules.md"
# "me.user" = "/path/to/just-me-user.md"   # override the kind for one source only
"""


def _render_config(  # noqa: PLR0913  (one keyword per config placeholder; all optional)
    *,
    init_version: str | None,
    language: str | None,
    name: str | None,
    role: str | None,
    environment: str | None,
    client: str | None,
    persona: str | None,
) -> str:
    """Fill every ``_CONFIG_TEMPLATE`` placeholder, active or commented, into one file."""
    return (
        _CONFIG_TEMPLATE.replace(_INIT_MARKER_PLACEHOLDER, _init_marker_block(init_version))
        .replace(_LANGUAGE_CODE_PLACEHOLDER, _language_line(language))
        .replace(_DEFAULT_ROLE_PLACEHOLDER, _role_line(role))
        .replace(_DEFAULT_ENVIRONMENT_PLACEHOLDER, _environment_line(environment))
        .replace(_CLIENT_DEFAULT_PLACEHOLDER, _client_default_line(client))
        .replace(_COMPANION_NAME_PLACEHOLDER, _companion_name_line(name))
        .replace(_COMPANION_PERSONA_PLACEHOLDER, _companion_persona_line(persona))
    )


class FilesystemLayoutSeeder(LayoutSeederPort):
    """Create the ``~/.gmlw`` profile/rules directories and seed a default config."""

    def __init__(self, home: Path) -> None:
        """Bind the seeder to the runtime home directory.

        Args:
            home: The ``~/.gmlw`` root under which the layout is created.
        """
        self._home = home

    def ensure(self, default_client: str | None = None, persona: str | None = None) -> None:
        """Create missing ``profile/me``, ``profile/company``, ``rules`` and config.

        The config write leaves the init-owned tables (``[init]``, ``[language]``,
        ``[profile]``, ``[companion] name``) commented — bootstrap must not stamp the
        gate marker; only :meth:`initialize` does.

        Args:
            default_client: When seeding a new config, bake this in as the active
                ``[client] default``. ``None`` seeds the commented placeholder.
            persona: When seeding a new config, bake this in as the active
                ``[companion] persona``. ``None`` seeds the commented placeholder.
        """
        self._ensure_dirs()
        config = self._home / _CONFIG
        if not config.exists():
            config.write_text(
                _render_config(
                    init_version=None,
                    language=None,
                    name=None,
                    role=None,
                    environment=None,
                    client=default_client,
                    persona=persona,
                ),
                encoding="utf-8",
            )

    def initialize(self, selections: InitSelections) -> bool:
        """Persist an init pass: full config on a fresh install, marker-only on a legacy one.

        Args:
            selections: What the init interview resolved.

        Returns:
            ``True`` on a fresh full write, ``False`` when only the marker was appended.
        """
        self._ensure_dirs()
        # The chosen environment's folder — the movie set the migration wraps company into.
        (self._home / _ENVIRONMENTS / selections.environment).mkdir(parents=True, exist_ok=True)
        # The chosen role's folder, with an empty rules/ drop-zone (role-scoped reflexes).
        (self._home / _ROLES / selections.role / "rules").mkdir(parents=True, exist_ok=True)
        config = self._home / _CONFIG
        if config.exists():
            self._append_marker(config, selections.version)
            return False
        config.write_text(
            _render_config(
                init_version=selections.version,
                language=selections.language,
                name=selections.name,
                role=selections.role,
                environment=selections.environment,
                client=selections.client,
                persona=selections.persona,
            ),
            encoding="utf-8",
        )
        return True

    def _ensure_dirs(self) -> None:
        """Create the runtime directories and the copy-me seed files (missing-only)."""
        self._home.mkdir(parents=True, exist_ok=True)
        # Owner-only: the home holds credentials, config (which names code to run), and state.
        self._home.chmod(0o700)
        for relative in _DIRS:
            (self._home / relative).mkdir(parents=True, exist_ok=True)
        learned = self._home / _LEARNED
        if not learned.exists():
            learned.write_text(NOTEBOOK_TEMPLATE, encoding="utf-8")
        example_rule = self._home / _EXAMPLE_RULE
        if not example_rule.exists():
            example_rule.write_text(EXAMPLE_RULE, encoding="utf-8")

    @staticmethod
    def _append_marker(config: Path, version: str) -> None:
        """Append the ``[init]`` marker to a legacy config, once (append-only, idempotent).

        A pre-init config already carries the user's settings and comments; rather than
        rewrite it (and risk losing either), the marker is appended at the end. Guarded so
        a re-run is a no-op — a legacy config already carrying ``[init]`` is left as is.
        """
        existing = config.read_text(encoding="utf-8")
        if "[init]" in existing:
            return
        separator = "" if existing.endswith("\n") else "\n"
        config.write_text(
            f"{existing}{separator}\n{_init_marker_block(version)}\n",
            encoding="utf-8",
        )
