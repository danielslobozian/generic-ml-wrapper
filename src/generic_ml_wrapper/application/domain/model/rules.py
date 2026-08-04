# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The rule format: a user-editable template and the capture directive that carries it.

A rule is a *correction the user demanded* — a reusable reflex to apply again, born
from a concrete dissatisfaction (distinct from ``learned``, which is what the AI
notices about the user). The format is trimmed to fields that fit any job:
``Rule`` / ``When`` / ``Signals`` / ``Strength`` / ``Origin`` (+ an optional
``Precedence``). ``Origin`` is provenance for the user and is stripped before the
model; the rest reach it.

A rule is a projection of the *user*, so it lives on one of the two axes that describe
them: the **environment** (the place — its processes and standards) or the **role**
(the craft — how the work is done, wherever it happens). There is no global tier and
no workflow tier: a workflow that behaves wrongly is fixed in the workflow itself.

``RULE_TEMPLATE`` is seeded once to ``~/.gmlw/templates/rule.template.md`` and never
overwritten, so a user who reshapes it keeps their version — and because
:func:`rule_capture_directive` embeds whatever is on disk, their edits are what the
model is told to follow.

A rule is **active from the moment it is created** — the user demanded it, so it applies.
``status: draft`` is the off-switch they reach for later to retire a rule without deleting
it; a draft is read but injected into no session.
"""

from __future__ import annotations

# Seeded once to ``templates/rule.template.md``. Kept free of commentary so it can be
# embedded verbatim into the capture directive — one copy of the format, not two.
RULE_TEMPLATE = """\
---
name: <slug>
status: active
---
# <slug>

**Rule:** State the correction as an instruction — what to do, or never do, every time
it applies.

**When:** The situation that should trigger it, described so it is recognisable in work
you have not seen yet.

**Signals:** How you know you are in that situation — the tells that this rule applies.

**Strength:** soft   (soft = a strong preference; hard = always applies, never trimmed)

**Precedence:** (optional) a number; the higher one wins when two rules conflict.

**Origin:** Where this came from — the moment it was demanded. This stays with you; it
is stripped before the model sees the rule.
"""

DIRECTIVE_TEMPLATE = """\
## Rules — the user's demanded reflexes

The user keeps rules that gmlw reads into every AI tool they use, so a standard held in
one client holds in all of them. Their active rules, if any, are included with this note.

A rule lives on one of two axes, and this session has one of each active:

- **environment — `{environment}`** — a **constraint**, set by the company, the project, or
  the tooling: how documentation is written here, how a particular service is built, how the
  code is linted. Not the user's preference and not open to their taste — it is how this
  place works, and it stops applying elsewhere.
- **role — `{role}`** — a **preference or decision of the user's own**, about the craft:
  design patterns, how they approach code, what they consider good work. It travels with
  them wherever they work.

When the two conflict, the environment rule wins: a constraint is not overridden by a
preference. Within a single axis, an explicit `Precedence:` number decides.

There is no general or per-workflow rule. If a workflow behaves wrongly, fix the workflow.

When the user is dissatisfied with something you did and wants it to never happen again —
or otherwise asks you to hold to a standard — offer to record it as a rule. A rule is a
*reusable reflex*, not a one-off: a choice that only makes sense for this one task is not a
rule, but a one-off decision often encodes a reflex underneath — extract the reflex, drop
the specifics. Offer, don't impose: one line, and only when the reflex is genuinely durable
and reusable.

Work out which axis it belongs to and say which you propose and why — but the choice is the
user's, so let them redirect it. When you genuinely cannot tell, ask rather than guess: a
rule filed on the wrong axis is silently absent from every session that does not use it.

Before writing one, read the existing rules on the axis you are about to write to (drafts
included). If one already covers this, update or supersede that file in place rather than
stacking a near-duplicate — the same way you correct the learned notebook on a contradiction
instead of piling a second, conflicting note on top.

Then judge whether the rule is *mechanically enforceable* — deterministic and checkable by a
script (a formatter, a lint, a guard), rather than needing judgment, taste, or reading intent.
If it is, offer to realise it as a small script or check the user can run, not just a standing
reminder — faster and reliable. Offer the code, leave the judgment rules as prose, and get the
user's OK before writing either.

Write the new rule as `<slug>.rule.md` in the folder for the chosen axis:

- environment → `{environment_dir}`
- role → `{role_dir}`

Write it `status: active`: the user demanded this correction, so it applies from the moment
it is recorded — do not park it awaiting approval. Setting `status: draft` is *their* switch,
to retire a rule later without deleting it. This is the user's own template — if they have
reshaped it, follow their version:

{template}
"""
