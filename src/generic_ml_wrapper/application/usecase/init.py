# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Init use case: the ordered forced-setup interview that shapes every session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.init import Init, InitOutcome
from generic_ml_wrapper.application.port.outbound.layout_seeder import InitSelections

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
    from generic_ml_wrapper.application.port.outbound.client_setup import ClientSetupPort
    from generic_ml_wrapper.application.port.outbound.language_chooser import LanguageChooserPort
    from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort
    from generic_ml_wrapper.application.port.outbound.persona_chooser import PersonaChooserPort
    from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort
    from generic_ml_wrapper.application.port.outbound.text_prompt import TextPromptPort
    from generic_ml_wrapper.common.i18n import Localizer


class InitUseCase(Init):
    """Run the forced setup in order, then persist it.

    The order is deliberate — **language → name → role → environment → persona → client**:
    language comes first because it sets the voice the *rest* of the interview speaks
    (the ``$LANG``-seeded localiser drives the language step itself; once a language is
    chosen the localiser is rebuilt in it and threaded through every later prompt). Each
    step carries a sensible default, and every prompt declines to that default off a
    terminal, so a non-interactive run completes without blocking. The technical client
    step comes last, after the human context is set.
    """

    def __init__(  # noqa: PLR0913  (one seam per ordered step; all injected)
        self,
        *,
        detector: ClientDetectorPort,
        seeder: LayoutSeederPort,
        language_chooser: LanguageChooserPort,
        text_prompt: TextPromptPort,
        personas: PersonaSourcePort,
        persona_chooser: PersonaChooserPort,
        client_setup: ClientSetupPort,
        localizer_factory: Callable[[str], Localizer],
        languages: list[str],
        default_language: str,
        default_name: str,
        version: str,
        default_role: str = "default",
        default_environment: str = "work",
    ) -> None:
        """Wire the use case to the ports and defaults for each ordered step.

        Args:
            detector: Reports which built-in clients are installed.
            seeder: Persists the interview (full config, or legacy marker) and dirs.
            language_chooser: Picks the language gmlw speaks (step one).
            text_prompt: Asks the three free-text steps (name, role, environment).
            personas: The source the offered personas come from.
            persona_chooser: Offers the persona choice (declines non-interactively).
            client_setup: Runs the guided client step (choose / update / install+verify).
            localizer_factory: Builds a localiser for a chosen language code.
            languages: The supported language codes offered at step one.
            default_language: The language the language step defaults to ($LANG-seeded).
            default_name: The name the name step defaults to (typically the OS user).
            version: The gmlw version stamped into the ``[init]`` gate marker.
            default_role: The role the role step defaults to.
            default_environment: The environment the environment step defaults to.
        """
        self._detector = detector
        self._seeder = seeder
        self._language_chooser = language_chooser
        self._text_prompt = text_prompt
        self._personas = personas
        self._persona_chooser = persona_chooser
        self._client_setup = client_setup
        self._localizer_factory = localizer_factory
        self._languages = languages
        self._default_language = default_language
        self._default_name = default_name
        self._version = version
        self._default_role = default_role
        self._default_environment = default_environment

    def execute(self) -> InitOutcome:
        """Run the ordered interview, persist it, and report what it decided.

        Returns:
            The outcome: the resolved axes, the client picked, and whether the install
            was fresh (full config seeded) or legacy (only the marker appended).
        """
        language = self._language_chooser.choose(self._languages, self._default_language)
        i18n = self._localizer_factory(language)
        name = self._text_prompt.ask(i18n.t("init.name.header"), self._default_name, i18n)
        role = self._text_prompt.ask(i18n.t("init.role.header"), self._default_role, i18n)
        environment = self._text_prompt.ask(
            i18n.t("init.environment.header"), self._default_environment, i18n
        )
        persona = self._persona_chooser.choose(self._personas.available(), i18n)
        found = self._detector.available()
        client = self._client_setup.choose(found, i18n)
        persisted = self._seeder.initialize(
            InitSelections(
                version=self._version,
                language=language,
                name=name,
                role=role,
                environment=environment,
                persona=persona,
                client=client,
            )
        )
        return InitOutcome(
            language=language,
            name=name,
            role=role,
            environment=environment,
            persona=persona,
            client=client,
            found=found,
            fresh=persisted.fresh,
            overwrites=persisted.overwrites,
        )
