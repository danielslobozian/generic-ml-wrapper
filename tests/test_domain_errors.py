# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Every :class:`DomainError` subclass renders through the catalogue, in every language.

0.9.1 closed a gap where a domain exception's message was a raw English literal,
interpolated verbatim into an otherwise-localised shell (``i18n.t("error.generic",
error=error)``). This guards the fix: each user-facing exception must render to real,
language-specific text — never the raw catalogue key, and never the same string in both
languages (the one case a same-string check would miss silently is a key whose template
happens to be identical in English and French; every key added here has a distinct
French wording precisely so this test can tell them apart).
"""

from __future__ import annotations

import pytest

from generic_ml_wrapper.adapter.outbound.config.settings_registry import InvalidSettingValueError
from generic_ml_wrapper.application.domain.model.archive_unreadable_error import (
    ArchiveUnreadableError,
)
from generic_ml_wrapper.application.domain.model.axis_exists_error import AxisExistsError
from generic_ml_wrapper.application.domain.model.axis_label_error import AxisLabelError
from generic_ml_wrapper.application.domain.model.domain_error import DomainError
from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.no_edit_to_resume_error import NoEditToResumeError
from generic_ml_wrapper.application.domain.model.no_such_draft_error import NoSuchDraftError
from generic_ml_wrapper.application.domain.model.resume_not_supported_error import (
    ResumeNotSupportedError,
)
from generic_ml_wrapper.application.domain.model.unknown_workflow_error import UnknownWorkflowError
from generic_ml_wrapper.application.domain.model.workflow_name_error import WorkflowNameError
from generic_ml_wrapper.application.domain.model.workflow_not_found_error import (
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.wiring import localization as i18n

_EN = i18n.load_localizer("en")
_FR = i18n.load_localizer("fr")

_CASES: list[DomainError] = [
    IdentifierError("error.identifier.job_id", value="bad id"),
    IdentifierError("error.identifier.workflow_name", value="Bad Name"),
    IdentifierError("error.identifier.env_var_name", value="1BAD"),
    WorkflowNameError("error.workflow.reserved_name", name="_common"),
    WorkflowNotFoundError("error.workflow.not_found", name="missing"),
    UnknownWorkflowError("error.workflow.unknown", name="missing"),
    ResumeNotSupportedError("error.workflow.resume_unsupported", client="codex"),
    ResumeNotSupportedError("error.workflow.resume_lost", session_id="JOB-1_003", client="codex"),
    NoEditToResumeError("error.workflow.no_edit_session", name="my-workflow"),
    NoEditToResumeError(
        "error.workflow.no_edit_resume_unsupported", client="codex", session_id="JOB-1_003"
    ),
    NoSuchDraftError("error.draft.not_found", key="abc123"),
    NoSuchDraftError("error.draft.no_session", key="abc123"),
    NoSuchDraftError("error.draft.resume_unsupported", client="codex", session_id="abc123"),
    NoSuchDraftError("error.draft.none_unfinished"),
    AxisLabelError("error.axis.label_invalid", label="???"),
    AxisExistsError("error.axis.exists.role", slug="qa"),
    AxisExistsError("error.axis.exists.environment", slug="work"),
    ArchiveUnreadableError("error.archive.not_found", archive="missing.zip"),
    ArchiveUnreadableError("error.archive.no_workflow", archive="bad.zip", steps="workflow.md"),
    InvalidSettingValueError("companion.persona", "loud", None),
    InvalidSettingValueError("logging.level", "shout", ("debug", "info", "warning", "error")),
]


@pytest.mark.parametrize("error", _CASES, ids=lambda error: error.catalogue_key)
def test_domain_error_renders_in_every_language(error: DomainError) -> None:
    rendered_en = error.localized(_EN)
    rendered_fr = error.localized(_FR)
    assert rendered_en != error.catalogue_key, "no English template for this key"
    assert rendered_fr != error.catalogue_key, "no French template for this key"
    assert rendered_en != rendered_fr, "French falls back to the English template"
