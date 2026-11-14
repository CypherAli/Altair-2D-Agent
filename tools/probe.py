"""Run the in-browser probe: real pointer events and rig maths, no manual clicking.

Starts Altair's server if nothing answers on the port, opens dev-tests.html in
headless Chrome, collects the results the page posts back and exits non-zero on
any failure. Nothing is written to the user's history, notes or settings.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APP = "http://127.0.0.1:8124"
REPORT_PORT = 8799
CHROME_CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def up(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=timeout):
            return True
    except Exception:
        return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def start_app():
    from altair_core.server import serve

    threading.Thread(target=serve, daemon=True).start()
    for _ in range(60):
        if up(APP + "/api/status"):
            return True
        threading.Event().wait(0.1)
    return False


class Collector(BaseHTTPRequestHandler):
    body: list = []

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(size).decode("utf-8", "replace")
        try:
            self.body.append(json.loads(raw))
        except ValueError:
            self.body.append({"error": raw[:200]})
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def log_message(self, *args):
        pass


def find_browser() -> str | None:
    for path in CHROME_CANDIDATES:
        if path and Path(path).exists():
            return path
    return None


def main() -> int:
    if not up(APP + "/api/status"):
        if not port_free(8124):
            print("Port 8124 is used by something that is not Altair.")
            return 2
        if not start_app():
            print("Could not start the Altair server.")
            return 2
        print("server: started on", APP)
    else:
        print("server: reusing", APP)

    if not port_free(REPORT_PORT):
        print(f"Port {REPORT_PORT} is busy; stop the other collector first.")
        return 2

    collector = HTTPServer(("127.0.0.1", REPORT_PORT), Collector)
    threading.Thread(target=collector.serve_forever, daemon=True).start()

    browser = find_browser()
    if not browser:
        print("No Chrome/Edge binary found; skipping the in-browser probe.")
        return 0

    profile = Path(tempfile.mkdtemp(prefix="altair-probe-"))
    shot = profile / "shot.png"
    cmd = [
        browser, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
        f"--user-data-dir={profile}", "--virtual-time-budget=45000",
        "--window-size=440,900", f"--screenshot={shot}",
        "http://127.0.0.1:8124/dev-tests.html",
    ]
    print("browser:", browser)
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)

    if not Collector.body:
        print("probe: no report received (page failed to run?)")
        return 2

    results = Collector.body[0]
    if isinstance(results, dict):
        print("probe: bad report", results)
        return 2

    failed = [r for r in results if not r["ok"]]
    for row in results:
        print(("PASS " if row["ok"] else "FAIL ") + row["name"] + (f"  [{row['detail']}]" if row["detail"] else ""))
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
