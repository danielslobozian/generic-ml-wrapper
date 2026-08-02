<!-- SPDX-FileCopyrightText: 2026 Daniel Slobozian -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Roadmap

Where `generic-ml-wrapper` has been and where it's going. Direction, not a
commitment — see [CHANGELOG.md](CHANGELOG.md) for what has actually shipped.

The through-line: turn a metering wrapper into something a person *wants* to open —
a companion that carries **who you are and how you work across every client**, and
stays a wrapper (it extends each client; it never reimplements one).

## Shipped

### 0.1.0
The metering foundation — jobs & sessions, four clients (claude / cursor / codex /
vibe), a per-turn metering relay into a SQLite ledger, a client-aware status line,
and the workflow system. On PyPI.

### 0.2.0 — the companion
Everything a session inherits, and the ergonomics around it.

- **First-run init** — detect installed clients, seed a filled config with a default.
- **Config-driven, mode-aware context packaging** — a `[startup.<mode>]` matrix picks
  which sources compose (persona · profile · learned · company · rules · workflow
  base/steps) for each mode (default / workflow / authoring), with **typed per-source
  compression** (`[compress.prompts]`).
- **Personas** — selectable tone with a universal floor; `gmlw persona list`; a free,
  local **host greeting** at launch; a first-run persona choice.
- **Learned** — a portable, user-owned notebook the client mirrors into, read into
  every client so what one learns they all inherit; **negatives are first-class**.
- **Rule format** — a domain-neutral `Rule / When / Signals / Strength / Origin`
  (+ optional `Precedence`), with in-session capture during a workflow.
- **Formal plugins folder** — reference a caller by id (`~/.gmlw/plugins/<id>/`),
  `gmlw plugins list`.
- **Cursor allowance block** — the status line renders cursor's plan pools from an
  optional local cache when the client doesn't pipe them.
- **Ergonomics** — client & working-directory preflight (clear guidance instead of a
  cryptic crash), implicit `gmlw <job>` (shorthand for `start`), a friendly no-job
  message, and auto-help for an incomplete sub-command.
- **Create-workflow** — the interviewer assesses each step's *codeability* and offers
  to script the mechanical ones, keeping the AI for the judgment steps.

### 0.3.0 — lifecycle action hooks
gmlw already hooks **content**: the interceptor chain transforms context sections at
compile time and wire traffic at relay time (e.g. anonymisation on `request`). It now
also hooks **actions** — "after this phase, run something" — at two lifecycle seams
that bracket the client run:

- **`pre-launch`** — after the context is compiled and the caller resolved, before the
  client starts. Knows the client, the working directory, and the session. For
  per-client setup: deploying skills/rules into a client's *native* mechanism, writing
  MCP config, warming a cache.
- **`post-session`** — after the client exits. Knows the exit code and the session.
  For cleanup, notification, archival, or roll-up.

Config mirrors the existing extension points — a `[[hooks]]` entry with a `phase`, a
`spec` (a plugin id or `path.py:Class`), and an optional `client` scope — under the
same trusted-code boundary as `[[interceptors]]`, `[callers]`, and plugins. Hooks are
best-effort and never break a launch. Both launch paths (`start`, `workflow new`) route
through one shared launch sequence, so the seams bracket every run. Shipped with a
built-in `SessionLogger` reference hook.

**Still open — the flagship example hook:** a **cross-client skills/rules deployer** that
consumes a git repo of skills and installs them, per client, as faithfully as each
client's format allows. It is its own initiative (per-client format knowledge), built on
the seam above; the infrastructure is done and waiting for it.

