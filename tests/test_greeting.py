# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pure greeting service."""

from generic_ml_wrapper.application.domain.service.greeting_composer import GreetingComposer


def test_greeting_context_wraps_the_greeting_as_a_renderable_section() -> None:
    section = GreetingComposer().greeting_context("Good evening, Dan.")
    assert section.startswith("# Greeting")
    assert "Good evening, Dan." in section
