# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Structural gates on the rings where types live: the domain and the ports.

The import contracts police *direction* — who may depend on whom. They say nothing
about the shape of a module, so a ring can stay contract-green while its modules decay
into bags of loose functions and unrelated types sharing a file. These two checks close
that gap, and they are deliberately mechanical: a reviewer's judgement is not a gate.

`test_no_loose_functions` — in the domain and the ports, behaviour belongs to a named
type. A public module-level function is behaviour with no owner: it cannot be
substituted, it accretes parameters instead of state, and it is invisible to every
naming convention the project has.

`test_one_concept_per_module` — a module defines one thing. It may define exactly one
public class, or a family whose members all derive from a base declared in the same
module (an error hierarchy), or several types when one of them is what the file is
named after. What it may not do is hold several unrelated types, because then the
file's location and name stop telling the reader what is inside it.

Naming is *not* checked here: whether the class matching a file is called `AxisCatalog`
or `AxisCatalogPort` is the naming-convention slot's business, not this one.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_RINGS = ("application/domain", "application/port")
_SOURCE = Path(__file__).resolve().parents[1] / "src" / "generic_ml_wrapper"


def _modules() -> list[Path]:
    """Return every non-``__init__`` module in the rings these gates police."""
    found = [path for ring in _RINGS for path in sorted((_SOURCE / ring).rglob("*.py"))]
    modules = [path for path in found if path.name != "__init__.py"]
    if not modules:  # a moved or renamed ring must fail loudly, not pass vacuously
        message = f"no modules found under {_RINGS} — the gate is pointing at nothing"
        raise AssertionError(message)
    return modules


def _snake(name: str) -> str:
    """Return ``AxisCatalogPort`` as ``axis_catalog_port``."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _public_classes(tree: ast.Module) -> list[ast.ClassDef]:
    return [node for node in tree.body if isinstance(node, ast.ClassDef)]


def _is_family(classes: list[ast.ClassDef]) -> bool:
    """Whether every class derives from another class declared in the same module."""
    declared = {node.name for node in classes}
    roots = [
        node
        for node in classes
        if not any(isinstance(base, ast.Name) and base.id in declared for base in node.bases)
    ]
    return len(roots) == 1


def _names_the_module(classes: list[ast.ClassDef], stem: str) -> bool:
    """Whether one class is what the file is named after, ignoring a role suffix."""
    for node in classes:
        snake = _snake(node.name)
        if snake == stem or snake.removesuffix("_port").removesuffix("_adapter") == stem:
            return True
    return False


def test_no_loose_functions() -> None:
    """The domain and the ports carry behaviour on named types, never module-level."""
    offenders: list[str] = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        loose = [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and not node.name.startswith("_")
        ]
        if loose:
            offenders.append(f"{path.relative_to(_SOURCE)}: {', '.join(loose)}")
    assert not offenders, "public module-level functions in a ring that owns types:\n" + "\n".join(
        offenders
    )


def test_one_concept_per_module() -> None:
    """Each module in the domain and the ports defines one thing, not a grab bag."""
    offenders: list[str] = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = _public_classes(tree)
        if len(classes) <= 1:
            continue
        if _is_family(classes) or _names_the_module(classes, path.stem):
            continue
        offenders.append(f"{path.relative_to(_SOURCE)}: {', '.join(c.name for c in classes)}")
    assert not offenders, "unrelated types sharing a module:\n" + "\n".join(offenders)
