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

    gmlw workflow new            # name it at the end
    gmlw workflow new <name>     # or seed a name up front (optional)

This runs the shipped `create-workflow` meta-workflow as a metered **authoring**
session. Authoring files under a job called `create-workflow` — creating and editing
alike — and `gmlw jobs` leaves that one name out, since you never chose it. The job is
otherwise ordinary: its spend is metered and its history can be deleted like any
other's. The name is decided at the **end** of the interview, not the
start — a name given up front is only a seed you can change (though it lets a known name
fail fast if it is already taken). It is a warm, one-question-at-a-time interview, not a
form.

**Guided or quick.** Creating a workflow well is the part that pays off — a well-shaped
one makes every future run smoother — so at the start you choose the depth: **guided**
adds a facilitative consultant (a parking lot for tangents, a diverge→converge rhythm,
process-leveling on "is this a step or its own workflow?", and proposing the stages you
left out), keeping a `draft.md` and `parking-lot.md` on disk so a long session survives
compaction — richer, and a bit costlier. **quick** is the lean interview. An interactive
run asks (Enter takes guided); `--guided` / `--quick` answer up front, and a
non-interactive run defaults to quick. The steps below are the quick core; guided layers
on top of them. It:

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
4. **Names it and writes `workflow.md`** into a private draft folder
   (`~/.gmlw/drafts/`), then proposes the workflow's name and marks it finished. gmlw
   deploys the finished draft into `~/.gmlw/workflows/<name>/` (an atomic move) and tells
   you how to run it. A half-authored workflow never appears in `workflow list` or `run`;
   if the name is taken, the draft is kept and you are pointed at `gmlw workflow edit`.

You can pass `--client X` to author under a specific client. See [CLI.md](CLI.md) for
the full command surface.

**If authoring is interrupted** (a crash, Ctrl+C, a closed laptop) before it reaches a
finished marker, the draft is not lost — it stays in `~/.gmlw/drafts/`:

    gmlw workflow drafts            # list what's unfinished
    gmlw workflow resume            # reopen the most recent one
    gmlw workflow resume <name>     # reopen a specific one

A resumed `new` still proposes its name and deploys at convergence exactly as an
uninterrupted run would; a resumed `edit` reopens on the same client and authoring
depth the original session used.

## File layout

A workflow lives under `~/.gmlw/workflows/<name>/`:

    ~/.gmlw/workflows/
      _common/              # shared base — never runnable
      create-workflow/      # the meta-workflow — never runnable
      <name>/
        workflow.md         # required: the ordered steps
        scripts/            # optional: scripted mechanical steps

Only `workflow.md` is required. The hidden `_common/` and `create-workflow/` folders
are packaged with the wrapper and are **never** listed as runnable workflows by
`gmlw workflow list`.

## Compilation order

At launch the workflow is compiled into a **single blob** and injected into the child
client. For claude that is a native `--append-system-prompt-file`; other clients
receive it via a context-file or initial instruction (see [CLIENTS.md](CLIENTS.md)).

The stages are assembled in this **fixed order**:

    session snapshot  →  profile/*  →  role rules  →  environment rules  →  _common/base.md  →  workflow steps

- session snapshot — the active environment, role, persona and job, as a small JSON
  block, so the client can answer "which role am I in?" by reading a field.
- `_common/base.md` — the shared "how to behave" base (orient first, one step at a
  time, work in the user's language, offer to capture rules).
- `profile/me/` — your `me/` context; place-specific context comes from the active
  `environments/<env>/`.
- role rules — `~/.gmlw/profile/roles/<role>/rules/*`.
- environment rules — `~/.gmlw/environments/<env>/rules/*`. These come *last* of the two
  because they outrank the role's on conflict.
- workflow steps — this workflow's `workflow.md`.

There are **no workflow-scoped rules**. If a workflow behaves wrongly, fix the workflow so
it is right the next time it runs; rules describe the user, not a procedure.

Each stage passes through the interceptor chain on its way in (see
[CONFIGURATION.md](CONFIGURATION.md) for interceptors and the per-mode context
matrix that decides which sources are activated and compressed).

**Rule cleaning** happens on every rule, always, and is lossless: the YAML
frontmatter and the `Origin`/`Notes` sections are stripped before the model sees the
rule, and any rule the user has switched off with `status: draft` is skipped entirely.

## Rules

See [CONCEPTS.md § Rules](CONCEPTS.md#rules) for the full mechanism (the environment
vs role axis, `status: draft`, `Precedence`, always-on capture). The one thing specific
to workflows: there is **no per-workflow rule tier**. A workflow that behaves wrongly
is fixed in the workflow's own `workflow.md`, not patched by a rule beside it — rules
describe the user, not a procedure.

A rule file's shape, for reference:

    ---
    name: <slug>
    status: active
    ---
    # <slug>

    **Rule:** <what to do, or never do>
    **When:** <the situation that should trigger it>
    **Signals:** <how to recognise you are in that situation>
    **Strength:** hard   (always applies) — or soft (a strong preference)
    **Origin:** <the moment it was demanded — stripped before the model>

## Scripts

When a step is mechanical, the authoring flow offers to turn it into a script under
`scripts/<name>` (python or shell). The workflow's instruction for that step then
becomes "run `scripts/<name>`" — the wrapper runs the script instead of having the
model re-reason a deterministic task every run. Keep judgment steps as prose for the
model; script only what genuinely simplifies.

## Sharing a workflow

A workflow travels: `export` packs it into an archive, `import` installs one back —
to another machine, or to someone else.

    gmlw workflow export <name>              # -> ~/.gmlw/exports/<name>...
    gmlw workflow import <archive>            # install it
    gmlw workflow import <archive> --replace  # displace an existing one of the same name

Without `--replace`, a name clash prompts interactively (keeping a backup of what it
replaces); off a TTY the import is refused rather than silently overwriting.

Both are also in `gmlw tui` under Workflow → Export / Import, and both stay in the menu:
Export packs the file and says where it went with the list still in front of you, and
Import installs, asks about a name clash on the spot, and leaves the new workflow
immediately runnable from Workflow → Run.

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

See also: [CONCEPTS.md](CONCEPTS.md) · [USER_GUIDE.md](USER_GUIDE.md) · [CLI.md](CLI.md) ·
[CONFIGURATION.md](CONFIGURATION.md) · [CLIENTS.md](CLIENTS.md) ·
[DESIGN.md](DESIGN.md) · [../ROADMAP.md](../ROADMAP.md) ·
[../SECURITY.md](../SECURITY.md)
