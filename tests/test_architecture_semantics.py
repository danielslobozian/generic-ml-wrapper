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

`test_no_use_case_reaches_the_filesystem` and `test_no_use_case_holds_a_location` — a use
case orchestrates: it receives a request, calls ports in an order, and decides what that
order means. Reaching a file itself is a use case doing an adapter's work, and it takes two
checks to say so, because there are two ways in. One imports path handling and builds a
location; the other is handed one and keeps it. An import-based check alone misses the
second entirely — which is how the update check came to read and write its own cache file
while importing nothing at all.

A location arriving as a *request parameter* is data, not a reach: the user said "import
this file", and passing that through to a port is exactly the use case's job. What it may
not do is hold one as state.

`test_a_port_is_the_contract` — a port declares its own methods and extends nothing but
`ABC`. A port already *is* the abstraction the application owns and an adapter implements,
so a second interface behind it is a layer the pattern does not have. This one was written
after four ports were found extending an empty domain interface each: the domain may not
import a port, so an interface was put in the domain and the port made to extend it —
scaffolding built to get around a layering rule rather than to express a contract.

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

#: Where orchestration lives: the ring that drives ports and decides what their answers mean.
_USE_CASES = ("application/usecase",)

#: The filesystem, specifically. A use case reaches the world *through* ports, and the
#: modules here are the ones that would let it reach the disk without one. Narrower than
#: :data:`_REACHES_OUT` on purpose: this gate is the filesystem rule, and widening it to
#: every technology is a separate decision with a separate set of failures to fix.
_TOUCHES_FILES = frozenset({"pathlib", "shutil", "os", "tempfile", "glob"})

#: Type names that denote a filesystem location. A use case that declares one as a
#: constructor parameter or keeps one as state is holding storage configuration, whoever
#: handed it over -- and it does so without importing anything, so the import check above
#: cannot see it. Matched by name because the annotation is all there is to go on: these
#: modules are usually imported under ``TYPE_CHECKING``, where no import runs at all.
_LOCATION_TYPES = frozenset({"Path", "PurePath", "PurePosixPath", "PureWindowsPath"})

#: The delivery surface: everything a person or another program talks to us through.
_INBOUND = ("adapter/inbound",)

#: What an inbound adapter is allowed to name on our own side of the line. It drives the
#: application through its inbound ports, speaks the domain's types because those ports take
#: and return them, and asks the wiring to assemble what it drives. Nothing else -- and
#: notably not an outbound *port*: a rule that names only outbound adapters leaves the port
#: as an open door, which is exactly how the CLI came to import one.
_INBOUND_MAY_NAME = (
    # The distribution's own version constant. Not a ring, and not a reach: it is a fact
    # about the build, and rendering it is the delivery layer's job.
    "generic_ml_wrapper.__init__",
    "generic_ml_wrapper.adapter.inbound",
    "generic_ml_wrapper.application.port.inbound",
    "generic_ml_wrapper.application.domain",
    "generic_ml_wrapper.application.wiring",
)

#: Ways of *acquiring* state. An inbound adapter parses what it was handed, calls a port,
#: and renders the answer; anything here fetches something it was not given, and belongs
#: behind an outbound port or in the wiring.
#:
#: Three deliberate absences. ``sys`` is the command line's own channel -- its arguments and
#: its two output streams -- and banning it would ban the adapter from speaking at all.
#: ``json`` turns a value into text and back, reaching nothing, for the same reason the core
#: is allowed it. ``datetime`` is arithmetic on a value it was given; asking the clock what
#: time it is arrives through a port, and no inbound adapter does that today.
_ACQUIRES = frozenset(
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
        "signal",
        "importlib",
        "getpass",
        "platform",
        "sysconfig",
        "shlex",
    }
)


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


def test_no_use_case_reaches_the_filesystem() -> None:
    """A use case drives ports; it does not open, create, or walk anything itself."""
    offenders: list[str] = []
    for path in _modules(*_USE_CASES):
        reached = sorted(
            _imported_roots(ast.parse(path.read_text(encoding="utf-8"))) & _TOUCHES_FILES
        )
        if reached:
            offenders.append(f"{path.relative_to(_SOURCE)}: {', '.join(reached)}")
    assert not offenders, "a use case reached the filesystem instead of a port:\n" + "\n".join(
        offenders
    )


def _location_annotations(node: ast.AST) -> list[str]:
    """Every filesystem-location type named anywhere inside an annotation.

    Nested rather than top-level, because the hiding place is a wrapper:
    ``Callable[[], Path]`` is a held location with one more step to reach it, and a check
    that only read the outermost name would have called it a callable and moved on.
    """
    found: list[str] = []
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name) and inner.id in _LOCATION_TYPES:
            found.append(inner.id)
        elif isinstance(inner, ast.Attribute) and inner.attr in _LOCATION_TYPES:
            found.append(inner.attr)
    return found


