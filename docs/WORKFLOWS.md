# Workflows

A workflow is an *optional* operating context you author once and then launch a job
with. It is not required: `gmlw start <job>` with no workflow is already the whole
wrapper — it meters, records, and renders the status line exactly the same. A
workflow just prepends a compiled set of instructions ("here is how you behave, and
here are the steps for this kind of task") to the session so you don't re-explain the
job every time.

If you have never authored one, you can ignore this file entirely and use
[USER_GUIDE.md](USER_GUIDE.md) and [CLI.md](CLI.md).

## Creating one

    gmlw workflow new <name>

This runs the shipped `create-workflow` meta-workflow as a metered **authoring**
session (kind `authoring`, so it stays hidden from `gmlw jobs`). It is a warm,
one-question-at-a-time interview, not a form. It:

1. **Interviews you** about a task you do repeatedly — what it's for, how you do it
   today start to finish, what "done" looks like, and what you always check. It keeps
   a running "what I've captured so far" summary visible as it goes.
2. **Drafts lean, ordered steps** from your answers — one clear purpose and one
   concrete output per step — and shows them as a table with a **Code?** column that
   marks each step's nature:
   - scriptable — deterministic and mechanical (parsing, formatting, file moves,
     computations, a fixed API call)
   - partly — a mix of mechanical and judgment
   - needs judgment — taste, intent, reviewing tone, drafting prose
3. **Offers to script the mechanical ones** into `scripts/` (python or shell). You
   approve each one; a scripted step then becomes "run `scripts/<name>`" instead of
   re-reasoning it every run — faster, cheaper, reliable. Judgment steps stay with
   the model.
4. **Writes `workflow.md`** into the new workflow's folder and tells you how to run
   it.

You can pass `--client X` to author under a specific client. See [CLI.md](CLI.md) for
the full command surface.

## File layout

A workflow lives under `~/.gmlw/workflows/<name>/`:

    ~/.gmlw/workflows/
      _common/              # shared base — never runnable
      create-workflow/      # the meta-workflow — never runnable
      <name>/
        workflow.md         # required: the ordered steps
        rules/              # optional: workflow-scoped rules
        scripts/            # optional: scripted mechanical steps

Only `workflow.md` is required. The hidden `_common/` and `create-workflow/` folders
are packaged with the wrapper and are **never** listed as runnable workflows by
`gmlw workflow list`.

## Compilation order

At launch the workflow is compiled into a **single blob** and injected into the child
client. For claude that is a native `--append-system-prompt-file`; other clients
receive it via a context-file or initial instruction (see [CLIENTS.md](CLIENTS.md)).

The stages are assembled in this **fixed order**:

    _common/base.md  →  profile/*  →  global rules  →  workflow rules  →  workflow steps

- `_common/base.md` — the shared "how to behave" base (orient first, one step at a
  time, work in the user's language, offer to capture rules).
- `profile/*` — your `me/` and `company/` context.
- global rules — `~/.gmlw/rules/*`.
- workflow rules — the workflow's own `rules/`.
- workflow steps — this workflow's `workflow.md`.

Each stage passes through the interceptor chain on its way in (see
[CONFIGURATION.md](CONFIGURATION.md) for interceptors and the per-mode context
matrix that decides which sources are activated and compressed).

**Rule cleaning** happens on every rule, always, and is lossless: the YAML
frontmatter and the `Origin`/`Notes` sections are stripped before the model sees the
rule, and any rule marked `status: draft` is skipped entirely.

## Rules

A rule is a *reusable reflex* — a standard you want held to on every future run, not
a one-off decision about a single task. Rules live at
`~/.gmlw/rules/<slug>.rule.md`:

    ---
    name: <slug>
    status: draft
    ---
    # <slug>

    **Rule:** <what to do, or never do>
    **When:** <the situation that should trigger it>
    **Signals:** <how to recognise you are in that situation>
    **Strength:** hard   (always applies) — or soft (a strong preference)
    **Origin:** <the moment it was demanded — stripped before the model>

Fields: `Rule`, `When`, `Signals`, `Strength` (`soft` | `hard`), `Origin`
(provenance, stripped before the model), and an optional `Precedence: <n>` (higher
wins) added only when a rule may conflict with another.

A rule with `status: draft` is **not injected** until you promote it to `active` by
editing that field. Rules are captured during a workflow: when you are dissatisfied
with something and want it to never happen again, the client offers to record it as a
draft for your approval.

> Forward note: proposing rules during normal, non-workflow usage is on the 0.3.0
> roadmap — see [../ROADMAP.md](../ROADMAP.md). Today only workflow sessions offer
> them.

## Scripts

When a step is mechanical, the authoring flow offers to turn it into a script under
`scripts/<name>` (python or shell). The workflow's instruction for that step then
becomes "run `scripts/<name>`" — the wrapper runs the script instead of having the
model re-reason a deterministic task every run. Keep judgment steps as prose for the
model; script only what genuinely simplifies.

## Credentials

If a workflow (or its scripts) needs a secret, register the environment variable it
should be exposed under:

    gmlw creds set <workflow> <ENV_VAR>

The value is stored in `~/.gmlw/credentials.toml` (mode `0600`) and injected into the
child process environment at launch. A corrupt `credentials.toml` is never
overwritten. See [SECURITY.md](../SECURITY.md) for the credential handling boundary.

## A complete example

Author a `doc-review` workflow:

    gmlw workflow new doc-review

The interview draws out how you review docs today. Suppose it lands on three steps —
the first mechanical (collect the changed files), the last two judgment. It offers to
script step 1 into `scripts/collect.sh`, you accept, and it writes
`~/.gmlw/workflows/doc-review/workflow.md`:

    # doc-review

    *Review a documentation change for clarity and correctness before it ships.*

    ## Steps

    ### 1. Collect the changed docs
    Run `scripts/collect.sh` to list the docs touched on this branch and gather
    their diffs.

    ### 2. Review clarity and accuracy
    Read each changed doc. Flag anything unclear, out of date, or contradicted by
    the code. Propose concrete rewrites — do not just point at problems.

    ### 3. Report and stop
    Summarise the findings as a short checklist the author can act on, then stop.

Then launch a real job with it:

    gmlw start DOCS-1 -w doc-review

The session opens with `_common/base.md` + your profile + rules + `doc-review`'s
steps compiled in, orients itself, and waits for you to confirm before running step
one. It is metered and recorded like any other job (`gmlw sessions DOCS-1`,
`gmlw export DOCS-1`).

---

See also: [USER_GUIDE.md](USER_GUIDE.md) · [CLI.md](CLI.md) ·
[CONFIGURATION.md](CONFIGURATION.md) · [CLIENTS.md](CLIENTS.md) ·
[DESIGN.md](DESIGN.md) · [../ROADMAP.md](../ROADMAP.md) ·
[../SECURITY.md](../SECURITY.md)
