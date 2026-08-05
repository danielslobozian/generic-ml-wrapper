# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A local metering relay: forward a client's API traffic and record per-turn usage.

The relay listens on ``127.0.0.1``; the caller points the client at it via the
client's official base-URL override (Claude: ``ANTHROPIC_BASE_URL``). Each request
is forwarded verbatim to the upstream API and the response is streamed straight
back to the client, so the interactive experience is unchanged. While streaming,
the relay tees the response to read the turn's token usage and record it.

The upstream forwarder is injectable so the relay is testable against a fake
upstream; the default talks HTTPS to the real API. When a transcript port is
injected, each metered turn's request, response, and usage are handed to it, so the
run is recorded per call.
"""

from __future__ import annotations

import contextlib
import http.client
import itertools
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import read_usage as _anthropic_usage
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.port.outbound.transcript_call import TranscriptCall
from generic_ml_wrapper.application.wiring import localization as i18n
from generic_ml_wrapper.application.wiring.diagnostics_log import log

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import StreamUsage
    from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
    from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort

    UsageReader = Callable[[str], "StreamUsage | None"]
    MeteredPredicate = Callable[[str, str], bool]
    PathMap = Callable[[str], str]
    SessionIdReader = Callable[[str], "str | None"]
    SessionIdSink = Callable[[str], None]

_ANTHROPIC = "https://api.anthropic.com"


def _claude_metered(method: str, path: str) -> bool:
    """The default metered-turn predicate: a Claude ``POST /v1/messages``."""
    return method == "POST" and path.split("?", 1)[0].endswith("/v1/messages")


# Headers that describe one hop's connection, not the payload; never forwarded.
_HOP_BY_HOP = frozenset(
    {
        "host",
        "content-length",
        "connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailers",
        "upgrade",
        "proxy-authorization",
    }
)


@dataclass(frozen=True)
class UpstreamResponse:
    """An upstream response: a status, headers, and a streaming body."""

    status: int
    headers: list[tuple[str, str]]
    body: Iterable[bytes]


class MeteringRelay:
    """Forward a client's traffic to an upstream API and record each turn's usage."""

    def __init__(  # noqa: PLR0913  (per-client relay knobs, all keyword-only)
        self,
        *,
        job: str,
        session: str,
        metering: PerTurnMeteringPort,
        client: str = "claude",
        transcript: TranscriptPort | None = None,
        forwarder: Callable[[str, str, Mapping[str, str], bytes], UpstreamResponse] | None = None,
        upstream_base: str = _ANTHROPIC,
        path_map: PathMap | None = None,
        usage_reader: UsageReader | None = None,
        is_metered: MeteredPredicate | None = None,
        session_id_reader: SessionIdReader | None = None,
        session_id_sink: SessionIdSink | None = None,
        interceptors: InterceptorChain | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Bind the relay to a run and its metering store.

        Args:
            job: The job the turns belong to.
            session: The session the turns belong to.
            metering: Where per-turn usage is recorded.
            client: The client name, placed in the capability URL for observability.
            transcript: Where each call's request/response/usage is recorded, or ``None``.
            forwarder: The upstream forwarder; defaults to real HTTPS to ``upstream_base``.
            upstream_base: The upstream API base URL for the default forwarder.
            path_map: Maps the incoming request path to the upstream path for the
                default forwarder (e.g. Codex ``/v1/x`` -> ``/backend-api/codex/x``);
                identity when ``None``.
            usage_reader: Reads a turn's usage from a response body; defaults to the
                Anthropic reader. A per-client reader plugs in a different wire shape.
            is_metered: Predicate ``(method, path) -> bool`` selecting the turn
                endpoint; defaults to Claude's ``POST /v1/messages``.
            session_id_reader: Reads the client's own session id from a metered turn's
                *request* body; ``None`` (the default) for clients we hand an id to at
                launch rather than learn one from. Paired with ``session_id_sink``.
            session_id_sink: Receives the id ``session_id_reader`` finds, once per
                distinct value — clients mint it themselves, so this is how the wrapper
                learns which client-side session its named session actually became.
            interceptors: The interceptor chain applied to the wire — ``request`` to
                the outbound body, ``response`` to the captured reply; empty when ``None``.
            clock: Returns the current time (epoch seconds); injectable for tests.
                Used to stamp each turn's timestamp and duration.
        """
        self._job = job
        self._session = session
        self._metering = metering
        self._transcript = transcript
        self._client = client
        # A per-run capability token: the client is pointed at
        # http://127.0.0.1:<port>/<client>/<token>, so only a caller that was handed
        # this base URL (our client) can drive the relay. This is the sole auth guard;
        # the client segment is for observability + a routing sanity check.
        self._token = secrets.token_urlsafe(16)
        self._forward = forwarder or _https_forwarder(upstream_base, path_map)
        self._read_usage = usage_reader or _anthropic_usage
        self._metered = is_metered or _claude_metered
        self._read_session_id = session_id_reader
        self._session_id_sink = session_id_sink
        # The last id handed to the sink. The id is stable for a session's life, so this
        # makes the common case one write per session; it is a "last observation wins"
        # latch rather than a write-once so a client that ever does rotate still lands
        # on its current id.
        self._seen_session_id: str | None = None
        self._interceptors = interceptors or InterceptorChain(())
        self._clock = clock
        self._server: ThreadingHTTPServer | None = None
        # A thread-safe capture counter: the server is threaded, so two concurrent turns
        # must not read-modify-write a shared int (which could collide on a filename).
        self._turns = itertools.count(1)

    def start(self) -> None:
        """Bind an ephemeral local port and serve in a background thread."""
        self._server = _RelayServer(("127.0.0.1", 0), _Handler, self)
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        """Run the accept loop, recording a crash instead of dying silently.

        Per-request failures are handled below (``_Handler._proxy`` and
        ``_RelayServer.handle_error``). This guards the loop *itself*: if it dies, the
        relay stops metering while the client keeps working, and on a daemon thread that
        would otherwise leave no trace at all — the session would just quietly stop being
        recorded, which is worse than a failure you can see.
        """
        server = self._server
        if server is None:  # pragma: no cover  (start() always sets it first)
            return
        try:
            server.serve_forever()
        except Exception as error:  # noqa: BLE001  (a daemon thread's last chance to speak)
            log.error(
                i18n.t("log.gateway_stopped", error=error),
                exc=error,
                key="log.gateway_stopped",
            )

    def stop(self) -> None:
        """Stop serving and release the port."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    @property
    def port(self) -> int:
        """The bound port (only valid after ``start``)."""
        if self._server is None:
            message = "relay is not started"
            raise RuntimeError(message)
        return self._server.server_address[1]

    @property
    def base_url(self) -> str:
        """The capability base URL to point the client at (only valid after ``start``).

        Carries the run's client name (observability) and the per-run token (auth):
        ``http://127.0.0.1:<port>/<client>/<token>``. The client appends its API path
        (e.g. ``/v1/messages``) to this, so requests arrive already authenticated.
        """
        return f"http://127.0.0.1:{self.port}/{self._client}/{self._token}"

    def authorize(self, path: str) -> str | None:
        """Validate a request path's ``/<client>/<token>`` prefix and strip it.

        Args:
            path: The incoming request path.

        Returns:
            The upstream path (prefix removed), or ``None`` if the client segment or
            token does not match this run -- in which case the request is refused.
        """
        prefix = f"/{self._client}/{self._token}"
        if path == prefix:
            return "/"
        if path.startswith(prefix + "/"):
            return path[len(prefix) :]
        return None

    def forward(
        self, method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> UpstreamResponse:
        """Forward one request upstream."""
        return self._forward(method, path, headers, body)

    def now(self) -> float:
        """The current time, from the injected clock."""
        return self._clock()

    def is_metered(self, method: str, path: str) -> bool:
        """Whether a request to ``path`` is a metered turn for this client."""
        return self._metered(method, path)

    def wants_body(self, method: str, path: str) -> bool:
        """Whether the full response body must be captured this request.

        True only when something consumes it -- a metered turn, a ``response``
        interceptor, or raw capture. When False the relay streams the response
        straight through without buffering it in memory.
        """
        return self._metered(method, path) or self._interceptors.has("response")

    def intercept_request(self, body: bytes) -> bytes:
        """Apply ``request`` interceptors to the outbound body (identity if none).

        The body is left byte-for-byte untouched when no ``request`` interceptor is
        configured, so the common path never re-encodes.

        Args:
            body: The raw request body from the client.

        Returns:
            The (possibly transformed) body to forward upstream.
        """
        if not self._interceptors.has("request"):
            return body
        transformed = self._interceptors.apply("request", body.decode("utf-8", "replace"))
        return transformed.encode("utf-8")

    def intercept_response(self, captured: bytes) -> None:
        """Run ``response`` interceptors over the captured body (observe only).

        The response has already streamed to the client, so this is for logging or
        redacting-for-logs; the returned text is intentionally discarded.

        Args:
            captured: The full captured response body.
        """
        if self._interceptors.has("response"):
            self._interceptors.apply("response", captured.decode("utf-8", "replace"))

    def bind_session_id(self, request: bytes) -> None:
        """Hand the client's own session id to the sink, once per distinct value.

        A no-op unless both a reader and a sink are configured. Runs on the metered turn
        because that is the request that carries the id.

        Args:
            request: The request body forwarded upstream.
        """
        if self._read_session_id is None or self._session_id_sink is None:
            return
        found = self._read_session_id(request.decode("utf-8", "replace"))
        if found is None or found == self._seen_session_id:
            return
        self._seen_session_id = found
        self._session_id_sink(found)

    def record(self, request: bytes, captured: bytes, started_at: float) -> None:
        """Record the turn's usage (if any) and its transcript (if configured).

        Args:
            request: The request body forwarded upstream.
            captured: The full response body.
            started_at: The turn's start time (from :meth:`now`), for timestamp/duration.
        """
        usage = self._read_usage(captured.decode("utf-8", "replace"))
        turn: TurnUsage | None = None
        if usage is not None:
            turn = TurnUsage(
                self._session,
                usage.input_tokens,
                usage.output_tokens,
                None,
                usage.model,
                cache_creation_tokens=usage.cache_creation_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                timestamp=started_at,
                duration_s=round(self._clock() - started_at, 3),
                turn_id=usage.turn_id,
            )
            self._metering.record(self._job, turn)
        if self._transcript is not None:
            self._transcript.record(
                TranscriptCall(self._job, self._session, next(self._turns), request, captured, turn)
            )


class _RelayServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        relay: MeteringRelay,
    ) -> None:
        super().__init__(address, handler)
        self.relay = relay

    def handle_error(self, request: object, client_address: object) -> None:  # noqa: ARG002
        """Log a handler thread's uncaught exception instead of printing it.

        The stdlib default writes ``'-' * 40``, a raw traceback, and another rule
        straight to ``sys.stderr``. The relay serves from a daemon thread inside the
        process that launched the client, so that stderr **is the client's screen**: the
        traceback lands on top of a live TUI, cannot be copied before the next redraw
        paints over it, and is preserved nowhere. Route it to the diagnostics sink.

        This is the belt to :meth:`_Handler._proxy`'s braces — that boundary should catch
        everything, so anything arriving here is a bug we still want recorded rather than
        displayed.
        """
        log.error(
            i18n.t("log.gateway_handler_crashed", client=client_address),
            exc=sys.exc_info()[1],
            key="log.gateway_handler_crashed",
        )


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002  (stdlib signature)
        log.debug(i18n.t("log.gateway", message=(format % args if args else format)))

    def _proxy(self) -> None:
        """Proxy one request, with an error boundary around the whole exchange.

        Everything past this point talks to the upstream API over TLS, and a TLS error
        (``ssl.SSLError``, ``SSLEOFError``) can surface at the handshake, mid-stream, or
        anywhere in between. Without this boundary such an exception escapes the handler
        thread, and the stdlib prints it as a raw traceback to a stderr that belongs to
        the client's TUI (issue #59).

        With it, the client gets a clean ``502`` it can retry, and the traceback goes to
        the log file where it can actually be read.
        """
        self._responded = False
        try:
            self._exchange()
        except Exception as error:  # noqa: BLE001  (the boundary: nothing may escape)
            log.error(
                i18n.t("log.gateway_request_failed", method=self.command, path=self.path),
                exc=error,
                key="log.gateway_request_failed",
            )
            self._fail()

    def _fail(self) -> None:
        """Tell the client the gateway failed, if it is still possible to say so.

        Once the response head is on the wire a status can no longer be sent — the client
        sees a truncated stream and its own retry logic takes over, which is the honest
        outcome. Before that, ``502`` says exactly what happened: the relay could not
        complete the upstream call.
        """
        if self._responded:
            return
        # The client being gone too is the ordinary case here; there is then nothing left
        # to report the failure to, and the log already has it.
        with contextlib.suppress(OSError):
            self.send_error(HTTPStatus.BAD_GATEWAY)

    def _exchange(self) -> None:
        relay = cast("_RelayServer", self.server).relay
        # A browser cross-origin POST carries Origin; a real client SDK does not. And
        # any request whose /<client>/<token>/ prefix doesn't match this run is refused,
        # so a stray local process can't drive the relay.
        if self.headers.get("Origin") is not None:
            self.send_error(HTTPStatus.FORBIDDEN)
            self._responded = True
            return
        upstream_path = relay.authorize(self.path)
        if upstream_path is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            self._responded = True
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = relay.intercept_request(self.rfile.read(length) if length else b"")
        # Force an uncompressed upstream response so usage can be read off it; the
        # client accepts identity fine (only the localhost hop loses compression).
        request_headers = {
            name: value for name, value in self.headers.items() if name.lower() != "accept-encoding"
        }
        request_headers["Accept-Encoding"] = "identity"
        started_at = relay.now()
        response = relay.forward(self.command, upstream_path, request_headers, body)

        self.close_connection = True  # signal end-of-stream by closing (no content-length)
        try:
            self.send_response(response.status)
            for name, value in response.headers:
                if name.lower() not in _HOP_BY_HOP:
                    self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
        except OSError:
            pass  # client already gone; still drain upstream below to record usage
        finally:
            # The head is on the wire (or the socket is gone). Either way a status can no
            # longer be sent, so a later failure must not try to.
            self._responded = True

        if relay.wants_body(self.command, upstream_path):
            captured = _tee(response.body, self._write_chunk)
            self._bookkeep(relay, upstream_path, body, captured, started_at)
        else:
            _stream(response.body, self._write_chunk)

    def _bookkeep(
        self,
        relay: MeteringRelay,
        upstream_path: str,
        request: bytes,
        captured: bytes,
        started_at: float,
    ) -> None:
        """Run the post-response work — response interceptors and metering.

        Guarded separately from the exchange: by this point the client already has its
        answer, so a metering or interceptor failure is *our* bookkeeping problem and must
        not be reported as a gateway error. Recording a turn is never worth losing a turn
        over.
        """
        try:
            relay.intercept_response(captured)
            if relay.is_metered(self.command, upstream_path):
                relay.bind_session_id(request)
                relay.record(request, captured, started_at)
        except Exception as error:  # noqa: BLE001  (metering must never break a turn)
            log.warning(
                i18n.t("log.gateway_record_failed", path=upstream_path, error=error),
                key="log.gateway_record_failed",
            )

    def _write_chunk(self, chunk: bytes) -> None:
        self.wfile.write(chunk)
        self.wfile.flush()


def _drain(chunks: Iterable[bytes]) -> Iterable[bytes]:
    """Yield ``chunks``, ending the stream cleanly if the *upstream* read fails.

    The two directions fail independently and were not guarded alike. A write to the
    client raises when it hangs up, and that was handled. But pulling the next chunk
    reaches across TLS to the API, and a connection dropped mid-response raises here —
    ``ssl.SSLError``/``SSLEOFError`` (both ``OSError``) or an ``IncompleteRead``. That
    exception used to escape the handler thread entirely and become a traceback on the
    user's screen (issue #59).

    Ending the iteration instead of propagating means the caller keeps whatever arrived
    before the break, so a turn cut short is still recorded with what it managed to send.

    Args:
        chunks: The upstream response body chunks.

    Yields:
        Each chunk read successfully, stopping at the first read failure.
    """
    iterator = iter(chunks)
    while True:
        try:
            chunk = next(iterator)
        except StopIteration:
            return
        except (OSError, http.client.HTTPException) as error:
            log.warning(
                i18n.t("log.gateway_stream_interrupted", error=error),
                key="log.gateway_stream_interrupted",
            )
            return
        yield chunk


def _stream(chunks: Iterable[bytes], sink: Callable[[bytes], None]) -> None:
    """Stream ``chunks`` to the client without buffering (nothing consumes the body)."""
    for chunk in _drain(chunks):
        try:
            sink(chunk)
        except OSError:
            return  # client hung up; no body to record or capture, so stop


def _tee(chunks: Iterable[bytes], sink: Callable[[bytes], None]) -> bytes:
    """Stream ``chunks`` to ``sink`` while capturing them all for usage extraction.

    If the client hangs up mid-stream (e.g. it exits or cancels), writes raise and
    are swallowed, but the upstream is still drained fully so the turn's usage —
    which arrives at the end — is captured. If the *upstream* fails instead, the
    capture ends there and what arrived so far is returned rather than lost.

    Args:
        chunks: The upstream response body chunks.
        sink: Writes a chunk to the client (may raise ``OSError`` once it hangs up).

    Returns:
        The captured body (complete, or as much of it as arrived).
    """
    captured = bytearray()
    client_gone = False
    for chunk in _drain(chunks):
        captured.extend(chunk)
        if not client_gone:
            try:
                sink(chunk)
            except OSError:
                client_gone = True
    return bytes(captured)


def _https_forwarder(
    base: str, path_map: PathMap | None = None
) -> Callable[[str, str, Mapping[str, str], bytes], UpstreamResponse]:
    parsed = urlsplit(base)
    host = parsed.hostname or ""
    port = parsed.port or 443

    def forward(
        method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> UpstreamResponse:  # pragma: no cover  (real network; verified by a live round-trip)
        connection = http.client.HTTPSConnection(host, port, timeout=600)
        sent = {name: value for name, value in headers.items() if name.lower() not in _HOP_BY_HOP}
        sent["Host"] = host
        up_path = path_map(path) if path_map is not None else path
        connection.request(method, up_path, body=body or None, headers=sent)
        upstream = connection.getresponse()

        def stream() -> Iterable[bytes]:
            try:
                while True:
                    chunk = upstream.read(8192)
                    if not chunk:
                        break
                    yield chunk
            finally:
                connection.close()

        return UpstreamResponse(upstream.status, list(upstream.getheaders()), stream())

    return forward
