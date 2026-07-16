# Configuration

gmlw reads a single optional config file at `~/.gmlw/config.toml`. On first run gmlw
seeds it fully commented — every real setting is off, so a freshly seeded file parses
to (at most) the `[client] default` chosen from the clients found on your `PATH`.

Every section is optional. Uncomment and edit only what you need. Delete the file
entirely to fall back to the built-in defaults.

Related guides: [WORKFLOWS.md](WORKFLOWS.md), [CLIENTS.md](CLIENTS.md),
[DESIGN.md](DESIGN.md), and the [security model](../SECURITY.md).

## Trusted-code boundary

The `[callers]` and `[[interceptors]]` sections name Python code that gmlw **loads and
runs with your permissions** on the next invocation — this file is a trusted-code
boundary. Point them only at code you wrote or trust. A configured-but-unloadable spec
fails **loudly** (it does not silently degrade); an absent one is a silent no-op. See
[SECURITY.md](../SECURITY.md).

## `[client]`

Selects the client to wrap when `--client` is not passed on the command line.

| Key | Meaning | Default |
| --- | --- | --- |
| `default` | Built-in client to wrap: `claude` \| `cursor` \| `codex` \| `vibe` | `claude` |

On first run gmlw bakes in whichever client(s) it found on your `PATH`; edit freely
afterward. See [CLIENTS.md](CLIENTS.md) for what each client can and cannot do.

```toml
[client]
default = "claude"
```

## `[callers]`

Per-client caller overrides, loaded at runtime in place of the built-in caller. The
key is the client name; the value is one of:

- an importable `"module:Class"` spec,
- an explicit `"/path/to/file.py:Class"` spec, or
- a **plugin id** — a folder `~/.gmlw/plugins/<id>/` containing a `plugin.toml`
  (see `gmlw plugins list`). The plugin id is the tidy way to drop in a private
  metering caller.

