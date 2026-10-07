# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A reference interceptor that logs each message's size and returns it unchanged."""

from __future__ import annotations

from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort
from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.log import log


class MessageSizeLogger(InterceptorPort):
    """Log the size of every intercepted message; a non-transforming observer.

    A reference interceptor and the simplest example of the plugin contract: it logs
    how many characters flow through each target it is bound to — e.g. ``request`` for
    outbound prompts, ``response`` for the replies — and returns the text untouched.
    Configure it under ``[[interceptors]]`` on the targets you want traced; put it on
    both ``request`` and ``response`` to log sizes in and out.
    """

    def intercept(self, text: str, target: str) -> str:
        """Log the message size for ``target`` and return the text unchanged.

        Args:
            text: The intercepted message.
            target: The target it is running for (e.g. ``request``, ``response``).

        Returns:
            The input text, unchanged.
        """
        log.info(i18n.t("log.interceptor_size", target=target, chars=len(text)))
        return text
