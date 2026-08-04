# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The drift guard: no user-facing string may be a literal at its call site.

0.5.0 localised the app and the English literals crept back over the four releases
that followed, because nothing failed when they did. Key parity
(``test_catalogues_have_identical_key_sets``) only checks that the languages agree
with *each other* — it cannot see a string that never reached the catalogue at all.
This closes that half:

1. **No literal at a message call site.** ``print``, ``log.*``, argparse help/metavar,
   and Textual key bindings must resolve their text through ``i18n.t``.
2. **Every key used exists.** A ``t("...")`` call naming a key no catalogue defines
   renders as the raw key to the user — silent, and invisible to parity. The same check
   covers a :class:`DomainError` subclass raised with a
   literal catalogue key (0.9.1): the key is exactly as checkable as a ``t()`` call, since
   :meth:`DomainError.localized` is just ``loc.t(self.catalogue_key, **self.params)``.
3. **Every setting is described.** A new registry field must arrive with its
   ``setting.<key>`` entry, since its description is a key resolved at render time.

The scan is deliberately mechanical: it reads the AST rather than the intent, so it is
cheap to run and impossible to argue with. Where it is genuinely wrong, the exception is
listed in :data:`ALLOWED` **with its reason** rather than the rule being loosened.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

import generic_ml_wrapper
import generic_ml_wrapper.adapter.inbound.cli.app  # pyright: ignore[reportUnusedImport]
from generic_ml_wrapper.adapter.outbound.config import settings_registry
from generic_ml_wrapper.application.domain.model.domain_error import DomainError
from generic_ml_wrapper.application.wiring.localization import SUPPORTED_LANGUAGES

SRC = Path(generic_ml_wrapper.__file__).parent

#: Keyword arguments whose value is shown to a human.
MESSAGE_KEYWORDS = frozenset({"help", "description", "epilog", "metavar"})

#: Calls whose message keywords are user-facing.
PARSER_CALLS = frozenset({"add_argument", "add_parser", "add_subparsers", "ArgumentParser"})

#: Deliberate exceptions: ``(module suffix, text)`` -> why it is not translatable.
ALLOWED: dict[tuple[str, str], str] = {
    ("cli/app.py", "gmlw"): "the program name argparse prints in usage lines",
}


def _catalogue(lang: str) -> dict[str, str]:
    path = resources.files("generic_ml_wrapper").joinpath("resources", "i18n", f"{lang}.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


def _domain_error_subclass_names() -> frozenset[str]:
    """Every :class:`DomainError` subclass name reachable from the app's entry point.

    Importing the CLI app (above) pulls in every port/usecase module, so every subclass
    has registered itself with Python by the time this walks ``__subclasses__``.
    """

    def _all(cls: type) -> set[type]:
        direct = set(cls.__subclasses__())
        return direct | {grandchild for child in direct for grandchild in _all(child)}

    return frozenset(cls.__name__ for cls in _all(DomainError))


def _literals_outside_t(node: ast.AST) -> list[str]:
    """Return literal strings under *node* that are not arguments to a ``t(...)`` call."""
    found: list[str] = []

    def walk(current: ast.AST, inside_t: bool) -> None:
        if isinstance(current, ast.Call):
            func = current.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in {"t", "_key"}:
                inside_t = True
        # Punctuation, separators and layout scaffolding carry no meaning to translate.
        if (
            isinstance(current, ast.Constant)
            and isinstance(current.value, str)
            and not inside_t
            and any(char.isalpha() for char in current.value)
        ):
            found.append(current.value)
        for child in ast.iter_child_nodes(current):
            walk(child, inside_t)

    walk(node, False)
    return found


def _message_arguments(call: ast.Call) -> Sequence[ast.AST]:
    """Return the arguments of *call* that carry user-facing text, if any."""
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    if name == "print":
        return list(call.args)
    if name in {"debug", "info", "warning", "error"} and isinstance(func, ast.Attribute):
        base = func.value
        is_logger = getattr(base, "id", "") == "log" or getattr(base, "attr", "") == "log"
        return call.args[:1] if is_logger else []
    if name in PARSER_CALLS:
        return [kw.value for kw in call.keywords if kw.arg in MESSAGE_KEYWORDS]
    if name == "Binding":
        # Textual's third positional argument is the label shown in the footer. Bindings
        # are built by the `_key` helper so the label comes from the catalogue.
        return list(call.args[2:3])
    return []


def _violations() -> list[str]:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for argument in _message_arguments(node):
                for text in _literals_outside_t(argument):
                    if any(
                        _rel(path).endswith(suffix) and text == allowed
                        for suffix, allowed in ALLOWED
                    ):
                        continue
                    found.append(f"{_rel(path)}:{node.lineno}  {text!r}")
    return found


def test_no_user_facing_literal_at_a_message_call_site() -> None:
    violations = _violations()
    assert not violations, (
        "user-facing text must be a catalogue key, not a literal — add it to "
        "resources/i18n/{en,fr}.json and render it with i18n.t():\n  " + "\n  ".join(violations)
    )


def test_every_key_used_in_the_code_exists_in_the_catalogue() -> None:
    # A key that never reached the catalogue renders as the raw key to the user, and key
    # parity cannot see it: both languages are equally missing it. A DomainError subclass
    # raised with a literal key is the same failure mode, so it is checked the same way.
    english = _catalogue("en")
    domain_errors = _domain_error_subclass_names()
    unknown: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if (name != "t" and name not in domain_errors) or not node.args:
                continue
            first = node.args[0]
            # Only literal keys are checkable; a computed key is checked by its callers.
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value not in english
            ):
                unknown.append(f"{_rel(path)}:{node.lineno}  {first.value!r}")
    assert not unknown, (
        "i18n.t()/DomainError raised with keys absent from en.json:\n  " + "\n  ".join(unknown)
    )


def test_every_setting_has_a_localised_description() -> None:
    # A registry field's `description` holds a catalogue key, so a new setting that
    # forgets its entry would render its own key as the description in `config list`.
    for lang in SUPPORTED_LANGUAGES:
        catalogue = _catalogue(lang)
        missing = [
            f"setting.{row.key}"
            for row in settings_registry.registry_rows()
            if f"setting.{row.key}" not in catalogue
        ]
        assert not missing, f"{lang}.json is missing setting descriptions: {missing}"
