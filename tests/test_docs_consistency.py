# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Guardrails against documentation drift.

Three checks that keep the docs honest as the code moves:
- the declared version agrees across ``__init__``, ``VERSION``, and ``pyproject.toml``;
- every relative Markdown link across the repo resolves to a real file;
- ``docs/CLI.md`` documents every command the CLI actually exposes (``_COMMANDS``).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.cli.app import _COMMANDS

_ROOT = Path(__file__).resolve().parent.parent
_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def test_version_is_consistent_across_sources() -> None:
    version_file = (_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = str(pyproject["project"]["version"])
    assert __version__ == version_file == project_version, (
        f"version mismatch: __version__={__version__}, VERSION={version_file}, "
        f"pyproject={project_version}"
    )


def _markdown_files() -> list[Path]:
    return sorted([*_ROOT.glob("*.md"), *(_ROOT / "docs").glob("*.md")])


def test_relative_markdown_links_resolve() -> None:
    broken: list[str] = []
    for md in _markdown_files():
        for match in _LINK.finditer(md.read_text(encoding="utf-8")):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            if not (md.parent / path_part).resolve().exists():
                broken.append(f"{md.relative_to(_ROOT)} -> {target}")
    assert not broken, "broken relative markdown links:\n" + "\n".join(broken)


def test_cli_reference_documents_every_command() -> None:
    cli_doc = (_ROOT / "docs" / "CLI.md").read_text(encoding="utf-8")
    missing = [cmd for cmd in sorted(_COMMANDS) if f"gmlw {cmd}" not in cli_doc]
    assert not missing, f"docs/CLI.md does not document: {missing}"


# Harness tool-call markers that must never leak into a doc (a generation slip once
# shipped `</content></invoke>`). Deliberately specific — real docs use HTML like <img>.
# The namespaced marker is assembled at runtime so this file does not itself contain it.
_FORBIDDEN_TAGS = ("</content>", "<invoke", "</invoke>", "<function_calls", "<" + "antml:")


def test_docs_have_no_stray_tool_tags() -> None:
    offenders: list[str] = []
    for md in _markdown_files():
        text = md.read_text(encoding="utf-8")
        offenders += [f"{md.relative_to(_ROOT)}: {tag}" for tag in _FORBIDDEN_TAGS if tag in text]
    assert not offenders, "stray tool-artifact tags in docs:\n" + "\n".join(offenders)
