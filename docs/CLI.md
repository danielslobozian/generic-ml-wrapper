# CLI reference

Complete command reference for the `gmlw` console script. This page documents exactly
what `build_parser()` exposes — every command, positional, and flag. For the concepts
behind these commands see [CONCEPTS.md](CONCEPTS.md); for deeper behaviour, follow the
cross-links to [CONFIGURATION.md](CONFIGURATION.md), [WORKFLOWS.md](WORKFLOWS.md), and
[CLIENTS.md](CLIENTS.md).

## Synopsis

```
gmlw init                                # forced first-run setup (auto-runs when needed)
gmlw <job>                              # shorthand for: gmlw start <job>
gmlw start [job] [--client X] [--client-args ARGS] [--resume-latest] [--workflow|-w NAME]
gmlw run [workflow] [--client X] [--client-args ARGS]   # run a workflow directly (job named after it)
gmlw jobs [--json]
gmlw jobs delete <job> [<job>...] [--yes]      # removes the job and everything under it
gmlw sessions <job> [--json]
gmlw sessions <job> delete <session> [...] [--yes]
gmlw export <job> [--json]
gmlw clients [--json]                    # supported clients + installed versions
gmlw statusline                          # called by the client, not by hand
gmlw workflow new [name] [--client X] [--guided|--quick]   # name optional; asks depth if unset
gmlw workflow edit <name> [--client X] [--guided|--quick] [--resume-latest]
gmlw workflow list [--json]
gmlw workflow drafts [--json]
gmlw workflow resume [draft]
gmlw workflow export <name>
gmlw workflow import <archive> [--replace]
gmlw persona list [--json]
gmlw plugins list [--json]
gmlw creds set <workflow> <ENV_VAR_NAME>
gmlw config list [--json]
gmlw config get <key> [--json]
gmlw config set <key> <value>
gmlw environment new <label> [--description D] [--default]
gmlw role new <label> [--description D] [--default]
```

`--json` is accepted by the read commands only: `jobs`, `sessions`, `export`,
`clients`, `workflow list`, `workflow drafts`, `persona list`, `plugins list`,
`config list`, and `config get`. It prints pretty-printed JSON instead of the
human-readable text.

`--yes` is accepted by the delete commands only — `jobs delete` and `sessions delete` —
and skips their confirmation prompt.

### Implicit `start`

A first argument that is not a known command and does not begin with `-` is treated
as a job name: `gmlw myjob` is rewritten to `gmlw start myjob` (git-style). A recognized
subcommand or a leading flag is left untouched.

### Incomplete sub-commands

`workflow`, `persona`, `plugins`, `creds`, `environment`, and `role` do their real work in a sub-action.
Invoked without one (e.g. `gmlw workflow`), the command re-parses itself as `-h` and
prints its own help, then exits 0.

### Environment variables

- `GMLW_LOG_LEVEL` — overrides the configured `[logging] level` for the run
  (`debug|info|warning|error`; default `warning`). See [CONFIGURATION.md](CONFIGURATION.md).
- `GMLW_CLIENT`, `GMLW_JOB`, `GMLW_SESSION` — exported by the launching caller and read
  by `statusline`; you do not set these yourself.

---

## init

Run the forced first-run setup that shapes every session. `init` is both a command and
a **gate**: the first time you run *any* command on a new or pre-0.4.0 install, gmlw
funnels you through it before that command runs. Once it has run, a marker
(`[init] version` in `~/.gmlw/config.toml`) records it, and the gate stays out of the way.

```
gmlw init
```

The interview captures, in order — each with a sensible default, so a non-interactive
run completes without blocking:

1. **language** — which language gmlw speaks *to you* (`en` | `fr`); it does not force the
   companion's language. Seeded from `$LANG`.
2. **name** — what the companion calls you (defaults to your OS user).
3. **role** — the functional hat you wear (a lens over *you*), e.g. `engineer`, `qa`.
4. **environment** — where the work happens, e.g. `work`, a personal project.
5. **persona** — the companion's voice (skippable; leaves the companion off).
6. **client** — the client to wrap by default; a lone installed one is taken silently,
   several prompt a choice, none leaves it unset.

On a **fresh** install a full `config.toml` is seeded with your choices. On a **legacy**
install (a pre-0.4.0 config already exists) only the `[init]` marker is appended — your
existing file is left untouched; migrating the older layout comes in a later release.

