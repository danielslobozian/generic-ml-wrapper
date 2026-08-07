# User guide

Task-oriented recipes for the `gmlw` CLI. Each section is a concrete job with the exact
command to run. For the mental model behind these (job/session/workflow, the four
context sources, rules) see [CONCEPTS.md](CONCEPTS.md); for the full flag reference see
[CLI.md](CLI.md), for every config key see [CONFIGURATION.md](CONFIGURATION.md), and
for per-client behaviour see [CLIENTS.md](CLIENTS.md).

## 1. Track one ticket across multiple sessions

Pick a stable job id (your ticket number works well) and pass it to `start` every time you sit
back down. Each launch appends a new session to the same job, so cost and activity accumulate
under one name. List them oldest-first with `sessions`.

```
gmlw start PROJ-482
gmlw start PROJ-482          # later — a second session on the same job
gmlw sessions PROJ-482
```

Job ids are validated (`[A-Za-z0-9][A-Za-z0-9_-]{0,63}`, no path separators). A bare
`gmlw PROJ-482` is rewritten to `gmlw start PROJ-482`.

## 2. Resume the latest session

Add `--resume-latest` to continue where the previous session left off instead of starting fresh.
**claude** and **cursor** resume any session; **codex** resumes one that has taken at least one
turn (that is when the wrapper learns the id codex minted); **vibe** always begins a new session
(see the resume column in [CLIENTS.md](CLIENTS.md)).

```
gmlw start PROJ-482 --resume-latest
```

## 3. Compare cost by model

`export` breaks a job down into per-turn tokens and cost, per-session cost, and **per-model
totals** — the last is what you want when comparing how much each model cost you on the ticket.

```
gmlw export PROJ-482
```

Cursor sessions are not metered by the wrapper (its usage isn't on an interceptable API), so they
carry no cost figures.

## 4. Create and run a workflow

`workflow new` runs the shipped `create-workflow` meta-workflow: it interviews you, drafts ordered
steps, marks which are scriptable, and writes `~/.gmlw/workflows/<name>/workflow.md`. Then launch
any job with that workflow injected using `-w`.

```
gmlw workflow new triage
gmlw workflow list
gmlw start PROJ-482 -w triage
```

The authoring session is hidden from `gmlw jobs`. See [WORKFLOWS.md](WORKFLOWS.md) for the compile
order and the `scripts/` folder.

## 5. Add profile and environment context

Drop markdown files under `~/.gmlw/profile/me/` (about you — spans every session) and
`~/.gmlw/environments/<env>/` (about where the work happens: your organisation, a personal
project). `<env>` is your active `[profile] default_environment` (`work` by default), chosen at
`gmlw init`. They are compiled into the launch context so every session knows who you are.

```
$EDITOR ~/.gmlw/profile/me/about.md
$EDITOR ~/.gmlw/environments/work/overview.md
```

Learnings can also be **role-scoped**: drop them under
`~/.gmlw/profile/roles/<role>/learned.md`, and they compose only when `<role>` is your active
`[profile] default_role` (the functional hat you picked at `gmlw init` — a lens over `me`, not a
separate you). `profile/me/learned.md` always applies; the role's adds on top.

Rules are *always* scoped — see section 7.

```
$EDITOR ~/.gmlw/profile/roles/engineer/learned.md
```

Which sources are activated (and compressed) per mode is controlled by the `[startup.<mode>]`
matrix in [CONFIGURATION.md](CONFIGURATION.md); `me.user` and `company` (the environment source)
are active by default. If you upgraded from an older layout, `gmlw` migrates your old
`profile/company/` into `environments/work/` automatically on first run.

## 6. Choose a persona

A persona voices a short local host greeting at launch and can inject a persona context source.
List the built-ins, then set one in `config.toml`.

```
gmlw persona list
```

```toml
# ~/.gmlw/config.toml
[companion]
persona = "mentor"     # plain | companion | mentor | butler | terse, or a file in ~/.gmlw/personas/
```

Personas are off and invisible until you set this key.

## 7. Record a rule

A rule is filed on the environment or the role, not globally or per-workflow — see
[CONCEPTS.md § Rules](CONCEPTS.md#rules) for the full mechanism (which of the two wins on
conflict, `status: draft`, `Precedence`). In practice, either edit the file directly or
let the client capture it the moment you correct it:

```
$EDITOR ~/.gmlw/profile/roles/engineer/rules/no-force-push.rule.md
# to retire it later, edit the front matter: status: active  ->  status: draft
```

Browse what you have with `gmlw tui` → **Rules**, which lists only the environments and
roles that actually hold rules and marks the ones you have switched off.

## 8. Enable transcripts safely

Transcripts are **off by default**. Turning them on writes full prompts and responses to disk.

```toml
# ~/.gmlw/config.toml
[transcript]
enabled = true
# root = "/some/dir"   # default ~/.gmlw/transcripts
```

Caveat: stored transcripts contain your full prompts and model responses at rest (owner-only
permissions, not encrypted). Read the data-at-rest guidance in [../SECURITY.md](../SECURITY.md)
before enabling.

## 9. Add a plugin or caller override

List installed plugins, then point a client at a custom caller in `[callers]`. A caller spec can be
a `module:Class`, a `/path/to/file.py:Class`, or a `<plugin-id>`.

```
gmlw plugins list
```

```toml
# ~/.gmlw/config.toml
[callers]
claude = "my_pkg.callers:MyClaudeCaller"
```

Warning: `[callers]` and `[[interceptors]]` specs are **loaded and run as you** — this is trusted
code, no sandbox. A configured-but-unloadable spec fails loudly. Details in
[../SECURITY.md](../SECURITY.md) and [CONFIGURATION.md](CONFIGURATION.md).

## 10. Clear out jobs and sessions you are done with

Jobs and sessions are kept until you say otherwise, and a session is recorded *before* its
client starts — so one you opened, remembered something, and quit out of is on the list like
any other. `sessions` marks those: a session that never took a turn reads as **empty**.

```
gmlw sessions PROJ-482
gmlw sessions PROJ-482 delete PROJ-482_002        # one session, and its data
gmlw jobs delete spike-1 throwaway --yes          # whole jobs, several at a time
```

Deleting removes the ledger rows *and* the files: the compiled context under
`~/.gmlw/contexts/`, and the transcript folder under your transcript root when transcripts
were on. Both commands print what will go before asking, and `--yes` answers in advance —
off a terminal, without `--yes`, the delete is refused rather than assumed.

Deleting a session in the middle of a job is safe. The next id is minted one past the highest
that exists, so a gap is never filled and no session id is ever reused.

In the menu the same two grains live under **Job > Delete**: `space` ticks rows, `⏎` asks. The
question opens on **No** and shows the same footprint the CLI prints, so `⏎` again is always the
safe answer; Esc is a no as well. Answer either way and you stay exactly where you were, on the
list you were clearing, with what you removed already gone from it.

## 11. Export JSON for automation

Add `--json` to emit machine-readable output instead of the rendered tables. It's supported on
`jobs`, `sessions`, `export`, `clients`, `workflow list`, `workflow drafts`, `persona list`,
`plugins list`, `config list`, and `config get`.

```
gmlw jobs --json
gmlw sessions PROJ-482 --json
gmlw export PROJ-482 --json
gmlw clients --json
gmlw workflow list --json
gmlw persona list --json
gmlw plugins list --json
gmlw config list --json
```

For the complete command surface, see [CLI.md](CLI.md) and the project [../README.md](../README.md).
For the mental model behind these recipes, see [CONCEPTS.md](CONCEPTS.md).
