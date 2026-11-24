"""DNS wire-format encoding and decoding (RFC 1035) using only struct.

No DNS library is used here. The module builds query messages and parses
responses, including name compression pointers (RFC 1035 section 4.1.4).
"""

from __future__ import annotations

import ipaddress
import random
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

TYPES = {
    "A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "PTR": 12, "MX": 15,
    "TXT": 16, "AAAA": 28, "OPT": 41, "ANY": 255,
}
TYPE_NAMES = {v: k for k, v in TYPES.items()}
CLASS_IN = 1
RCODES = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN",
          4: "NOTIMP", 5: "REFUSED"}

HEADER = struct.Struct("!HHHHHH")   # id, flags, qd, an, ns, ar
MAX_POINTER_JUMPS = 32


class DNSFormatError(Exception):
    """Raised when a message cannot be encoded or decoded."""


def type_code(qtype) -> int:
    if isinstance(qtype, int):
        return qtype
    try:
        return TYPES[qtype.upper()]
    except KeyError:
        raise DNSFormatError(f"unknown record type {qtype!r}") from None


def type_name(code: int) -> str:
    return TYPE_NAMES.get(code, f"TYPE{code}")


def normalize(name: str) -> str:
    """Lower-case, fully qualified form ("www.example.lab.")."""
    name = name.strip().lower()
    if name in ("", "."):
        return "."
    return name if name.endswith(".") else name + "."


def is_subdomain(child: str, parent: str) -> bool:
    child, parent = normalize(child), normalize(parent)
    return parent == "." or child == parent or child.endswith("." + parent)


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------

@dataclass
class Header:
    id: int
    flags: int
    qdcount: int = 0
    ancount: int = 0
    nscount: int = 0
    arcount: int = 0

    @property
    def qr(self) -> bool: return bool(self.flags & 0x8000)
    @property
    def opcode(self) -> int: return (self.flags >> 11) & 0xF
    @property
    def aa(self) -> bool: return bool(self.flags & 0x0400)
    @property
    def tc(self) -> bool: return bool(self.flags & 0x0200)
    @property
    def rd(self) -> bool: return bool(self.flags & 0x0100)
    @property
    def ra(self) -> bool: return bool(self.flags & 0x0080)
    @property
    def rcode(self) -> int: return self.flags & 0xF

    def flag_text(self) -> str:
        names = [n for n, on in (("qr", self.qr), ("aa", self.aa), ("tc", self.tc),
                                 ("rd", self.rd), ("ra", self.ra)) if on]
        return " ".join(names)


@dataclass
class Question:
    name: str
    qtype: int
    qclass: int = CLASS_IN

    def __str__(self) -> str:
        return f"{self.name} IN {type_name(self.qtype)}"


@dataclass
class ResourceRecord:
    name: str
    rtype: int
    rclass: int
    ttl: int
    rdata: bytes
    value: object = None          # parsed form (str, tuple, list)

    @property
    def type_text(self) -> str:
        return type_name(self.rtype)

    def value_text(self) -> str:
        v = self.value
        if self.rtype == TYPES["MX"]:
            return f"{v[0]} {v[1]}"
        if self.rtype == TYPES["SOA"]:
            return " ".join(str(x) for x in v)
        if self.rtype == TYPES["TXT"]:
            return " ".join('"' + s + '"' for s in v)
        return str(v)

    def __str__(self) -> str:
        return f"{self.name}\t{self.ttl}\tIN\t{self.type_text}\t{self.value_text()}"


@dataclass
class Message:
    header: Header
    questions: List[Question] = field(default_factory=list)
    answers: List[ResourceRecord] = field(default_factory=list)
    authority: List[ResourceRecord] = field(default_factory=list)
    additional: List[ResourceRecord] = field(default_factory=list)
    size: int = 0

    @property
    def rcode_text(self) -> str:
        return RCODES.get(self.header.rcode, f"RCODE{self.header.rcode}")


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------

def encode_name(name: str) -> bytes:
    """Encode a domain name as a sequence of length-prefixed labels."""
    name = normalize(name)
    if name == ".":
        return b"\x00"
    out = bytearray()
    for label in name[:-1].split("."):
        raw = label.encode("ascii")
        if not raw:
            raise DNSFormatError(f"empty label in {name!r}")
        if len(raw) > 63:
            raise DNSFormatError(f"label longer than 63 octets in {name!r}")
        out.append(len(raw))
        out += raw
    out.append(0)
    if len(out) > 255:
        raise DNSFormatError(f"name longer than 255 octets: {name!r}")
    return bytes(out)


