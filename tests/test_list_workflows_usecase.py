# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListWorkflows use case, driven by a fake source."""

from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.list_workflows import ListWorkflowsUseCase


class FakeWorkflows(WorkflowSourcePort):
    def __init__(self, names: list[str]) -> None:
        self._names = names

    def seed(self) -> None:
        raise NotImplementedError

    def names(self) -> list[str]:
        return self._names

    def exists(self, name: str) -> bool:
        raise NotImplementedError

    def create(self, name: str) -> str:
        raise NotImplementedError

    def compile(self, name: str) -> str:
        raise NotImplementedError


def test_lists_the_source_names() -> None:
    assert ListWorkflowsUseCase(FakeWorkflows(["a", "b"])).execute() == ["a", "b"]


def test_no_workflows_yields_empty_list() -> None:
    assert ListWorkflowsUseCase(FakeWorkflows([])).execute() == []
