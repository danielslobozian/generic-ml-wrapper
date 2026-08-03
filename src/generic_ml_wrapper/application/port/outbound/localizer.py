# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for localisation: where a catalogue key becomes a sentence."""

from __future__ import annotations

from abc import ABC

from generic_ml_wrapper.application.domain.service.localizer import Localizer


class LocalizerPort(Localizer, ABC):
    """Outbound port for a string catalogue.

    The contract is the domain
    :class:`~generic_ml_wrapper.application.domain.service.localizer.Localizer`. Core
    renders through this port and never reads a catalogue file itself; where the strings
    come from — packaged JSON, a bundle, a stub in a test — is a wiring choice.
    """
