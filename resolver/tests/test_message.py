"""Unit tests for DNS wire-format encoding/decoding.

Run from the repository root:
    python -m unittest discover -s resolver/tests -t resolver
If dnspython is installed (it is in the client container), our parser is
also cross-checked against dnspython on the same bytes.
"""

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dnsresolver.message import (DNSFormatError, build_query, decode_name,  # noqa: E402
                                  encode_name, is_subdomain, parse_message)

try:
    import dns.message
    import dns.rrset
    HAVE_DNSPYTHON = True
except ImportError:
    HAVE_DNSPYTHON = False


def make_response() -> bytes:
    """A referral-style response built by hand, using compression pointers.

    Question: www.example.lab A
    Authority: example.lab NS ns1.example.lab
    Additional: ns1.example.lab A 10.10.1.12
    """
    hdr = struct.pack("!HHHHHH", 0x1234, 0x8000, 1, 0, 1, 1)
    q = encode_name("www.example.lab") + struct.pack("!HH", 1, 1)
    # offset of "example.lab" inside the question name = 12 + 4 ("\x03www")
    ptr_example = struct.pack("!H", 0xC000 | 16)
    ns_rdata = b"\x03ns1" + ptr_example
    auth = ptr_example + struct.pack("!HHIH", 2, 1, 86400, len(ns_rdata)) + ns_rdata
    ns_name_offset = 12 + len(q) + len(ptr_example) + 10      # start of ns_rdata
    ptr_ns1 = struct.pack("!H", 0xC000 | ns_name_offset)
    add = ptr_ns1 + struct.pack("!HHIH", 1, 1, 86400, 4) + bytes([10, 10, 1, 12])
    return hdr + q + auth + add


class EncodeTests(unittest.TestCase):
    def test_encode_name(self):
        self.assertEqual(encode_name("www.example.lab"), b"\x03www\x07example\x03lab\x00")
        self.assertEqual(encode_name("www.example.lab."), b"\x03www\x07example\x03lab\x00")
        self.assertEqual(encode_name("."), b"\x00")

    def test_label_too_long(self):
        with self.assertRaises(DNSFormatError):
            encode_name("a" * 64 + ".lab")

    def test_build_query_layout(self):
        qid, wire = build_query("www.example.lab", "A", qid=0xABCD)
        self.assertEqual(qid, 0xABCD)
        self.assertEqual(wire[:12], struct.pack("!HHHHHH", 0xABCD, 0, 1, 0, 0, 0))
        self.assertEqual(wire[12:], b"\x03www\x07example\x03lab\x00\x00\x01\x00\x01")

    def test_build_query_rd_flag(self):
        _, wire = build_query("a.lab", "MX", qid=1, rd=True)
        self.assertEqual(struct.unpack("!H", wire[2:4])[0], 0x0100)
        self.assertEqual(wire[-4:], b"\x00\x0f\x00\x01")


class DecodeTests(unittest.TestCase):
    def test_decode_with_pointer(self):
        buf = make_response()
        name, end = decode_name(buf, 12)
        self.assertEqual(name, "www.example.lab.")
        self.assertEqual(end, 12 + 17)

    def test_pointer_loop_is_rejected(self):
        buf = b"\x00" * 12 + b"\xc0\x0c"          # pointer to itself
        with self.assertRaises(DNSFormatError):
            decode_name(buf, 12)

    def test_parse_referral(self):
        msg = parse_message(make_response())
        self.assertTrue(msg.header.qr)
        self.assertFalse(msg.header.aa)
        self.assertEqual(msg.questions[0].name, "www.example.lab.")
        self.assertEqual(msg.authority[0].name, "example.lab.")
        self.assertEqual(msg.authority[0].value, "ns1.example.lab.")
        self.assertEqual(msg.additional[0].name, "ns1.example.lab.")
        self.assertEqual(msg.additional[0].value, "10.10.1.12")

    def test_truncated_header(self):
        with self.assertRaises(DNSFormatError):
            parse_message(b"\x00\x01")

    def test_is_subdomain(self):
        self.assertTrue(is_subdomain("www.example.lab", "lab"))
        self.assertTrue(is_subdomain("lab.", "."))
        self.assertFalse(is_subdomain("www.badexample.lab", "example.lab"))


@unittest.skipUnless(HAVE_DNSPYTHON, "dnspython not installed")
class CrossCheckWithDnspython(unittest.TestCase):
    def test_our_query_parses_in_dnspython(self):
        _, wire = build_query("mail.example.lab", "MX", qid=7)
        m = dns.message.from_wire(wire)
        self.assertEqual(m.id, 7)
        self.assertEqual(m.question[0].to_text(), "mail.example.lab. IN MX")

    def test_dnspython_response_parses_in_ours(self):
        q = dns.message.make_query("big.example.lab", "TXT")
        r = dns.message.make_response(q)
        r.answer.append(dns.rrset.from_text("big.example.lab.", 300, "IN", "TXT", '"hello" "world"'))
        r.answer.append(dns.rrset.from_text("big.example.lab.", 300, "IN", "MX", "10 mail.example.lab."))
        r.authority.append(dns.rrset.from_text("example.lab.", 300, "IN", "SOA",
                           "ns1.example.lab. hostmaster.example.lab. 1 2 3 4 5"))
        ours = parse_message(r.to_wire())          # dnspython compresses names
        self.assertEqual(ours.answers[0].value, ["hello", "world"])
        self.assertEqual(ours.answers[1].value, (10, "mail.example.lab."))
        self.assertEqual(ours.authority[0].value[:3],
                         ("ns1.example.lab.", "hostmaster.example.lab.", 1))

    def test_hand_built_response_matches_dnspython(self):
        theirs = dns.message.from_wire(make_response())
        ours = parse_message(make_response())
        self.assertEqual(theirs.authority[0].name.to_text(), ours.authority[0].name)
        self.assertEqual(theirs.additional[0][0].address, ours.additional[0].value)


if __name__ == "__main__":
    unittest.main()
