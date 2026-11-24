"""Web dashboard for the live POC (standard library only).

    python3 scripts/dashboard.py            # opens http://127.0.0.1:8050
    python3 scripts/dashboard.py --port 9000 --no-browser

It runs the same steps as scripts/demo.py through `docker exec`, but returns
structured results that the page in scripts/dashboard.html draws as a
resolution ladder, latency bars and tables. It also shows the saved
experiment table, plots, Wireshark screenshots and the architecture diagram.

The server listens on 127.0.0.1 only, runs one lab command at a time, and
validates every input before it reaches `docker exec`.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import mimetypes
import os
import re
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PAGE = os.path.join(ROOT, "scripts", "dashboard.html")
CONTAINERS = ["r1", "r2", "root", "tld", "auth", "unbound", "client"]
ROUTERS = ("r1", "r2")
QTYPES = {"A", "NS", "MX", "TXT", "CNAME", "SOA", "AAAA"}
NAME_RE = re.compile(r"^[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})*\.?$")
HOP_NAMES = {"10.10.3.1": "R2", "10.10.2.1": "R1", "10.10.1.10": "root server",
             "10.10.1.11": "TLD server", "10.10.1.12": "authoritative", "10.10.4.10": "Unbound"}
# Folders the page may load files from (images, the diagram).
STATIC_DIRS = ("results/plots", "captures/screenshots/wireshark", "docs")

LOCK = threading.Lock()          # one lab command at a time


class LabError(Exception):
    pass


# ---------------------------------------------------------------- lab calls
def sh(cmd, timeout=180):
    """Run a command; return (exit code, combined output)."""
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise LabError(f"{cmd[0]} not found - is Docker installed?")
    except subprocess.TimeoutExpired:
        raise LabError(f"timed out after {timeout} s: {' '.join(cmd)}")
    return r.returncode, (r.stdout + r.stderr).strip()


def dexec(container, *args, timeout=180):
    return sh(["docker", "exec", container, *args], timeout=timeout)


def require_lab():
    code, out = sh(["docker", "ps", "--format", "{{.Names}}"], timeout=20)
    if code != 0:
        raise LabError("Docker is not running. Start Docker Desktop, then press Start lab.")
    missing = [c for c in CONTAINERS if c not in out.split()]
    if missing:
        raise LabError(f"lab is not running (missing: {', '.join(missing)}). Press Start lab.")


def netem_state():
    """Current impairment on the transit link, read from R1 (both routers match)."""
    code, out = dexec("r1", "/opt/lab/netem.sh", "show", timeout=20)
    if code != 0:
        return None
    delay = re.search(r"delay ([\d.]+)ms", out)
    loss = re.search(r"loss ([\d.]+)%", out)
    one_way = float(delay.group(1)) if delay else 0.0
    return {"rtt_ms": one_way * 2, "loss_pct": float(loss.group(1)) if loss else 0.0, "raw": out}


# ------------------------------------------------------------------ actions
def act_status(_):
    code, out = sh(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"], timeout=20)
    if code != 0:
        return {"docker": False, "containers": {}, "netem": None}
    running = dict(line.split("\t", 1) for line in out.splitlines() if "\t" in line)
    containers = {c: running.get(c, "not running") for c in CONTAINERS}
    netem = netem_state() if "r1" in running else None
    return {"docker": True, "containers": containers, "netem": netem}


def act_start(_):
    code, out = sh(["docker", "compose", "up", "-d"], timeout=900)
    if code != 0:
        raise LabError(out or "docker compose up failed")
    return {"output": out}


def act_topology(_):
    require_lab()
    routes = {r: dexec(r, "ip", "route")[1] for r in ROUTERS}
    _, trace = dexec("client", "traceroute", "-n", "-q", "1", "-w", "2", "10.10.1.10", timeout=60)
    hops = []
    for line in trace.splitlines():
        m = re.match(r"\s*(\d+)\s+(\S+)\s+([\d.]+) ms", line)
        if m:
            hops.append({"hop": int(m.group(1)), "ip": m.group(2), "ms": float(m.group(3)),
                         "name": HOP_NAMES.get(m.group(2), "")})
    return {"routes": routes, "traceroute": trace, "hops": hops}


def act_resolve(body):
    require_lab()
    name = str(body.get("name", "www.example.lab")).strip()
    qtype = str(body.get("qtype", "A")).upper()
    if not NAME_RE.match(name) or len(name) > 253:
        raise LabError(f"not a valid domain name: {name!r}")
    if qtype not in QTYPES:
        raise LabError(f"record type must be one of {', '.join(sorted(QTYPES))}")
    cmd = ["python3", "-m", "dnsresolver", name, "--type", qtype, "--json"]
    code, out = dexec("client", *cmd, timeout=120)
    try:
        data = json.loads(out[out.index("{"):])
    except ValueError:
        raise LabError(out or "resolver produced no output")
    data["command"] = "docker exec client " + " ".join(cmd)
    return data


def act_verify(_):
    require_lab()
    _, trace = dexec("client", "dig", "@10.10.1.10", "www.example.lab", "+trace", "+nodnssec", timeout=60)
    _, out = dexec("client", "python3", "experiments/verify.py", timeout=120)
    rows = []
    for line in out.splitlines():
        m = re.match(r"^(MATCH|DIFF)\s+(\S+)\s+(\S+)\s+ours=(.*)$", line)
        if not m:
            continue
        ours, _, dig = m.group(4).partition("  dig=")
        rows.append({"ok": m.group(1) == "MATCH", "name": m.group(2), "qtype": m.group(3),
                     "ours": _literal(ours), "dig": _literal(dig) if dig else None})
    return {"dig_trace": trace, "rows": rows, "output": out}


def _literal(text):
    try:
        return ast.literal_eval(text.strip())
    except (ValueError, SyntaxError):
        return [text.strip()]


def act_compare(body):
    require_lab()
    n = int(body.get("n", 5))
    if not 1 <= n <= 20:
        raise LabError("n must be between 1 and 20")
    code, out = dexec("client", "python3", "experiments/compare.py", "--n", str(n), "--json", timeout=300)
    try:
        data = json.loads(out[out.index("{"):])
    except ValueError:
        raise LabError(out or "compare.py produced no output")
    data["netem"] = netem_state()
    return data


def act_netem(body):
    require_lab()
    rtt, loss = float(body.get("rtt_ms", 0)), float(body.get("loss_pct", 0))
    if not (0 <= rtt <= 1000 and 0 <= loss <= 50):
        raise LabError("RTT must be 0-1000 ms and loss 0-50 %")
    outputs = []
    for r in ROUTERS:
        if rtt == 0 and loss == 0:
            code, out = dexec(r, "/opt/lab/netem.sh", "clear")
        else:
            code, out = dexec(r, "/opt/lab/netem.sh", "set", f"{rtt / 2:g}", f"{loss:g}")
        if code != 0:
            raise LabError(out)
        outputs.append(out)
    return {"netem": netem_state(), "output": "\n".join(outputs)}


def act_results(_):
    table_md = _read("results/experiment_table.md")
    plots = sorted(f for f in os.listdir(os.path.join(ROOT, "results/plots")) if f.endswith(".png"))
    shots_dir = os.path.join(ROOT, "captures/screenshots/wireshark")
    shots = sorted(f for f in os.listdir(shots_dir) if f.endswith(".png")) if os.path.isdir(shots_dir) else []
    return {"table_md": table_md, "plots": plots, "screenshots": shots, "summary": _summary()}


def _summary():
    """Rows of results/summary.csv (mean, std, min, max of the 3 run means per condition)."""
    rows = []
    try:
        with open(os.path.join(ROOT, "results/summary.csv"), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows.append({"condition": r["condition"], "rtt_ms": float(r["rtt_ms"]),
                             "loss_pct": float(r["loss_pct"]), "metric": r["metric"], "label": r["label"],
                             "mean": float(r["mean"]), "std": float(r["std"] or 0),
                             "min": float(r["min"]), "max": float(r["max"]), "runs": int(r["runs"])})
    except (OSError, KeyError, ValueError):
        pass
    return rows


def _read(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


ACTIONS = {"status": act_status, "start": act_start, "topology": act_topology,
           "resolve": act_resolve, "verify": act_verify, "compare": act_compare,
           "netem": act_netem, "results": act_results}
NO_LOCK = {"status", "results"}      # read-only, may run while a step is busy


# ------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):          # keep the terminal quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            with open(PAGE, "rb") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")
        if path.startswith("/files/"):
            return self._static(path[len("/files/"):])
        if path.startswith("/api/"):
            return self._api(path[len("/api/"):], {})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        except ValueError:
            return self._send(400, {"error": "body must be JSON"})
        if not path.startswith("/api/"):
            return self._send(404, {"error": "not found"})
        self._api(path[len("/api/"):], body)

    def _api(self, name, body):
        action = ACTIONS.get(name)
        if action is None:
            return self._send(404, {"error": f"unknown action {name}"})
        if name not in NO_LOCK and not LOCK.acquire(blocking=False):
            return self._send(409, {"error": "another step is still running"})
        try:
            self._send(200, action(body))
        except LabError as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:                 # report, don't crash the server
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
        finally:
            if name not in NO_LOCK:
                LOCK.release()

    def _static(self, rel):
        full = os.path.realpath(os.path.join(ROOT, rel))
        allowed = any(full.startswith(os.path.normpath(os.path.join(ROOT, d)) + os.sep) for d in STATIC_DIRS)
        if not allowed or not os.path.isfile(full):
            return self._send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as fh:
            self._send(200, fh.read(), ctype)


def main():
    p = argparse.ArgumentParser(description="Web dashboard for the DNS lab POC")
    p.add_argument("--port", type=int, default=8050)
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}"
    print(f"DNS lab dashboard on {url}  (Ctrl+C to stop)", flush=True)
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("\ndashboard stopped")


if __name__ == "__main__":
    main()
