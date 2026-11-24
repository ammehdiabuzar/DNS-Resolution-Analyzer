"""Iterative DNS resolver built on raw sockets.

Starting at the root server, the resolver sends non-recursive (RD=0)
queries, follows referrals using glue from the additional section, resolves
nameserver names itself when glue is missing, follows CNAMEs, and falls back
to TCP when a UDP reply has the TC bit set. Every query is recorded as a
Step with its timing, so a lookup can be printed step by step.
"""

from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .message import (TYPES, DNSFormatError, Message, ResourceRecord,
                      build_query, is_subdomain, normalize, parse_message,
                      type_code, type_name)

DEFAULT_ROOTS = [("a.root-servers.lab.", "10.10.1.10")]


class ResolutionError(Exception):
    pass


@dataclass
class Step:
    index: int
    depth: int                 # 0 = main lookup, 1+ = nameserver sub-lookup
    server_ip: str
    server_name: str
    zone: str                  # zone the server was asked as authority for
    qname: str
    qtype: str
    transport: str = "udp"     # "udp", or "udp>tcp" after truncation
    attempts: int = 1
    rtt_ms: float = 0.0
    outcome: str = ""          # referral / answer / cname / nxdomain / nodata / timeout / error
    detail: str = ""
    start_offset_ms: float = 0.0
    response_bytes: int = 0


@dataclass
class Resolution:
    qname: str
    qtype: str
    rcode: str = "SERVFAIL"
    answers: List[ResourceRecord] = field(default_factory=list)
    steps: List[Step] = field(default_factory=list)
    total_ms: float = 0.0
    packets_sent: int = 0      # includes UDP retries and the TCP retry
    sub_lookups: int = 0       # nameserver addresses resolved for missing glue

    @property
    def queries(self) -> int:
        """Number of server queries (steps) needed for the lookup."""
        return len(self.steps)

    def addresses(self) -> List[str]:
        want = type_code(self.qtype)
        return [rr.value_text() for rr in self.answers if rr.rtype == want]

    def to_dict(self) -> dict:
        return {
            "qname": self.qname, "qtype": self.qtype, "rcode": self.rcode,
            "answers": [str(rr) for rr in self.answers],
            "total_ms": round(self.total_ms, 3), "queries": self.queries,
            "packets_sent": self.packets_sent, "sub_lookups": self.sub_lookups,
            "steps": [s.__dict__ for s in self.steps],
        }


class _Context:
    def __init__(self, t0: float):
        self.t0 = t0
        self.steps: List[Step] = []
        self.packets = 0
        self.sub_lookups = 0
        self.ns_addr_cache: Dict[str, List[str]] = {}