#### Rule lifecycle
0.2.0 shipped rule *capture*, but only inside a workflow (the directive lived in the
workflow base) and without dedup or a path to code. The rule loop is now rounded out —
the directive moved out of the workflow base to the head of the always-on `rules`
context source (verbatim, gmlw's voice), and the source is active by default in a plain
start:

- **Rule proposal in normal usage** — the "offer to record a rule" directive is
  always-on, so a demanded correction becomes a draft rule wherever it happens, not only
  inside a workflow.
- **Existing-rule check (dedup / update-not-duplicate)** — before proposing, the client
  reads the existing rules and updates or supersedes a matching one instead of stacking a
  near-duplicate, mirroring the learned notebook's supersede-on-contradiction.
- **Rule → code feasibility** — a captured rule is judged for *mechanical
  enforceability* and, if so, offered as a script/check rather than a reminder — the
  step-codeability logic (create-workflow) generalised from workflow steps to rules, and
  a natural future `pre-launch` hook consumer.

### 0.4.0 — first run: the forced setup that shapes every session
One job, done properly: a **mandatory `init`** every user passes through once — new or
existing — because it establishes the model the rest of the app runs on and migrates the
on-disk layout to match. It is a *forced update*: the old single-context folder layout is
wrapped into the new one non-destructively, and role + environment are chosen before the
first session. The discoverability work that used to sit here has moved to 0.5.0; this
release is the init and the two concepts under it.

**The movie-set model.** A launch composes four axes — three describe *you and your
context* (they become the briefing the wrapper hands the companion), one describes *the
companion itself*:

- **Me — the actor.** Who you are, invariant across everything: name, language, the
  journal. Spans every launch.
- **Role — the character.** The functional hat you're wearing (software engineer, product
  owner, QA, a private individual buying groceries). A *lens over `me`*, not a copy — it
  parameterises the `me`-extraction (which facets are in scope) and scopes rules/learned.
  You stay one person; you play different parts.
- **Environment — the movie set.** Where the work happens (work-at-a-company, a personal
  project, open source). It swaps the *place-specific context* — today's forced `company`
  becomes one environment's bucket. Changing environment changes the set and the
  guidelines, not who you are.
- **Persona — the director.** The one entity you actually talk to: the companion. Persona
  is *its* manner (manner over method — see 0.6.0).

gmlw itself is the **stage organiser / assistant director**: it builds the set, arranges
costume and makeup, briefs the director, then cedes the screen ([[wrapper-not-standalone]]).

- **Forced init (`gmlw init`, and the gate)** — init is both a command and a first-class
  gate: a stored marker records that it ran, and bare `gmlw` routes an un-initialised or
  old-layout install into it before anything else runs. It captures, in order, **language
  → name → role → environment → persona**, then does the technical client step. Each
  answer carries a sensible default so the forced pass stays short.
- **Two new concepts — role & environment** — the two axes above, made real: `default_role`
  and `default_environment` in `config.toml` (read directly — no registry yet), a
  `profile/roles/<role>/` folder for role-scoped rules/learned, and an
  `environments/<env>/` folder for place-specific context. Both are changeable later (via
  the `config` commands landing in 0.5.0). This **resolves the parked _profiles_ fork** —
  `me` spans, role is a lens over it, environment is the external place — by splitting one
  container into two orthogonal axes.
- **Forced migration** — the existing global layout (`profile/company`, single-context
  `rules`) is wrapped non-destructively into the new shape — `profile/company` →
  `environments/work/`, a `default` role seeded — surfacing exactly what moved
  ([[no-silent-removals]]). No install is left on the old layout.
- **Localised setup (EN / FR)** — onboarding strings move into a keyed language file
  (`i18n/en.*`, `i18n/fr.*`) read through a small `t(key, lang)` lookup with English
  fallback; the default is seeded from `$LANG`. Mechanism built to extend; content scoped
  to onboarding for now.
- **`language` — our voice only** — a `language` setting fixes the language gmlw speaks to
  *you* (onboarding now, receipts/help later). It does **not** force the companion's
  language: only Claude Code exposes a real language setting; Cursor, Codex and Vibe have
  none, so pushing it would be a leaky per-client hack for one client out of four. gmlw
  speaks your language; the companion stays as its own config leaves it.
