# generic-ml-wrapper — design

*The canonical record of how the wrapper is laid out and why. A fresh session
should read this and not re-derive the model. Companion to `VISION.md` (the why).
When this and `VISION.md` disagree, VISION wins for intent; this wins for how we
build it.*

---

## 1. What it is

A **wrapper around an ML coding CLI.** You enter it at a **job** — a piece of
work you're tagging; it mints a named, resumable session on the
client, optionally injects a **workflow** (a small operating context you author
once), meters the run, and hands you the client exactly as you know it.

It is *"an application that uses an ML client, not an ML client pretending to be
an application"* — the deterministic parts (session identity, launch, context
compilation, persistence) are Python; the judgment stays in the client.

**v0.1.0 targets Claude Code only.**

## 2. The family

`generic-ml-wrapper` is a sibling of `generic-ml-cache` and
`generic-ml-workflow`, and follows their conventions: single `src/` package,
hexagonal internals, `nox` (lint · typecheck · tests · coverage · sonar · green),
`ruff@100`, `pyright`, Apache-2.0, published, forkable, contributions welcome.

The wrapper is **not** a stripped "v1 of the workflow." It is its own product:
sessions + launch + metering out of the box, with the workflow as an *optional*
enrichment, not its identity.

## 3. The home — `~/.gmlw`

One hidden home holds everything the wrapper owns:

```
~/.gmlw/
  config.toml                       tool settings
  jobs/<job>/                       per-job data
    sessions.jsonl                    the job's sessions (id · client · uuid)
    db.jsonl                          one line per metered turn
    session-costs.json                cumulative $ per session
    <session>.context.md              the exact context a session was launched with
  profile/  me/*.md · company/*.md    who you are        ┐ seeded defaults,
  rules/    *.rule.md · rule.spec.md   rules that grow     ├ user-edited, loaded
  workflows/ _common/ · create-workflow/ · <name>/         ┘ into every workflow
```

A **job** is the unit of work you tag; a **session** is one named, resumable
conversation belonging to a job.

## 4. Entities (the domain model)

- **Job** — an identifier for a unit of work (`JOB-123`). Owns sessions.
- **Session** — `<job>_NNN`, a resumable client conversation; carries the client
  it ran on and the client-side id (uuid for Claude).
- **WorkflowContext** — the compiled operating context injected at launch:
  common base + profile + rules + the workflow's steps.
- **Usage** — a metered turn: model, input/output/cache tokens, cost, timing.

These are pure value objects; they know nothing about the filesystem, the client,
or HTTP.

## 5. The hexagon

Single package, hexagonal internals, dependencies point **inward only**
(enforced by import-linter):

```
adapter.inbound  →  application.port.inbound  →  application.usecase
                                                      │ (depends only on ports)
                                                      ▼
adapter.outbound ←  application.port.outbound  ←──────┘
                          ▲
                    application.domain  (depends on nothing)
```

- **domain** — entities + pure services (naming, compilation, cleaning). No I/O.
- **application.port.inbound** — the use-case interfaces (what the app *does*).
- **application.port.outbound** — what the app *needs* from the world.
- **application.usecase** — orchestration; depends only on ports, never adapters.
- **application.wiring** — the composition root; binds ports to adapters, reads
  config to choose the client caller.
- **adapter.inbound.cli** — argparse controllers that call inbound use-cases.
- **adapter.outbound.*** — the concrete implementations of outbound ports.

## 6. Inbound ports (use cases)

| Use case | What it does |
|---|---|
| `StartJob` | mint/resume a session on a job, optionally with a workflow, launch |
| `ListJobs` | the jobs with recorded activity (authoring sessions hidden) |
| `ListSessions` | a job's sessions with turns · tokens · $ |
| `ExportUsage` | per-turn / per-session usage report for a job |
| `RenderStatusline` | one live status block from the client's native payload |
| `NewWorkflow` | author a workflow via the create-workflow interview |
| `ListWorkflows` | available workflows |

## 7. Outbound ports (what the app needs)

| Port | Contract |
|---|---|
| **`CliCallerPort`** | run a client: `start_metering` · `start_client` · `end_metering` |
| `SessionStorePort` | persist/read sessions, jobs, usage, session-costs |
| `WorkflowSourcePort` | seed defaults, read profile/rules/workflows, compile context |
| `ClientStatusPort` | parse a client's native statusline payload (cost/tokens/quota) |
| `CompressorPort` | optionally compress rules (default: no-op) |
| `ClockPort` | time (injected, for testable timestamps) |

## 8. The `CliCallerPort` — the extension seam

