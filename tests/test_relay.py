# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the metering relay, driven over a real local socket with a fake upstream."""

import http.client
import json
import socket
import ssl
from collections.abc import Iterator, Mapping

import pytest

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import StreamUsage
from generic_ml_wrapper.adapter.outbound.gateway.relay import (
    MeteringRelay,
    UpstreamResponse,
    _Handler,
    _RelayServer,
    _tee,
)
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.domain.service.diagnostics import Diagnostics
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort
from generic_ml_wrapper.application.port.outbound.transcript_call import TranscriptCall
from generic_ml_wrapper.application.wiring.diagnostics_log import set_active

_SSE = (
    b'data: {"type":"message_start","message":{"model":"m","usage":{"input_tokens":10}}}\n\n'
    b'data: {"type":"message_delta","usage":{"output_tokens":20}}\n\n'
)


def _zero() -> float:
    return 0.0


class _FakeStore(PerTurnMeteringPort):
    def __init__(self) -> None:
        self.recorded: list[tuple[str, TurnUsage]] = []

    def record(self, job: str, turn: TurnUsage) -> None:
        self.recorded.append((job, turn))

    def turns_for_job(self, job: str) -> list[TurnUsage]:
        return []


def _echo_forwarder(
    method: str, path: str, headers: Mapping[str, str], body: bytes
) -> UpstreamResponse:
    return UpstreamResponse(200, [("Content-Type", "text/event-stream")], [_SSE])


def _post(relay: MeteringRelay, body: bytes = b"{}") -> bytes:
    connection = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=5)
    try:
        # Requests carry the capability prefix the client is handed via base_url.
        connection.request("POST", f"/{relay._client}/{relay._token}/v1/messages", body=body)
        return connection.getresponse().read()
    finally:
        connection.close()


class _Redact(InterceptorPort):
    def intercept(self, text: str, target: str) -> str:
        return text.replace("secret", "REDACTED")


class _Spy(InterceptorPort):
    def __init__(self) -> None:
        self.seen: list[tuple[str, str]] = []

    def intercept(self, text: str, target: str) -> str:
        self.seen.append((target, text))
        return text


