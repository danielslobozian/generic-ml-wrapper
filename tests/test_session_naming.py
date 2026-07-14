# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pure session-naming service."""

from generic_ml_wrapper.application.domain.service.session_naming import next_session_id


def test_first_session_is_001() -> None:
    assert next_session_id("JOB-1", []) == "JOB-1_001"


def test_next_is_one_past_the_highest() -> None:
    assert next_session_id("JOB-1", ["JOB-1_001", "JOB-1_002"]) == "JOB-1_003"


def test_gaps_do_not_cause_collisions() -> None:
    assert next_session_id("JOB-1", ["JOB-1_001", "JOB-1_005"]) == "JOB-1_006"


def test_ids_without_a_suffix_are_ignored() -> None:
    assert next_session_id("JOB-1", ["weird", "JOB-1_002"]) == "JOB-1_003"
