# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Semantic architecture gates: the rules the import contracts cannot express.

An import contract knows one thing — module X imports module Y. It cannot tell you that
a domain type opened a file, or that an exception the CLI catches was invented by an
adapter. These checks close that gap, and they are deliberately mechanical: a reviewer's
judgement is not a gate.

`test_the_core_reaches_nothing_outside_itself` — the domain and the ports describe *what*
the application does, never *how* it reaches the world. A filesystem, database, network,
subprocess or operating-system import there is a technology decision made in the one
place that must outlive every technology.

`test_no_adapter_defines_an_exception` — an exception that leaves an adapter is part of a
contract, and a contract belongs to the application. An adapter-owned type forces every
caller to know which adapter is installed, and it cannot carry a catalogue key, so it
reaches the user in English whatever language they configured. Adapters raise the
application's exceptions; they do not invent their own.

Serialisation (`json`) is not on the banned list: it turns a value into text, it reaches
nothing, and the domain legitimately knows the shape of its own persisted forms.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SOURCE = Path(__file__).resolve().parents[1] / "src" / "generic_ml_wrapper"

# Modules that reach the world. Importing one is how "the outside" enters a package.
_REACHES_OUT = frozenset(
    {
        "pathlib",
        "shutil",
        "os",
        "sqlite3",
        "subprocess",
        "socket",
        "ssl",
        "urllib",
        "http",
        "requests",
        "httpx",
        "tomllib",
        "tomlkit",
        "tempfile",
        "glob",
        "io",
        "signal",
        "importlib",
        "sys",
    }
)

_CORE = ("application/domain", "application/port")


def _modules(*roots: str) -> list[Path]:
    """Return every non-``__init__`` module under *roots*, failing loudly if empty."""
    found = [
        path
        for root in roots
        for path in sorted((_SOURCE / root).rglob("*.py"))
        if path.name != "__init__.py"
    ]
    if not found:
        message = f"no modules found under {roots} — the gate is pointing at nothing"
        raise AssertionError(message)
    return found


def _imported_roots(tree: ast.Module) -> set[str]:
    """The top-level package of every import that runs, ignoring typing-only ones."""
    roots: set[str] = set()
    for node in tree.body:  # module level only: a TYPE_CHECKING block is nested, so skipped
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_core_reaches_nothing_outside_itself() -> None:
    """The domain and the ports import nothing that touches the world."""
    offenders: list[str] = []
    for path in _modules(*_CORE):
        reached = sorted(
            _imported_roots(ast.parse(path.read_text(encoding="utf-8"))) & _REACHES_OUT
        )
        if reached:
            offenders.append(f"{path.relative_to(_SOURCE)}: {', '.join(reached)}")
    assert not offenders, "the core reaches outside itself:\n" + "\n".join(offenders)


def test_no_adapter_defines_an_exception() -> None:
    """No exception type is invented by an adapter; adapters raise the application's."""
    offenders: list[str] = []
    for path in _modules("adapter"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {base.id for base in node.bases if isinstance(base, ast.Name)}
            if bases & {"Exception", "BaseException", "ValueError", "KeyError", "RuntimeError"}:
                offenders.append(f"{path.relative_to(_SOURCE)}:{node.lineno} {node.name}")
    assert not offenders, "exceptions invented inside adapters:\n" + "\n".join(offenders)
