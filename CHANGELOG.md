# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **A job is only its name.** The ledger used to tag every job `work` or `authoring` and
  keep the two apart, which meant a name held by one was refused to the other — and, before
  that refusal existed, meant the two silently shared a row and leaked each other's
  sessions. The tag is gone. One name is one job, reusing it is how a job accumulates its
  history, and nothing is refused. The `jobs.kind` column stops being written; an existing
  database keeps it, unread and unchanged, rather than being migrated destructively.
- **Editing a workflow is filed with creating it.** `gmlw workflow edit <name>` used to
  record its sessions under a job named after the workflow, invisible only because of the
  tag above. It now files under `create-workflow` alongside `gmlw workflow new`, so all
  authoring is one history and one cost. Which workflow a session edited is still carried
  by the session's folder, so `--resume-latest` reopens the right conversation.
- **`gmlw jobs` leaves out `create-workflow`, and nothing else.** It is the one job name
  the system chooses for itself. It is not protected: it can be deleted, and its spend is
  metered, like any other job's.

## [0.11.0] - 2026-08-02

Things can be removed now. Until this release gmlw only ever accumulated: every job that had
ever had a session stayed in the listing and in the menu for good, next to the throwaway ones
made while trying something out. Deletion arrives at two grains, in the CLI and in the menu,
and `gmlw sessions` gains the turn count and cost you need to decide what is worth keeping.
Alongside it, a pass over the menu itself — a launch can now be pointed at a client without
changing the global default, `Job > New` offers the jobs you already have, and the three
places that used to drop you back at the shell mid-task stay in the app.

