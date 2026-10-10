# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""gmlw has no notion of workflow: attachments replaced it, and the word must not creep back.

Checked by searching, not by reading. Every text file under ``src``, ``tests`` and
``docs`` is searched, case-insensitively, and each hit must fall under one of the
exceptions below, each with its reason. A new one is added here, with its reason, rather
than the search being loosened.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SEARCHED = ("src", "tests", "docs")
_SUFFIXES = frozenset({".py", ".md", ".json", ".toml", ".yaml", ".tape", ".sh", ".txt"})
_WORD = re.compile("workflow", re.IGNORECASE)

# Names that contain the word without being the notion: the attachment gmlw ships, the
# sibling project, GitHub Actions links.
_NAMES = ("workflow-creator", "workflow_creator", "generic-ml-workflow", "actions/workflow")

# Whole files where the word is the subject.
_FILES = (
    # The attachment that writes workflows: its content is about them.
    "src/generic_ml_wrapper/resources/attachments/workflow-creator/",
    # The ledger's history: old databases replay its past migrations.
    "src/generic_ml_wrapper/adapter/outbound/store/ledger.py",
    "tests/test_ledger_migration.py",
    # The one-time legacy import of an older gmlw's workflows.
    "src/generic_ml_wrapper/adapter/outbound/attachment/filesystem_legacy_workflows.py",
    "src/generic_ml_wrapper/application/port/outbound/legacy_workflows.py",
    "src/generic_ml_wrapper/application/usecase/migrate_legacy_workflows.py",
    "tests/test_migrate_legacy_workflows.py",
    # The format's page explains what a workflow is to it, and what upgrading does.
    "docs/ATTACHMENTS.md",
    # This file.
    "tests/test_vocabulary.py",
)

# A line that names the legacy import, or the attachment that writes workflows, may say it.
_LINE = re.compile(r"legacy|workflow-creator", re.IGNORECASE)


def _searched_files() -> list[Path]:
    found: list[Path] = []
    for top in _SEARCHED:
        for path in sorted((_ROOT / top).rglob("*")):
            if path.is_file() and path.suffix in _SUFFIXES and "__pycache__" not in path.parts:
                found.append(path)
    return found


def _offences(path: Path, root: Path = _ROOT) -> list[str]:
    relative = path.relative_to(root).as_posix()
    if any(relative.startswith(allowed) for allowed in _FILES):
        return []
    offences: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if _LINE.search(line):
            continue
        stripped = line
        for name in _NAMES:
            stripped = re.sub(re.escape(name), "", stripped, flags=re.IGNORECASE)
        if _WORD.search(stripped):
            offences.append(f"{relative}:{number}: {line.strip()}")
    return offences


def test_the_word_workflow_stays_out_of_gmlw() -> None:
    offences = [offence for path in _searched_files() for offence in _offences(path)]
    assert not offences, "'workflow' outside its exceptions:\n" + "\n".join(offences)


def test_the_search_sees_the_files_it_guards() -> None:
    # A search that finds nothing because it looks nowhere would pass forever.
    relative = {path.relative_to(_ROOT).as_posix() for path in _searched_files()}
    assert "src/generic_ml_wrapper/adapter/inbound/cli/app.py" in relative
    assert "src/generic_ml_wrapper/resources/i18n/en.json" in relative
    assert "docs/CLI.md" in relative
    assert "docs/tapes/tui.tape" in relative


def test_the_search_catches_a_mention(tmp_path: Path) -> None:
    sample = tmp_path / "docs" / "probe.md"
    sample.parent.mkdir()
    sample.write_text("run the Workflow\nthe workflow-creator\nlegacy workflows\n")

    assert _offences(sample, tmp_path) == ["docs/probe.md:1: run the Workflow"]
