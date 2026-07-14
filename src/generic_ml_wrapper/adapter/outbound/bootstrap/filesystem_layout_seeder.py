# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``LayoutSeederPort``: create ``~/.gmlw`` dirs and a commented config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort

if TYPE_CHECKING:
    from pathlib import Path

_DIRS = ("profile/me", "profile/company", "rules")
_CONFIG = "config.toml"

# Seeded once when no config exists. Every real setting is commented out, so the
# file parses to nothing and the wrapper keeps its built-in defaults until edited.
_CONFIG_TEMPLATE = """\
# gmlw configuration. Every setting is optional; delete this file to fall back to
# the built-in defaults. Uncomment and edit what you need.

[client]
# The client to wrap when --client is not given.
# Built-in clients: claude | cursor | codex | vibe.
# default = "claude"

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

# The context compressor is one such interceptor. It compresses through generic-ml-cache
# (record/replay), so compressing the same context replays for free and returns the same
# result. It is OFF until [compress] prompt names a prompt file (the prompt is your IP —
# the repo ships none). To enable it, add it as an interceptor on the "context" target:
# [[interceptors]]
# target = "context"
# spec = "generic_ml_wrapper.adapter.outbound.interceptor.compressor:CompressorInterceptor"

[compress]
# The compression prompt file (NOT shipped — it is your IP). Compression stays off
# until this points at a prompt.
# prompt = "/path/to/compress-prompt.md"
#
# We tested gpt-5.4 at low effort via the cursor adapter as the best compressor; change
# it to whatever you have (any generic-ml-cache client adapter / model / effort).
# adapter = "cursor"
# model = "gpt-5.4"
# effort = "low"
"""


class FilesystemLayoutSeeder(LayoutSeederPort):
    """Create the ``~/.gmlw`` profile/rules directories and seed a default config."""

    def __init__(self, home: Path) -> None:
        """Bind the seeder to the runtime home directory.

        Args:
            home: The ``~/.gmlw`` root under which the layout is created.
        """
        self._home = home

    def ensure(self) -> None:
        """Create missing ``profile/me``, ``profile/company``, ``rules`` and config."""
        self._home.mkdir(parents=True, exist_ok=True)
        # Owner-only: the home holds credentials, config (which names code to run), and state.
        self._home.chmod(0o700)
        for relative in _DIRS:
            (self._home / relative).mkdir(parents=True, exist_ok=True)
        config = self._home / _CONFIG
        if not config.exists():
            config.write_text(_CONFIG_TEMPLATE, encoding="utf-8")
