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

from generic_ml_wrapper.application.domain.model.attachment import (
    AttachmentError,
    AttachmentVersionError,
)
from generic_ml_wrapper.application.domain.model.identifiers import IdentifierError
from generic_ml_wrapper.application.port.inbound.create_axis import (
    AxisExistsError,
    AxisLabelError,
)
from generic_ml_wrapper.application.port.inbound.start_job import ResumeNotSupportedError
from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.errors import DomainError
from generic_ml_wrapper.common.settings_registry import InvalidSettingValueError

_EN = i18n.load_localizer("en")
_FR = i18n.load_localizer("fr")

_CASES: list[DomainError] = [
    IdentifierError("error.identifier.job_id", value="bad id"),
    IdentifierError("error.identifier.env_var_name", value="1BAD"),
    IdentifierError("error.identifier.attachment_name", value="Bad Name"),
    AttachmentVersionError("error.attachment.version", value="2.1"),
    AttachmentError("error.attachment.archive_unreadable", archive="x.zip"),
    AttachmentError("error.attachment.archive_unsafe", archive="x.zip", entry="../x"),
    AttachmentError("error.attachment.manifest_missing", archive="x.zip", manifest="manifest.yaml"),
    AttachmentError("error.attachment.manifest_unreadable", archive="x.zip"),
    AttachmentError("error.attachment.manifest_line", line=2),
    AttachmentError("error.attachment.manifest_unknown_key", key="author"),
    AttachmentError("error.attachment.manifest_duplicate_key", key="name"),
    AttachmentError("error.attachment.manifest_missing_key", key="version"),
    AttachmentError("error.attachment.main_path", file="../x.md"),
    AttachmentError("error.attachment.main_missing", file="main.md"),
    AttachmentError("error.attachment.exists", name="notes", version="1.0.0"),
    AttachmentError("error.attachment.not_found", name="notes"),
    AttachmentError("error.attachment.version_not_found", name="notes", version="2.0.0"),
    AttachmentError("error.attachment.invalid", name="notes", version="1.0.0"),
    AttachmentError("error.attachment.export_exists", path="/tmp/notes-1.0.0.zip"),
    ResumeNotSupportedError("error.resume.unsupported", client="codex"),
    ResumeNotSupportedError("error.resume.lost", session_id="JOB-1_003", client="codex"),
    AxisLabelError("error.axis.label_invalid", label="???"),
    AxisExistsError("error.axis.exists.role", slug="qa"),
    AxisExistsError("error.axis.exists.environment", slug="work"),
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