def test_request_interceptor_transforms_the_outbound_body() -> None:
    captured: dict[str, bytes] = {}

    def capturing_forwarder(
        method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> UpstreamResponse:
        captured["body"] = body
        return UpstreamResponse(200, [("Content-Type", "text/event-stream")], [_SSE])

    relay = MeteringRelay(
        job="J",
        session="J_001",
        metering=_FakeStore(),
        forwarder=capturing_forwarder,
        interceptors=InterceptorChain([("request", _Redact())]),
        clock=_zero,
    )
    relay.start()
    try:
        _post(relay, body=b'{"prompt":"my secret"}')
    finally:
        relay.stop()

    assert captured["body"] == b'{"prompt":"my REDACTED"}'  # request rewritten before forwarding


def test_response_interceptor_observes_the_captured_body_without_altering_the_stream() -> None:
    spy = _Spy()
    relay = MeteringRelay(
        job="J",
        session="J_001",
        metering=_FakeStore(),
        forwarder=_echo_forwarder,
        interceptors=InterceptorChain([("response", spy)]),
        clock=_zero,
    )
    relay.start()
    try:
        returned = _post(relay)
    finally:
        relay.stop()

    assert returned == _SSE  # client still sees the unmodified stream
    assert len(spy.seen) == 1
    assert spy.seen[0][0] == "response"
    assert "message_start" in spy.seen[0][1]


def test_relay_streams_response_back_and_records_usage() -> None:
    store = _FakeStore()
    relay = MeteringRelay(
        job="JOB-1", session="JOB-1_001", metering=store, forwarder=_echo_forwarder, clock=_zero
    )
    relay.start()
    try:
        returned = _post(relay)
    finally:
        relay.stop()

    assert returned == _SSE  # the client sees the upstream stream unchanged
    assert store.recorded == [("JOB-1", TurnUsage("JOB-1_001", 10, 20, None, "m"))]


class _FakeTranscript(TranscriptPort):
    def __init__(self) -> None:
        self.calls: list[TranscriptCall] = []

    def record(self, call: TranscriptCall) -> None:
        self.calls.append(call)


def test_relay_records_the_transcript_when_configured() -> None:
    transcript = _FakeTranscript()
    relay = MeteringRelay(
        job="JOB-1",
        session="JOB-1_001",
        metering=_FakeStore(),
        forwarder=_echo_forwarder,
        transcript=transcript,
        clock=_zero,
    )
    relay.start()
    try:
        _post(relay, body=b'{"prompt":"hi"}')
    finally:
        relay.stop()

    assert len(transcript.calls) == 1
    call = transcript.calls[0]
    assert (call.job, call.session, call.call_seq) == ("JOB-1", "JOB-1_001", 1)
    assert call.request == b'{"prompt":"hi"}'  # the forwarded request body
    assert call.response == _SSE
    assert call.usage is not None
    assert call.usage.input_tokens == 10


def test_relay_ignores_a_non_stream_response() -> None:
    store = _FakeStore()

    def error_forwarder(
        method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> UpstreamResponse:
        return UpstreamResponse(400, [], [b'{"type":"error"}'])

    relay = MeteringRelay(
        job="JOB-1", session="JOB-1_001", metering=store, forwarder=error_forwarder
    )
    relay.start()
    try:
        _post(relay)
    finally:
        relay.stop()

    assert store.recorded == []  # nothing to meter from a non-stream response


def test_relay_forces_identity_encoding_upstream() -> None:
    seen: dict[str, str] = {}

    def capturing(
        method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> UpstreamResponse:
        seen.update(headers)
        return UpstreamResponse(200, [], [_SSE])

    relay = MeteringRelay(job="J", session="S", metering=_FakeStore(), forwarder=capturing)
    relay.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=5)
        connection.request(
            "POST",
            f"/{relay._client}/{relay._token}/v1/messages",
            body=b"{}",
            headers={"Accept-Encoding": "gzip"},
        )
        connection.getresponse().read()
        connection.close()
    finally:
        relay.stop()

    assert seen.get("Accept-Encoding") == "identity"  # client's gzip was overridden


def test_relay_meters_only_the_messages_endpoint() -> None:
    store = _FakeStore()
    relay = MeteringRelay(job="J", session="S", metering=store, forwarder=_echo_forwarder)
    relay.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=5)
        connection.request(
            "POST",
            f"/{relay._client}/{relay._token}/v1/messages/count_tokens",
            body=b"{}",
        )  # not a turn
        connection.getresponse().read()
        connection.close()
    finally:
        relay.stop()

    assert store.recorded == []


def test_relay_records_non_streaming_json_usage() -> None:
    store = _FakeStore()

    def json_forwarder(
        method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> UpstreamResponse:
        envelope = b'{"type":"message","model":"m","usage":{"input_tokens":7,"output_tokens":3}}'
        return UpstreamResponse(200, [("Content-Type", "application/json")], [envelope])

    relay = MeteringRelay(
        job="J", session="S", metering=store, forwarder=json_forwarder, clock=_zero
    )
    relay.start()
    try:
        _post(relay)
    finally:
        relay.stop()

    assert store.recorded == [("J", TurnUsage("S", 7, 3, None, "m"))]


def test_relay_uses_pluggable_usage_reader_and_metered_path() -> None:
    store = _FakeStore()

    def reader(text: str) -> StreamUsage | None:
        return StreamUsage(1, 2, "m") if "ok" in text else None

    def is_metered(method: str, path: str) -> bool:
        return path.endswith("/v1/responses")

    def forwarder(
        method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> UpstreamResponse:
        return UpstreamResponse(200, [], [b"ok"])

    relay = MeteringRelay(
        job="J",
        session="S",
        metering=store,
        forwarder=forwarder,
        usage_reader=reader,
        is_metered=is_metered,
        clock=_zero,
    )
    relay.start()
    try:
        for path in ("/v1/responses", "/v1/messages"):  # only the first is metered here
            connection = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=5)
            connection.request("POST", f"/{relay._client}/{relay._token}{path}", body=b"{}")
            connection.getresponse().read()
            connection.close()
    finally:
        relay.stop()

    assert store.recorded == [("J", TurnUsage("S", 1, 2, None, "m"))]


def test_relay_records_timestamp_duration_and_turn_id() -> None:
    store = _FakeStore()
    sse = (
        b'data: {"type":"message_start","message":'
        b'{"id":"msg_1","model":"m","usage":{"input_tokens":10}}}\n\n'
        b'data: {"type":"message_delta","usage":{"output_tokens":20}}\n\n'
    )

    def forwarder(
        method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> UpstreamResponse:
        return UpstreamResponse(200, [], [sse])

    times = iter([100.0, 100.5])  # start, then end -> duration 0.5
    relay = MeteringRelay(
        job="J", session="S", metering=store, forwarder=forwarder, clock=lambda: next(times)
    )
    relay.start()
    try:
        _post(relay)
    finally:
        relay.stop()

    assert store.recorded == [
        ("J", TurnUsage("S", 10, 20, None, "m", timestamp=100.0, duration_s=0.5, turn_id="msg_1"))
    ]


def test_tee_captures_everything_even_when_client_hangs_up() -> None:
    written: list[bytes] = []

    def sink(chunk: bytes) -> None:
        if written:  # the client hangs up after the first chunk
            raise BrokenPipeError
        written.append(chunk)

    captured = _tee([b"a", b"b", b"c"], sink)
    assert captured == b"abc"  # full body still captured for usage
    assert written == [b"a"]  # stopped writing once the client left


def test_authorize_strips_matching_prefix_and_rejects_the_rest() -> None:
    relay = MeteringRelay(job="J", session="S", metering=_FakeStore(), client="claude")
    token = relay._token
    assert relay.authorize(f"/claude/{token}/v1/messages") == "/v1/messages"
    assert relay.authorize(f"/claude/{token}") == "/"
    assert relay.authorize("/claude/wrong-token/v1/messages") is None
    assert relay.authorize(f"/codex/{token}/v1/messages") is None  # wrong client segment
    assert relay.authorize("/v1/messages") is None  # no prefix at all


def test_unauthenticated_request_is_refused_and_not_metered() -> None:
    store = _FakeStore()
    relay = MeteringRelay(job="J", session="S", metering=store, forwarder=_echo_forwarder)
    relay.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=5)
        connection.request("POST", "/v1/messages", body=b"{}")  # no capability prefix
        assert connection.getresponse().status == 404
        connection.close()
    finally:
        relay.stop()
    assert store.recorded == []


def test_request_with_an_origin_header_is_refused() -> None:
    relay = MeteringRelay(job="J", session="S", metering=_FakeStore(), forwarder=_echo_forwarder)
    relay.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=5)
        prefix = f"/{relay._client}/{relay._token}"
        connection.request(
            "POST", f"{prefix}/v1/messages", body=b"{}", headers={"Origin": "http://evil.example"}
        )
        assert connection.getresponse().status == 403
        connection.close()
    finally:
        relay.stop()


# ---------------------------------------------------------------------------
# Error boundaries (issue #59)
#
# Every one of these used to end the same way: an exception escaped the handler
# thread, socketserver printed a raw traceback to stderr -- which during a wrapped
# session is the client's own screen -- and nothing was written to any log file.
# ---------------------------------------------------------------------------


class _Recording(Diagnostics):
    """A sink that keeps what it was handed, so a test can assert the failure was logged."""

    def __init__(self) -> None:
        self.records: list[tuple[str, str, BaseException | None, dict[str, object]]] = []

    def debug(self, message: str, **context: object) -> None:
        self.records.append(("debug", message, None, context))

    def info(self, message: str, **context: object) -> None:
        self.records.append(("info", message, None, context))

    def warning(self, message: str, **context: object) -> None:
        self.records.append(("warning", message, None, context))

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        self.records.append(("error", message, exc, context))

    def keys(self, level: str) -> list[object]:
        """The catalogue keys logged at *level* — asserted on instead of rendered text,
        so these tests do not break when a message is reworded or translated."""
        return [context.get("key") for name, _, _, context in self.records if name == level]


def _post_status(relay: MeteringRelay, body: bytes = b"{}") -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=5)
    try:
        connection.request("POST", f"/{relay._client}/{relay._token}/v1/messages", body=body)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def _raise_ssl_error() -> None:
    raise ssl.SSLError("EOF occurred in violation of protocol")


