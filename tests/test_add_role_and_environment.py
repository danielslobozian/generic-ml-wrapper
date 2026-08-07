# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for AddRole / AddEnvironment and their set-default siblings (fake repositories)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from generic_ml_wrapper.application.domain.model.environment import Environment
from generic_ml_wrapper.application.domain.model.environment_code_already_exists_error import (
    EnvironmentCodeAlreadyExistsError,
)
from generic_ml_wrapper.application.domain.model.role import Role
from generic_ml_wrapper.application.domain.model.role_code_already_exists_error import (
    RoleCodeAlreadyExistsError,
)
from generic_ml_wrapper.application.domain.model.uncodable_role_label_error import (
    UncodableRoleLabelError,
)
from generic_ml_wrapper.application.port.inbound.add_environment_command import (
    AddEnvironmentCommand,
)
from generic_ml_wrapper.application.port.inbound.add_role_command import AddRoleCommand
from generic_ml_wrapper.application.port.inbound.set_default_environment_command import (
    SetDefaultEnvironmentCommand,
)
from generic_ml_wrapper.application.port.inbound.set_default_role_command import (
    SetDefaultRoleCommand,
)
from generic_ml_wrapper.application.port.outbound.config_writer import ConfigWriterPort
from generic_ml_wrapper.application.port.outbound.environment_repository import (
    EnvironmentRepositoryPort,
)
from generic_ml_wrapper.application.port.outbound.role_repository import RoleRepositoryPort
from generic_ml_wrapper.application.usecase.add_environment import AddEnvironmentService
from generic_ml_wrapper.application.usecase.add_role import AddRoleService
from generic_ml_wrapper.application.usecase.set_default_environment import (
    SetDefaultEnvironmentService,
)
from generic_ml_wrapper.application.usecase.set_default_role import SetDefaultRoleService


class _FakeRoles(RoleRepositoryPort):
    def __init__(self, *codes: str) -> None:
        self.saved: list[Role] = []
        self._codes = set(codes)

    def find_all(self) -> tuple[Role, ...]:
        return tuple(Role(code, code) for code in sorted(self._codes))

    def exists(self, role: Role) -> bool:
        return role.code in self._codes

    def save(self, role: Role) -> None:
        self.saved.append(role)
        self._codes.add(role.code)


class _FakeEnvironments(EnvironmentRepositoryPort):
    def __init__(self, *codes: str) -> None:
        self.saved: list[Environment] = []
        self._codes = set(codes)

    def find_all(self) -> tuple[Environment, ...]:
        return tuple(Environment(code, code) for code in sorted(self._codes))

    def exists(self, environment: Environment) -> bool:
        return environment.code in self._codes

    def save(self, environment: Environment) -> None:
        self.saved.append(environment)
        self._codes.add(environment.code)


class _FakeWriter(ConfigWriterPort):
    def __init__(self) -> None:
        self.merges: list[list[tuple[str, str, object | None]]] = []

    def merge(self, entries: Sequence[tuple[str, str, object | None]]) -> tuple[str, ...]:
        self.merges.append(list(entries))
        return ()


def test_adding_a_role_derives_its_code_from_the_label() -> None:
    roles = _FakeRoles()
    result = AddRoleService(roles).execute(
        AddRoleCommand(label="Code Reviewer", description="reads the diff")
    )
    assert result.role.code == "code-reviewer"
    assert result.role.label == "Code Reviewer"
    assert result.role.description == "reads the diff"
    assert roles.saved == [result.role]


def test_adding_an_environment_derives_its_code_from_the_label() -> None:
    environments = _FakeEnvironments()
    result = AddEnvironmentService(environments).execute(
        AddEnvironmentCommand(label="Client Project", description="the gig")
    )
    assert result.environment.code == "client-project"
    assert environments.saved == [result.environment]


def test_a_label_with_nothing_codeable_is_refused() -> None:
    with pytest.raises(UncodableRoleLabelError):
        AddRoleService(_FakeRoles()).execute(AddRoleCommand(label="  !!!  "))


def test_a_taken_role_code_is_refused_and_nothing_is_stored() -> None:
    roles = _FakeRoles("work")
    with pytest.raises(RoleCodeAlreadyExistsError):
        AddRoleService(roles).execute(AddRoleCommand(label="Work"))
    assert roles.saved == []  # never clobbered


def test_a_taken_environment_code_is_refused_and_nothing_is_stored() -> None:
    environments = _FakeEnvironments("work")
    with pytest.raises(EnvironmentCodeAlreadyExistsError):
        AddEnvironmentService(environments).execute(AddEnvironmentCommand(label="Work"))
    assert environments.saved == []


def test_two_labels_reducing_to_the_same_code_collide() -> None:
    roles = _FakeRoles()
    AddRoleService(roles).execute(AddRoleCommand(label="Code Reviewer"))
    with pytest.raises(RoleCodeAlreadyExistsError):
        AddRoleService(roles).execute(AddRoleCommand(label="code reviewer!"))


def test_setting_the_default_role_writes_the_profile_key() -> None:
    writer = _FakeWriter()
    SetDefaultRoleService(writer).execute(SetDefaultRoleCommand(code="code-reviewer"))
    assert writer.merges == [[("profile", "default_role", "code-reviewer")]]


def test_setting_the_default_environment_writes_the_profile_key() -> None:
    writer = _FakeWriter()
    SetDefaultEnvironmentService(writer).execute(SetDefaultEnvironmentCommand(code="work"))
    assert writer.merges == [[("profile", "default_environment", "work")]]
