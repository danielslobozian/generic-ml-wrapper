# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pure persona parser."""

from generic_ml_wrapper.application.domain.service.persona_parser import parse_persona


def test_parses_frontmatter_and_body() -> None:
    text = (
        "---\nname: butler\ndescription: A Jeeves.\n"
        'greeting: "{daypart}, {name}. How may I help?"\n---\n'
        "# Identity\n\nUnflappable."
    )
    persona = parse_persona("fallback", text)
    assert persona.name == "butler"
    assert persona.description == "A Jeeves."
    assert persona.greeting == "{daypart}, {name}. How may I help?"  # quotes + slots preserved
    assert persona.body == "# Identity\n\nUnflappable."


def test_name_falls_back_to_the_file_stem() -> None:
    persona = parse_persona("mentor", "---\ndescription: Guide.\n---\nBody.")
    assert persona.name == "mentor"  # frontmatter omitted name
    assert persona.description == "Guide."


def test_no_frontmatter_is_all_body() -> None:
    persona = parse_persona("plain", "Just a tone block, no metadata.")
    assert persona.name == "plain"
    assert persona.description == ""
    assert persona.greeting == ""
    assert persona.body == "Just a tone block, no metadata."


def test_single_quotes_and_blank_lines_are_handled() -> None:
    persona = parse_persona("x", "---\nname: 'terse'\n\ndescription: 'Short.'\n---\nB")
    assert persona.name == "terse"
    assert persona.description == "Short."
