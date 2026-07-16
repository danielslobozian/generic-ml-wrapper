# Release checklist

Steps to cut a `generic-ml-wrapper` release. The point is to keep the version and the
docs in lockstep; the checks under [`tests/test_docs_consistency.py`](tests/test_docs_consistency.py)
enforce the parts that can be enforced.

## 1. Version & metadata (these must all agree)

- [ ] `pyproject.toml` — `version`
- [ ] `src/generic_ml_wrapper/__init__.py` — `__version__`
- [ ] `VERSION`
- [ ] `CHANGELOG.md` — move `[Unreleased]` items under a new `[x.y.z] - YYYY-MM-DD`, and update the link refs at the bottom
- [ ] `SECURITY.md` — the stated current version
- [ ] `ROADMAP.md` — move the shipped milestone into "Shipped"

`test_version_is_consistent_across_sources` fails if `__version__`, `VERSION`, and
`pyproject.toml` disagree.

## 2. Supported Python

- [ ] `pyproject.toml` classifiers, `noxfile.py` `PYTHON_VERSIONS`, the README badge/text, and `CONTRIBUTING.md` all state the same range

## 3. Gate & audit

- [ ] `nox -s green` passes (lint · format · imports · pyright · coverage)
- [ ] the full CI matrix is green (Python 3.11–3.14 × Linux / macOS / Windows)
- [ ] `./secret-audit.sh .` reports clean

## 4. Docs

- [ ] README capability matrix and the [`docs/`](docs/) guides reflect the release
- [ ] relative links resolve (`test_relative_markdown_links_resolve`) and the CLI reference covers every command (`test_cli_reference_documents_every_command`)

## 5. Tag & publish

- [ ] merge to `main`; tag `vX.Y.Z`
- [ ] create the GitHub Release — `release.yml` publishes to PyPI via Trusted Publishing (no token)
- [ ] confirm the new version on PyPI and that `uv tool install generic-ml-wrapper` pulls it
