"""Do thoi gian tra loi Ali that: dem tu luc gui den khi nhan su kien done.
Chay: python tools/time_ask.py "<cau hoi>" [mode] [repo]
"""
import json
import sys
import time
import urllib.request


def timed_ask(q, mode, repo, label):
    body = json.dumps({"q": q, "mode": mode, "repo": repo}).encode()
    req = urllib.request.Request("http://localhost:8123/api/ask_stream", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        buf = b""
        n = 0
        while True:
            chunk = r.read(512)
            if not chunk:
                break
            buf += chunk
            while b"\n\n" in buf:
                line, buf = buf.split(b"\n\n", 1)
                if not line.startswith(b"data:"):
                    continue
                try:
                    j = json.loads(line[5:].decode())
                except Exception:
                    continue
                n += 1
                if j.get("done"):
                    dt = time.time() - t0
                    print(f"{label}: {dt:.1f}s ({n} su kien)")
                    return dt
    print(f"{label}: KHONG nhan duoc done sau {time.time() - t0:.1f}s")
    return None


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "review extension/panel.js: 3 loi that FILE:DONG"
    mode = sys.argv[2] if len(sys.argv) > 2 else "nhanh"
    repo = sys.argv[3] if len(sys.argv) > 3 else "C:/Users/trinh/Downloads/Ali_tool"
    timed_ask(q, mode, repo, f"[{mode}] {q[:40]}")
