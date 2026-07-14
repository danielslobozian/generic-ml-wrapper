# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the metering relay, driven over a real local socket with a fake upstream."""

import http.client
from collections.abc import Mapping

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import StreamUsage
from generic_ml_wrapper.adapter.outbound.gateway.relay import MeteringRelay, UpstreamResponse, _tee
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.transcript import TranscriptCall, TranscriptPort

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
