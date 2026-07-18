# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Forced init + the gate.** A mandatory first-run setup, `gmlw init`, is now both a
  command and a first-class gate: `[init] version` in `config.toml` records that it ran,
  and any command on an un-initialised or pre-0.4.0 install is funnelled through init
  before it runs (`statusline` and bare `--help` are exempt). The interview captures, in
  order — each with a sensible default so a non-interactive run never blocks — **language
  → name → role → environment → persona → client**: language sets the voice the rest of
  the interview speaks (chosen language re-localises every later prompt), name is what the
  companion calls you, role and environment seed the movie-set axes (`[profile]
  default_role` / `default_environment`), persona and client reuse the existing choosers.
  A fresh install gets a full seeded `config.toml`; a legacy install has only the `[init]`
  marker appended, its existing file left verbatim (settings migration comes next). Retires
  the thinner 0.2.0 `FirstRunInit`.

## [0.3.0] - 2026-07-18

The lifecycle release — hooks that act at the seams around a run, and rule capture that
works everywhere.

### Added
- **Lifecycle action hooks.** gmlw already hooks *content* (the interceptor chain); it now
  hooks *actions* at two seams bracketing the client run. A `[[hooks]]` entry binds a
  `HookPort` spec (a `module:Class` / `/path.py:Class`, or a plugin id) to a `phase` —
  `pre-launch` (after the context is compiled and the caller resolved, before the client
  starts) or `post-session` (after the client exits, with its exit code) — with an optional
  `client` scope, under the same trusted-code boundary as `[[interceptors]]` and `[callers]`.
  Hooks are best-effort: a failing hook never breaks a launch or its teardown. Both launch
  paths (`start`, `workflow new`) route through one `run_with_hooks` sequence. Ships the
  built-in `SessionLogger` as a reference hook.
- **Always-on rule lifecycle.** Rule capture is no longer workflow-only: the `rules`
  context source (now active by default in a plain start, config-overridable) leads with
  a capture directive so a demanded correction becomes a draft rule in **any** session.
  The directive carries the full loop — offer to record a durable, reusable reflex;
  **dedup** against the existing rules and update/supersede a match instead of stacking a
  near-duplicate; and, when a rule is **mechanically enforceable**, offer to realise it as
  a script or check rather than a standing reminder.

### Fixed
- Docs: removed a stray tool artifact from `docs/CLIENTS.md`; corrected the workflow
  compression default in `docs/CONFIGURATION.md` (every source defaults to
  `compression = false`); documented `[companion] name`. Added a doc-consistency guard
  against leaked tool-artifact tags.

## [0.2.0] - 2026-07-16

The companion release — everything a session inherits, and the ergonomics around it.

### Added
- **Mode-aware context packaging.** A `[startup.<mode>]` matrix picks which sources
  compose (persona · profile · learned · company · rules · workflow base/steps) for
  each mode (default / workflow / authoring), with typed per-source compression
  (`[compress.prompts]`).
- **Personas.** Selectable tone with a universal floor (`gmlw persona list`), a free
  local host greeting at launch, and a first-run persona choice — configured under
  `[companion]`.
- **Learned notebook.** A portable, user-owned notebook (`profile/me/learned.md`) the
  client mirrors into, read into every client so what one learns they all inherit;
  negatives are first-class.
- **Rule format.** A domain-neutral `Rule / When / Signals / Strength / Origin`
  (+ optional `Precedence`), captured as a draft during a workflow.
- **Formal plugins folder.** Reference a caller by id (`~/.gmlw/plugins/<id>/` with a
  `plugin.toml`); `gmlw plugins list`.
- **Cursor allowance block.** The status line renders cursor's plan pools from an
  optional local cache when the client does not pipe them.
- **First-run init.** Detect installed clients and seed a filled config with a default.
- **JSON output** for the listing/reporting commands (`--json`).
- **Ergonomics.** Client and working-directory preflight, implicit `gmlw <job>`
  (shorthand for `start`), a friendly no-job message, and auto-help for an incomplete
  sub-command.

### Changed
- Documentation overhaul: task-oriented guides (`docs/USER_GUIDE.md`, `docs/CLI.md`,
  `docs/CONFIGURATION.md`, `docs/CLIENTS.md`, `docs/WORKFLOWS.md`,
  `docs/TROUBLESHOOTING.md`), a client capability matrix in the README, and `DESIGN.md`
  synchronised with the code; `GOVERNANCE.md` corrected. Supported Python stated as
  3.11–3.14 to match CI.

## [0.1.0] - 2026-07-14

First public release — a metering wrapper around ML coding CLIs.

### Added
- **Jobs & sessions.** Enter at a **job** you tag; the wrapper mints a named,
  resumable **session** on the client and persists it. `gmlw start`, `jobs`,
  `sessions`, `export`.
- **Four clients** driven the same way: **claude**, **cursor**, **codex**, **vibe**.
  Which one is config-driven (`[client]`) or `--client`.
- **Metering relay.** A local, capability-URL-authenticated relay records **per-turn
  tokens and cost** for the metered clients (claude/codex/vibe) into a SQLite ledger;
  `gmlw export` reports per-turn rows, per-model totals, and per-session cost.
- **Status line** for the clients that host one (claude, cursor): git · folder ·
  model · context% · a client-specific allowance block, plus a per-session and
  per-job usage footer.
- **Workflows.** Author a small operating context once (`gmlw workflow new`, a warm
  create-workflow interview) and launch a job with it; context is compiled from a
  shared base + your profile + rules + the workflow steps, through an interceptor
  chain (with opt-in context compression via `generic-ml-cache`).
- **Durable provenance.** The exact compiled context is written per session
  (`contexts/<job>/<session>.context.md`); an **opt-in transcript** keeps each metered
  call's request/response/usage.
- **Credentials.** Per-workflow secrets stored `0600` and injected into the client's
  environment at launch (`gmlw creds set`).
- **Storage.** A single SQLite ledger (`~/.gmlw/ledger.db`, WAL) for jobs, sessions,
  per-turn usage, and session costs.
- **Safety.** Validated `JobId` + filesystem containment under an owner-only `~/.gmlw`;
  never overwriting an unparseable client-settings or credentials file.

### Engineering
- Hexagonal (ports & adapters), enforced by `import-linter`; strict `ruff` + `pyright`
  over `src` and `tests`; `nox` gates mirrored by CI across Python 3.11–3.14; a
  server-side no-AI-attribution check and branch protection.

[Unreleased]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/danielslobozian/generic-ml-wrapper/releases/tag/v0.1.0
