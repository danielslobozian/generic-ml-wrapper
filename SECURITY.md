# Security Policy

`generic-ml-wrapper` is early, alpha software (`0.0.x`). It is published openly
and takes security seriously regardless of maturity. Thank you for helping keep
it and its users safe.

## Supported versions

During the alpha (`0.0.x`) series, only the **latest released version** receives
fixes. There are no long-term support branches or backports before `1.0.0`. If you
hit a security issue, please first confirm it still reproduces on the most recent
release or on `main`.

| Version        | Supported          |
| -------------- | ------------------ |
| latest `0.0.x` | :white_check_mark: |
| older `0.0.x`  | :x:                |

## Reporting a vulnerability

**Please do not open a public issue, pull request, or discussion for a security
vulnerability.** Public disclosure before a fix is available puts users at risk.

Instead, report it privately through GitHub:

1. Go to the **Security** tab of this repository.
2. Choose **Report a vulnerability** to open a private security advisory.
3. Describe the issue with enough detail to reproduce it — ideally the exact REPL
   exchange or library call involved, and what you observed versus what you
   expected.

This routes the report privately to the maintainers without needing an email
address, and lets us discuss and fix the issue confidentially before any public
disclosure. If GitHub's private reporting is somehow unavailable to you, you may
instead report the repository or content to GitHub directly via
https://docs.github.com/en/site-policy/github-terms/reporting-abuse.

## Security posture, plainly

`generic-ml-wrapper` is a local, single-user workspace that orchestrates work
and — through its sibling tool
[`generic-ml-cache`](https://github.com/danielslobozian/generic-ml-cache) —
launches external ML coding clients as subprocesses. A few properties are central
to its posture:

- **The engine itself executes no model call** and holds no client credentials;
  client execution and its security properties live in `generic-ml-cache` (see
  its SECURITY.md). Issues with client behavior, isolation, or cassettes belong
  there.
- **Secrets never transit a model call** (design invariant 7). Credential roles
  and their handling arrive with roadmap slice 0.0.9; until then the app holds no
  tokens at all. When they land: tokens live in a separate, chmod-600
  `credentials.toml` and never appear in events, logs, prompts, context, or
  cassettes. Reports that find a token leaking into any of those are exactly what
  we want to hear about.
- **Executable steps are the user's own code** (or code the user has explicitly
  adopted). The engine runs what the user's meta-code declares, with the user's
  permissions — it is not a sandbox and does not claim to be. Run only meta-code
  you trust.
- **The event log is local state**, one SQLite file under the user's own paths.
  Nothing leaves the machine; there is no telemetry.

Reports that amount to "my own workflow definition ran something harmful" are
generally **expected behavior**, not vulnerabilities. Reports about the engine
itself — a credential surfacing where the design says it never can, the app
writing outside its configured paths, location-blindness being violated — are in
scope and we want to hear about them.
