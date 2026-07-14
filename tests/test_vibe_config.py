# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the vibe config redirect helper."""

from generic_ml_wrapper.adapter.outbound.caller import vibe_config

_CONFIG = """\
active_model = "mistral-medium-3.5"

[[providers]]
name = "mistral"
api_base = "https://api.mistral.ai/v1"
api_style = "openai"
backend = "mistral"

[[providers]]
name = "llamacpp"
api_base = "http://127.0.0.1:8080/v1"

[[models]]
name = "mistral-vibe-cli-latest"
provider = "mistral"
alias = "mistral-medium-3.5"

[[models]]
name = "devstral"
provider = "llamacpp"
alias = "local"
"""


def test_active_upstream_resolves_via_alias() -> None:
    # active_model matches the model's alias, whose provider is "mistral".
    assert vibe_config.active_upstream(_CONFIG) == "https://api.mistral.ai/v1"


def test_active_upstream_resolves_via_name() -> None:
    config = _CONFIG.replace('active_model = "mistral-medium-3.5"', 'active_model = "devstral"')
    assert vibe_config.active_upstream(config) == "http://127.0.0.1:8080/v1"


def test_active_upstream_is_none_when_unresolvable() -> None:
    assert vibe_config.active_upstream('active_model = "nope"\n') is None
    assert vibe_config.active_upstream("not [ valid toml") is None
    assert vibe_config.active_upstream("theme = 'dark'\n") is None  # no active_model


def test_redirect_points_the_upstream_at_the_relay_keeping_the_path() -> None:
    out = vibe_config.redirect(_CONFIG, "https://api.mistral.ai/v1", "http://127.0.0.1:52001")

    assert 'api_base = "http://127.0.0.1:52001/v1"' in out
    assert "https://api.mistral.ai/v1" not in out
    # the other provider is left untouched
    assert 'api_base = "http://127.0.0.1:8080/v1"' in out


def test_redirect_leaves_config_untouched_when_upstream_absent() -> None:
    out = vibe_config.redirect(_CONFIG, "https://example.invalid/v1", "http://127.0.0.1:52001")
    assert out == _CONFIG


def test_redirect_changes_only_the_active_providers_table() -> None:
    # llamacpp shares mistral's api_base, but only mistral (the active provider) is repointed;
    # the blind string-replace used to change both.
    shared = _CONFIG.replace(
        'api_base = "http://127.0.0.1:8080/v1"', 'api_base = "https://api.mistral.ai/v1"'
    )
    out = vibe_config.redirect(shared, "https://api.mistral.ai/v1", "http://127.0.0.1:52001")
    assert out.count('api_base = "http://127.0.0.1:52001/v1"') == 1  # only the active provider
    assert out.count('api_base = "https://api.mistral.ai/v1"') == 1  # llamacpp left untouched
