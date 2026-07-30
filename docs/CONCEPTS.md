# Concepts

The mental model behind `gmlw`, in one place. Read this once, before the task-oriented
[User guide](USER_GUIDE.md) or the reference docs — the pieces here (job, workflow,
the four context axes, rules, why clients differ) recur across every other doc, and
this is where each is explained in full rather than re-derived.

## The job model

A **job** is the one concept everything hangs off — the piece of work you're tagging
(a ticket, a refactor, an investigation) and the primary key of the whole ledger. A
**session** is one launch of a client against a job; a client's own resumable
conversation lives inside it. A **turn** is one metered request/response round within
a session.

```
job  ──►  sessions  ──►  turns ──► tokens + cost
                    └───► context.md (what it launched with)
                    └───► transcript (opt-in: in / out / usage per call)
```

A **workflow** is optional and orthogonal to this: it's a compiled operating context
you author once and launch a job with, so you don't re-explain standing instructions
every session. `gmlw start <job>` with no workflow is already the whole wrapper —
metered, recorded, status-lined. See [WORKFLOWS.md](WORKFLOWS.md) for authoring one.

`run <workflow>` vs `start <job> -w <workflow>` is the other axis worth naming: `start`
enters a job you return to; `run` launches a *recurring procedure* whose job is named
after the workflow itself (`gmlw help start-vs-run` from the CLI covers the same
ground).

<div align="center">
<img src="images/gmlw-help.gif" alt="gmlw help — the built-in concept explainer" width="760">
</div>

## The four context axes

Beyond metering, `gmlw` composes a portable operating context for the client from four
independent axes:

- **Me** — who you are, invariant across every launch (`profile/me/`, including the
  `learned` notebook your tools mirror into — negatives ["what to avoid"] are
  first-class).
- **Role** — the functional hat you're wearing (engineer, QA, reviewer). A *lens* over
  `me`, not a copy — it scopes role-specific rules and learnings
  (`profile/roles/<role>/`), chosen at `gmlw init` and changeable with
  `gmlw config set profile.default_role <role>`.
- **Environment** — where the work happens (a company, a personal project, open
  source). Place-specific context and constraints (`environments/<env>/`), also
  chosen at `init` and changeable via `config set profile.default_environment`.
- **Persona** — the companion's own manner, not yours. A selectable tone with a free
  local greeting at launch (`gmlw persona list`); off and invisible until set.

Which sources are active (and optionally compressed) per launch mode is controlled by
the `[startup.<mode>]` matrix — see [CONFIGURATION.md](CONFIGURATION.md).

## Rules

A **rule** is a reusable reflex you've demanded — a standard held on every future run,
not a one-off decision about a single task. Because a rule is a projection of *you*, it
lives on exactly one of the two axes above that describe you, never globally and never
per-workflow:

| Axis | Folder | What belongs there |
| --- | --- | --- |
| Environment | `~/.gmlw/environments/<env>/rules/` | Constraints of the place — how docs are written here, how a service is built, the house lint config. Not your taste; it stops applying elsewhere. |
| Role | `~/.gmlw/profile/roles/<role>/rules/` | Your own preferences about the craft — design patterns, how you approach code. They travel with you. |

At the moment a rule is born, exactly one environment and one role are active, so the
choice is always between two concrete folders. When the two conflict, the
**environment wins** — a constraint is not overridden by a preference. Within one
axis, an explicit `Precedence: <n>` decides (higher wins).

A rule is **active from the moment it is recorded** — you demanded it, so it applies
immediately. Setting `status: draft` is your own off-switch, for retiring a rule later
without deleting it; a draft is injected into no session. There is deliberately **no
global rule tier and no per-workflow rule tier**: a workflow that behaves wrongly is
fixed in the workflow itself, not patched by a rule beside it.

Rule capture is **always-on**, in any session — not only inside a workflow. When
you're dissatisfied with something and want it to never recur, the client offers to
record the rule for you: proposing an axis (and letting you redirect it), reading your
existing rules first so it updates or supersedes a match instead of stacking a
near-duplicate, and — when the rule is mechanically enforceable — offering to realise
it as a small script or check rather than a standing reminder.

Browse what you have with `gmlw tui` → **Rules**, or edit the files directly:

```
$EDITOR ~/.gmlw/profile/roles/engineer/rules/no-force-push.rule.md
```

The rule format itself (`Rule` / `When` / `Signals` / `Strength` / `Origin`, optional
`Precedence`) lives as a plain template at `~/.gmlw/templates/rule.template.md` — yours
to reshape.

## Why client capabilities differ

`gmlw` drives four clients (`claude`, `cursor`, `codex`, `vibe`) behind one surface,
but what it can meter, resume, or render a status line for depends on what each
underlying tool actually exposes — not on any wrapper limitation:

- **Metering** needs the client's requests to travel over an API the wrapper can sit
  in front of as a local relay. Claude, codex, and vibe all do; Cursor's usage does
  not travel over an interceptable API at all, so it is never metered by the
  open-source wrapper — not a bug, a hard ceiling of what's observable.
- **Resume** needs a stable session id the wrapper can either hand the client at
  launch or bind once minted. Claude and cursor accept a session id up front. Codex
  mints its own and announces it on the wire, so the wrapper binds it off the first
  metered turn — meaning a codex session with zero completed turns has no id yet and
  isn't resumable. Vibe exposes no stable id at all, so every vibe run is a fresh
  session.
- **Status line** needs a surface in the client to render into. Claude and Cursor both
  expose one; codex and vibe don't, so their numbers are read after the fact with
  `gmlw export <job>` instead of live.

The concrete matrix (and per-client setup) lives in [CLIENTS.md](CLIENTS.md); the
architecture behind the relay and the per-client caller seam is in
[DESIGN.md](DESIGN.md).

## See also

- [../README.md](../README.md) — what `gmlw` is and why.
- [USER_GUIDE.md](USER_GUIDE.md) — task-oriented recipes built on these concepts.
- [WORKFLOWS.md](WORKFLOWS.md) — authoring a workflow, file layout, scripts.
- [CLIENTS.md](CLIENTS.md) — the concrete per-client capability matrix.
- [CONFIGURATION.md](CONFIGURATION.md) — every `config.toml` key, including
  `[startup.<mode>]`.
- [CLI.md](CLI.md) — every command, including `gmlw help <topic>`.
