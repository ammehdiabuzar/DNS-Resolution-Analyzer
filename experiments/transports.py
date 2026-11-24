"""Do53, DoT and DoH clients used for the latency comparison.

dnspython builds and parses the DNS messages; the framing for each transport
is written out here so that what goes on the wire is easy to follow:
  Do53: one DNS message per UDP datagram (port 53)
  DoT : TCP 853 + TLS 1.3, each message prefixed by a 2-byte length (RFC 7858)
  DoH : TCP 443 + TLS 1.3 + HTTP/2, POST /dns-query with
        content-type application/dns-message (RFC 8484)

Each transport offers:
  first_query(name)  -> ms, opening a new connection (TCP + TLS handshakes)
  open(); query_open(name) -> ms; close()   for connection reuse
"""

from __future__ import annotations

import socket
import ssl
import struct
import time

import dns.message
import dns.rdatatype
import httpx

from common import CA_FILE, UNBOUND_IP


class QueryFailed(Exception):
    pass


def _make_query(name: str, qtype: str = "A") -> dns.message.Message:
    return dns.message.make_query(name, qtype)       # RD=1: recursive query to Unbound


def _check(q: dns.message.Message, wire: bytes) -> dns.message.Message:
    r = dns.message.from_wire(wire)
    if r.id != q.id:
        raise QueryFailed("response ID mismatch")
    if not r.answer:
        raise QueryFailed(f"empty answer (rcode {r.rcode()})")
    return r


def tls_context(keylog: str | None, alpn=None) -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=CA_FILE)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    if alpn:
        ctx.set_alpn_protocols(alpn)
    if keylog:
        ctx.keylog_filename = keylog
    return ctx


class Do53:
    name = "do53"

    def __init__(self, server: str = UNBOUND_IP, timeout: float = 1.0, retries: int = 3, **_):
        self.server, self.timeout, self.retries = server, timeout, retries
        self.sock = None

    def _exchange(self, sock: socket.socket, name: str) -> None:
        q = _make_query(name)
        wire = q.to_wire()
        for _ in range(self.retries):
            sock.sendto(wire, (self.server, 53))
            deadline = time.perf_counter() + self.timeout
            while (remaining := deadline - time.perf_counter()) > 0:
                sock.settimeout(remaining)
                try:
                    data, addr = sock.recvfrom(65535)
                except OSError:              # timeout, or ICMP port unreachable
                    break
                if addr[0] == self.server and data[:2] == struct.pack("!H", q.id):
                    _check(q, data)
                    return
        raise QueryFailed(f"no UDP reply after {self.retries} attempts")

    def first_query(self, name: str) -> float:
        t0 = time.perf_counter()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            self._exchange(s, name)
            return (time.perf_counter() - t0) * 1000

    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def query_open(self, name: str) -> float:
        t0 = time.perf_counter()
        self._exchange(self.sock, name)
        return (time.perf_counter() - t0) * 1000

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None


class DoT:
    name = "dot"

    def __init__(self, server: str = UNBOUND_IP, keylog: str | None = None, timeout: float = 15.0, **_):
        self.server, self.timeout = server, timeout
        self.ctx = tls_context(keylog, alpn=["dot"])
        self.sock = None

    def open(self):
        raw = socket.create_connection((self.server, 853), timeout=self.timeout)
        # Disable Nagle, as real DoT stubs do: otherwise the small query waits for the
        # ACK of the TLS Finished (+1 RTT). httpx already does this for DoH.
        raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = self.ctx.wrap_socket(raw, server_hostname=self.server)   # TLS handshake here

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise QueryFailed("DoT connection closed")
            buf += chunk
        return buf

    def query_open(self, name: str) -> float:
        q = _make_query(name)
        wire = q.to_wire()
        t0 = time.perf_counter()
        self.sock.sendall(struct.pack("!H", len(wire)) + wire)
        length = struct.unpack("!H", self._recv_exact(2))[0]
        _check(q, self._recv_exact(length))
        return (time.perf_counter() - t0) * 1000

    def first_query(self, name: str) -> float:
        t0 = time.perf_counter()
        self.open()
        try:
            self.query_open(name)
            return (time.perf_counter() - t0) * 1000
        finally:
            self.close()

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None


class DoH:
    name = "doh"

    def __init__(self, server: str = UNBOUND_IP, keylog: str | None = None, timeout: float = 15.0, **_):
        self.url = f"https://{server}/dns-query"
        self.timeout = timeout
        self.keylog = keylog
        self.client = None

    def open(self):
        # httpx sets ALPN to h2 on this context; the connection opens on the first request.
        self.client = httpx.Client(http1=False, http2=True, verify=tls_context(self.keylog),
                                   timeout=self.timeout, trust_env=False)

    def query_open(self, name: str) -> float:
        q = _make_query(name)
        t0 = time.perf_counter()
        r = self.client.post(self.url, content=q.to_wire(),
                             headers={"content-type": "application/dns-message",
                                      "accept": "application/dns-message"})
        if r.status_code != 200:
            raise QueryFailed(f"HTTP {r.status_code}")
        if r.http_version != "HTTP/2":
            raise QueryFailed(f"expected HTTP/2, got {r.http_version}")
        _check(q, r.content)
        return (time.perf_counter() - t0) * 1000

    def first_query(self, name: str) -> float:
        t0 = time.perf_counter()
        self.open()                          # includes TCP + TLS + HTTP/2 setup on first request
        try:
            self.query_open(name)
            return (time.perf_counter() - t0) * 1000
        finally:
            self.close()

    def close(self):
        if self.client:
            self.client.close()
            self.client = None


TRANSPORTS = [Do53, DoT, DoH]