> **Trusted code.** A caller spec is imported and run as you. Only reference code you
> wrote or trust — see the [trusted-code boundary](#trusted-code-boundary) above and
> [SECURITY.md](../SECURITY.md).

Default: no overrides (each client uses its built-in caller).

```toml
[callers]
cursor = "cursor-mitm"                                # by plugin id
# cursor = "/path/to/my_cursor_caller.py:CursorCaller" # by explicit spec
```

## `[[interceptors]]`

Zero or more ordered `str -> str` transforms (`InterceptorPort`), each bound to a
target. Declare each as its own `[[interceptors]]` array-of-tables entry with a
`target` and a `spec`. A single target may have many interceptors; one spec may appear
under several targets.

| Key | Meaning |
| --- | --- |
| `target` | Where the transform is bound (see below) |
| `spec` | The `"module:Class"` / `"/path.py:Class"` to load |

**Compile-time targets** (context assembly, all clients): `profile` \| `rules` \|
`workflow` \| `context`.

**Wire targets** (metered clients only): `request` (outbound body) \| `response`
(captured reply, observe-only).

The built-in `MessageSizeLogger` logs each message's size — bind it to `request` and
`response` to trace sizes in and out.

Default: no interceptors.

> **Trusted code.** Interceptor specs are loaded and run as you — see the
> [trusted-code boundary](#trusted-code-boundary).

```toml
[[interceptors]]
target = "request"
spec = "generic_ml_wrapper.adapter.outbound.interceptor.size_logger:MessageSizeLogger"

[[interceptors]]
target = "response"
spec = "generic_ml_wrapper.adapter.outbound.interceptor.size_logger:MessageSizeLogger"
```

## `[startup.<mode>]`

On every run gmlw composes an operating context from a fixed set of sources.
`[startup]` decides, per mode, which sources are **active** and which are
**compressed**. There are three modes:

| Mode | Triggered by |
| --- | --- |
| `default` | a plain `gmlw start` |
| `workflow` | `gmlw start -w <name>` |
| `authoring` | `gmlw workflow new` |

**Sources:**

- `me.user` — `profile/me/*.md`
- `me.learned` — `profile/me/learned*`
- `company` — `profile/company/*.md`
- `rules` — `rules/*.md`
- `persona` — the selected persona plus the shared floor (see [`[companion]`](#companion))
- `base` / `steps` — a workflow run also composes its `base` and `steps`

Each source is configured as `{ activated = <bool>, compression = <bool> }`. The keys
nest by source group:

- `[startup.<mode>.context.me]` holds `user` and `learned`.
- `[startup.<mode>.context]` holds `company`, `rules`, and `persona`.
- `[startup.workflow.context]` also holds `base` and `steps` — in workflow and
  authoring modes these are **always active**, so only their `compression` is read
  (`activated` is ignored).

Omit all of this to get the built-in per-mode defaults. The default-mode defaults,
written out explicitly:

```toml
[startup.default.context.me]
user    = { activated = true,  compression = false }
learned = { activated = true,  compression = false }

[startup.default.context]
company = { activated = true,  compression = false }
rules   = { activated = false, compression = false }
persona = { activated = false, compression = false }
```

Every source defaults to `compression = false` — nothing is compressed unless you turn
it on *and* a prompt resolves (see [`[compress]`](#compress)). For a workflow run you
might, for example, opt to compress the longer `steps` while leaving `base` verbatim:

```toml
[startup.workflow.context]
base  = { compression = false }
steps = { compression = true }   # opt-in; the default is false
```

See [WORKFLOWS.md](WORKFLOWS.md) for how base and steps are compiled.

## `[companion]`

Selects the persona gmlw adopts. The persona voices a free local host greeting at
launch, and its tone is injected as the `persona` context source (only when that
source is `activated` in the relevant `[startup.<mode>]` block above). Off — invisible
— until set.

| Key | Meaning | Default |
| --- | --- | --- |
| `persona` | Built-in persona or a custom file name | unset (invisible) |
| `name` | The name the host greeting addresses you by | unset (falls back to the OS user) |

Built-in personas: `plain` \| `companion` \| `mentor` \| `butler` \| `terse`. List
them with `gmlw persona list`. Author your own by dropping a file into
`~/.gmlw/personas/`.

```toml
[companion]
persona = "companion"
```

## `[compress]` and `[compress.prompts]`

When a source has `compression = true`, gmlw compresses it through
[generic-ml-cache](DESIGN.md) (record/replay — the same source replays for free). The
`[compress]` block selects the client adapter, model, and effort used for that pass.

| Key | Meaning |
| --- | --- |
| `adapter` | Any generic-ml-cache client adapter (e.g. `cursor`) |
| `model` | Model id (e.g. `gpt-5.4`) |
| `effort` | Reasoning effort (e.g. `low`) |

The compression prompt is chosen by the source's **kind**:

| Kind | Covers |
| --- | --- |
| `human-touch` | `me.user` + `me.learned` |
| `technical` | workflow `base` + `steps` |
| `rules` | `rules` |

`company` and `persona` are always verbatim (never compressed). Under
`[compress.prompts]` you supply a prompt file per kind, or per **specific source key**
(the specific key wins over its kind).

> **The repo ships no prompts.** Every prompt is your own IP; until a prompt resolves
> for a source, that source stays verbatim even with `compression = true`. Compression
> is inert until you configure at least one prompt here.

```toml
[compress]
adapter = "cursor"
model = "gpt-5.4"
effort = "low"

[compress.prompts]
human-touch = "/path/to/human-touch.md"
technical = "/path/to/technical.md"
rules = "/path/to/rules.md"
"me.user" = "/path/to/just-me-user.md"   # override the kind for one source only
```

## `[transcript]`

Persists the request, response, and usage of each **metered** call under
`transcripts/<job>/<session>/` as a portable per-call trio (`call_NNN.in.json`,
`call_NNN.out.sse`, `call_NNN.usage.json`).

| Key | Meaning | Default |
| --- | --- | --- |
| `enabled` | Turn transcript capture on | `false` (OFF) |
| `root` | Directory to write under | `~/.gmlw/transcripts` |

> **Data at rest.** When enabled, transcripts contain your full prompts and the
> model's replies — a local data-at-rest surface you own; nothing manages retention.
> See [SECURITY.md](../SECURITY.md).

```toml
[transcript]
enabled = true
root = "/some/dir"   # optional; defaults to ~/.gmlw/transcripts
```

## `[logging]`

Controls diagnostic verbosity on stderr.

| Key | Meaning | Default |
| --- | --- | --- |
| `level` | `debug` \| `info` \| `warning` \| `error` | `warning` |

The environment variable `GMLW_LOG_LEVEL` sets the same value and is handy for a
one-off run without editing the file.

```toml
[logging]
level = "warning"
```
