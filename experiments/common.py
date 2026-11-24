"""Shared helpers for code that runs inside the client container."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import Dict, List, Optional

LAB = os.environ.get("LAB_DIR", "/lab")
sys.path.insert(0, os.path.join(LAB, "resolver"))

CLIENT_IP = "10.10.3.10"
UNBOUND_IP = "10.10.4.10"
ROOT_IP = "10.10.1.10"
CA_FILE = os.path.join(LAB, "certs", "ca.pem")
TEST_NAMES = ["www.example.lab", "mail.example.lab", "www.noglue.lab"]
TRANSPORT_NAME = "www.example.lab"


def iface_for(prefix: str = "10.10.3.") -> str:
    out = subprocess.run(["ip", "-o", "-4", "addr", "show"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if parts[3].startswith(prefix):
            return parts[1].split("@")[0]
    raise RuntimeError(f"no interface with an address in {prefix}0/24")


class Capture:
    """Run dumpcap (writes .pcapng natively) for the duration of a with-block."""

    def __init__(self, path: str, iface: Optional[str] = None, bpf: Optional[str] = None):
        self.path = path
        self.iface = iface or iface_for()
        self.bpf = bpf
        self.proc = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if os.path.exists(self.path):
            os.remove(self.path)
        cmd = ["dumpcap", "-q", "-i", self.iface, "-w", self.path]
        if self.bpf:
            cmd += ["-f", self.bpf]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 10
        while time.time() < deadline and not (os.path.exists(self.path) and os.path.getsize(self.path) > 0):
            time.sleep(0.1)
        time.sleep(0.7)        # let the capture settle before traffic starts
        return self

    def __exit__(self, *exc):
        time.sleep(0.5)
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        return False


def tshark_fields(path: str, fields: List[str], display_filter: Optional[str] = None,
                  keylog: Optional[str] = None) -> List[Dict[str, str]]:
    cmd = ["tshark", "-n", "-r", path, "-T", "fields", "-E", "separator=/t",
           "-E", "occurrence=a", "-E", "aggregator=,"]
    if keylog and os.path.exists(keylog):
        cmd += ["-o", f"tls.keylog_file:{keylog}"]
    if display_filter:
        cmd += ["-Y", display_filter]
    for f in fields:
        cmd += ["-e", f]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        vals = line.split("\t")
        vals += [""] * (len(fields) - len(vals))
        rows.append(dict(zip(fields, vals)))
    return rows


def inject_secrets(pcap: str, keylog: str, out: str) -> bool:
    """Embed the TLS key log in the pcapng (Wireshark then decrypts it directly)."""
    if not (os.path.exists(keylog) and os.path.getsize(keylog) > 0):
        return False
    r = subprocess.run(["editcap", "--inject-secrets", f"tls,{keylog}", pcap, out],
                       capture_output=True, text=True)
    return r.returncode == 0
