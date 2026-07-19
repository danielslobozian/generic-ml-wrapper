# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-07-19

Discoverability and progressive disclosure — shortening time-to-first-session and
revealing depth gradually — plus app-wide localisation.

### Added
- **App-wide localisation.** Every user-facing message **and every diagnostic log line**
  now renders through a process-global active localiser (`i18n.set_active` / `active` /
  `t`), bound once at startup from the configured language, English-fallback then raw-key
  safe. The EN/FR catalogues are kept in lockstep by a drift-guard test. Localising the
  logs too is a deliberate choice, not the usual English-only-logs convention.
- **Config registry + `config` commands.** A `pydantic-settings` model is the typed source
  of truth for every settable scalar key (type, default, allowed values, description).
  `gmlw config list / get / set` render and validate against it; `set` merges through a
  shared tomlkit writer (comments and formatting preserved, never rewritten) and surfaces
  the old→new change. The home for changing `default_role` / `default_environment` after
  init. Scope is the scalar keys; the structural matrices (`[[hooks]]`, `[[interceptors]]`,
  `[startup.*.context]`, `[compress.prompts]`) stay hand-rolled, a deferred follow-up.
- **Bare `gmlw` capability index + `gmlw help <topic>`.** Bare `gmlw` is first-run-aware: a
  fresh install runs `init`, thereafter it shows a grouped capability index
  (launch / inspect / author) with a next-action footer. `gmlw help` explains the core
  concepts (`job-vs-workflow`, `start-vs-run`, `personas`, `cost`). `--help` keeps the
  argparse view.
- **Exit receipt.** On the return (client exit), a persistent summary: this session's and
  the job's cost, the resume/report commands, and one usage-driven, suppressible tip (shown
  once each; `[hints] show = false` disables). `StartJob` now returns a `StartJobResult` so
  the receipt can name the session.
- **Ambient capability card.** An off-by-default context injection
  (`[ambient] capability_card`): a localised "how do I … in gmlw" card appended to a new
  session's context so the client can answer gmlw questions mid-session.
- **`gmlw workflow edit`.** Amend an existing workflow in an authoring session — opens its
  folder, never creates or overwrites; an unknown workflow exits non-zero with guidance.

### Changed
- **Greeting → context.** The launch-time host greeting (structurally invisible once the
  client clears the screen) is no longer printed to stderr; it is injected into a new
  session's context so the client renders it in-band. The parting `Bye, <name>.` on exit
  stays.
- **`--version`.** Reports `gmlw <version> (build <id>)`; the git sha was dropped — it was
  captured at build time and every distributed artifact is built without a `.git` checkout,
  so it was always `unknown` where it would matter.

### Notes
- Authoring-cost visibility is deferred: the authoring bucket is deliberately kept out of
  `gmlw jobs`; surfacing its spend cleanly is its own design.

## [0.4.0] - 2026-07-19

The first-run release — a mandatory `init` that establishes the model the rest of the app
runs on, migrates the on-disk layout to match, and settles a working client before the
first session.

### Added
- **Guided client setup.** The init client step is no longer a silent chooser — it always
  talks the choice through. It lists each installed client with its version, and when a
  first-party release channel reports a newer one it flags an **old install** and offers
  the one-line update (comparing on numeric components, so a build *ahead* of a lagging
  stable channel is never nagged). It lets you switch, or **install a different client**:
  it prints the OS-specific install command (macOS/Linux vs Windows), copies it to the
  clipboard when a clipboard tool is present, offers to **run it for you** or let you run
  it yourself, then polls `PATH` until the client appears — and installs a prerequisite
  first (`uv` for Vibe) when it is missing. Every client's latest version comes from its
  vendor's own channel with a changelog/registry fallback: Claude Code's native stable
  manifest → GitHub `CHANGELOG.md`; Cursor's install-script version → the Homebrew cask
  JSON; the npm registry → GitHub releases for Codex; PyPI → GitHub releases for Vibe.
  All version reads are best-effort — an offline machine degrades to a plain list, never
  a block. The launch-time "client not on your PATH" guidance now shows the same
  OS-specific command. The client catalog (`client_catalog.py`) carries per-OS
  install/update commands, the paid-plan framing, and the version sources.