### Added
- **Jobs and sessions can be deleted** ([#82](https://github.com/danielslobozian/generic-ml-wrapper/issues/82)).
  Until now nothing in the wrapper removed anything: every job that had ever had a session
  stayed in `gmlw jobs` and in the menu for good, alongside the throwaway ones made while
  trying things out. Two grains, mirroring each other:
  - `gmlw jobs delete <job>...` removes whole jobs — every session, its per-turn usage and
    cost, its compiled contexts, and its transcripts. The job's folders go whole, so residue
    no recorded session still claims goes with them.
  - `gmlw sessions <job> delete <session>...` removes single sessions and leaves the job
    standing. This is the one for the session you opened, remembered something, and quit out
    of: `StartJob` records a session *before* the client runs (by design — a rejected start
    must not burn an id), so an abandoned session is recorded like any other and was, until
    now, permanent.

  Both take several ids at once, because cleaning up one item at a time is not worth doing —
  which is how the list got long. Both print exactly what will be removed (sessions, turns,
  cost, context and transcript files) and then ask; `--yes` answers in advance, and off a
  terminal without it the delete is **refused** rather than assumed. One unknown id aborts the
  whole batch untouched rather than deleting half of it. Bare `gmlw jobs` and
  `gmlw sessions <job>` are unchanged.

  In the menu, **Job > Delete** offers the same two grains: `space` ticks rows, `⏎` asks. The
  question is asked *in* the app, on a screen that opens on **No** — `⏎` is the most reflexive
  key there is and must not be the destructive one — and shows the same footprint the CLI
  prints. Either answer leaves you on the list you were clearing, with the removed rows already
  gone from it. The removal itself is an injected closure, so the TUI still holds no port.

  Deleting a session in the middle of a job is safe by construction: `next_session_id` already
  minted one past the highest suffix "so gaps never cause a collision", so nothing renumbers
  and no id is reused.

- **The menu can point a launch at a client**
  ([#79](https://github.com/danielslobozian/generic-ml-wrapper/issues/79),
  [#80](https://github.com/danielslobozian/generic-ml-wrapper/issues/80)). Every launch from
  `gmlw tui` used the configured default, so running one job on a different client meant
  changing the global default in Config and changing it back afterwards. **Job → New**,
  **Workflow → Run**, **Create**, and **Edit** now end with a client step — the menu's
  equivalent of `--client`, which the CLI has always had.

  It opens on the configured default with the cursor already there, so `⏎` is "whatever I
  normally use" and choosing otherwise is deliberate. The choice is **per-launch** and never
  rewrites `client.default`. **Resume is not asked about**, by design — a resumed session
  relaunches on the client it was made with.

  **Only clients that can actually be launched on are offered**, from two sources with two
  different rules. A built-in appears when its binary is on `PATH`. Every name under
  `[callers]` appears too, marked 🔌 — including custom callers gmlw does not ship, since
  `DefaultCliCallerProvider` resolves an override *by name before* any built-in, making
  `cursor-mitm = "…:CursorMitmCaller"` as real a client as `claude`. A configured caller is
  offered whatever `PATH` says: gmlw has no idea what someone else's caller needs, and
  configuring one is already the statement that it works. A chooser built from the catalog
  alone would have been the one place in gmlw where those clients did not exist.

  Behind it, a `ListLaunchClients` port: a `PATH` lookup, the `[callers]` map, and the
  default — and deliberately no version reads. `ListClients` (the Config → Clients view)
  runs `<binary> --version` per installed client, which is several subprocesses and not
  something that belongs between "start this job" and the job starting.

- **`Job > New` offers the jobs you already have**
  ([#81](https://github.com/danielslobozian/generic-ml-wrapper/issues/81)). It was a free-text
  field, so starting more work on an existing job meant remembering its exact name and typing
  it back — while the menu was showing that same list under `Job > List` and `Job > Resume`.
  It now opens on a picker: **Type a new name…** first (it is what the verb says, it is the
  only row on an install with no jobs, and a fixed first row means the flow does not shift as
  jobs come and go), then one row per recorded job. Picking one starts a *new session* on it,
  numbered after its last — exactly what `gmlw start <existing-job>` has always done, which is
  why nothing new was needed underneath. Typing a brand-new name is unchanged, and still
  validated in-form. Resume is untouched and still reopens a recorded session.

### Fixed
- **Deleting from the menu no longer leaves the menu.** The first cut handed the selection back
  to the wiring and asked on the restored terminal, which meant the app tore down, asked, and
  came back at the *front door* — three levels away from the list being cleaned, whichever way
  the question was answered. Declining also printed an acknowledgement that had to be dismissed,
  for an action that did nothing. The question is now a screen inside the app: it opens on
  **No**, Esc is a no, and either answer returns to the very list it was asked from, re-read so
  the removed rows are gone and with the ticks cleared. Nothing is printed for a no.
- **Exporting and importing a workflow no longer exit the menu.** Both borrowed the restored
  terminal to print a result or ask about a name clash, and then ended the process — dropping
  the user back at the shell mid-task. Both now happen in the app. Export packs in place and
  says where the file went, so exporting a second workflow is one keypress away with the list
  still in front of you. Import installs, re-reads the catalogue so the new workflow is
  immediately runnable, and asks about a name clash on the same confirmation screen deleting
  uses — worded for *replacing*, since an import keeps a backup and is precisely not the
  irreversible thing a delete is.
- **The menu no longer exits after re-running setup.** `Config > Setup` is an interview that
  genuinely needs the terminal, so it still steps out — but `_tui` now loops rather than
  ending, and returns to the menu afterwards. A *launch* (start, resume, run, authoring) still
  ends gmlw, because a client owned the terminal and the session is over when it is.

### Changed
- **`gmlw sessions` shows what each session used** — turn count and cost per row, and the word
  `empty` for a session that never took a turn. Without it, deciding what to delete is a guess:
  the listing had no way to tell a day's work from a session abandoned at the prompt. `--json`
  rows gain `turn_count` and `cost_usd`; the existing fields are untouched.

## [0.10.0] - 2026-08-01

The documentation release. The docs had grown as residue rather than deliverable — seven
files under `docs/` plus a README that had absorbed every capability since 0.1.0, the same
concepts written out three and four times with the nuance drifting between copies, and
three files still opening with a "v0.2.0" header seven releases stale. This release makes
one pass over all of it, and adds the two things that were missing entirely: a
first-contact install path, and an answer to "how do I update?"

### Added
- **A one-line install, on both platforms.** `install.sh` (`curl -LsSf … | sh`) and
  `install.ps1` (`irm … | iex`) ensure `uv` is present — Astral's own installer when it is
  not — then `uv tool install generic-ml-wrapper`. **No Python prerequisite**: `uv` fetches
  its own interpreter, so the usual "which Python, is it recent enough, is it the distro's
  broken split package" question never arises. Both check whether the install actually
  landed on `PATH` and, when it did not, say so loudly with the exact line to add and which
  rc file — rather than exiting silently successful. Two scripts rather than one with OS
  branches: the PATH and shell-reload story differs too much between POSIX and PowerShell
  to share code honestly.
- **`docs/CONCEPTS.md`** — one canonical explanation of the job/session/workflow model, the
  four context axes (me / role / environment / persona), the Rules mechanism, and why
  client capabilities differ. Every doc that used to re-explain one of these now links here
  instead.
- **`docs/README.md`** — a reading-order index (start here → do things → reference → deep
  dives), replacing the flat list of guides.
- **An update notice on the exit receipt.** A `VersionCheckPort` and `PypiVersionChecker`
  (stdlib `urllib.request`, ~2s timeout, no new dependency) plus a `CheckForUpdate` use
  case report when a newer gmlw is on PyPI. The answer is cached at
  `~/.gmlw/state/update-check.json` with a fixed 24h TTL, so most launches never touch the
  network at all, and every failure mode — network, timeout, bad JSON, unexpected shape —
  degrades to silence rather than raising. The notice appears only on a launched session's
  exit (`start` / `run` / `tui`), never on `jobs` / `export` or other read commands. Opt out
  with `gmlw config set update.check false`.
- **How to update, said out loud.** The README now answers the question that notice raises:
  gmlw never updates itself. It checks PyPI at most once a day and reports; installing the
  new version stays yours to do, with `uv tool upgrade generic-ml-wrapper`.
- **Cassettes for `gmlw tui` and `gmlw help`** — `docs/images/gmlw-tui.gif`, embedded in
  `CLI.md`'s `tui` section, and `gmlw-help.gif`. The TUI tour is browse-only by
  construction: it walks the cursor across the front door and into exactly three read-only
  list screens, and never enters a verb that would launch a client or write config.

### Changed
- **The docs describe the surface that actually ships.** An audit of every page against
  the CLI's argparse definitions, the settings registry, the TUI menu, and the client
  catalogue found the drift had collected in three places. `CLI.md` documented neither
  `workflow export` / `import` / `drafts` / `resume` nor the `--resume-latest`,
  `--client-args`, and `--description` flags, and its `tui` section still described the
  0.7.0-era menu — three top-level items, most verbs "placeholders until they are built
  out" — when the menu has had a fourth (Rules) since 0.8.1 and no placeholder verbs
  since 0.8.2. `CONFIGURATION.md` was missing `[language]`, `[ambient]`, and
  `client.args` entirely. `WORKFLOWS.md` never mentioned that a workflow can be shared
  or that an interrupted authoring session can be reopened. `USER_GUIDE.md`'s `--json`
  list was a strict subset of the commands that accept it. `README.md`, `CLIENTS.md`,
  `TROUBLESHOOTING.md`, and `CONCEPTS.md` were checked and needed no correction.
- **Each concept explained once.** The Rules mechanism had been written out in full in
  `USER_GUIDE.md`, `WORKFLOWS.md`, and `DESIGN.md`, the three copies drifting apart;
  client-capability reasoning was duplicated across `README.md`, `CLIENTS.md`, and
  `DESIGN.md`. Both now live in `CONCEPTS.md` and are linked from everywhere they used to
  be restated. The stale "v0.2.0" headers in `USER_GUIDE.md`, `CLI.md`, and
  `TROUBLESHOOTING.md` are gone, and every See-also footer cross-links `CONCEPTS.md`.
- **`CONFIGURATION.md` documents `[hints]`.** It never had — a gap predating this release,
  fixed alongside the new `[update]` section since the two sit next to each other.

### Fixed
- **The TUI's Export and Import subtitles rendered as raw key strings.** When the workflow
  Export/Import verbs were wired in 0.8.2, the title keys `tui.wf.export` / `tui.wf.import`
  were added to both catalogues but the `.d` subtitle keys were not, so the Workflow menu
  showed the key itself in EN and FR alike. Both catalogues now carry them. The drift guard
  cannot catch this class of bug: the menu builds its subtitle key as `t(f"{key}.d")`, a
  computed lookup the AST-based check cannot verify statically. Recorded as a known blind
  spot rather than papered over.
- **The rendered cassettes had been showing the wrong thing.** `docs/tapes/seed.py` never
  accounted for the forced first-run init gate added in 0.4.0, so the demo `$HOME` carried
  no `[init]` marker and `gmlw jobs` / `sessions` / `export` were silently hitting the
  interactive language prompt instead of rendering real output — which is why
  `gmlw-usage.gif` had been stale on `main`. The seed now writes a minimal `config.toml`
  with the marker, and every GIF was re-rendered and inspected frame by frame.

## [0.9.1] - 2026-07-30

Every user-facing exception carried a raw English message, interpolated verbatim into
the CLI's localised error wrapper — a French user saw French wrapped around English.
The 0.8.0 drift guard never caught this, since it only checked `print`/`log.*`/argparse/
`Binding` call sites, never `raise` sites.

### Fixed
- **Domain exceptions are localised.** A new `DomainError` base
  (`common/errors.py`) gives an exception a catalogue key and structured params instead
  of a formatted string. The 11 classes that leaked raw English (`IdentifierError`,
  `WorkflowNameError`, `WorkflowNotFoundError`, `UnknownWorkflowError`,
  `ResumeNotSupportedError`, `AxisLabelError`, `AxisExistsError`,
  `InvalidSettingValueError`, `ArchiveUnreadableError`, `NoSuchDraftError`,
  `NoEditToResumeError`) now carry one, with ~21 new EN/FR catalogue entries rendering
  them.

### Changed
- **The drift guard now checks `raise` sites too.** `test_no_untranslated_literals.py`
  flags a future `raise` site with a missing catalogue key the same way it already
  flagged a bad `t()` call.

## [0.9.0] - 2026-07-30

Personas, proven. "Personas shape tone" was an untested claim — an external evaluation
(three independent judges, blind attribution) checked it and fed the fixes back in.

### Added
- **Persona `dimensions` in frontmatter.** Warmth, Verbosity, Formality, and Proactivity
  move from the injected tone body into frontmatter — declared for `gmlw persona list`
  and for evaluation, without spending context restating them on every turn.
- **A floor invariant: persona colors prose, never artifacts.** Commit messages, code,
  code comments, JSON, and tool arguments now read the same under every persona.

### Changed
- **Five personas tuned against evaluation findings.** `mentor` was statistically
  indistinguishable from the client's own default voice and now leads with the
  mechanism; `butler` dropped contractions, caps itself to one anticipatory offer, and
  stopped fabricating facts it doesn't have; `plain`/`terse` moved from the same dial at
  two strengths to genuinely different mechanical dials; `companion` was given a
  "light polish" that, once all five were tested together, turned out to have traded
  away its actual distinctiveness — reverted once the numbers showed it.

### Fixed
- **TUI pickers show workflow labels, not slugs.** Run, Edit, Export, and the List
  screen were fed bare folder slugs; they now use the same labelled catalog that
  `gmlw workflow list` already had.

## [0.8.2] - 2026-07-29

Work that survives leaving. A codex session you can come back to, an authoring interview
that outlives the crash that interrupted it, and a workflow that travels to someone else's
machine — plus the client parity and TUI corrections that came with them.

### Added
- **Codex sessions resume.** Codex mints its own session id and takes no launch flag to
  accept one, so the wrapper simply marked it unresumable. The fix inverts the direction:
  the relay *learns* the id from the first metered turn's `client_metadata.session_id`,
  binds it to the session record, and registers the session's `<job>_NNN` name in codex's
  own `session_index.jsonl` — so `codex resume <job>_NNN` works with or without gmlw. What
  rotates on the wire is `turn_id`, sitting right beside it; binding that would rebind the
  session every turn and resume nothing, and a test pins the distinction. Every resume is
  gated on the rollout file existing, because `codex resume <unknown>` does not fail — it
  silently starts a *new* session, handing back an empty one wearing a resumed session's
  name.
- **`gmlw workflow export <name>` and `gmlw workflow import <path>`.** A workflow's own
  folder packs into a zip and installs back on another machine, asking before it replaces
  an existing workflow. Both are in the TUI's Workflow menu; import takes a typed path
  rather than a picker, because the archive you want is usually the one a colleague just
  sent you, sitting wherever your browser put it.
- **Authoring survives an interruption.** A crash, a Ctrl+C, a closed laptop used to take
  the whole interview with it. `workflow new` and `workflow edit` now write the draft as
  they go and reopen where they stopped.
- **A status line for codex**, reading like the wrapper's own, so moving between clients no
  longer means losing the bar. Session and job durations now show there.
- **`[client.args]`** passes user-supplied arguments straight through to the client,
  per-client — so a machine configured for claude doesn't inherit claude's flags.

### Changed
- **A workflow is named in words**, with the slug derived from the name: what you type
  reads like a title, what lands on disk stays a safe identifier.
- **`can_resume` moved onto the caller.** It was looked up by client *name* in the built-in
  catalog, which meant a caller supplied through `[callers]` or a plugin could never be
  resumable however capable it was. Resumability is now a property of the session, not the
  client: codex answers false at launch and true from the first turn, once the relay has
  bound the id.

### Fixed
- **The clients listing stopped lying about codex.** It still read the catalog's
  launch-time flag and printed `resume: no` long after codex started resuming. The flag now
  means what the listing says, and carries the condition:
  `resume: yes (once its id is bound, after the first turn)`. Five doc pages said
  otherwise; they no longer do.
- **A config change applies to the launch that follows it.** The default client was
  resolved *before* the Textual app ran, so switching it in Config took effect only on the
  next run of gmlw — the job you started right after launched on the client you had just
  left.
- **The settings picker's first row is really selected.** It rebuilt its rows and set the
  highlight in the same breath, but `ListView.clear()` removes asynchronously, so the index
  landed on rows already on their way out and nothing ended up marked — the first Down
  looked like it skipped a row. The row is also painted at focused strength there, since
  the filter `Input` holds focus and the list itself never does.
- **Config → Clients answers "use that one"**, not just "what have I got". Enter on a row
  writes `client.default`, moves the marker in place, and keeps the menu's notion of the
  default in step, so the resume picker's "will launch on X" notes stay honest.
- **The TUI's workflow-name rule describes what the validator actually enforces.**

## [0.8.1] - 2026-07-26

A rule is a projection of the user, so it belongs on one of the two axes that describe one:
the **environment** (constraints of the place — its processes, standards, tooling) or the
**role** (the user's own preferences about the craft). This release moves rules onto those
axes and deletes the two tiers that sat outside them.

### Changed
- **Rules now live on the environment and role axes; the global and per-workflow tiers are
  removed.** A rule is read from `~/.gmlw/environments/<env>/rules/<slug>.rule.md` or
  `~/.gmlw/profile/roles/<role>/rules/<slug>.rule.md`, and from nowhere else. The global
  `~/.gmlw/rules/` and per-workflow `<workflow>/rules/` directories are no longer read — a
  workflow that behaves wrongly is fixed in the workflow, not patched by a rule sitting
  beside it.

  **Migration.** Existing files are **not** moved for you: rules left in `~/.gmlw/rules/` or
  in a workflow's `rules/` folder are silently inactive after upgrading. Move each one into
  the environment (if it encodes a constraint of the place) or the role (if it encodes your
  own craft preference). The config key is migrated automatically — see below.
- **On conflict the environment wins.** A constraint is not overridden by a preference, so
  environment rules compose *last*, closest to the model, and the capture directive says so
  outright. Within a single axis, an explicit `Precedence:` number decides.
- **A rule is active from creation.** The user demanded the correction, so it applies —
  rather than being parked as a draft awaiting promotion. `status: draft` survives as the
  user's own off-switch, for retiring a rule without deleting it.
- **The rule format moved to `~/.gmlw/templates/rule.template.md`**, seeded once and never
  overwritten. The capture directive reads it from disk and embeds it, so the format the
  model follows is the user's own file — collapsing two hand-synced copies that could
  silently drift into one.
- **Config keys `rules.environment` / `rules.role` replace the scalar `rules`.** The
  migration carries an explicit legacy setting onto *both* axes, so a deliberate opt-out is
  never silently undone by the rename.

### Added
- **A Rules browser in `gmlw tui`** (Job · Workflow · Config · Rules · Quit). It lists only
  the axes and groups that actually hold rules, and marks the ones switched off.
- **A session snapshot at the head of every compiled context** — the active environment,
  role, persona, user, language, and job as a JSON block, so a client answers "which role am
  I in?" by reading a field instead of inferring it.
- **A `rules/` folder for environments at creation.** `FilesystemAxisCatalog.create()` made
  one only for roles.

### Fixed
- **Draft-ness is read from frontmatter** rather than a substring search over the whole file,
  which silently dropped any live rule whose prose happened to mention drafting.
- **`docs/CONFIGURATION.md` documented the rules source as `activated = false`** when the
  code default was `true`.

## [0.8.0] - 2026-07-25

Two sweeps over the *whole* application, both about the same thing: gmlw was saying things
in the wrong language and writing them to the wrong place. Neither is a feature you switch
on — each is a pass that ends with a guard, so the debt cannot quietly come back.

### Added
- **Logging as a real subsystem — a diagnostics port and swappable sinks.** gmlw's
  diagnostics were 83 lines printing to `stderr`, which during a wrapped session **is the
  client's own screen** — so a warning either corrupted the client's TUI or vanished on its
  next redraw, and was written nowhere else. There is now a `DiagnosticsPort` that core
  emits through, importing no logging library, with the destination chosen at the
  composition root. The contract is that **a sink never raises**: a diagnostics failure must
  not break or alter the run it was only observing.
- **A rolling log file at `~/.gmlw/logs/gmlw.log`.** Appended across runs, size-capped with
  bounded backups, and it preserves a caught exception's traceback — so a failure no longer
  has to reach the screen to be diagnosable. The destination is now a wiring decision rather
  than a branch at every call site: file **and** `stderr` for a utility command, file only
  once a command hands the terminal over (`start` / `run` / `tui` / `workflow new|edit`), and
  silence for the statusline, which renders into another program's prompt from a short-lived
  subprocess many times a session. Configurable via `[logging]` (`to_file`, `max_bytes`,
  `backup_count`).
- **Secret and PII scrubbing in the sink**, so no call site has to remember. Deliberately
  narrowed twice against over-redaction, because a log that has eaten its own identifiers is
  useless: session ids and content hashes survive, and the entropy rule no longer treats `/`
  as secret-ish — the inherited rule ate every file path in a traceback and rendered it
  `[secret].py`.
- **Localisation, finished — every message a key, technical logs included.** 0.5.0 built the
  catalogue mechanism; four releases of new surfaces put English literals back, because
  nothing failed when they did. 87 new keys (EN and FR, **395 each**) convert what drifted:
  every argparse `help` / `description` / `metavar`, the TUI footer labels, the 17
  settings-registry descriptions, and the client catalogue's login hints. Logs are localised
  on purpose rather than by oversight — a French user reading their own log file, or pasting
  one into an issue, is the case that decides it.
- **A drift guard that fails the build** (`tests/test_no_untranslated_literals.py`). It
  catches the three things key-parity cannot see, since parity only checks the languages
  against each other: a literal at a `print` / `log` / argparse / `Binding` call site, a
  `t()` key missing from the catalogue (which renders as the raw key), and a registry setting
  with no `setting.<key>` entry. Each was verified to actually fail by introducing the
  violation it targets.

### Changed
- **`--help` speaks one language instead of two.** `build_parser()` ran before the localiser
  was installed, so `--help` would have stayed English whatever the language setting; that
  ordering is fixed. argparse's own chrome (`usage:`, `positional arguments`, `options`, `-h`,
  `--version`) comes from its gettext domain, which the catalogue cannot reach — so
  `add_help=False` plus a localised help formatter brings it under the same roof.

### Fixed
- **A TLS failure in the relay can no longer reach the client's screen**
  ([#59](https://github.com/danielslobozian/generic-ml-wrapper/issues/59)). An error in a
  relay request thread escaped uncaught and `socketserver`'s default `handle_error` printed a
  raw traceback to `stderr` — unreadable, uncopyable, and in no log file, while the session
  carried on as if nothing had happened. Three operations talked to the upstream over TLS
  with no guard; the only `try`/`except` covered writes *to the client*, the direction that
  was not failing. `_proxy` is now a boundary around the whole exchange, returning a clean
  `502` if it fails before the response head is on the wire and ending the stream cleanly
  after; `handle_error` routes through the diagnostics port; `_drain` guards the upstream
  **read**, so a connection dropped mid-response keeps what arrived and a cut-short turn is
  still metered rather than lost; post-response bookkeeping is guarded separately, because by
  then the client has its answer and a ledger failure is ours; and the accept loop is guarded
  too — it runs on a daemon thread, so its death would silently stop metering while the
  session kept working, the one failure mode worse than a visible error.

### Engineering
- Registry descriptions hold a catalogue **key** resolved at render time, since a pydantic
  `Field` is evaluated at import, long before a localiser exists. TUI bindings resolve at
  import too, which is correct because the module is imported lazily after the localiser is
  installed — documented at the top of the module.
- Deliberately left in English: the TOML comments in the generated `config.toml` (the keys
  they annotate are English, and a half-translated config reads worse than a consistent one),
  install and login commands, vendor plan names, and the `gmlw > ` breadcrumb.

## [0.7.0] - 2026-07-24

The interactive release — a full-screen TUI over every verb, roles and environments you
can create rather than only configure, and data screens that render as real tables.

### Added
- **Interactive TUI menu (`gmlw tui`).** An additive, opt-in full-screen menu that fronts
  **every Job / Workflow / Config verb** — including launching a fresh session (Job → New)
  and resuming a *specific* named session, not just the latest. It never replaces the
  argv path: the CLI stays the fast lane and the menu is there when you want to browse.
  The copy is localised, and the menu was de-spiked into its final shape before the
  remaining verbs were wired in.
- **Create a role or environment (`CreateAxis`).** Roles and environments are now
  first-class **slug-folders** — a stable slug id plus a human label and description —
  and there is a use case and CLI to **create a new one**, not just select among seeded
  ones. The movie-set axes (`default_role` / `default_environment`) are authored, not
  only configured.
- **`gmlw sessions` text render.** The text view now shows each session's **folder,
  date, and whether it is resumable**, so the plain listing carries what you need to pick
  one to resume without dropping to `--json`.

### Changed
- **Status line token compaction.** Token counts render compacted (`k` / `M` / `G`) so a
  busy status line stays readable, and the remaining data screens now render through a
  shared **DataTable**, giving the listings one consistent, aligned presentation.

### Fixed
- **init announcement speaks the chosen language.** The first-run init announcement now
  renders in the language you chose during the interview, not the OS locale — matching the
  rest of the localised init flow.

### Engineering
- **Release trigger.** Publishing to PyPI now reacts to a **published GitHub Release**
  rather than a bare tag push, making the Release the single front door for a version (it
  carries the notes and mints the tag). Trusted Publishing is keyed on the workflow
  filename + environment, so no PyPI-side change was needed; the guard job still fails
  fast when the Release's tag does not match `VERSION`.

## [0.6.0] - 2026-07-19

The workflow, made first-class — a direct way to run one, name-at-the-end authoring, and
a guided authoring experience — plus a truthful context meter on the status line.

### Added
- **`run <workflow>`.** Launch a workflow directly: the job is named after the workflow
  and its sessions accumulate there — the recurring-procedure counterpart to `start`
  (which enters a job you return to), equivalent to `gmlw start <workflow> -w <workflow>`.
  With no workflow given, a trigger-gated pre-launch chooser offers the authored ones at a
  terminal and echoes the equivalent one-liner so interactive use teaches the fast path;
  full argv never prompts, and a non-interactive run degrades cleanly.
- **`workflow new` decides the name at the end.** The name is optional and proposed at the
  end of the interview, not demanded up front. Authoring runs in a private draft folder
  under `~/.gmlw/drafts/` (sessions accumulate under `create-workflow`); on a finished
  marker, gmlw atomically deploys the draft into `~/.gmlw/workflows/<name>/`, so a
  half-authored workflow never appears in `workflow list` or `run`. A name given up front
  is a seed that fails fast on a collision; a name taken at deploy, or an unfinished
  session, keeps the draft and points at `workflow edit`.
- **Guided authoring.** `workflow new` / `edit` offer a richer, facilitative guide — a
  parking lot for tangents, a diverge→converge rhythm, process-leveling ("a step, or its
  own workflow?"), proposing the upstream/downstream stages you left out, with
  anti-railroading and consent-gate guardrails, and distilled-state files (`draft.md`,
  `parking-lot.md`) so a long session survives context compaction. The choice is asked on
  every interactive run (Enter takes guided); `--guided` / `--quick` answer up front, and a
  non-interactive run defaults to quick. The guide is injected only when chosen, so quick
  is genuinely cheaper.
- **Status line: a truthful context meter.** The claude status line now shows the
  denominator — `ctx 155.6k/200k (78%)` instead of a bare percentage — so a window
  under-reported behind the metering relay (which looks like a gateway, capping the
  reported window at 200k) is visible. Rate-limit windows also render their time-to-reset
  (`5h 90% (↻ 12m) · wk 40% (↻ 3d)`) from `resets_at`, since a percentage without a reset
  time is not actionable. Both degrade to the previous output when a client omits the
  fields; the cursor parser reads the same context shape.

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

[Unreleased]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.11.0...HEAD
[0.11.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.9.1...v0.10.0
[0.9.1]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.8.2...v0.9.0
[0.8.2]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/danielslobozian/generic-ml-wrapper/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/danielslobozian/generic-ml-wrapper/releases/tag/v0.1.0
