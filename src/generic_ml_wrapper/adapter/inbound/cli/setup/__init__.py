# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The terminal side of the conversations gmlw holds with the user.

Everything here prints a question and reads an answer. That is the delivery channel, so
it is inbound: the application is asked what is on offer, the terminal decides what to
ask and in what words, and the answer goes back as a code.

These used to sit under ``adapter/outbound/bootstrap`` behind ports, which meant a use
case was running the conversation and a renderer had to be threaded outward to reach it.
"""
