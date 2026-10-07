# Contributing

Thanks for your interest in `generic-ml-wrapper`. This is an open project under the
Apache-2.0 license and contributions are welcome — bug reports, documentation, tests,
and code alike.

By participating you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to help

- **Report a bug.** Open an issue describing what you ran and what happened. A minimal
  repro — the exact `gmlw` command, the client, and a failing test if you can — is gold.
- **Propose a feature.** Open an issue and check [`docs/DESIGN.md`](docs/DESIGN.md)
  first — the design invariants there are load-bearing, and your idea may already be
  covered or deliberately out of scope.
- **Improve the docs.** If something was unclear, a doc fix helps the next person.
- **Send code.** See below.

## Development setup

You need Python 3.11–3.14 and [`uv`](https://docs.astral.sh/uv/). The gates run through
[`nox`](https://nox.thea.codes/) with the `uv` backend, from the committed `uv.lock`.

```bash
git clone https://github.com/danielslobozian/generic-ml-wrapper.git
cd generic-ml-wrapper
uv sync --extra dev        # install the project + dev tools into .venv
# or: nox -s dev           # build the IDE .venv the same way
pre-commit install         # wire the local git hooks (optional but recommended)
```

The only runtime dependencies are the sibling
[`generic-ml-cache`](https://github.com/danielslobozian/generic-ml-cache) packages
(`-core`, `-adapters`, `-bootstrap`) — used by the context compressor. Dev tooling
(`pytest`, `ruff`, `pyright`, `import-linter`, `nox`, `pre-commit`) lives in the `dev`
extra / dependency group and is pinned by the lock.

## The gate

The gates are defined once in [`noxfile.py`](noxfile.py); CI is a thin caller of them,
so what runs locally is byte-for-byte what runs in CI.

```bash
nox                # the default gate: lint · imports · typecheck · tests (3.11–3.14)
nox -s green       # the whole gate in one env: lint · format · imports · pyright · coverage
nox -s tests       # just the test matrix
nox -s coverage    # tests with the 80% coverage floor
```

- **`lint`** — `ruff check` + `ruff format --check` (line length 100, strict rule set).
- **`typecheck`** — `pyright` in **strict** mode over both `src/` **and** `tests/`
  (pinned to `pyright==1.1.411`; the 3.11 floor is checked deliberately).
- **`imports`** — `lint-imports`: the three hexagon contracts in `.importlinter`.
- **`coverage`** — the suite with an 80% floor.

The suite is **offline and token-free**: no real client is launched, no network call is
made, and no model is invoked — external boundaries are faked, and `~/.gmlw` is
redirected to a temp dir for every test. CI runs it on Linux, macOS, and Windows across
Python 3.11–3.14; make sure it passes locally before opening a PR.

## Coding guidelines

- **Dependencies point inward.** `domain ← usecase ← ports`; adapters depend on ports,
  never the reverse. This is enforced by `import-linter`, not just convention — see the
  hexagon in [`docs/DESIGN.md`](docs/DESIGN.md).
- **The domain is pure.** Entities and domain services do no I/O and import no adapter.
  A new capability the app *needs* from the world is an outbound **port**, implemented by
  an adapter and wired in `application/wiring/composition.py`.
- **Strict typing.** `pyright` strict, zero errors. A `# type: ignore` is only for a
  provably-safe case that cannot be expressed in the type system, with a comment.
- **Public-clean by construction.** No personal data, employer, internal hosts, or work
  identities in the repo — real content lives only under `~/.gmlw`. Commit with a public
  identity (a GitHub no-reply address), not a private/work one.
- **Cross-platform.** Don't assume an OS; the CI matrix (incl. Windows) will tell on you.
- **Match the existing style.** `ruff` formats and lints; run `nox -s lint` (or
  `ruff check . && ruff format .`).

## Pull request process

1. Branch from `main` — `feature/… tech/… fix/… docs/… chore/… test/…`. Direct pushes to
   `main` are blocked by branch protection.
2. Make your change with tests that cover it, keeping `nox -s green` passing.
3. Update [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]`.
4. Open the pull request and describe the *why*, not just the *what*; link any related
   issue. CI must be green and the **no-AI-attribution** check must pass — commit messages
   and PR text must contain no AI/assistant attribution (a hard project rule, enforced
   both by a local hook and server-side).

See [`GOVERNANCE.md`](GOVERNANCE.md) for how decisions get made.

## Reporting security issues

Please do **not** open a public issue for a vulnerability. Follow
[`SECURITY.md`](SECURITY.md) instead.