## start

Start or resume a session on a job.

```
gmlw start [job] [--client CLIENT] [--client-args ARGS] [--resume-latest] [--workflow|-w NAME]
```

- `job` (optional positional) — the job identifier. A job groups related sessions.
  With no job, `start` prints a friendly guide (not an argparse error) and exits 2:

  ```
  gmlw: start needs a job to work on.
    gmlw <job>          start (or resume) a session on <job>
    gmlw start <job>    the same, spelled out
  A job groups related sessions; list yours with:  gmlw jobs
  ```

- `--client CLIENT` — which client to wrap (`claude`, `cursor`, `codex`, `vibe`).
  Defaults to the configured default client, or `claude`. See [CLIENTS.md](CLIENTS.md).
- `--client-args ARGS` — extra arguments passed straight to the client for this one
  launch, overriding the configured `[client.args]` for this run only. See
  [CONFIGURATION.md](CONFIGURATION.md).
- `--resume-latest` — resume the job's most recent session instead of starting a new one.
  Not every client supports resume; unsupported clients report an error.
- `--workflow NAME`, `-w NAME` — run a workflow on the job (list them with
  `gmlw workflow list`). See [WORKFLOWS.md](WORKFLOWS.md).

Before launching, `start` preflights the working directory and the client: a deleted
cwd or an uninstalled/unsupported client prints guidance and exits 2 rather than
crashing the child. If a companion persona is set, its host greeting is printed to
stderr just before the client takes over.

Example:

```
gmlw start billing-api --client claude -w tidy-review --resume-latest
```

## run

Run a workflow directly. The job is named after the workflow and its sessions accumulate
there, so `run` is the counterpart to `start` for a *recurring procedure* — where `start`
enters a job you return to, `run` launches a repeatable workflow. It is equivalent to
`gmlw start <workflow> -w <workflow>`.

```
gmlw run [workflow] [--client CLIENT] [--client-args ARGS]
```

- `workflow` (optional positional) — the workflow to run. With no workflow given, `run`
  offers a chooser at an interactive terminal and, once you pick, echoes the equivalent
  one-liner (`gmlw run <workflow>`) so the interactive path teaches the fast one. Off a
  terminal (piped/scripted), or when you decline, it prints a guide and exits 2 rather
  than blocking. Full argv (`gmlw run <workflow>`) never prompts. With no workflows
  authored yet, it points you at `gmlw workflow new <name>`.
- `--client CLIENT` — which client to wrap (`claude`, `cursor`, `codex`, `vibe`).
  Defaults to the configured default client, or `claude`. See [CLIENTS.md](CLIENTS.md).
- `--client-args ARGS` — extra arguments passed straight to the client for this one
  launch, overriding the configured `[client.args]` for this run only.

Like `start`, `run` preflights the working directory and the client before launching, and
reports an unknown workflow cleanly. See [WORKFLOWS.md](WORKFLOWS.md).

Example:

```
gmlw run nightly-etl
```

## jobs

List the jobs with recorded activity. Authoring sessions (`workflow new`) are hidden.

```
gmlw jobs [--json]
```

- `--json` — output as JSON instead of text.

Example:

```
gmlw jobs
```

### jobs delete

Remove whole jobs and everything recorded under them: every session, its per-turn usage
and cost, its compiled contexts under `~/.gmlw/contexts/<job>/`, and its transcripts
under the configured transcript root. The job's folders go whole, so nothing is left
behind that no session still claims.

```
gmlw jobs delete <job> [<job>...] [--yes]
```

- `job` (positional, one or more) — the jobs to delete.
- `--yes` — delete without asking for confirmation.

What will be removed is printed first and the deletion is then confirmed. **This cannot
be undone.** Without `--yes` and with nothing to answer the prompt (a pipe, a script, CI),
the delete is refused rather than assumed — pass `--yes` when you mean it.

One unknown job aborts the whole request: nothing is removed and the exit code is `2`.
Authoring jobs are not reachable here, for the same reason they are absent from
`gmlw jobs`.

Example:

```
gmlw jobs delete spike-1 throwaway
```

```
This will permanently remove 2 job(s):

  spike-1    3 session(s) · 41 turn(s) · $1.25 · 3 context file(s) · 6 transcript file(s)
  throwaway  1 session(s) · 0 turn(s) · $0.00 · 1 context file(s) · 0 transcript file(s)

  Delete? This cannot be undone. [y/N]:
```

