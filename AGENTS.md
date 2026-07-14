# AGENTS.md — working rules for this repo

Rules an automated or human contributor must follow. Where a rule can be a
runnable gate it is one (see `.pre-commit-config.yaml` and `noxfile.py`); prose
here is the intent behind those gates.

## Process

- **Never commit directly to `main`.** Work on a branch named
  `feature/… tech/… fix/… release/… docs/… chore/… test/…`. Enforced by
  `tools/hooks/guard-branch.sh`.
- **`nox -s green` must pass before every commit** — ruff (lint + format), pyright
  strict, tests + coverage floor. The gate that runs locally is the one CI runs.
- **One use case per commit.** Each brings its domain model + port + adapter + its
  test, and leaves the gate green. The pipeline is never red.
- **No AI/assistant attribution** in commit messages or PRs. Enforced by
  `tools/hooks/check-commit-msg.sh`.

## Architecture

- The design is `docs/DESIGN.md`; do not re-derive it. Follow the hexagon:
  **dependencies point inward** (domain ← usecase ← ports; adapters depend on
  ports, never the reverse).
- **Public-clean by construction.** No personal data, employer, internal hosts, or
  private protocols in this repo. Real content lives only under `~/.gmlw`.
- **Strict typing.** pyright strict, zero errors. `# type: ignore` only for a
  provably-safe case that cannot be expressed in the type system, with a comment.
