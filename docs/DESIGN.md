# generic-ml-wrapper — design

*The canonical record of how the wrapper is laid out and why. A fresh session
should read this and not re-derive the model. Everything here is verified against
the source tree; when the code and this document disagree, the code wins — fix the
document.*

---

## 1. What it is

A **metering wrapper around an ML coding CLI.** You enter at a **job** — a piece of
work you tag — and the wrapper mints a named, resumable **session** on the client,
optionally driven by a **workflow** (a small operating context you author once),
records **every turn's tokens and cost** through a local metering relay, and hands
you the client exactly as you know it.

It is *"an application that uses an ML client, not an ML client pretending to be an
application"* — the deterministic parts (session identity, launch, context
compilation, persistence, metering) are Python; the judgment stays in the client.

Four clients are supported: **claude**, **cursor**, **codex**, and **vibe**. They
are all driven the same way and land in the same ledger; where they differ (metering,
resume, status line) is isolated inside each client adapter.

## 2. The family

`generic-ml-wrapper` is a sibling of
[`generic-ml-cache`](https://github.com/danielslobozian/generic-ml-cache) and
[`generic-ml-workflow`](https://github.com/danielslobozian/generic-ml-workflow), and
follows their conventions: a single `src/` package, hexagonal internals, `nox`
(lint · imports · typecheck · tests · coverage · sonar · green), `ruff@100`, strict
`pyright`, Apache-2.0, public and forkable.

The wrapper is **not** a stripped-down workflow tool. It is its own product: sessions
+ launch + metering out of the box, with the workflow as an *optional* enrichment,
not its identity. `gmlw start <job>` with no workflow is already the whole wrapper.

## 3. The hexagon

Single package, ports-and-adapters, dependencies point **inward only** — enforced by
import-linter (`.importlinter`), not just convention:

```
adapter.inbound.cli  →  application.port.inbound  →  application.usecase
                                                          │ (depends only on ports)
                                                          ▼
adapter.outbound.*   →  application.port.outbound  ←──────┘
                              ▲
                        application.domain  (depends on nothing)
```

- **`application.domain`** — entities, validated identifiers, and pure services. No
  I/O, no imports of ports/usecases/adapters.
- **`application.port.inbound`** — the use-case interfaces (what the app *does*).
- **`application.port.outbound`** — what the app *needs* from the world.
- **`application.usecase`** — orchestration; depends only on ports, never adapters.
- **`application.wiring`** — the composition root; binds ports to adapters and reads
  config to choose the client caller and interceptors.
- **`adapter.inbound.cli`** — argparse controllers that call inbound use-cases.
- **`adapter.outbound.*`** — the concrete implementations of the outbound ports.

The three enforced contracts:

1. **domain-purity** — `application.domain` must not import `usecase`, `port`,
   `wiring`, or `adapter`.
2. **application-ring** — `domain` / `usecase` / `port` must not import `adapter` or
   `wiring`.
3. **ports-no-usecases** — `application.port` must not import `application.usecase`.

## 4. The domain model

All value objects are frozen dataclasses (or validated `str` subclasses); they know
nothing about the filesystem, the client, or HTTP.

**Entities**
- **`RunContext`** — everything one run needs: `job`, `session_id`, `client`, `uuid`,
  `resume`, and the launch `cwd` / `context` / `kickoff` / `env`.
- **`Session`** — `<job>_NNN`, a resumable client conversation; carries the `client`
  it ran on and the client-side id (`uuid`, e.g. Claude's `--session-id`).
- **`TurnUsage`** — one metered request/response round: `input_tokens`,
  `output_tokens`, `cache_creation_tokens`, `cache_read_tokens`, `cost_usd`, `model`,
  `timestamp`, `duration_s`, `turn_id`. Validates non-negative, finite amounts.
- **`ClientStatus`** — a client-agnostic status snapshot: `model`, `context_pct`
  (0–100), `session_cost_usd`, `extras`.
- **`Workspace`** — the run's environment: `folder`, `repo`, `branch`, `short_sha`,
  `dirty`.

**Identifiers** (validated `str` subclasses, raise `IdentifierError` on bad input)
- **`JobId`** — `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. Constructed at the CLI boundary so a
  path-unsafe job id fails early, before any store is touched (CWE-22 defence).
- **`WorkflowName`** — lowercase kebab `[a-z0-9][a-z0-9-]*`.
- **`EnvVarName`** — POSIX `[A-Za-z_][A-Za-z0-9_]*`.

**Domain services** (pure)
- **`Interceptor`** (ABC) — the domain-owned contract `intercept(text, target) -> str`.
  The outbound `InterceptorPort` *extends* this, so the dependency arrow points inward.
- **`InterceptorChain`** — ordered `(target, interceptor)` pairs; `apply(target, text)`
  runs the matching interceptors in order (empty chain = identity).
- **`clean_rule`** (`rule_cleaner`) — strips YAML frontmatter and named `**Section:**`
  blocks from a rule; idempotent.
- **`next_session_id`** (`session_naming`) — the next `<job>_NNN`.
- **`render_statusline`** / **`render_job_usage`** (`statusline_renderer`) — compose the
  status-line string and the per-job usage footer.

## 5. Inbound ports (use cases)

| Use case | What it does |
|---|---|
| `StartJob` | validate (workflow/caller/resume), mint or resume a session, launch the client |
| `ListJobs` | the jobs with recorded activity (authoring sessions hidden) |
| `ListSessions` | a job's sessions |
| `ExportUsage` | per-turn rows + per-model totals + per-session cost for a job |
| `RenderStatusline` | one live status block from the client's native payload |
| `NewWorkflow` | author a workflow via the create-workflow interview (an authoring session) |
| `ListWorkflows` | the runnable workflows |
| `SetCredential` | store a per-workflow credential (0600) |
| `Bootstrap` | first-run self-init of `~/.gmlw` (idempotent) |

`StartJob` **validates before it persists** — a rejected start (unknown workflow,
resume unsupported) records no session, so there are no ghost sessions.

## 6. Outbound ports (what the app needs)

| Port | Contract |
|---|---|
| **`CliCaller`** + `CliCallerProvider` | launch and meter one client run (see §7) |
| `SessionStorePort` | persist/read sessions per job; list jobs |
| `PerTurnMeteringPort` | append/read per-turn `TurnUsage` for a job |
| `UsageStorePort` | record/read a session's cumulative cost (monotonic) |
| `TranscriptPort` | persist a call's request/response/usage (opt-in provenance) |
| `WorkflowSourcePort` | seed defaults; read/create/compile workflows |
| `CredentialsStorePort` | resolve/set per-workflow credentials |
| `ClientStatusParserPort` | parse a client's native status payload → `ClientStatus` |
| `InterceptorPort` | transform a named target (`profile`/`rules`/`workflow`/`context` at compile time; `request`/`response` on the wire) |
| `WorkspaceInspectorPort` | report the run's folder + git state |
| `LayoutSeederPort` | create the runtime dirs + a default config, missing-only |

## 7. The `CliCaller` seam — the four clients

A single port, one **stateful instance per run** (state set up before launch, torn
down after). `CliCallerProvider.for_run(run)` resolves the caller, honouring
`[callers]` overrides first, then the four built-ins by name.

```python
caller = provider.for_run(run)
caller.start_metering()          # stand up the relay / install the status line
try:    rc = caller.start_client()   # launch the CLI, BLOCKS until the user quits
finally: caller.end_metering()       # tear down
```

`start_client` is a blocking foreground process, so **quit is the stop signal** —
teardown always runs in `finally`. Capability flags let the use case adapt per client:
`can_deliver_statusline`, `can_meter_per_call`, `can_resume`.

| Client | Binary | Meters? | Status line? | Resume? | Notes |
|---|---|---|---|---|---|
| **claude** | `claude` | ✅ (Anthropic) | ✅ | ✅ | relay via `ANTHROPIC_BASE_URL`; `--append-system-prompt-file`, `--session-id` |
| **cursor** | `cursor-agent` | ❌ | ✅ | ✅ | status-line install only; no relay |
| **codex** | `codex` | ✅ (OpenAI Responses) | ❌ | ❌ | relay to `chatgpt.com/backend-api/codex` |
| **vibe** | `vibe` | ✅ (Mistral / Chat Completions) | ❌ | ❌ | throwaway `VIBE_HOME` repointed at the relay |

Status-line **rendering** currently parses Claude's payload format only
(`ClaudeStatusParser`); the seam is client-agnostic and other parsers can be added.

## 8. The metering relay

For a metered client, `start_metering` stands up a `MeteringRelay` on
`127.0.0.1:<ephemeral>` in a daemon thread, and points the client's base URL at it.

- **Capability-URL auth.** The base URL is `http://127.0.0.1:<port>/<client>/<token>`,
  where `token = secrets.token_urlsafe(16)` is minted per run. A request whose
  `/<client>/<token>` prefix is wrong is refused (404); the token is the sole auth
  boundary. Requests carrying an `Origin` header (a browser cross-origin POST) are
  refused (403). The prefix is stripped before forwarding.
- **Per-turn metering.** A per-client `is_metered` predicate marks the request that
  begins a turn (`/v1/messages`, `/responses`, `/chat/completions`); a per-client
  `usage_reader` (`anthropic_sse`, `openai_responses`, `openai_chat`) reads tokens/cost
  from the response and records a `TurnUsage`. If a `TranscriptPort` is bound, the
  call's request/response/usage is emitted too. The call counter is thread-safe.
- **Lean buffering.** The response body is buffered (teed) **only** when the turn is
  metered or a `response` interceptor is bound; otherwise it streams straight through.
  `Accept-Encoding: identity` is forced upstream so usage is always readable.

The relay is deliberately generic (Strategy pattern: one relay + injected
forwarder / path-map / usage-reader / is-metered / transcript), so it can be extracted
into a standalone project later without change to the ports.

## 9. Storage

Everything lives under `~/.gmlw`, owner-only, on your machine.

**The ledger** — a single SQLite file, `~/.gmlw/ledger.db` (WAL; one connection per
operation; `PRAGMA user_version` schema versioning). Pre-1.0 the schema is *created
from its final state* (`SCHEMA_VERSION = 1`, one create step, no migrations — a schema
change is a full store reset). Tables:

| Table | Holds |
|---|---|
| `jobs` | `job`, `kind` (`work` \| `authoring`), `created_at` |
| `sessions` | `session_id` (`<job>_NNN`), `job`, `client`, `uuid` |
| `turns` | one row per metered turn: tokens (incl. cache), `cost_usd`, `model`, timing |
| `session_costs` | per-session cumulative cost (monotonic upsert — highest wins) |

Authoring sessions share the DB but are tagged `kind = 'authoring'`, so they never
appear in `gmlw jobs` and their spend is its own bucket.

**Context** — the exact compiled context a session launched with is written to
`~/.gmlw/contexts/<job>/<session>.context.md` (atomic write). A durable, inspectable
artifact; never written into the user's working directory.

**Transcript (opt-in)** — when `[transcript]` is enabled, each metered call writes a
self-contained trio under `~/.gmlw/transcripts/<job>/<session>/`:
`call_NNN.in.json` (request), `call_NNN.out.sse` (raw response), `call_NNN.usage.json`
(tokens/cost/model/timing). The folder is portable — it can be copied out and read
with no knowledge of the ledger.

Config and credentials stay as files (`config.toml`, `credentials.toml`), not in the DB.

## 10. Workflows — optional operating context

A workflow is a set of markdown files compiled, in fixed order, into one blob and
injected at launch (Claude: `--append-system-prompt-file`):

```
_common/base.md → profile/* → global rules → workflow rules → workflow steps
```

Each stage passes through the **interceptor chain**, so a transform like context
compression is an opt-in plug-in bound to a target, not a fork of the engine.

- **Rule cleaning (always, lossless):** drop each rule's YAML frontmatter and the
  human-only `Origin` / `Notes` sections; skip rules marked `status: draft`.
- **Compression (optional, off):** the `CompressorInterceptor` sends a context section
  through `generic-ml-cache` record/replay — the lossy lever for large contexts,
  config-gated (`[compress] prompt`), non-destructive on failure. The repo ships no
  prompt, so it is inert until configured.
- **Authoring** (`gmlw workflow new`) runs the shipped **create-workflow** meta-workflow
  as a normal (metered) authoring session, kept out of `gmlw jobs`.

Hidden folders `_common` and `create-workflow` are not listed as runnable workflows;
`profile/` has `me/` and `company/` subdirs.

## 11. Config — `~/.gmlw/config.toml`

Seeded on first run, fully commented, every section optional:

| Section | Purpose | Default |
|---|---|---|
| `[client] default` | the client used when `--client` is absent | `claude` |
| `[callers]` | override a client with a `module:Class` / `/path.py:Class` spec | none |
| `[[interceptors]]` | bind an interceptor spec to a `target` | none |
| `[compress]` | the compressor prompt / adapter / model / effort | off |
| `[transcript]` | enable the opt-in transcript + its root | off |
| `[logging] level` | log verbosity (also `GMLW_LOG_LEVEL`) | `warning` |

`[callers]` and `[[interceptors]]` load and **run Python** with your permissions — a
trusted-code extension point (see `SECURITY.md`). A configured-but-unloadable spec
**fails loudly**; only an absent one is a silent no-op.

## 12. The home — `~/.gmlw`

Created owner-only (`0700`) on first run:

```
~/.gmlw/
  config.toml                     tool settings (trusted-code boundary)
  credentials.toml                per-workflow secrets (0600)
  ledger.db                       jobs · sessions · turns · session costs (SQLite, WAL)
  contexts/<job>/<session>.context.md   the context a session launched with
  transcripts/<job>/<session>/    opt-in per-call in/out/usage trio
  workflows/  _common/ · create-workflow/ · <name>/
  profile/    me/*.md · company/*.md
  rules/      *.md
  compress-cache/                 the generic-ml-cache store the compressor uses
```

## 13. Package layout

```
src/generic_ml_wrapper/
├── application/
│   ├── domain/
│   │   ├── model/         run · session · turn_usage · client_status · workspace · identifiers
│   │   └── service/       interceptor · interceptor_chain · rule_cleaner
│   │                      · session_naming · statusline_renderer
│   ├── port/
│   │   ├── inbound/       start_job · list_jobs · list_sessions · export_usage
│   │   │                  · render_statusline · new_workflow · list_workflows
│   │   │                  · set_credential · bootstrap
│   │   └── outbound/      cli_caller · session_store · per_turn_metering · usage_store
│   │                      · transcript · workflow_source · credentials_store
│   │                      · client_status · interceptor · workspace · layout_seeder
│   ├── usecase/           one class per inbound port (ports only)
│   └── wiring/            composition.py — the build_* factories
├── adapter/
│   ├── inbound/cli/       app.py (argparse) · banner.py
│   └── outbound/
│       ├── caller/        claude · cursor · codex · vibe callers + provider, loader,
│       │                  context_file, status_line_config, vibe_config
│       ├── gateway/       relay.py + anthropic_sse · openai_chat · openai_responses
│       ├── store/         ledger.py · sqlite_{session,per_turn,usage}_store
│       │                  · filesystem_transcript_store
│       ├── credentials/   filesystem_credentials_store
│       ├── interceptor/   compressor · size_logger
│       ├── status/        claude_status_parser
│       ├── workflow/      filesystem_workflow_source
│       ├── workspace/     local_workspace_inspector
│       └── bootstrap/     filesystem_layout_seeder
└── common/                config · paths · log · spec_loader
```

## 14. Extension points — transforms vs actions

gmlw is extended at named points, all sharing one plumbing — a config entry naming a
`spec` (trusted code loaded at runtime, `"module:Class"` / `"/path.py:Class"` / a
plugin id), the same trusted-code boundary, best-effort execution. But the extension
points come in **two shapes**, and the shape is not cosmetic — it is a difference in
kind. Do not conflate them.

**Transforms — `InterceptorPort` (built).** A *filter in a pipe*: `intercept(text,
target) -> text`. Bound to a **data channel** (a `target` that exists *in the flow* —
the compile sections `profile`/`rules`/`workflow`/`context`, the wire bodies
`request`/`response`). Content passes *through* it and comes out changed; **its value
is its return**, and matching interceptors **compose in a chain** (B sees A's output).
A transform that does nothing returns its input (identity). Anonymising a `request`
body or compressing a context section is a transform.

**Actions — hooks (planned, 0.3.0).** A *listener on an event*: `run(run) -> None`.
Bound to a **lifecycle moment** (a `phase` in *time* — `pre-launch`, `post-session`),
not a data channel. Nothing flows through it; it observes the `RunContext` and *does*
something; **its value is its side-effect** (files written, a notice sent), not a
returned value. Deploying skills into a client's native folder before launch, or
notifying/archiving after a session, is an action.

**Neither subsumes the other.** A hook is not a `str→str` transform — at
`post-session` there is no content flowing, only an exit code and the run; the
interceptor contract is meaningless there. An interceptor is not fire-and-forget — its
whole job is to *return* the content the next stage uses. They cover disjoint points:
some data channels (every wire `request`) are not tied to a lifecycle moment, and some
moments (teardown) have no data channel.

(A **caller override** / plugin is a third, coarser thing: it *replaces* the launch
mechanism for a client, rather than extending one point of it.)

## 15. Design invariants — do not re-litigate

1. **Public-clean by construction.** No personal data, employer, job prefixes, or
   internal hosts in the repo. Real content lives only in `~/.gmlw`. Commits use a
   dedicated public identity; `secret-audit.sh` gates every publish.
2. **Dependencies point inward.** domain ← usecase ← ports; adapters depend on ports,
   never the reverse. Enforced by import-linter.
3. **The workflow is optional.** `gmlw start <job>` with no workflow is the pure wrapper.
4. **Fail loud on overwriting user files; skip-with-warning on our own append logs.**
   An unparseable `settings.json` / `credentials.toml` aborts rather than being
   destroyed; a configured-but-unloadable spec errors rather than silently no-ops.
5. **Validate before persist.** Identifiers are checked at the boundary; a rejected
   start records nothing.
6. **The compiled context is self-contained** and lives per-session under `contexts/`
   — never in the user's working directory.
7. **Quit is the stop signal.** `start_client` blocks; teardown is `finally`.
