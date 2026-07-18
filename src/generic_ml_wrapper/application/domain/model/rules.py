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

# Injected as the head of the ``rules`` context section (gmlw's voice to the client), so
# rule capture is *always-on* — a demanded correction becomes a draft rule in any session,
# not only inside a workflow. It carries the whole rule loop: (1) offer to record a durable,
# reusable reflex; (2) before writing, read the existing rules and update/supersede a match
# instead of duplicating (mirrors the learned notebook's supersede-on-contradiction); and
# (3) judge whether the rule is mechanically enforceable and, if so, offer to realise it as a
# script/check — the create-workflow step-codeability logic generalised from steps to rules.
# The inline template mirrors ``EXAMPLE_RULE`` so a written file is correct on the first try.
RULE_CAPTURE_DIRECTIVE = """\
## Rules — the user's demanded reflexes

The user keeps rules at ~/.gmlw/rules/*.rule.md — corrections they demanded, that gmlw
reads into every AI tool they use, so a standard held in one client holds in all of them.
Their active rules, if any, are included with this note.

When the user is dissatisfied with something you did and wants it to never happen again —
or otherwise asks you to hold to a standard — offer to record it as a rule. A rule is a
*reusable reflex*, not a one-off: a choice that only makes sense for this one task is not a
rule, but a one-off decision often encodes a reflex underneath — extract the reflex, drop
the specifics. Offer, don't impose: one line, and only when the reflex is genuinely durable
and reusable.

Before writing one, read the existing rules in ~/.gmlw/rules/ (drafts included). If one
already covers this, update or supersede that file in place rather than stacking a
near-duplicate — the same way you correct the learned notebook on a contradiction instead
of piling a second, conflicting note on top.

Then judge whether the rule is *mechanically enforceable* — deterministic and checkable by a
script (a formatter, a lint, a guard), rather than needing judgment, taste, or reading intent.
If it is, offer to realise it as a small script or check the user can run, not just a standing
reminder — faster and reliable. Offer the code, leave the judgment rules as prose, and get the
user's OK before writing either.

Write a new rule to ~/.gmlw/rules/<slug>.rule.md as status: draft, so the user approves it
(they promote it by editing status to active):

    ---
    name: <slug>
    status: draft
    ---
    # <slug>

    **Rule:** <the correction, as an instruction — what to do, or never do>
    **When:** <the situation that should trigger it>
    **Signals:** <how to recognise you are in that situation>
    **Strength:** hard   (always applies) — or soft (a strong preference)
    **Origin:** <the moment it was demanded — stays with the user; stripped before the model>

Add **Precedence:** <n> only when it may conflict with another rule (higher wins).
"""
