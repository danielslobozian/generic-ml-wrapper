# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Redact secrets and PII from diagnostic records before they are written.

A wrapper's diagnostics are unusually sensitive: everything that flows through gmlw
is somebody's API key, bearer token, or context derived from their own journal. A log
file is durable and gets pasted into issues, so scrubbing happens *in the sink* — the
one place every record must pass through — rather than being a discipline each of the
hundred call sites has to remember.

Two mechanisms, deliberately both:

- **By key name.** A value stored under ``token``/``password``/``authorization``/… is
  redacted whatever it looks like, because a short or oddly-shaped secret is still a
  secret.
- **By pattern.** Applied to every string value, including rendered tracebacks — which
  is where credentials usually leak, since an exception message happily quotes the URL
  or header that failed.

**Over-redaction is its own bug.** A log that has eaten its own identifiers is useless,
so bare lowercase hex is deliberately preserved: session ids and content hashes look
exactly like a secret to an entropy heuristic. Our own values are caught by their
provenance prefix instead, which is what a prefix is for.

The rules mirror generic-ml-cache's scrubber, so the two products redact alike.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

# Key names whose value must never appear in a log, regardless of its shape.
SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "access_token",
        "credential",
        "key_material",
        "passwd",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "token",
    }
)

# Applied to every string value, and to rendered traceback text.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # E-mail addresses.
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[email]"),
    # Authorization / Bearer / api-key header values.
    (re.compile(r"(?i)(bearer|token|api[-_]?key)\s+[A-Za-z0-9\-._~+/=]{8,}"), r"\1 [token]"),
    # Anthropic / OpenAI style keys, caught by their provenance prefix.
    (re.compile(r"\b(sk-ant-|sk-|xai-|gsk_)[A-Za-z0-9\-_]{16,}"), "[secret]"),
    # generic-ml-cache's own encryption token, likewise by prefix: its body is bare
    # lowercase hex, indistinguishable from a checksum, so the entropy rule below
    # deliberately cannot catch it.
    (re.compile(r"gmlc_[0-9a-f]{32,}"), "[secret]"),
    # AWS access key id: fixed AKIA prefix + 16 chars. Too short for the entropy rule,
    # but a hard secret indicator by prefix.
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[secret]"),
    # Long opaque strings that look like keys or tokens. Two deliberate narrowings, both
    # about not eating things we need (see the over-redaction note above):
    #   - the trigger char excludes "/", and "/" is not in the body either, so a long
    #     filesystem path is never swallowed as one token. Tracebacks are mostly paths,
    #     and a traceback with "[secret].py" in place of the file is worse than no log.
    #   - no lowercase-only match, so session ids and SHA-256 digests survive.
    (re.compile(r"[a-z0-9]*[A-Z+][A-Za-z0-9+\-_]{30,}={0,2}"), "[secret]"),
]


def scrub_text(value: str) -> str:
    """Return *value* with every secret/PII pattern replaced."""
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def scrub_value(value: object) -> object:
    """Scrub a value recursively.

    Strings are scrubbed by pattern; mappings and sequences element-wise, so a secret
    buried inside a dict or list value never leaks through its rendered ``repr``. Other
    scalars pass through untouched.
    """
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, Mapping):
        # A read-only widening: any runtime mapping is a mapping of objects, but
        # isinstance narrowing cannot parameterise the generic itself.
        mapping = cast("Mapping[object, object]", value)
        return {key: scrub_field(key, item) for key, item in mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast("list[object] | tuple[object, ...]", value)
        return type(sequence)(scrub_value(item) for item in sequence)
    return value


def scrub_field(key: object, value: object) -> object:
    """Redact by key name first, then scrub the value by pattern."""
    if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
        return "[redacted]"
    return scrub_value(value)


def scrub_record(fields: Mapping[str, object]) -> dict[str, object]:
    """Return *fields* with every key and value scrubbed."""
    return {key: scrub_field(key, value) for key, value in fields.items()}