- **Forced init + the gate.** A mandatory first-run setup, `gmlw init`, is now both a
  command and a first-class gate: `[init] version` in `config.toml` records that it ran,
  and any command on an un-initialised or pre-0.4.0 install is funnelled through init
  before it runs (`statusline` and bare `--help` are exempt). The interview captures, in
  order — each with a sensible default so a non-interactive run never blocks — **language
  → name → role → environment → persona → client**: language sets the voice the rest of
  the interview speaks (chosen language re-localises every later prompt), name is what the
  companion calls you, role and environment seed the movie-set axes (`[profile]
  default_role` / `default_environment`), persona and client reuse the existing choosers.
  A fresh install gets a full seeded `config.toml`; a legacy install gets every answer
  merged into its existing file (see below). Retires the thinner 0.2.0 `FirstRunInit`.
- **Every init answer is persisted — on a legacy install too.** Previously a pre-0.4.0
  install had only the `[init]` marker appended, so the language, name, role, environment,
  persona and client you had just chosen were discarded and had to be re-entered. They are
  now **merged into the existing `config.toml`**: each value is written into its table
  (created when missing) through a round-trip TOML edit, so **every other setting, every
  comment, and the file's formatting survive untouched** — arrays like `[[interceptors]]`
  included. The persona and client are written only when one was chosen, so declining never
  clears an existing value. Any setting a fresh choice replaced is reported on stderr
  (`client.default: cursor → claude`) rather than changed silently.
- **Environment migration.** Place-specific context is now a first-class **environment**:
  it lives under `environments/<env>/` (one folder per environment, the movie set) instead
  of the single `profile/company/`. On any command, gmlw non-destructively wraps an old
  `profile/company/` into the **active** environment (`[profile] default_environment`,
  `work` by default) — a move (nothing copied or lost), a name that already exists at the
  target is left in place and reported (never overwritten), and the emptied old folder is
  retired. What moved and what was skipped is printed to stderr. The move runs on both the
  forced-init and the normal bootstrap paths, so an install initialised before the
  migration existed is caught too. The `company` context source is unchanged as a config
  key; only its on-disk home moved to `environments/<env>/`.
- **Role-scoped rules & learned.** The role chosen at init (`[profile] default_role`, a lens
  over `me`) now shapes context: rules under `profile/roles/<role>/rules/*.md` and a
  `profile/roles/<role>/learned.md` compose into the `rules` and `me.learned` sources **only
  when that role is active** — layered after the global rules/learned (general → specific).
  `gmlw init` seeds the chosen role's folder with an empty `rules/` drop-zone. Capture stays
  global for now (new reflexes are still written to `rules/` and `profile/me/learned.md`);
  role-aware capture is a later step.

### Changed
- **New runtime dependency: `tomlkit`** (MIT, pure Python, no transitive deps) — the
  round-trip TOML editor that merges init's answers into an existing `config.toml`
  without disturbing the user's comments or settings. stdlib `tomllib` reads TOML but
  cannot write it. `LayoutSeederPort.initialize` now returns an `InitPersist`
  (`fresh` + `overwrites`) instead of a bare bool.
- **`ClientInfo` gained per-OS commands.** The single `install` field became
  `install_unix` / `install_windows` (plus `update`, `subscription`, `version_probes`,
  `prereq`); callers use `install_for(system)` / `update_for(system)`. The 0.2.0
  `TtyClientChooser` and its `ClientChooserPort` were **removed**, superseded by the new
  `ClientSetupPort` (`TtyClientSetup`) that owns the full guided conversation.

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

[Unreleased]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/danielslobozian/generic-ml-wrapper/releases/tag/v0.1.0