def _exploding_forwarder(
    method: str, path: str, headers: Mapping[str, str], body: bytes
) -> UpstreamResponse:
    """A TLS handshake that fails -- the unguarded call at the top of the exchange."""
    raise ssl.SSLError("EOF occurred in violation of protocol")


def _half_stream() -> Iterator[bytes]:
    """A response that dies mid-stream, after the head and one chunk are already out."""
    yield b'data: {"type":"message_start","message":{"model":"m","usage":{"input_tokens":10}}}\n\n'
    raise ssl.SSLError("EOF occurred in violation of protocol")


def _dying_forwarder(
    method: str, path: str, headers: Mapping[str, str], body: bytes
) -> UpstreamResponse:
    return UpstreamResponse(200, [("Content-Type", "text/event-stream")], _half_stream())


def test_a_failed_handshake_returns_502_and_logs_instead_of_crashing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    sink = _Recording()
    previous = set_active(sink)
    relay = MeteringRelay(
        job="J", session="S", metering=_FakeStore(), forwarder=_exploding_forwarder
    )
    relay.start()
    try:
        status, _ = _post_status(relay)
    finally:
        relay.stop()
        set_active(previous)

    assert status == 502, "the client should get a clean gateway error it can retry"
    assert sink.keys("error") == ["log.gateway_request_failed"]
    errors = [record for record in sink.records if record[0] == "error"]
    assert isinstance(errors[0][2], ssl.SSLError), "the traceback must reach the sink"
    # The whole point: nothing reaches the terminal the client is drawing on.
    assert capsys.readouterr().err == ""