class IterativeResolver:
    def __init__(self, roots=None, timeout: float = 1.0, retries: int = 3,
                 max_steps: int = 60, max_depth: int = 4, max_cname: int = 8,
                 on_step: Optional[Callable[[Step], None]] = None,
                 on_event: Optional[Callable[[int, str], None]] = None):
        self.roots = list(roots or DEFAULT_ROOTS)
        self.timeout = timeout
        self.retries = retries
        self.max_steps = max_steps
        self.max_depth = max_depth
        self.max_cname = max_cname
        self.on_step = on_step
        self.on_event = on_event

    # ------------------------------------------------------------------ API
    def resolve(self, name: str, qtype: str = "A") -> Resolution:
        qname, qtype = normalize(name), qtype.upper()
        ctx = _Context(time.perf_counter())
        res = Resolution(qname=qname, qtype=qtype)
        try:
            res.rcode, res.answers = self._resolve(qname, qtype, 0, ctx)
        except ResolutionError as exc:
            self._event(0, f"resolution failed: {exc}")
            res.rcode = "SERVFAIL"
        res.total_ms = (time.perf_counter() - ctx.t0) * 1000
        res.steps, res.packets_sent, res.sub_lookups = ctx.steps, ctx.packets, ctx.sub_lookups
        return res

    # ------------------------------------------------------------ transport
    def _udp(self, ip: str, wire: bytes, qid: int, ctx: _Context) -> Tuple[Optional[bytes], int]:
        attempts = 0
        for _ in range(self.retries):
            attempts += 1
            ctx.packets += 1
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(self.timeout)
                s.sendto(wire, (ip, 53))
                deadline = time.perf_counter() + self.timeout
                while True:
                    remaining = deadline - time.perf_counter()
                    if remaining <= 0:
                        break
                    s.settimeout(remaining)
                    try:
                        data, addr = s.recvfrom(65535)
                    except OSError:          # timeout, or ICMP port unreachable
                        break
                    # Accept only a reply from the queried server with our ID.
                    if addr[0] == ip and len(data) >= 2 and struct.unpack("!H", data[:2])[0] == qid:
                        return data, attempts
        return None, attempts

    def _tcp(self, ip: str, wire: bytes, ctx: _Context) -> Optional[bytes]:
        ctx.packets += 1
        try:
            with socket.create_connection((ip, 53), timeout=self.timeout * self.retries) as s:
                s.sendall(struct.pack("!H", len(wire)) + wire)
                length = struct.unpack("!H", self._recv_exact(s, 2))[0]
                return self._recv_exact(s, length)
        except (OSError, struct.error):
            return None

    @staticmethod
    def _recv_exact(s: socket.socket, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise OSError("connection closed early")
            buf += chunk
        return buf

    def _query(self, ip: str, server_name: str, zone: str, qname: str, qtype: str,
               depth: int, ctx: _Context) -> Tuple[Optional[Message], Step]:
        if len(ctx.steps) >= self.max_steps:
            raise ResolutionError("too many queries for one lookup")
        qid, wire = build_query(qname, qtype)
        step = Step(index=len(ctx.steps) + 1, depth=depth, server_ip=ip,
                    server_name=server_name, zone=zone, qname=qname, qtype=qtype)
        t_start = time.perf_counter()
        step.start_offset_ms = (t_start - ctx.t0) * 1000
        data, step.attempts = self._udp(ip, wire, qid, ctx)
        msg = None
        if data is not None:
            try:
                msg = parse_message(data)
            except DNSFormatError as exc:
                step.outcome, step.detail = "error", f"bad reply: {exc}"
            if msg is not None and msg.header.tc:
                step.transport = "udp>tcp"
                tcp_data = self._tcp(ip, wire, ctx)
                msg = parse_message(tcp_data) if tcp_data else None
                data = tcp_data
        step.rtt_ms = (time.perf_counter() - t_start) * 1000
        step.response_bytes = len(data) if data else 0
        if data is None and not step.outcome:
            step.outcome, step.detail = "timeout", f"no reply after {step.attempts} attempt(s)"
        ctx.steps.append(step)
        return msg, step

    # ------------------------------------------------------------ algorithm
    def _event(self, depth: int, text: str):
        if self.on_event:
            self.on_event(depth, text)

    def _emit(self, step: Step):
        if self.on_step:
            self.on_step(step)

    def _ns_addresses(self, ns: str, depth: int, ctx: _Context) -> List[str]:
        """Resolve a nameserver name that came without glue (sub-lookup)."""
        if ns in ctx.ns_addr_cache:
            return ctx.ns_addr_cache[ns]
        if depth + 1 > self.max_depth:
            raise ResolutionError("nameserver sub-lookups nested too deeply")
        ctx.sub_lookups += 1
        self._event(depth, f"missing glue: resolving nameserver {ns} first")
        rcode, answers = self._resolve(ns, "A", depth + 1, ctx)
        addrs = [rr.value for rr in answers if rr.rtype == TYPES["A"]]
        ctx.ns_addr_cache[ns] = addrs
        self._event(depth, f"nameserver {ns} -> {', '.join(addrs) or rcode}")
        return addrs

    def _resolve(self, qname: str, qtype: str, depth: int,
                 ctx: _Context) -> Tuple[str, List[ResourceRecord]]:
        want = type_code(qtype)
        chain: List[ResourceRecord] = []
        cname_hops = 0
        zone = "."
        servers: List[Tuple[str, Optional[str]]] = list(self.roots)

        while True:
            msg, step = self._ask(zone, servers, qname, qtype, depth, ctx)
            if msg is None:
                return "SERVFAIL", chain

            rcode = msg.rcode_text
            if rcode == "NXDOMAIN":
                step.outcome, step.detail = "nxdomain", f"{qname} does not exist"
                self._emit(step)
                return "NXDOMAIN", chain
            if rcode != "NOERROR":
                step.outcome, step.detail = "error", rcode
                self._emit(step)
                return rcode, chain

            owned = [rr for rr in msg.answers if rr.name == qname]
            direct = [rr for rr in owned if rr.rtype == want]
            cname = next((rr for rr in owned if rr.rtype == TYPES["CNAME"]), None)

            if direct:
                step.outcome = "answer"
                vals = [rr.value_text() for rr in direct]
                step.detail = ", ".join(vals) if len(vals) <= 3 else \
                    f"{len(vals)} records, e.g. {vals[0][:40]}"
                self._emit(step)
                return "NOERROR", chain + direct

            if cname is not None and want != TYPES["CNAME"]:
                chain.append(cname)
                cname_hops += 1
                if cname_hops > self.max_cname:
                    raise ResolutionError("CNAME chain too long")
                target = cname.value
                step.outcome, step.detail = "cname", f"{qname} is an alias for {target}"
                self._emit(step)
                # Use in-message records for the target if the server sent them.
                follow = [rr for rr in msg.answers if rr.name == target and rr.rtype == want]
                if follow:
                    return "NOERROR", chain + follow
                qname, zone, servers = target, ".", list(self.roots)
                continue

            ns_records = [rr for rr in msg.authority if rr.rtype == TYPES["NS"]]
            if ns_records and not msg.header.aa:
                cut = ns_records[0].name
                # A useful referral moves strictly closer to the query name.
                if not is_subdomain(qname, cut) or not is_subdomain(cut, zone) or cut == zone:
                    step.outcome, step.detail = "error", f"lame or upward referral to {cut}"
                    self._emit(step)
                    return "SERVFAIL", chain
                glue = {}
                for rr in msg.additional:
                    if rr.rtype == TYPES["A"]:
                        glue.setdefault(rr.name, []).append(rr.value)
                servers = []
                parts = []
                for ns in ns_records:
                    addrs = glue.get(ns.value)
                    if addrs:
                        servers.extend((ns.value, a) for a in addrs)
                        parts.append(f"{ns.value} (glue {', '.join(addrs)})")
                    else:
                        servers.append((ns.value, None))
                        parts.append(f"{ns.value} (NO glue)")
                zone = cut
                step.outcome = "referral"
                step.detail = f"go to zone {cut}: " + "; ".join(parts)
                self._emit(step)
                continue

            step.outcome, step.detail = "nodata", f"no {qtype} record for {qname}"
            self._emit(step)
            return "NOERROR", chain

    def _ask(self, zone: str, servers, qname: str, qtype: str, depth: int,
             ctx: _Context) -> Tuple[Optional[Message], Optional[Step]]:
        """Query the servers of `zone` in order until one answers."""
        last_step = None
        tried = set()
        for ns, ip in servers:
            candidates = [ip] if ip else self._ns_addresses(ns, depth, ctx)
            for addr in candidates:
                if addr in tried:
                    continue
                tried.add(addr)
                msg, step = self._query(addr, ns, zone, qname, qtype, depth, ctx)
                last_step = step
                if msg is not None:
                    return msg, step
                self._emit(step)          # timeout or bad reply: try the next server
        if last_step is None:
            raise ResolutionError(f"no reachable nameserver for zone {zone}")
        return None, last_step


def format_step(step: Step) -> str:
    indent = "    " * step.depth
    via = "" if step.transport == "udp" else f" [{step.transport}]"
    retry = "" if step.attempts == 1 else f" [{step.attempts} UDP attempts]"
    return (f"{indent}[{step.index:2}] {step.qname} {step.qtype} -> {step.server_ip} "
            f"({step.server_name}, zone {step.zone}){via}{retry}  "
            f"{step.outcome.upper()}: {step.detail}  {step.rtt_ms:.1f} ms")