## sessions

List a job's sessions, oldest first, with what each one actually used. A session is
recorded before its client starts, so one you opened and left straight away is listed
like any other — it shows as `empty`, which is how you find it.

```
gmlw sessions <job> [--json]
```

- `job` (positional, required) — the job identifier.
- `--json` — output as JSON instead of text.

Example:

```
gmlw sessions billing-api
```

### sessions delete

Remove single sessions from a job: the session row, its turns, its cost, its compiled
context, and its transcript folder. The job itself stays, along with its other sessions.

```
gmlw sessions <job> delete <session> [<session>...] [--yes]
```

- `job` (positional, required) — the job the sessions belong to.
- `session` (positional, one or more) — the `<job>_NNN` session ids to delete.
- `--yes` — delete without asking for confirmation.

Same preview, same confirmation, same refusal off a terminal as `jobs delete`. One
unknown session id aborts the whole request.

Deleting a session in the middle of a job is safe: the next session id is minted one past
the highest that exists, so the gap is never reused and no id is ever recycled.

Example:

```
gmlw sessions billing-api delete billing-api_002
```

## export

Report a job's recorded usage: per-turn tokens and timing, totals by model, cost by
session, and grand totals.

```
gmlw export <job> [--json]
```

- `job` (positional, required) — the job identifier.
- `--json` — output as JSON instead of text.

Example:

```
gmlw export billing-api --json
```

## clients

List the supported clients (Claude Code, Cursor CLI, OpenAI Codex CLI, Mistral Vibe),
each with its installed on-disk version, whether it can resume a session, and which is
the configured default. Uninstalled clients are shown as such. Also available in the
interactive menu under `gmlw tui` → Config → Clients, where selecting a row also makes
that client the default (the same write as `gmlw config set client.default <name>`).

```
gmlw clients [--json]
```

- `--json` — output as JSON instead of text.

Example:

```
gmlw clients
```

## statusline

Render the status line. This command is invoked by the client's status-line hook, not
by hand — it reads the client's status payload from stdin and uses `GMLW_CLIENT`,
`GMLW_JOB`, and `GMLW_SESSION` from the environment to pick the right parser.

```
gmlw statusline
```

Takes no positionals or flags. See [CLIENTS.md](CLIENTS.md) for how each client's
status line is installed and parsed.

## tui

Open the interactive, full-screen menu — an alternative to the flag CLI. It is
object-first (**Job · Workflow · Config · Rules**), you navigate with the arrow keys, and
each row shows the equivalent command. On a terminal, **bare `gmlw` opens this menu too**
(once initialised) — `gmlw tui` is the explicit alias; off a terminal, both fall back to the
capability index.

```
gmlw tui
```

<div align="center">
<img src="images/gmlw-tui.gif" alt="gmlw tui — the object-first Job / Workflow / Config / Rules menu" width="760">
</div>

