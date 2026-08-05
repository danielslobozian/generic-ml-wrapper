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

`test_every_port_and_its_implementation_is_named_for_its_role` — the four roles in the
hexagon are visible in the class name or they are not visible at all. An inbound port is
the ``UseCase`` interface a driver calls; the class implementing it is the ``Service``. An
outbound port is the ``Port`` the application depends on; the class implementing it is the
``Adapter``. This is the convention the wider ports-and-adapters practice settled on, and
the sibling cache project already follows it.

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
from collections.abc import Callable
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
    """Whether one class is what the file is named after, ignoring its role suffix.

    The roles are ``Port`` and ``Adapter`` on the outbound side, and ``UseCase`` and
    ``Service`` on the inbound one -- the interface a driver calls, and the class that
    implements it.
    """
    for node in classes:
        snake = _snake(node.name)
        stripped = snake
        for suffix in ("_port", "_adapter", "_use_case", "_service"):
            stripped = stripped.removesuffix(suffix)
        if stem in (snake, stripped):
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


def _abstract(node: ast.ClassDef) -> bool:
    """Whether a class declares itself an interface rather than an implementation."""
    return any(ast.unparse(base) == "ABC" for base in node.bases)


def _implements_a_port(node: ast.ClassDef, siblings: dict[str, list[str]]) -> bool:
    """Whether a class implements an outbound port, directly or through a local base."""
    bases = [ast.unparse(base) for base in node.bases]
    return any(base.endswith("Port") for base in bases) or any(
        any(inherited.endswith("Port") for inherited in siblings.get(base, ())) for base in bases
    )


def _is_interface(node: ast.ClassDef, _siblings: dict[str, list[str]]) -> bool:
    """Whether the class declares itself an interface rather than an implementation."""
    return _abstract(node)


def _implements_a_use_case(node: ast.ClassDef, _siblings: dict[str, list[str]]) -> bool:
    """Whether the class implements an inbound port."""
    return any(ast.unparse(base).endswith("UseCase") for base in node.bases)


def _misnamed(
    ring: str, wanted: str, qualifies: Callable[[ast.ClassDef, dict[str, list[str]]], bool]
) -> list[str]:
    """Every class in ``ring`` that ``qualifies`` for a role but does not carry its suffix."""
    offenders: list[str] = []
    for path in sorted((_SOURCE / ring).rglob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        siblings = {
            node.name: [ast.unparse(base) for base in node.bases]
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }
        offenders += [
            f"{path.relative_to(_SOURCE)}: {node.name} is not a {wanted}"
            for node in _public_classes(tree)
            if qualifies(node, siblings) and not node.name.endswith(wanted.lstrip("*"))
        ]
    return offenders


def test_every_port_and_its_implementation_is_named_for_its_role() -> None:
    """The four roles are legible from the class name alone.

    Without this the direction of a dependency can only be learned by opening the file and
    reading what it inherits -- which is exactly the knowledge a naming convention exists
    to spare a reader. The check is on the *role*, never on the concept: whether a port is
    about workflows or sessions is nobody's business but the author's.
    """
    offenders = (
        _misnamed("application/port/inbound", "*UseCase", _is_interface)
        + _misnamed("application/port/outbound", "*Port", _is_interface)
        + _misnamed("application/usecase", "*Service", _implements_a_use_case)
        + _misnamed("adapter/outbound", "*Adapter", _implements_a_port)
    )
    assert not offenders, "a port or its implementation is not named for its role:\n" + "\n".join(
        offenders
    )


def test_a_port_declares_one_thing(  # the tightened form of one-concept-per-module
) -> None:
    """A port file holds the port, and nothing else.

    The looser gate above lets a module hold several types when one of them names the
    file — which was written for the ports, and which the ports then used to keep their
    commands, results and errors beside them. A transport type is a model: it has its own
    name, so it gets its own file, and a reader looking for it does not have to know which
    port happened to need it first.

    Errors are not here at all. They live in the domain with the rest of them, so there is
    one place to look rather than two.
    """
    offenders: list[str] = []
    for ring in ("application/port/inbound", "application/port/outbound"):
        for path in sorted((_SOURCE / ring).rglob("*.py")):
            if path.name == "__init__.py":
                continue
            classes = _public_classes(ast.parse(path.read_text(encoding="utf-8")))
            if len(classes) > 1:
                offenders.append(
                    f"{path.relative_to(_SOURCE)}: {', '.join(c.name for c in classes)}"
                )
    assert not offenders, "a port file holds more than one type:\n" + "\n".join(offenders)


def test_no_error_is_declared_in_a_port() -> None:
    """Exceptions belong to the domain, wherever they are raised.

    Two homes for one kind of thing is how a reader ends up grepping. The domain already
    holds every other error the application can raise, each carrying the catalogue key
    that lets it reach a person in their own language.
    """
    offenders: list[str] = []
    for ring in ("application/port/inbound", "application/port/outbound"):
        for path in sorted((_SOURCE / ring).rglob("*.py")):
            if path.name == "__init__.py":
                continue
            for node in _public_classes(ast.parse(path.read_text(encoding="utf-8"))):
                if any("Error" in ast.unparse(base) for base in node.bases):
                    offenders.append(f"{path.relative_to(_SOURCE)}: {node.name}")
    assert not offenders, "an exception declared in a port rather than the domain:\n" + "\n".join(
        offenders
    )
