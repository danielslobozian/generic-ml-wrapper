# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Task automation for generic-ml-wrapper.

``noxfile.py`` is the single source of truth for the project's gates -- lint,
format, type-check, tests, coverage. CI (``.github/workflows/``) is a *thin caller*
of these sessions, so the gate that runs locally is byte-for-byte the gate that
runs in CI. No local/CI drift.

Gate sessions build their own hermetic environments via the ``uv`` backend, synced
from the committed ``uv.lock`` (``--frozen``: the locked versions are installed
as-is, never re-resolved). The persistent root ``.venv`` is built only by
``nox -s dev`` and is the IDE's interpreter; the gate sessions never touch it.

Usage::

    nox                       # the default gates: lint, imports, typecheck, tests
    nox -s tests              # the suite across every supported interpreter
    nox -s green              # the whole local gate in one environment
    nox -s dev                # (re)build the IDE .venv at ./.venv
"""

from __future__ import annotations

import sys
from pathlib import Path

import nox

nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ["lint", "imports", "typecheck", "tests"]

PACKAGE = "generic_ml_wrapper"
PYTHON_VERSIONS: tuple[str, ...] = ("3.11", "3.12", "3.13", "3.14")
COVERAGE_FLOOR = 80


def _session_python(session: nox.Session) -> str:
    exe = "python.exe" if sys.platform == "win32" else "python"
    return str(Path(session.virtualenv.bin) / exe)


def _install(session: nox.Session) -> None:
    session.run_install(
        "uv",
        "sync",
        "--frozen",
        "--extra",
        "dev",
        "--python",
        _session_python(session),
        external=True,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session
def lint(session: nox.Session) -> None:
    _install(session)
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session
def imports(session: nox.Session) -> None:
    _install(session)
    session.run("lint-imports")


@nox.session
def typecheck(session: nox.Session) -> None:
    _install(session)
    session.run("pyright", "--pythonpath", _session_python(session))


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    _install(session)
    session.run("python", "-m", "pytest", *session.posargs)


@nox.session
def coverage(session: nox.Session) -> None:
    _install(session)
    session.run(
        "python",
        "-m",
        "pytest",
        f"--cov={PACKAGE}",
        "--cov-report=xml:coverage.xml",
        f"--cov-fail-under={COVERAGE_FLOOR}",
    )


@nox.session
def sonar(session: nox.Session) -> None:
    _install(session)
    session.run(
        "python",
        "-m",
        "pytest",
        f"--cov={PACKAGE}",
        "--cov-config=.coveragerc",
        "--cov-report=xml:coverage.xml",
    )


@nox.session
def green(session: nox.Session) -> None:
    _install(session)
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")
    session.run("lint-imports")
    session.run("pyright", "--pythonpath", _session_python(session))
    session.run(
        "python",
        "-m",
        "pytest",
        f"--cov={PACKAGE}",
        "--cov-report=xml:coverage.xml",
        f"--cov-fail-under={COVERAGE_FLOOR}",
    )


@nox.session(venv_backend="none")
def dev(session: nox.Session) -> None:
    session.run(
        "uv",
        "sync",
        "--frozen",
        "--extra",
        "dev",
        external=True,
        env={"UV_PROJECT_ENVIRONMENT": ".venv"},
    )
