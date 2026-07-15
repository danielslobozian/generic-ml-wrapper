# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The rule format: a domain-neutral, seeded example of a user-authored rule.

A rule is a *correction the user demanded* — a reusable reflex to apply again, born
from a concrete dissatisfaction (distinct from ``learned``, which is what the AI
notices about the user). The mature software-review format is trimmed here to fields
that fit any job: ``Rule`` / ``When`` / ``Signals`` / ``Strength`` / ``Origin`` (+ an
optional ``Precedence``). ``Origin`` is provenance for the user and is stripped before
the model; the rest reach it. Rules live under ``~/.gmlw/rules/*.rule.md``; a
``status: draft`` rule is not injected until the user promotes it to ``active``.
"""

from __future__ import annotations

# Seeded once into ``rules/example.rule.md`` as a draft (never injected), so the user
# has the format in front of them to copy. Frontmatter + the six fields.
EXAMPLE_RULE = """\
---
name: example
status: draft
---
# example — a template, not an active rule

**Rule:** State the correction as an instruction — what to do, or never do, every time
it applies.

**When:** The situation that should trigger it, described so it is recognisable in work
you have not seen yet.

**Signals:** How you know you are in that situation — the tells that this rule applies.

**Strength:** soft   (soft = a strong preference; hard = always applies, never trimmed)

**Precedence:** (optional) a number; the higher one wins when two rules conflict.

**Origin:** Where this came from — the moment it was demanded. This stays with you; it
is stripped before the model sees the rule.

<!-- This file is status: draft, so gmlw does not inject it. Copy it, rename to
<your-rule>.rule.md, fill it in, and set status to active to turn it on. Keep Origin
for yourself; the model sees Rule / When / Signals / Strength / Precedence. -->
"""
