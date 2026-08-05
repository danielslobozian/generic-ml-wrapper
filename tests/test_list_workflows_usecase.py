# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListWorkflowsUseCase use case, driven by a fake source."""

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import Draft, DraftMarker
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.list_workflows import ListWorkflowsService


class FakeWorkflows(WorkflowSourcePort):
    def __init__(self, names: list[str]) -> None:
        self._names = names

    def seed(self) -> None:
        raise NotImplementedError

    def names(self) -> list[str]:
        return self._names

    def find(self, name: str) -> Workflow | None:
        raise NotImplementedError

    def catalog(self) -> list[Workflow]:
        return []

    def create(self, name: str) -> str:
        raise NotImplementedError

    def folder(self, name: str) -> str:
        raise NotImplementedError

    def drafts(self) -> list[Draft]:
        raise NotImplementedError

    def create_draft(self, key: str) -> str:
        raise NotImplementedError

    def read_draft_marker(self, draft_path: str) -> DraftMarker:
        raise NotImplementedError

    def deploy_draft(
        self, draft_path: str, name: str, label: str, description: str, created: str
    ) -> str:
        raise NotImplementedError

    def meta_guide(self) -> str:
        raise NotImplementedError

    def compile(self, mode: CompileMode, name: str | None = None, job: str | None = None) -> str:
        raise NotImplementedError


def test_lists_the_source_names() -> None:
    assert ListWorkflowsService(FakeWorkflows(["a", "b"])).execute() == ["a", "b"]


def test_no_workflows_yields_empty_list() -> None:
    assert ListWorkflowsService(FakeWorkflows([])).execute() == []
