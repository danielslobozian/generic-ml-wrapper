# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys

from generic_ml_wrapper.adapter.inbound.cli.app import cli_main
from generic_ml_wrapper.adapter.inbound.common.i18n.language_context_holder import (
    LanguageContextHolder,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
    get_message,
)
from generic_ml_wrapper.adapter.inbound.common.renderer import render_error
from generic_ml_wrapper.adapter.inbound.common.terminal_valid_actions_policy import (
    TerminalValidActionsPolicy,
)
from generic_ml_wrapper.adapter.inbound.tui.app import tui_main
from generic_ml_wrapper.application.domain.model.domain_error import DomainError
from generic_ml_wrapper.application.wiring.composition import (
    build_check_store_contract,
    build_diagnostics,
    load_current_language,
)
from generic_ml_wrapper.application.wiring.diagnostics_log import (
    set_active as set_active_diagnostics,
)

REFUSED_EXIT_CODE = 1
INTERRUPTED_EXIT_CODE = 130


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    try:
        LanguageContextHolder.set_language(load_current_language())
        verdict = TerminalValidActionsPolicy.check(arguments)
        if not verdict.allowed:
            print(get_message(verdict.message_code), file=sys.stderr)
            return REFUSED_EXIT_CODE
        build_check_store_contract().execute()
        if not arguments:
            set_active_diagnostics(build_diagnostics(to_stderr=False))
            return tui_main()
        return cli_main(arguments)
    except DomainError as error:  # a refusal we phrased ourselves — say it, don't dump it
        print(render_error(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(file=sys.stderr)  # a tidy newline after ^C, never a traceback
        return INTERRUPTED_EXIT_CODE
    except Exception as error:  # noqa: BLE001  last resort: no traceback reaches the user
        print(get_message("error.unexpected", error=error), file=sys.stderr)
        return 1