def test_a_midstream_upstream_failure_ends_the_turn_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    sink = _Recording()
    previous = set_active(sink)
    store = _FakeStore()
    relay = MeteringRelay(job="J", session="S", metering=store, forwarder=_dying_forwarder)
    relay.start()
    try:
        status, body = _post_status(relay)
    finally:
        relay.stop()
        set_active(previous)

    # The head was already sent, so the status stands; the client sees a short stream.
    assert status == 200
    assert b"message_start" in body, "what arrived before the break is still delivered"
    assert "log.gateway_stream_interrupted" in sink.keys("warning")
    assert capsys.readouterr().err == ""


def test_a_partial_turn_is_still_recorded() -> None:
    # A turn cut short is worth recording with what it managed to send, rather than lost.
    store = _FakeStore()
    previous = set_active(_Recording())
    relay = MeteringRelay(job="J", session="S", metering=store, forwarder=_dying_forwarder)
    relay.start()
    try:
        _post_status(relay)
    finally:
        relay.stop()
        set_active(previous)
    assert store.recorded, "the input tokens seen before the break should still be metered"


def test_a_metering_failure_never_costs_the_client_its_turn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _BrokenStore(_FakeStore):
        def record(self, job: str, turn: TurnUsage) -> None:
            raise RuntimeError("the ledger is locked")

    sink = _Recording()
    previous = set_active(sink)
    relay = MeteringRelay(job="J", session="S", metering=_BrokenStore(), forwarder=_echo_forwarder)
    relay.start()
    try:
        status, body = _post_status(relay)
    finally:
        relay.stop()
        set_active(previous)

    # Bookkeeping happens after the client already has its answer: a failure there is
    # ours, and must not be reported as a gateway error.
    assert status == 200
    assert b"message_start" in body
    assert "log.gateway_record_failed" in sink.keys("warning")
    assert capsys.readouterr().err == ""


def test_the_server_logs_a_handler_crash_rather_than_printing_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The belt to _proxy's braces: even a bug that bypasses the boundary must not paint
    # a traceback over the client's screen.
    sink = _Recording()
    previous = set_active(sink)
    relay = MeteringRelay(job="J", session="S", metering=_FakeStore(), forwarder=_echo_forwarder)
    relay.start()
    server = relay._server
    assert server is not None
    try:
        with socket.socket() as request:
            try:
                _raise_ssl_error()
            except ssl.SSLError:
                server.handle_error(request, ("127.0.0.1", 1234))
    finally:
        relay.stop()
        set_active(previous)

    assert sink.keys("error") == ["log.gateway_handler_crashed"]
    assert capsys.readouterr().err == ""


