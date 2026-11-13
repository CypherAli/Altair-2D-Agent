"""Start Altair's dedicated local runtime and existing WebView2 shell."""
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("ALTAIR_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT))
from altair_core import runtime


def ensure_backend():
    from altair_core.litert_backend import installed
    if not installed():
        raise RuntimeError("Chưa cài model/runtime Altair. Chạy SetupAltair.bat.")


def main():
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ensure_backend()
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                "http://127.0.0.1:8124/api/status", timeout=2) as response:
            import json
            if json.load(response).get("name") != "Altair":
                raise RuntimeError("Cổng 8124 đang được ứng dụng khác sử dụng.")
    except urllib.error.URLError:
        from altair_core.server import serve
        threading.Thread(target=serve, daemon=True).start()
    url = "http://127.0.0.1:8124"
    if "--headless" in sys.argv:
        print("Altair: " + url, flush=True)
        while True:
            time.sleep(1)
    try:
        import webview
    except ImportError:
        import webbrowser
        webbrowser.open(url)
        print("Altair: " + url, flush=True)
        while True:
            time.sleep(1)
    if "--studio" in sys.argv:
        webview.create_window("Altair", url, width=1080, height=780)
    else:
        from altair_core.desktop_pet import create
        create(url)
    webview.start(gui="edgechromium", debug=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Altair: " + str(exc), file=sys.stderr)
        sys.exit(1)