def build_query(name: str, qtype="A", qid: Optional[int] = None,
                rd: bool = False) -> Tuple[int, bytes]:
    """Build a standard query. Iterative queries use RD=0 (the default)."""
    if qid is None:
        qid = random.SystemRandom().randrange(0, 65536)
    flags = 0x0100 if rd else 0x0000            # QR=0, OPCODE=0, RD bit
    header = HEADER.pack(qid, flags, 1, 0, 0, 0)
    question = encode_name(name) + struct.pack("!HH", type_code(qtype), CLASS_IN)
    return qid, header + question


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------

def decode_name(buf: bytes, offset: int) -> Tuple[str, int]:
    """Decode a (possibly compressed) name.

    Returns the name and the offset just after the name *in the original
    position* (a pointer occupies two bytes and ends the name there).
    """
    labels: List[str] = []
    end_offset: Optional[int] = None
    jumps = 0
    pos = offset
    while True:
        if pos >= len(buf):
            raise DNSFormatError("name runs past end of message")
        length = buf[pos]
        kind = length & 0xC0
        if kind == 0xC0:                         # compression pointer
            if pos + 1 >= len(buf):
                raise DNSFormatError("truncated compression pointer")
            target = ((length & 0x3F) << 8) | buf[pos + 1]
            if end_offset is None:
                end_offset = pos + 2
            jumps += 1
            if jumps > MAX_POINTER_JUMPS or target >= len(buf):
                raise DNSFormatError("compression pointer loop or bad target")
            pos = target
            continue
        if kind != 0:
            raise DNSFormatError(f"unsupported label type 0x{kind:02x}")
        pos += 1
        if length == 0:
            break
        if pos + length > len(buf):
            raise DNSFormatError("label runs past end of message")
        labels.append(buf[pos:pos + length].decode("ascii", errors="replace").lower())
        pos += length
    if end_offset is None:
        end_offset = pos
    return (".".join(labels) + "." if labels else "."), end_offset


def _parse_rdata(buf: bytes, offset: int, rdlen: int, rtype: int):
    rdata = buf[offset:offset + rdlen]
    if rtype == TYPES["A"]:
        if rdlen != 4:
            raise DNSFormatError("A record with length != 4")
        return str(ipaddress.IPv4Address(rdata))
    if rtype == TYPES["AAAA"]:
        if rdlen != 16:
            raise DNSFormatError("AAAA record with length != 16")
        return str(ipaddress.IPv6Address(rdata))
    if rtype in (TYPES["NS"], TYPES["CNAME"], TYPES["PTR"]):
        return decode_name(buf, offset)[0]       # may point anywhere in buf
    if rtype == TYPES["MX"]:
        pref = struct.unpack_from("!H", buf, offset)[0]
        return pref, decode_name(buf, offset + 2)[0]
    if rtype == TYPES["SOA"]:
        mname, pos = decode_name(buf, offset)
        rname, pos = decode_name(buf, pos)
        return (mname, rname) + struct.unpack_from("!IIIII", buf, pos)
    if rtype == TYPES["TXT"]:
        strings, pos = [], 0
        while pos < rdlen:
            n = rdata[pos]
            strings.append(rdata[pos + 1:pos + 1 + n].decode("utf-8", errors="replace"))
            pos += 1 + n
        return strings
    return rdata.hex()


def _parse_rr(buf: bytes, offset: int) -> Tuple[ResourceRecord, int]:
    name, offset = decode_name(buf, offset)
    if offset + 10 > len(buf):
        raise DNSFormatError("resource record header truncated")
    rtype, rclass, ttl, rdlen = struct.unpack_from("!HHIH", buf, offset)
    offset += 10
    if offset + rdlen > len(buf):
        raise DNSFormatError("rdata runs past end of message")
    value = _parse_rdata(buf, offset, rdlen, rtype)
    rr = ResourceRecord(name, rtype, rclass, ttl, buf[offset:offset + rdlen], value)
    return rr, offset + rdlen


def parse_message(buf: bytes) -> Message:
    if len(buf) < HEADER.size:
        raise DNSFormatError("message shorter than 12-byte header")
    header = Header(*HEADER.unpack_from(buf, 0))
    msg = Message(header=header, size=len(buf))
    offset = HEADER.size
    for _ in range(header.qdcount):
        name, offset = decode_name(buf, offset)
        if offset + 4 > len(buf):
            raise DNSFormatError("question truncated")
        qtype, qclass = struct.unpack_from("!HH", buf, offset)
        offset += 4
        msg.questions.append(Question(name, qtype, qclass))
    # A truncated (TC=1) UDP reply may legitimately stop early: keep what parses.
    for section, count in ((msg.answers, header.ancount),
                           (msg.authority, header.nscount),
                           (msg.additional, header.arcount)):
        for _ in range(count):
            try:
                rr, offset = _parse_rr(buf, offset)
            except DNSFormatError:
                if header.tc:
                    return msg
                raise
            section.append(rr)
    return msg
