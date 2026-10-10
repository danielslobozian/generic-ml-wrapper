# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``ContextCompilerPort``: a session's context from ``~/.gmlw``."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model import context_source
from generic_ml_wrapper.application.domain.model.context_source import CompileMode, ContextSource
from generic_ml_wrapper.application.domain.model.learned import CAPTURE_DIRECTIVE
from generic_ml_wrapper.application.domain.model.rules import RULE_TEMPLATE, rule_capture_directive
from generic_ml_wrapper.application.domain.model.session_snapshot import SessionSnapshot
from generic_ml_wrapper.application.domain.service import rule_parser
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.domain.service.rule_cleaner import clean_rule
from generic_ml_wrapper.application.port.outbound.context_compiler import ContextCompilerPort
from generic_ml_wrapper.common import config

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.context_compressor import (
        ContextCompressorPort,
    )
    from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort

_LEARNED_FILE = "learned.md"
_LEARNED_DIR = "learned"
_STRIP_SECTIONS = ("Origin", "Notes")
# The user-editable rule format, read from the templates root and embedded in the directive.
_RULE_TEMPLATE_FILE = "rule.template.md"


class FilesystemContextCompiler(ContextCompilerPort):
    """Compose a session's operating context from several ``~/.gmlw`` locations.

    The persona, the user's profile (self + learned + company), the rules of the active
    environment and role, and an attachment's section when the session has one. Which
    sources are active, and whether each is compressed, is decided per mode by the
    injected startup policy.
    """

    def __init__(  # noqa: PLR0913, PLR0917  (a composition adapter binding several ~/.gmlw roots)
        self,
        profile_root: Path | None = None,
        templates_root: Path | None = None,
        interceptors: InterceptorChain | None = None,
        personas: PersonaSourcePort | None = None,
        compressor: ContextCompressorPort | None = None,
        startup: Callable[[str], dict[str, config.SourceSetting]] | None = None,
        companion: Callable[[], str | None] | None = None,
        environments_root: Path | None = None,
        default_environment: Callable[[], str] | None = None,
        default_role: Callable[[], str] | None = None,
        user_name: Callable[[], str | None] | None = None,
        language: Callable[[], str | None] | None = None,
    ) -> None:
        """Bind the source to its roots and context policy.

        Args:
            profile_root: The user's profile directory, or ``None`` to omit it.
            templates_root: The user-editable templates directory, holding
                ``rule.template.md``. ``None`` (or a missing file) falls back to the
                packaged format, so the directive always carries a usable template.
            interceptors: The per-section interceptor chain, or ``None`` for none.
            personas: The persona source; the selected persona (plus the shared floor)
                is the ``persona`` context section. ``None`` omits the section.
            compressor: The typed compressor for per-source compression, or ``None``
                to leave every source verbatim.
            startup: Resolves a mode's activation matrix; defaults to the baked-in
                matrix (:func:`config.default_startup`), so the composition root
                injects :func:`config.startup` to honor the user's config file.
            companion: Resolves the selected persona name; defaults to none selected
                (the persona section stays invisible until the composition root injects
                :func:`config.companion`).
            environments_root: The environments directory holding one folder per
                environment; the ``company`` source reads the active one. ``None`` omits
                the source (place-specific context is off).
            default_environment: Resolves the active environment's name; defaults to
                ``"work"`` until the composition root injects
                :func:`config.default_environment`.
            default_role: Resolves the active role's name; the ``rules.role`` and
                ``me.learned`` sources read that role's ``profile/roles/<role>/`` folder.
                Defaults to ``"default"`` until the composition root injects
                :func:`config.default_role`.
            user_name: Resolves the user's name for the session snapshot; defaults to
                unset, which renders as ``""``.
            language: Resolves the language gmlw speaks for the session snapshot; defaults
                to unset, which renders as ``""``.
        """
        self._profile_root = profile_root
        self._templates_root = templates_root
        self._interceptors = interceptors or InterceptorChain(())
        self._personas = personas
        self._compressor = compressor
        self._startup = startup or config.default_startup
        self._companion = companion or (lambda: None)
        self._environments_root = environments_root
        self._default_environment = default_environment or (lambda: "work")
        self._default_role = default_role or (lambda: "default")
        self._user_name = user_name or (lambda: None)
        self._language = language or (lambda: None)

    def compile(
        self, mode: CompileMode, job: str | None = None, attachment: str | None = None
    ) -> str:
        """Compose a run's operating context for a mode.

        The order is: the session snapshot, the profile family (persona, self, learned,
        company), then rules, then the attachment's section. Each active source is
        optionally compressed (per its config), sections pass through the interceptor
        chain for their target, and the joined result through ``context``. The snapshot
        leads because it frames everything after it, and stays verbatim: six scalars are
        not worth compressing and a paraphrase would make them wrong rather than shorter.
        The attachment's section is never compressed: it is delivered as written.

        Args:
            mode: The compile mode (default/attachment).
            job: The job this session runs on, for the snapshot.
            attachment: An attachment's section, last and verbatim, or ``None``.

        Returns:
            The composed context (active sections, joined by blank lines).
        """
        settings = self._startup(mode)
        snapshot = self._snapshot(job).render()
        profile = self._interceptors.apply("profile", self._profile_group(settings))
        rules = self._interceptors.apply("rules", self._rules_group(settings))
        attached = self._interceptors.apply("attachment", attachment or "")
        context = "\n\n\n".join(part for part in (snapshot, profile, rules, attached) if part)
        return self._interceptors.apply("context", context)

    def _snapshot(self, job: str | None) -> SessionSnapshot:
        """Build the session snapshot from the live selections.

        Args:
            job: The job this session runs on, or ``None``.

        Returns:
            The snapshot, with any unset selection rendered as ``""``.
        """
        return SessionSnapshot(
            user_name=self._user_name() or "",
            user_prefered_language=self._language() or "",
            user_environment=self._default_environment(),
            user_role=self._default_role(),
            ai_persona=self._companion() or "",
            job_name=job or "",
        )

    def _profile_group(self, settings: dict[str, config.SourceSetting]) -> str:
        """Compose the active profile-family sources (persona, self, learned, company)."""
        parts: list[str] = []
        for source in context_source.PROFILE_FAMILY:
            setting = settings[source.key]
            if not setting.activated:
                continue
            text = self._maybe_compress(self._read_source(source), source, setting)
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def _rules_group(self, settings: dict[str, config.SourceSetting]) -> str:
        """Compose the rule-capture directive and the two axis-scoped rule sets.

        Rules are a projection of the user, so they live on the two axes that describe
        one: the environment (the place) and the role (the craft). When either axis is
        active the section leads with the capture directive (gmlw's voice) so a demanded
        correction becomes a draft rule in any session — even one with no rules yet. The
        directive stays verbatim; only the user's rule content is subject to compression.

        Activation governs *loading*, not authoring: an axis switched off for this mode
        still names a real folder, and a rule written there loads in the sessions where
        that axis is on. So the directive offers both axes whenever it is shown at all.
        """
        env_setting = settings[context_source.RULES_ENVIRONMENT.key]
        role_setting = settings[context_source.RULES_ROLE.key]
        if not env_setting.activated and not role_setting.activated:
            return ""
        env_dir = self._environment_rules_dir()
        role_dir = self._role_rules_dir()
        parts: list[str] = [
            rule_capture_directive(
                environment=self._default_environment(),
                role=self._default_role(),
                environment_dir=str(env_dir) if env_dir else "(no environment configured)",
                role_dir=str(role_dir) if role_dir else "(no role configured)",
                template=self._rule_template(),
            )
        ]
        # Role first, environment last. The environment's constraints outrank the role's
        # preferences on conflict (the directive says so outright), and the authoritative
        # set also sits closest to the model, where late instructions carry more weight.
        if role_setting.activated:
            rules = self._maybe_compress(
                self._rules(role_dir), context_source.RULES_ROLE, role_setting
            )
            if rules:
                parts.append(rules)
        if env_setting.activated:
            rules = self._maybe_compress(
                self._rules(env_dir), context_source.RULES_ENVIRONMENT, env_setting
            )
            if rules:
                parts.append(rules)
        return "\n\n\n".join(parts)

    def _environment_rules_dir(self) -> Path | None:
        """The active environment's rules folder, or ``None`` without an environments root."""
        if self._environments_root is None:
            return None
        return self._environments_root / self._default_environment() / "rules"

    def _role_rules_dir(self) -> Path | None:
        """The active role's rules folder, or ``None`` without a profile root."""
        role_dir = self._role_dir()
        return None if role_dir is None else role_dir / "rules"

    def _rule_template(self) -> str:
        """The user's rule template, falling back to the packaged one when absent.

        Read from disk on every compile so a user who reshapes the template immediately
        changes what the client is told to write — the template and the directive's copy
        of it can never drift, because there is only one copy.
        """
        if self._templates_root is not None:
            text = self._read(self._templates_root / _RULE_TEMPLATE_FILE)
            if text:
                return text
        return RULE_TEMPLATE

    def _maybe_compress(
        self, text: str, source: ContextSource, setting: config.SourceSetting
    ) -> str:
        """Compress a source's text when its config asks and a compressor is wired."""
        if not (text and setting.compression) or self._compressor is None:
            return text
        return self._compressor.compress(text, source_key=source.key, kind=source.kind_name)

    def _read_source(self, source: ContextSource) -> str:
        """Read a profile-family source's raw text from its filesystem location."""
        if source is context_source.PERSONA:
            return self._persona()
        if source is context_source.ME_USER:
            return self._me_user()
        if source is context_source.ME_LEARNED:
            return self._me_learned()
        if source is context_source.COMPANY and self._environments_root is not None:
            # Place-specific context now lives per environment; read the active one. The
            # config key stays "company"; only its on-disk home moved (environments/<env>/).
            return self._concat_dir(self._environments_root / self._default_environment())
        return ""

    def _persona(self) -> str:
        """Compose the selected persona's tone body over the shared floor.

        Invisible (``""``) until a persona is selected and found: no source, no
        selection, or an unknown name all yield nothing, so a stranger is never
        greeted by a character.
        """
        if self._personas is None:
            return ""
        name = self._companion()
        if not name:
            return ""
        persona = self._personas.get(name)
        if persona is None:
            return ""
        parts = [persona.body, self._personas.floor()]
        return "\n\n---\n\n".join(part for part in parts if part)

    def _me_user(self) -> str:
        """Concatenate ``profile/me/*.md`` — the user about the user — excluding learned."""
        if self._profile_root is None:
            return ""
        directory = self._profile_root / "me"
        if not directory.is_dir():
            return ""
        texts = [
            self._read(path)
            for path in sorted(directory.glob("*.md"))
            if path.name != _LEARNED_FILE
        ]
        return "\n\n".join(text for text in texts if text)

    def _me_learned(self) -> str:
        """Compose the learned section: the capture directive over the user's notebooks.

        The notebook (``learned.md`` and any ``learned/`` folder) is the AI-about-the-user
        store; the directive (gmlw's voice) asks the client to keep mirroring into it. Both
        the shared ``profile/me`` notebook and the active role's ``profile/roles/<role>``
        notebook compose here (role notes are still learned — just scoped to the role); the
        directive stays global (capture is not role-aware yet). The section is invisible when
        both notebooks are absent, so a run without one stays clean.
        """
        if self._profile_root is None:
            return ""
        notebooks = [
            self._notebook(self._profile_root / "me"),
            self._notebook(self._profile_root / "roles" / self._default_role()),
        ]
        notebook = "\n\n".join(text for text in notebooks if text)
        return f"{CAPTURE_DIRECTIVE}\n\n{notebook}" if notebook else ""

    def _notebook(self, directory: Path) -> str:
        """Concatenate a learned notebook: ``learned.md`` then ``learned/*.md`` (sorted)."""
        parts: list[str] = []
        learned_file = directory / _LEARNED_FILE
        if learned_file.is_file():
            parts.append(self._read(learned_file))
        learned_dir = directory / _LEARNED_DIR
        if learned_dir.is_dir():
            parts += [self._read(path) for path in sorted(learned_dir.glob("*.md"))]
        return "\n\n".join(text for text in parts if text)

    def _role_dir(self) -> Path | None:
        """The active role's folder (``profile/roles/<role>``), or ``None`` without a profile."""
        if self._profile_root is None:
            return None
        return self._profile_root / "roles" / self._default_role()

    def _concat_dir(self, directory: Path | None) -> str:
        """Concatenate every ``*.md`` in a folder, sorted by filename."""
        if directory is None or not directory.is_dir():
            return ""
        files = [self._read(path) for path in sorted(directory.glob("*.md"))]
        return "\n\n".join(text for text in files if text)

    def _rules(self, directory: Path | None) -> str:
        if directory is None or not directory.is_dir():
            return ""
        cleaned: list[str] = []
        for path in sorted(directory.glob("*.rule.md")):
            raw = path.read_text(encoding="utf-8").strip()
            # Draft-ness is a frontmatter key, not a phrase: a substring search over the
            # whole file silently dropped any live rule that merely mentioned drafting.
            if raw and not rule_parser.is_draft(raw):
                rule = clean_rule(raw, _STRIP_SECTIONS)
                if rule:
                    cleaned.append(rule)
        return "\n\n---\n\n".join(cleaned)

    @staticmethod
    def _read(path: Path) -> str:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8").strip()