A single port, three methods, one **stateful instance per run** (state set up
before launch and torn down after):

```python
class CliCaller(ABC):
    def start_metering(self) -> None: ...   # BEFORE launch
    def start_client(self) -> int: ...      # launch the CLI, BLOCKS until quit
    def end_metering(self) -> None: ...      # AFTER quit
```

The use case runs them in order:

```python
caller.start_metering()
try:    rc = caller.start_client()
finally: caller.end_metering()
```

`start_client` is a blocking foreground process, so **quit is the stop signal** —
when the user exits the client, `start_client` returns and `finally` fires
`end_metering`. No polling, no server-shutdown guesswork.

**Base `start_client` merges `self.env_overlay`** (empty by default), so a caller
that needs extra environment sets it up in `start_metering` and reuses the whole
launch — writing only its own additions.

**Which adapter is chosen is config-driven** (`[callers] <client>`): blank → the
built-in default; a path → an external adapter loaded at runtime.

## 9. Metering

Each turn's usage — model, input/output/cache tokens, cost — is captured by the
active client caller and written to the job's store (`db.jsonl`,
`session-costs.json`). It surfaces live in the statusline and after the fact via
`gmlw export`. **How** a given client exposes its usage is the caller adapter's
private concern; the rest of the app reads only the stored `Usage` records.

## 10. Workflows — optional operating context

A workflow is a folder of markdown compiled, in fixed order, into one blob and
injected at launch (Claude: `--append-system-prompt-file`):

```
_common/base.md  →  profile/*  →  global rules  →  workflow rules  →  workflow.md
```

- **Clean step (always, lossless):** drop each rule's YAML frontmatter and any
  human-only `**Section:**` (default `Origin`, `Notes`).
- **Compress step (optional, off):** send rules through `gmlcache` — the lossy
  lever for large rule sets, config-gated, prompt supplied by the user (the repo
  ships none). Requires the `gmlcache` CLI.
- **Authoring** (`gmlw workflow new`) runs the shipped **create-workflow**
  meta-workflow: a warm OARS interview that writes a new workflow. It's a normal
  (metered) session tagged `create:<name>`, hidden from `gmlw jobs`.
- The compiled context is written per-session to `jobs/<job>/<session>.context.md`
  — a durable, inspectable artifact; never into the user's launch directory.

Everything the client needs is *in* the injected context (self-contained); the
scaffolding is shipped English but the agent **works in the user's language**
(French welcome) and offers voice input where the client supports it.

## 11. Config — `~/.gmlw/config.toml`

Seeded on first run, fully commented. Sections: `[capture]` (persist raw
request/response, default off), `[client]` (default agent), `[callers]` (per-client
adapter override by import path), `[rules]` (strip-sections), `[compress]`
(enabled + prompt path + gmlcache backend, default off), `[workflow]`.

## 12. Package layout

```
src/generic_ml_wrapper/
├── application/
│   ├── domain/
│   │   ├── model/            job · session · workflow_context · usage
│   │   └── service/          session_naming · workflow_compiler · rule_cleaner
│   ├── port/
│   │   ├── inbound/          start_job · list_jobs · list_sessions · export_usage
│   │   │                     · render_statusline · new_workflow · list_workflows
│   │   └── outbound/         cli_caller · session_store · workflow_source
│   │                         · client_status · compressor · clock
│   ├── usecase/              one class per inbound port (ports only)
│   └── wiring/               build_application() — composition root + config
├── adapter/
│   ├── inbound/cli/          argparse controllers → inbound use-cases
│   └── outbound/
│       ├── caller/           claude_caller · loader (config-driven selection)
│       ├── store/            filesystem_store (jobs/, sessions.jsonl, db.jsonl)
│       ├── workflow/         packaged_workflow_source (+ seeding)
│       ├── compress/         gmlcache_compressor
│       └── clock/            system_clock
├── common/                   errors · config
└── resources/                base.md · create-workflow/ · rule.spec.md · profile/
```

## 13. Design invariants — do not re-litigate

1. **Public-clean by construction.** No personal data, no employer, no job
   prefixes, no internal hosts in the repo. Real content lives only in `~/.gmlw`.
2. **Dependencies point inward.** domain ← usecase ← ports; adapters depend on
   ports, never the reverse. Enforced by import-linter.
3. **The workflow is optional.** `gmlw start <job>` with no workflow is the pure
   wrapper; the workflow only enriches.
4. **The compiled context is self-contained** and lives per-session under the job
   folder — never in the user's working directory.
5. **Quit is the stop signal.** `start_client` blocks; teardown is `finally`.