Every top-level verb is wired, not a placeholder: **Job** covers New, Resume (a specific
job's latest session), List, and Export; **Workflow** covers Run, Edit, Create, List,
Export, and Import; **Config** covers listing/getting/setting a value, the **Clients**
switcher (selecting a row also sets it as the default — the `gmlw config set client.default`
path), and re-running **Setup**; **Rules** browses the environment and role rule axes.

Off a TTY (piped/redirected) it never blocks: it falls back to the capability index,
exactly as bare `gmlw` does. Every action has a direct-command equivalent, so the flag CLI
remains the scripting path.

## workflow

Author and list workflows. Invoked with no action, prints its own help.

```
gmlw workflow new [name] [--client CLIENT] [--guided | --quick]
gmlw workflow edit <name> [--client CLIENT] [--guided | --quick] [--resume-latest]
gmlw workflow list [--json]
gmlw workflow drafts [--json]
gmlw workflow resume [draft]
gmlw workflow export <name>
gmlw workflow import <archive> [--replace]
```

### workflow new

Author a new workflow by running the shipped `create-workflow` meta-workflow as a
metered authoring session (no job — it is hidden from `gmlw jobs`; sessions accumulate
under `create-workflow`).

The workflow's name is decided at the **end** of the interview, not the start — forcing a
name up front presumes you already know the shape. So authoring happens in a private draft
folder under `~/.gmlw/drafts/`, and when the session marks the workflow finished, gmlw
deploys the draft into `~/.gmlw/workflows/<name>/` (an atomic move). A half-authored
workflow never appears in `workflow list` or `run`.

- `name` (positional, **optional**) — a suggested name. Omit it and the authoring session
  proposes one at convergence. When given, it is only a seed (the session may rename it),
  but it lets a known name **fail fast** on a collision before any work is done.
- `--description` — a one-line description of what the workflow does, carried into it.
- `--client CLIENT` — which client to wrap; defaults to the configured default, or
  `claude`.
- `--guided` / `--quick` — the authoring depth. **Guided** adds a facilitative
  consultant layer (a parking lot for tangents, diverge→converge, process-leveling,
  proposing the stages you left out) and keeps distilled state on disk so a long session
  survives compaction — richer, and it costs a bit more. **Quick** is the lean interview.
  With neither flag, an interactive run **asks** (Enter takes guided); a non-interactive
  run defaults to quick. Passing a flag skips the prompt.

On the return, gmlw reports how the draft resolved:

- **deployed** — the workflow was named, finished, and moved into place; run it with
  `gmlw run <name>`.
- **name already taken** — the draft is kept under `~/.gmlw/drafts/`; change the existing
  workflow with `gmlw workflow edit <name>` instead.
- **not finished** — the session left no finished marker; the draft is kept so nothing is
  lost.

Example:

```
gmlw workflow new              # interview, name it at the end, gmlw deploys it
gmlw workflow new tidy-review  # same, but seed the name (fails fast if it exists)
```

### workflow edit

Open an existing workflow for changes in a metered authoring session (no job). Unlike
`new`, it never creates or overwrites — it opens the workflow's existing folder and amends
its `workflow.md`. An unknown workflow exits non-zero with guidance.

- `name` (positional, required) — the workflow to edit.
- `--client CLIENT` — which client to wrap; defaults to the configured default, or
  `claude`.
- `--guided` / `--quick` — the authoring depth, exactly as for `workflow new` (an
  interactive run asks when neither is given).
- `--resume-latest` — reopen this workflow's most recent editing session instead of
  starting a new one, on the client and authoring depth that session already carries
  (the depth prompt is skipped).

Example:

```
gmlw workflow edit tidy-review
```

### workflow list

List the runnable workflows. The hidden `_common` and `create-workflow` folders are
never listed.

- `--json` — output as JSON instead of text.

Example:

```
gmlw workflow list
```

### workflow drafts

List unfinished authoring drafts — a `workflow new`/`workflow edit` session that was
interrupted (crash, Ctrl+C, a closed laptop) before it reached a finished marker.

- `--json` — output as JSON instead of text.

Example:

```
gmlw workflow drafts
```

### workflow resume

Reopen an unfinished authoring draft on the client and authoring depth its own session
carries. The name is only ever proposed at the end, so a resumed `new` still names and
deploys itself at convergence exactly as an uninterrupted run would.

- `draft` (positional, optional) — the draft to reopen. Omit it to reopen the most
  recently unfinished one. An unknown draft exits non-zero with guidance.

Example:

```
gmlw workflow resume              # reopen the most recent unfinished draft
gmlw workflow resume tidy-review  # reopen a specific one
```

### workflow export

Pack a workflow into a shareable archive under `~/.gmlw/exports/`, so it can travel to
another machine or another person.

- `name` (positional, required) — the workflow's slug to export.

Example:

```
gmlw workflow export tidy-review
```

### workflow import

Install a workflow from an archive produced by `workflow export`.

- `archive` (positional, required) — the archive to import.
- `--replace` — displace an existing workflow of the same name without asking. Without
  it, a name clash prompts interactively (a backup of the replaced workflow is kept); off
  a TTY the import is refused rather than silently overwriting.

Example:

```
gmlw workflow import ~/Downloads/tidy-review.zip
gmlw workflow import ~/Downloads/tidy-review.zip --replace
```

See [WORKFLOWS.md](WORKFLOWS.md) for the authoring flow and workflow layout.

## persona

List the selectable personas. Invoked with no action, prints its own help.

```
gmlw persona list [--json]
```

- `--json` — output as JSON instead of text.

Personas are selected in config, not on the command line
(`[companion] persona = "<name>"`); see [CONFIGURATION.md](CONFIGURATION.md).

Example:

```
gmlw persona list
```

## plugins

List the installed plugins. Invoked with no action, prints its own help.

```
gmlw plugins list [--json]
```

- `--json` — output as JSON instead of text.

Plugins live at `~/.gmlw/plugins/<id>/` (each with a `plugin.toml`) and are wired in via
`[callers] <client> = "<id>"`. See [CONFIGURATION.md](CONFIGURATION.md).

Example:

```
gmlw plugins list
```

## creds

Manage per-workflow credentials. Invoked with no action, prints its own help.

```
gmlw creds set <workflow> <ENV_VAR_NAME>
```

### creds set

Store a credential for a workflow. The value is read securely: a hidden prompt at a TTY,
otherwise one line from stdin. It is written `0600` into `~/.gmlw/credentials.toml` and
injected into the child process environment as `ENV_VAR_NAME` at launch.

- `workflow` (positional, required) — the workflow the credential belongs to.
- `name` (positional, required) — the environment-variable name to export at launch.

Example:

```
gmlw creds set deploy-bot DEPLOY_TOKEN
```

---

## config

View and change the settable `~/.gmlw/config.toml` settings. Every key is backed by a
typed registry (its type, default, allowed values, and description); `set` validates
against it and merges the change into your file, preserving comments and formatting.
Invoked with no action, prints its own help.

```
gmlw config list [--json]
gmlw config get <key> [--json]
gmlw config set <key> <value>
```

### config list

List every setting with its current value and description.

### config get

Show one setting — its value, description, default, and any allowed values.

- `key` (positional, required) — the dotted setting key (e.g. `profile.default_role`).

### config set

Change one setting. The value is validated against the registry (type and allowed
values) before anything is written; the change is echoed (old → new), never silent. Use
`none` to clear an optional key back to its default.

- `key` (positional, required) — the dotted setting key.
- `value` (positional, required) — the new value.

Example:

```
gmlw config set profile.default_role reviewer
gmlw config set logging.level debug
gmlw config get client.default
```

The home for changing `default_role` / `default_environment` after `init`.

## environment

Create and manage environments (the place work happens). Invoked with no action, prints
its own help.

```
gmlw environment new <label> [--description D] [--default]
```

- `new <label>` — create a new environment. `label` is the human name you type; a
  kebab-case `slug` is derived from it (`slugify`), and that slug is the folder name under
  `~/.gmlw/environments/<slug>/` and the value stored in `profile.default_environment`. The
  typed label and `--description` are saved to the folder's `.about.toml`.
- `--default` — also point `profile.default_environment` at the new slug.

An empty/unusable label, or a slug that already exists, prints an error and exits 2 (the
existing folder is never overwritten).

```
gmlw environment new "Client Project" --default
```

## role

Create and manage roles (the functional hat, a lens over *you*). Same shape as
`environment`; the folder lives under `~/.gmlw/profile/roles/<slug>/` (with an empty
`rules/` drop-zone) and the value is stored in `profile.default_role`.

```
gmlw role new <label> [--description D] [--default]
```

```
gmlw role new "Code Reviewer" --default
```

---

## help

Explain a core concept. `gmlw help` lists the topics; `gmlw help <topic>` prints one.

```
gmlw help
gmlw help <topic>
```

- `topic` (positional, optional) — one of `job-vs-workflow`, `start-vs-run`, `personas`,
  `cost`. Omit to list the topics. An unknown topic exits non-zero with guidance.

Bare `gmlw` (no arguments) is first-run-aware: on a fresh install it runs `init` (which,
at the end, tells you how to re-run setup from the menu). Once initialised, on a terminal
it opens the interactive menu (`gmlw tui`); off a terminal (piped/redirected) it prints a
grouped capability index (**launch / inspect / author**) with a next-action footer. The
flat argparse view is still available via `gmlw --help`.

---

## See also

- [CONCEPTS.md](CONCEPTS.md) — the mental model behind these commands.
- [USER_GUIDE.md](USER_GUIDE.md) — task-oriented walkthrough.
- [CONFIGURATION.md](CONFIGURATION.md) — `~/.gmlw/config.toml`, logging, personas, plugins.
- [WORKFLOWS.md](WORKFLOWS.md) — authoring and running workflows.
- [CLIENTS.md](CLIENTS.md) — supported clients and their capabilities.
- [../README.md](../README.md) · [../SECURITY.md](../SECURITY.md) · [../ROADMAP.md](../ROADMAP.md)