def test_no_use_case_holds_a_location() -> None:
    """No use case is *given* a filesystem location to keep, either.

    Where something is stored is the adapter's to know. A use case handed a location has
    been handed storage configuration it cannot verify and has no use for -- and unlike
    the import above, it leaves no import behind to find it by.

    Only what the class is constructed with is checked. A location arriving as a request
    parameter is the user's input, not the use case's state.
    """
    offenders: list[str] = []
    for path in _modules(*_USE_CASES):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for klass in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            for member in klass.body:
                if not isinstance(member, ast.FunctionDef) or member.name != "__init__":
                    continue
                arguments = member.args
                declared = (
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                )
                named = [
                    (argument.arg, _location_annotations(argument.annotation))
                    for argument in declared
                    if argument.annotation is not None
                ]
                held = [f"{arg}: {', '.join(types)}" for arg, types in named if types]
                if held:
                    offenders.append(
                        f"{path.relative_to(_SOURCE)}: {klass.name}({'; '.join(held)})"
                    )
    assert not offenders, "a use case was handed a location to hold:\n" + "\n".join(offenders)


def _imported_modules(tree: ast.Module) -> set[str]:
    """Every module an import names in full, not just its top-level package.

    :func:`_imported_roots` collapses to the root, which cannot tell an inbound port from
    an outbound one -- and that distinction is the whole of the check below.
    """
    modules: set[str] = set()
    for node in tree.body:  # module level only, matching _imported_roots
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_inbound_adapters_name_only_what_they_drive() -> None:
    """An inbound adapter reaches the application through its inbound ports, or not at all.

    An allowlist rather than a denylist, because the failure this catches is a *new* kind
    of reach nobody thought to forbid. Listing what is permitted fails on the reach that
    has not been invented yet; listing what is forbidden never does.
    """
    offenders: list[str] = []
    for path in _modules(*_INBOUND):
        named = _imported_modules(ast.parse(path.read_text(encoding="utf-8")))
        strayed = sorted(
            module
            for module in named
            if module.startswith("generic_ml_wrapper")
            and module != "generic_ml_wrapper"  # see _INBOUND_MAY_NAME's first entry
            and not module.startswith(_INBOUND_MAY_NAME)
        )
        if strayed:
            offenders.append(f"{path.relative_to(_SOURCE)}: {', '.join(strayed)}")
    assert not offenders, "an inbound adapter named something it does not drive:\n" + "\n".join(
        offenders
    )


def test_inbound_adapters_acquire_nothing() -> None:
    """An inbound adapter parses its input, calls a port, and renders the answer.

    Reading a file, asking the operating system anything, installing a process handler or
    loading code by name are acquisitions: they fetch state the adapter was not handed.
    They belong behind an outbound port, or in the wiring that assembles the application.
    Parsing its own input and formatting its own output are not acquisitions -- that is the
    channel, which is what the adapter exists to speak.
    """
    offenders: list[str] = []
    for path in _modules(*_INBOUND):
        reached = sorted(_imported_roots(ast.parse(path.read_text(encoding="utf-8"))) & _ACQUIRES)
        if reached:
            offenders.append(f"{path.relative_to(_SOURCE)}: {', '.join(reached)}")
    assert not offenders, "an inbound adapter acquired what it was not handed:\n" + "\n".join(
        offenders
    )


#: Both port rings. A port is a contract wherever it faces.
_PORTS = ("application/port",)

#: The role suffixes that mark a class as a port rather than a transport type sharing the
#: package. An enum of outcomes declaring ``Enum`` as its base is not a port and not a
#: finding; ``ImportOutcomeUseCase`` would be.
_PORT_SUFFIXES = ("Port", "UseCase")


def test_a_port_is_the_contract() -> None:
    """A port declares its own methods and extends nothing but ``ABC``.

    The failure this exists to catch is not a naming slip, it is a whole invented layer:
    an interface declared somewhere the port may reach, and the port reduced to an empty
    subtype of it. That reads as tidy and costs the architecture its central claim —
    that the port *is* the boundary, owned by the application, implemented by an adapter.
    """
    offenders: list[str] = []
    for path in _modules(*_PORTS):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not node.name.endswith(_PORT_SUFFIXES):
                continue
            inherited = [ast.unparse(base) for base in node.bases if ast.unparse(base) != "ABC"]
            if inherited:
                offenders.append(
                    f"{path.relative_to(_SOURCE)}: {node.name} extends {', '.join(inherited)}"
                )
    assert not offenders, "a port is standing in front of another interface:\n" + "\n".join(
        offenders
    )


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
