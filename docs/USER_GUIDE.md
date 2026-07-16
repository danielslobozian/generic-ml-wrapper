# User guide

Task-oriented recipes for the `gmlw` CLI (generic-ml-wrapper v0.2.0). Each section is a
concrete job with the exact command to run. For the full flag reference see [CLI.md](CLI.md),
for every config key see [CONFIGURATION.md](CONFIGURATION.md), and for per-client behaviour see
[CLIENTS.md](CLIENTS.md).

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
Only the **claude** and **cursor** clients can resume; codex and vibe always begin a new session
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
order and the `rules/` and `scripts/` folders.

## 5. Add profile and company context

Drop markdown files under `~/.gmlw/profile/me/` (about you) and `~/.gmlw/profile/company/` (about
your organisation). They are compiled into the launch context so every session knows who you are.

```
$EDITOR ~/.gmlw/profile/me/about.md
$EDITOR ~/.gmlw/profile/company/overview.md
```

Which sources are activated (and compressed) per mode is controlled by the `[startup.<mode>]`
matrix in [CONFIGURATION.md](CONFIGURATION.md); `me.user` and `company` are active by default.

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

## 7. Record and activate a rule

Rules live in `~/.gmlw/rules/<slug>.rule.md`. A rule with `status: draft` is **not** injected;
promote it to `active` once you're happy with it. The `Origin` field is stripped before the model
sees the rule.

```
$EDITOR ~/.gmlw/rules/no-force-push.rule.md   # write Rule / When / Signals / Strength, status: draft
# edit the front matter: status: draft  ->  status: active
```

During a workflow, when you're dissatisfied and want something to never recur, the client offers
to record it as a draft rule for you. See [WORKFLOWS.md](WORKFLOWS.md).

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

## 10. Export JSON for automation

Add `--json` to emit machine-readable output instead of the rendered tables. It's supported on
`jobs`, `sessions`, `export`, `workflow list`, `persona list`, and `plugins list`.

```
gmlw jobs --json
gmlw sessions PROJ-482 --json
gmlw export PROJ-482 --json
gmlw workflow list --json
gmlw persona list --json
gmlw plugins list --json
```

For the complete command surface, see [CLI.md](CLI.md) and the project [../README.md](../README.md).
