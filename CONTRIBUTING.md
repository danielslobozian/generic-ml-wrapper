# Contributing

Thanks for your interest in `generic-ml-wrapper`. This is an open project under
the Apache-2.0 license and contributions are welcome — bug reports, documentation,
tests, and code alike. It is early (alpha), so the most valuable contributions
right now are the ones that harden the core and keep the slices small.

By participating you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to help

- **Report a bug.** Open an issue with the bug-report template. A failing test or
  the exact REPL exchange that reproduces the problem is gold.
- **Propose a feature.** Open an issue with the feature-request template. Check
  [`docs/ROADMAP.md`](docs/ROADMAP.md) and [`docs/DESIGN.md`](docs/DESIGN.md)
  first — your idea may already be planned, scheduled for a later slice, or
  deliberately out of scope (the design invariants in `DESIGN.md` §16 are
  load-bearing).
- **Improve the docs.** If something was unclear, a doc fix helps the next person.
- **Send code.** See below.

## Development setup

You need Python 3.11 or newer.

```bash
git clone https://github.com/danielslobozian/generic-ml-wrapper.git
cd generic-ml-wrapper
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running the tests

```bash
python -m pytest
```

The suite is **offline and token-free**: no real ML client, no `gmlcache`
install, and no model call is ever needed — external boundaries are covered by
frozen fixtures and the scripted-input REPL harness. Continuous integration runs
it on Linux, macOS, and Windows across Python 3.11–3.13; please make sure it
passes locally before opening a pull request.

For coverage:

```bash
python -m pytest --cov=generic_ml_wrapper
```

## Coding guidelines

- **Respect the wall.** `core` is a surface-agnostic library: it must not import
  the `repl` package, `prompt_toolkit`, `rich`, or anything terminal-shaped. The
  rule is enforced by `tests/test_wall.py`; extend the surface, not the core's
  imports.
- **The engine calls no model and knows no client.** Anything about *calling
  models* — usage extraction, client quirks, new clients — belongs in
  [`generic-ml-cache`](https://github.com/danielslobozian/generic-ml-cache), not
  here. If a client quirk surfaces in this repo, it is a `gmlcache` issue by
  definition.
- **The verb set is closed.** Adding a verb is one row in the REPL's table, and a
  deliberate design decision — natural-language surfaces route onto the verbs,
  never around them.
- **Events are decisions; payloads hold pointers, never blobs.** Changes near the
  event store must preserve the append-only, pointer-only discipline.
- **Dependencies are a high bar.** The runtime carries a small, deliberate set
  (`prompt_toolkit`, `rich`, `pyyaml`, `platformdirs`); dev-only tools belong in
  the `dev` extra.
- **Cross-platform.** Do not assume a particular OS; the CI matrix will tell on
  you.
- **Match the existing style.** Code is formatted and linted with `ruff`.

```bash
pip install ruff
ruff check .
ruff format .
```

## Pull request process

1. Fork and branch from `main`.
2. Make your change with tests that cover it.
3. Ensure `python -m pytest` passes and `ruff check .` plus
   `ruff format --check .` are clean.
4. Update [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]`.
5. Open the pull request using the template and describe the *why*, not just the
   *what*. Link any related issue.

Maintainers review with a bias toward keeping slices small and the core honest.
See [`GOVERNANCE.md`](GOVERNANCE.md) for how decisions get made.

## Reporting security issues

Please do **not** open a public issue for a vulnerability. Follow
[`SECURITY.md`](SECURITY.md) instead.