- **A working client — the one hard requirement** — after the human setup, the technical
  step. *Fast path*: detect an installed, authenticated client and reach a session in
  seconds. *Guided path* when none is found: a subscription→client map (*"do you pay for
  Claude / ChatGPT / Cursor / Mistral?"*), the **official install command for the detected
  OS** (Windows / Linux / macOS), and **guide-and-verify auth** — print the exact login
  command, poll readiness until it goes green (guide, don't drive).
- **A default persona** — the experience-defining choice, offered with a one-line
  description per persona so it can be made without reading docs.

Deferred but homed: a detached model call to synthesise a `role.md` for an unfamiliar role
(e.g. product owner) is a natural future consumer of the 0.3.0 `pre-launch` seam — parked,
not built. **Persona *previews* moved to 0.9.0** — sample lines are only worth shipping once
the personas behind them are proven to actually differ, and doing them in French requires
localising persona content, which is the same job (see 0.9.0).

### 0.5.0 — discoverability & progressive disclosure
Reframed around the real metric for a new user: **time to a first live session**, and then
revealing depth *gradually*. Because the wrapper cedes the screen to the client, discovery
lives in the thin surfaces **around** a run — bare-command indexes, the return, and ambient
context pushed *into* the client — never a persistent UI over a live session.

- **App-wide localisation** (`0fe8c0a`) — the init-only JSON catalogue now spans the whole
  app: every user-facing message **and every diagnostic log line** renders through a
  process-global active localiser (`i18n.set_active`/`active`/`t`), English-fallback then
  raw-key safe. A catalogue-drift guard keeps EN/FR key sets identical. Localising the logs
  too was a deliberate choice, not the usual English-only-logs convention.
- **Config registry** (`9fe05b6`) — a `pydantic-settings` model is the typed source of
  truth for every settable scalar key (type, default, allowed values, description);
  `registry_rows()`/`coerce()`/`load()` drive help, `config`, and validation. `config.py`
  sources its defaults from it (no duplicated literals) while keeping its tolerant reads.
  *Scope:* scalar keys only — the structural matrices (`[[hooks]]`, `[[interceptors]]`,
  `[startup.*.context]`, `[compress.prompts]`) stay hand-rolled, a deferred follow-up.
- **`config` commands** (`0db3ca7`) — `config list / get / set`, rendering + validating
  against the registry; `set` merges through the shared tomlkit writer (comments preserved,
  never rewritten) and surfaces the old→new change. The home for changing `default_role` /
  `default_environment` after init.
- **Bare `gmlw` + `gmlw help`** (`61bb15f`) — bare `gmlw` is first-run-aware: fresh install
  → init; thereafter → a grouped capability index (*launch / inspect / author*) with a
  next-action footer. `gmlw help <topic>` explains the core concepts (job-vs-workflow,
  start-vs-run, personas, cost). `--help` keeps the argparse view.
- **Greeting → context** (`85a77da`) — the launch-time host greeting (structurally
  invisible once the client clears the screen) is retired from stderr and injected into a
  new session's context, so the client renders it in-band. `_farewell` (exit) stays.
- **Exit receipt + ambient card** (`f36fcd8`) — on the return, a persistent receipt: this
  session's and the job's cost, the resume/report commands, and one usage-driven,
  suppressible tip (shown once each; `[hints] show` to disable). `StartJob` returns a
  `StartJobResult` so the receipt can name the session. The off-by-default ambient
  capability card (`[ambient] capability_card`) injects a "how do I …" gmlw card into the
  context. **Authoring-cost visibility deferred** — the authoring bucket is deliberately
  kept out of `gmlw jobs`; surfacing its spend cleanly is its own design.
- **`workflow edit`** (`0445c6d`) — amend an existing workflow in an authoring session
  (opens its folder, never creates/overwrites; unknown name → clean error).
- **Already shipped earlier, verified here:** **`--version`** (surfaces the running version)
  and **robustness** (clean Ctrl+C / SIGTERM interrupt-exit) were already present; their few
  strings were folded into the app-wide localisation pass.

### 0.6.0 — the workflow, first-class
Two ways people relate to a workflow: *applied to a job* (a ticket it treats), or *the
recurring job itself* (a repeatable extraction). Make both first-class, and make
authoring one a guided conversation — because most people don't arrive with a clear
model of their own process.

- **`run <workflow>`** — launch a workflow directly; the job defaults to the workflow
  name and sessions accumulate under it. `start <job> [--workflow]` stays for the
  applied case. A trigger-gated pre-launch chooser fills only *missing* arguments and
  always echoes the equivalent one-liner, so interactive use teaches the fast path
  (full argv never gains a prompt).
- **Name at the end, not the start** — `workflow new` no longer demands a name up front;
  forcing one presumes the user already knows the shape. The authoring conversation
  shapes the workflow and *proposes* the name at convergence. (Distinct from
  `run <workflow>`, where an existing, recurring workflow's name has already earned it.)
- **Facilitative + constructive authoring** — the create-workflow conversation as a
  blended consultant. Two axes: *facilitate* (a **parking lot** for tangents so nothing
  is lost, reflective listening, a **diverge → converge** phase model, and **process
  leveling** to answer "step or its own workflow?") and *contribute* (start in inquiry
  and **move to expert when warranted**, propose the upstream/downstream stages the
  author omitted, surface **implications** they haven't hit) — bounded by guardrails
  against railroading a novice and a **consent gate** on anything personal. Authoring
  keeps distilled state (a draft plus the parking lot) as files in the workflow folder,
  so it survives context compaction.

#### Statusline — render the data Claude Code already hands us
A separate, self-contained thread riding in this release: the status payload gmlw
receives already carries more than it displays, and two of those fields are parsed out
and dropped. No new plumbing — the data arrives at the status parser today; the fix is to
keep it and render it. Claude-first (the cursor parser shares the context shape and
benefits where the fields overlap); codex and vibe pipe no status payload, so this
degrades honestly rather than fabricating a denominator.

- **Show the denominator** — today gmlw renders a bare `78%` against an *unstated*
  window size. The payload also carries `context_window_size` (200k default, 1M for
  extended-context models), so render `155.6k/200k (78%)` instead. This is what makes the
  percentage falsifiable: a Max user who sees `/200k` knows the window is being
  under-reported (the metering relay looks like a gateway, so Claude Code can't verify 1M
  support and budgets 200k) and can act on it themselves. Extend the client status with
  `context_window_size` and `context_tokens`.
- **Quota: time-to-reset, not just percentage** — `5h 90%` is unactionable without
  knowing whether reset is in 10 minutes or 4 hours. The payload carries `resets_at`
  (epoch seconds) per window; render it as a relative duration — `5h 90% (↻12m) · wk 40%
  (↻3d)`. Each window may be independently absent (subscriber-only, appears after the
  first response), so tolerate a missing reset per field exactly as the percentage
  already is. The single most decision-relevant pair a metering wrapper can show.
- **Baseline & drift (candidate)** — a session that opens at 26% full looks identical to
  one at 5% until it's too late. A pre-launch / first-turn line surfacing the baseline
  cost (tools · mcp · skills), and a note when the baseline drifts upward across a client
  auto-update. Softer than the two above; carried as a candidate, not a commitment.

### 0.7.0 — bug fixes & the interactive TUI menu
An additive, opt-in terminal menu, and the role/environment axes made *authorable* rather
than only configurable — plus a round of data-screen and localisation fixes.

- **Interactive TUI menu (`gmlw tui`)** — an opt-in menu that fronts **every Job / Workflow
  / Config verb**, including launching a fresh session (Job → New) and resuming a *specific*
  named session, not just the latest. It never replaces argv: the CLI stays the fast lane and
  the menu is there to browse. Built additively, de-spiked into shape, and localised.
- **Create a role or environment (`CreateAxis`)** — the movie-set axes introduced in 0.4.0
  become **first-class slug-folders** (a stable slug plus a human label and description), with
  a use case and CLI to *create* a new role or environment, not only select among the seeded
  ones. `default_role` / `default_environment` are now authored, not just configured.
- **`gmlw sessions` text render** — the plain listing shows each session's folder, date, and
  whether it is resumable, so you can pick one to resume without dropping to `--json`.
- **Statusline token compaction + DataTable** — token counts render compacted (k / M / G),
  and the remaining data screens render through a shared table for one consistent, aligned
  presentation.
- **Fixes** — the first-run init announcement speaks the chosen language, not the OS locale.

### 0.8.0 — every string a key, every log a file
Two sweeps over the *whole* application, both about the same thing: gmlw was saying things in
the wrong language and writing them to the wrong place. Neither was a feature — each was a
pass that ends with a guard, so the debt cannot quietly come back.

- **Localisation, finished** — 87 new keys (EN and FR, **395 each**) convert what had drifted
  back since 0.5.0: every argparse `help` / `description` / `metavar`, the TUI footer labels,
  the 17 settings-registry descriptions, the client catalogue's login hints. Technical logs are
  localised on purpose — a French user reading their own log file is the case that decided it.
  `--help` now speaks one language rather than two, argparse's own chrome included.
- **A drift guard that fails the build** — rejects a literal at a `print` / `log` / argparse /
  `Binding` call site, a `t()` key missing from the catalogue, and a registry setting with no
  `setting.<key>` entry. The mechanically enforceable half that key-parity could not see.
- **Logging as a real subsystem** — a `DiagnosticsPort` in core with the concrete adapter built
  at the composition root, a never-raises contract, a rolling file sink at `~/.gmlw/logs/`, a
  structured line format, and PII scrubbing in the sink (narrowed twice against over-redaction).
  The destination is a wiring decision: file + `stderr` for a utility command, file only once a
  command hands the terminal over, silence for the statusline.
- **Relay error boundaries ([#59](https://github.com/danielslobozian/generic-ml-wrapper/issues/59))**
  — a TLS failure in a request thread no longer dumps a raw traceback onto the live client's
  screen. Boundaries around the exchange, the upstream read, post-response bookkeeping, and the
  accept loop, all recorded through the port.

### 0.8.1 — rules, scoped to the axes
A rule is a projection of the user, so it lives on one of the two axes that describe one —
and the tiers that sat outside them are gone.

- **Rules move onto the environment and role axes** — the place's constraints at
  `~/.gmlw/environments/<env>/rules/`, your own craft preferences at
  `~/.gmlw/profile/roles/<role>/rules/`. The global `~/.gmlw/rules/` and per-workflow
  `<workflow>/rules/` tiers are removed: a workflow that behaves wrongly is fixed in the
  workflow, not patched by a rule beside it. Existing files must be moved by hand.
- **The environment wins on conflict** — a constraint is not overridden by a preference, so
  environment rules compose last, closest to the model. `Precedence:` decides within an axis.
- **Active from creation** — the user demanded the correction, so it applies; `status: draft`
  becomes their off-switch rather than a promotion gate. Draft-ness is read from frontmatter
  instead of a substring search that silently dropped live rules mentioning drafting.
- **One rule format, on disk** — `~/.gmlw/templates/rule.template.md`, seeded once and read
  by the capture directive, replacing two hand-synced copies that could drift.
- **A Rules browser in `gmlw tui`**, plus a **session snapshot** heading every compiled
  context (environment · role · persona · user · language · job), so a client reads which
  role it is in rather than inferring it.

### 0.8.2 — work that survives leaving
A session, an interview, a workflow — none of them should end because you did.

- **Codex sessions resume.** The relay learns the id codex minted from the first metered
  turn and registers the session's `<job>_NNN` name in codex's own index, so
  `codex resume <job>_NNN` works with or without gmlw. Resumability becomes a property of
  the *session*, not the client — which also frees callers supplied through `[callers]` to
  be resumable at all.
- **Workflows leave the machine** — `workflow export` packs one into a zip, `workflow
  import` installs it back, both from the CLI and the TUI.
- **Authoring survives an interruption** — `workflow new` and `workflow edit` write the
  draft as they go and reopen where they stopped; a workflow is named in words, with the
  slug derived from the name.
- **Client parity** — a status line for codex, `[client.args]` passthrough per client, and
  a clients listing that no longer claims codex cannot resume.
- **TUI corrections** — a config change applies to the launch that follows it, the settings
  picker's first row is really selected, and Config → Clients sets the default rather than
  just listing.

### 0.9.0 — personas, proven
Going in, "personas shape tone" was an **untested claim**. A persona ships a tone block, but
nothing demonstrated that `mentor` and `terse` actually answer differently — and the tone
block is injected *on top of* each client's own system prompt, which could simply swamp it.
An external, manual evaluation (three independent judges — Claude, codex, composer — blind
attribution) checked the claim and fed the fixes back in. Not a harness built into gmlw yet
— a one-time pass whose *outcome* shipped; the reusable harness itself is 0.9.1.

- **Persona `dimensions` move into frontmatter** — Warmth · Verbosity · Formality ·
  Proactivity, declared for `gmlw persona list` and for evaluation, without spending
  context restating them on every turn.
- **A floor invariant: persona colors prose, never artifacts** — commit messages, code,
  code comments, JSON, and tool arguments read the same under every persona.
- **Five personas tuned against what the judges found** — `mentor` was statistically
  indistinguishable from the client's own default voice and now leads with the mechanism;
  `butler` dropped contractions, caps itself to one anticipatory offer, and stopped
  fabricating facts it doesn't have; `plain`/`terse` moved from the same dial at two
  strengths to genuinely different mechanical dials; `companion` was given a "light polish"
  that — found only once all five were finally tested together — traded away its actual
  distinctiveness (warmth) for a generic efficiency habit, and was reverted once the numbers
  showed it.

### 0.9.1 — i18n, the remaining gap
Every user-facing exception carried a raw English message, interpolated verbatim into
the CLI's localised error wrapper — a French user saw French wrapped around English.
The 0.8.0 drift guard never caught this, since it only checked `print`/`log.*`/argparse/
`Binding` call sites, never `raise` sites.

- **Domain exceptions are localised** — a new `DomainError` base gives an exception a
  catalogue key and structured params instead of a formatted string; the 11 classes that
  leaked raw English now carry one, with ~21 new EN/FR catalogue entries rendering them.
- **The drift guard now checks `raise` sites too** — `test_no_untranslated_literals.py`
  flags a future `raise` site with a missing catalogue key the same way it already
  flagged a bad `t()` call.

### 0.10.0 — the documentation release
The docs had grown alongside the features: seven files under `docs/` plus a README that had
absorbed every new capability since 0.1.0. This release treated documentation as the deliverable
rather than the residue — one pass over what existed, plus the thing missing entirely, a
first-contact install path.

- **A one-line install, on both platforms** — `install.sh` for Linux/macOS and `install.ps1` for
  Windows, served from the repo and pasted into the README. Each does one job: ensure `uv` is
  present (Astral's own installer when it is not), then `uv tool install generic-ml-wrapper`.
  **No Python prerequisite** — `uv` fetches its own interpreter, so the usual "which Python, is it
  recent enough, is it the distro's broken split package" logic never arises. Two separate scripts
  rather than one with branches: the PATH story differs too much between them to share code
  honestly.
- **PATH, said out loud** — the common failure for a tool installed this way is a shim directory
  that is not on `PATH`, and the second most common is a shell that has not been restarted. The
  scripts detect both and say so loudly rather than exiting silently successful; the README
  carries the same note so it is findable without re-running anything.
- **Hosted from the repo, not a site** — the raw GitHub URL is stable and CDN-cached. The cost is
  no server-side OS detection, so the README shows both commands, labelled. Accepted deliberately:
  a dedicated install page is not worth standing up a web property for.
- **A pass over the existing docs** — README, `USER_GUIDE`, `CLI`, `CONFIGURATION`, `CLIENTS`,
  `WORKFLOWS`, `TROUBLESHOOTING` audited against the surface that actually ships, so what they
  describe and what gmlw does are the same thing. The pass also collapsed the duplication it
  found: `CONCEPTS.md` was added as the one place the job/session/workflow model, the four context
  axes, the Rules mechanism, and client capabilities are explained, and `docs/README.md` as a
  reading-order index.
- **Not in the original milestone, shipped alongside:** the other half of the install story — a
  cached, rate-limited **update notice on the exit receipt**, telling you when a newer gmlw is on
  PyPI and leaving the upgrade to you. Once a day at most, degrades to silence on any failure,
  `gmlw config set update.check false` to turn it off.

### 0.11.0 — removal, and a menu you can stay in
gmlw had only ever accumulated. Nothing in the wrapper removed anything, so every job that had
ever had a session stayed in the listing and in the menu permanently, alongside the throwaway
ones made while trying something out. This release adds deletion at two grains and fixes the
places where the menu let go of the terminal mid-task.

- **Deletion, at two grains** — `gmlw jobs delete <job>...` takes whole jobs (sessions, per-turn
  usage and cost, compiled contexts, transcripts, folders and all); `gmlw sessions <job> delete
  <session>...` takes single sessions and leaves the job standing. Both accept several ids,
  print the exact footprint before asking, and refuse rather than assume off a terminal without
  `--yes`. One unknown id aborts the whole batch untouched. In the menu, **Job > Delete** offers
  the same two grains on a confirmation screen that opens on **No**.
- **`gmlw sessions` shows what each session used** — turn count and cost per row, `empty` for one
  that never took a turn. Without it, deciding what to delete is guesswork. `--json` rows gain
  `turn_count` and `cost_usd`.
- **A launch can be pointed at a client** — **Job → New**, **Workflow → Run**, **Create** and
  **Edit** end with a client step, the menu's equivalent of `--client`. Per-launch, never
  rewrites `client.default`, and offers only clients that can actually be launched on: built-ins
  found on `PATH`, plus every name under `[callers]` whatever `PATH` says.
- **`Job > New` offers the jobs you already have** — a picker instead of a free-text field, with
  **Type a new name…** fixed as the first row. Picking an existing job starts a new session on
  it, which is what `gmlw start <existing-job>` always did.
- **The menu stays the menu** — delete, workflow export/import, and re-running `Config > Setup`
  each used to end the process and drop the user at the shell. All three now happen in the app
  and return to the list they were asked from. A *launch* still ends gmlw, because a client
  owned the terminal and the session is over when it is.

## Planned

_Next milestone not yet chosen._

## Parked

- **External source connectors** — let a workflow pull from external systems (APIs,
  cloud storage, platforms) rather than manual input. Large; its own initiative.
- Relay extraction to a standalone project (shelved — no second consumer yet).
- Workspace layout feature.