def test_a_dead_accept_loop_is_recorded_rather_than_vanishing() -> None:
    # A daemon thread that dies takes the metering with it and leaves no trace: the
    # session keeps working while silently going unrecorded. Make it say so.
    sink = _Recording()
    previous = set_active(sink)
    relay = MeteringRelay(job="J", session="S", metering=_FakeStore(), forwarder=_echo_forwarder)
    server = _RelayServer(("127.0.0.1", 0), _Handler, relay)
    relay._server = server
    try:
        # Drive _serve directly with an accept loop that dies immediately. Note we must
        # not call relay.stop() afterwards: shutdown() waits on a serve_forever that
        # never ran, and would block forever.
        server.serve_forever = _raise_ssl_error  # type: ignore[method-assign]
        relay._serve()
    finally:
        server.server_close()
        set_active(previous)

    assert sink.keys("error") == ["log.gateway_stopped"]


# ── learning the client's own session id off the wire ──
def _sink_relay(sink: list[str], **kwargs: object) -> MeteringRelay:
    """A relay that learns a session id from the request body's ``session_id`` field."""

    def read(text: str) -> str | None:
        try:
            return dict(json.loads(text)).get("session_id")
        except ValueError:
            return None

    return MeteringRelay(
        job="J",
        session="S",
        metering=_FakeStore(),
        forwarder=_echo_forwarder,
        session_id_reader=read,
        session_id_sink=sink.append,
        **kwargs,  # type: ignore[arg-type]
    )


def test_the_session_id_is_learned_from_the_first_metered_turn() -> None:
    # Codex mints its own id and takes no flag to accept ours, so the wire is the only
    # place to learn it -- and it is there from the very first turn.
    seen: list[str] = []
    relay = _sink_relay(seen)
    relay.start()
    try:
        _post(relay, b'{"session_id":"019f-abc"}')
    finally:
        relay.stop()
    assert seen == ["019f-abc"]


def test_an_unchanged_session_id_is_reported_once_not_per_turn() -> None:
    # The id is stable for the session's life, so every later turn repeats it. Binding it
    # again on each turn would be a write per turn for a value that never moved.
    seen: list[str] = []
    relay = _sink_relay(seen)
    relay.start()
    try:
        for _ in range(3):
            _post(relay, b'{"session_id":"019f-abc"}')
    finally:
        relay.stop()
    assert seen == ["019f-abc"]


def test_a_changed_session_id_is_reported_again() -> None:
    # Last observation wins: nothing observed rotates an id today, but if a client ever
    # does, the binding must follow it rather than latch onto the first value forever.
    seen: list[str] = []
    relay = _sink_relay(seen)
    relay.start()
    try:
        _post(relay, b'{"session_id":"019f-abc"}')
        _post(relay, b'{"session_id":"019f-def"}')
    finally:
        relay.stop()
    assert seen == ["019f-abc", "019f-def"]


def test_a_body_without_a_session_id_binds_nothing() -> None:
    seen: list[str] = []
    relay = _sink_relay(seen)
    relay.start()
    try:
        _post(relay, b"{}")
    finally:
        relay.stop()
    assert seen == []


def test_a_failing_sink_never_costs_the_client_its_turn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The sink writes to the ledger from a handler thread mid-turn. A locked database
    # must cost the resume, not the answer the user is waiting on.
    def explode(uuid: str) -> None:
        raise RuntimeError("the ledger is locked")

    sink = _Recording()
    previous = set_active(sink)
    relay = MeteringRelay(
        job="J",
        session="S",
        metering=_FakeStore(),
        forwarder=_echo_forwarder,
        session_id_reader=lambda text: "019f-abc",
        session_id_sink=explode,
    )
    relay.start()
    try:
        body = _post(relay, b'{"session_id":"019f-abc"}')
    finally:
        relay.stop()
        set_active(previous)
    assert body == _SSE, "the client still gets its full turn"
    assert capsys.readouterr().err == "", "and no traceback lands on its screen"
