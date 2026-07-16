# Governance

This document describes how decisions get made in `generic-ml-wrapper`. It is
deliberately lightweight, matching the size of the project: this is early, alpha
software with a small maintainer team. As the project grows, this document can
grow with it (see [Changing this document](#changing-this-document)).

## Roles

**Users** are anyone who uses the tool. You do not need to contribute anything to
file issues, ask questions, or suggest changes. Your reports and use cases are a
primary input to the roadmap.

**Contributors** are anyone who proposes a change — a bug report, a documentation
fix, a test, or code. You do not need any special status to contribute; see
[`CONTRIBUTING.md`](CONTRIBUTING.md). Contributors retain copyright over their
work; by opening a pull request you agree to license your contribution under the
project's [Apache-2.0 license](LICENSE) (inbound contributions are accepted under
the same license the project is released under). There is no separate contributor
license agreement to sign.

**Maintainers** are the people with commit access who are responsible for
reviewing and merging changes, cutting releases, and stewarding the project's
direction. Maintainers also act as the project's Community Moderators under the
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). The current maintainers are listed in
the repository's metadata and visible from the commit history; while the project
is this young, it is maintainer-led by its original author.

## How decisions are made

Most decisions are made informally through discussion on issues and pull requests,
and most changes need only one maintainer's review and approval to merge. The
guiding aim is rough consensus: if a proposal is uncontroversial and fits the
project's scope, it lands; if a maintainer raises a concern, it is discussed until
resolved rather than forced through.

For larger or contested decisions — anything that changes the public CLI, the
ledger schema, the metering behaviour, or the project's scope — the maintainers
decide together, and the reasoning is recorded in the relevant issue or pull
request so it can be revisited later. Where maintainers disagree and cannot reach
consensus, the original author has the final say. This is a practical arrangement
for an alpha project, not a permanent power structure; it is expected to give way
to a more shared model as the maintainer team grows.

## Design stances that shape decisions

Some decisions are effectively already made, and proposals that cut against them
will usually be declined — not out of inflexibility, but because they are the
point of the project. These are documented in [`docs/DESIGN.md`](docs/DESIGN.md)
and [`ROADMAP.md`](ROADMAP.md); the load-bearing ones are:

- **gmlw wraps a client; it never reimplements one.** The judgment stays in the
  client. gmlw adds only the deterministic parts an *application* needs — session
  identity, launch, context compilation, persistence, metering. The four client
  adapters (claude / cursor / codex / vibe) are the core, and adding or improving
  client support is *in* scope, not declined.
- **Model calls sink to [`generic-ml-cache`](https://github.com/danielslobozian/generic-ml-cache).**
  The wrapper implements no record/replay cache or model-call layer of its own; the
  optional context compressor talks to that sibling. Proposals to reinvent it here
  will be declined.
- **The workflow is optional.** `gmlw start <job>` with no workflow is already the
  whole wrapper; the workflow is an enrichment, never the identity of the product.
- **Metering is not a toggle for a metered client.** A metered client always runs
  through the local relay; there is no plain, un-metered caller path.
- **Public-clean by construction.** No personal data, employer, job prefixes, or
  internal hosts in the repo — real content lives only under `~/.gmlw`, and
  `secret-audit.sh` gates every publish.
- **Dependencies point inward.** The hexagon (domain ← usecase ← ports; adapters
  depend on ports) is enforced by import-linter, not just convention.

The full set is `docs/DESIGN.md` §15 ("Design invariants — do not re-litigate").

A maintainer may still decide that a stance should change — but doing so is a
deliberate, recorded decision, not an incidental side effect of another change.

## Proposing a change

Anyone may propose a change by opening an issue. For features, check
[`ROADMAP.md`](ROADMAP.md) first — your idea may already be planned, or
deliberately out of scope. The roadmap is a living document: it reflects current
intent, not a binding contract, and the maintainers decide what lands in which
version. For how to actually submit work, see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Becoming a maintainer

There is no application form. Maintainers are invited by existing maintainers,
based on a track record of sustained, high-quality contributions and good judgment
about the project's scope and design stances. Being added as a maintainer is a
matter of trust earned over time, not a reward for a single large contribution.

## Changing this document

This governance document is itself subject to the process it describes. Proposed
changes go through a pull request and require maintainer agreement. As the project
matures past alpha and the contributor base grows, the expectation is that
governance moves away from "the original author decides ties" toward a more
explicitly shared model, and this document should be updated to match reality when
that happens.
