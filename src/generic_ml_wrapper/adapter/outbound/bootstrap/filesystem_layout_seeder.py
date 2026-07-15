# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``LayoutSeederPort``: create ``~/.gmlw`` dirs and a commented config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.learned import NOTEBOOK_TEMPLATE
from generic_ml_wrapper.application.domain.model.rules import EXAMPLE_RULE
from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort

if TYPE_CHECKING:
    from pathlib import Path

# The personas/ folder is seeded on demand by the persona source (packaged defaults),
# so it is not created here.
_DIRS = ("profile/me", "profile/company", "rules")
_CONFIG = "config.toml"
# The learned notebook, seeded empty (header + the two sections) for the client to fill.
_LEARNED = "profile/me/learned.md"
# A draft example rule (never injected) so the user has the rule format to copy.
_EXAMPLE_RULE = "rules/example.rule.md"

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


_COMPANION_PERSONA_PLACEHOLDER = "__COMPANION_PERSONA__"


def _companion_persona_line(persona: str | None) -> str:
    """Render the ``[companion] persona`` line: active when chosen, else commented."""
    if not persona:
        return '# persona = "companion"'
    return f'# gmlw set this on first run.\npersona = "{persona}"'


# Seeded once when no config exists. Every real setting but the first-run-chosen
# ``[client] default`` is commented out, so the file parses to just that choice (or to
# nothing, keeping the built-in defaults, when none was chosen).
_CONFIG_TEMPLATE = """\
# gmlw configuration. Every setting is optional; delete this file to fall back to
# the built-in defaults. Uncomment and edit what you need.

[client]
# The client to wrap when --client is not given.
# Built-in clients: claude | cursor | codex | vibe.
__CLIENT_DEFAULT__

# SECURITY: the [callers] and [[interceptors]] specs below name Python code that gmlw
# LOADS AND RUNS with your permissions on the next invocation. Only point them at code
# you wrote or trust -- this file is a trusted-code boundary.

[callers]
# Per-client caller overrides: map a client to an importable "module:Class" or
# "/path/to/file.py:Class" spec, loaded at runtime in place of the built-in caller.
# (This is how a private, uncommitted metering caller is plugged in.)
# cursor = "/path/to/my_cursor_caller.py:CursorCaller"

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

# Context packaging. On every run gmlw composes an operating context from a fixed set of
# sources; [startup] decides, per mode, which are active and which are compressed. Modes:
# default (a plain `gmlw start`), workflow (`start -w`), authoring (`workflow new`).
# Sources: me.user (profile/me/*.md), me.learned (profile/me/learned*), company
# (profile/company/*.md), rules (rules/*.md), persona (the selected persona + shared floor,
# see [companion]); a workflow run also composes its base and steps. Omit all of this for the
# built-in per-mode defaults; the default-mode defaults, shown explicitly:
# [startup.default.context.me]
# user    = { activated = true,  compression = false }
# learned = { activated = true,  compression = false }
# [startup.default.context]
# company = { activated = true,  compression = false }
# rules   = { activated = false, compression = false }
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

        Args:
            default_client: When seeding a new config, bake this in as the active
                ``[client] default``. ``None`` seeds the commented placeholder.
            persona: When seeding a new config, bake this in as the active
                ``[companion] persona``. ``None`` seeds the commented placeholder.
        """
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
        config = self._home / _CONFIG
        if not config.exists():
            text = _CONFIG_TEMPLATE.replace(
                _CLIENT_DEFAULT_PLACEHOLDER, _client_default_line(default_client)
            ).replace(_COMPANION_PERSONA_PLACEHOLDER, _companion_persona_line(persona))
            config.write_text(text, encoding="utf-8")
