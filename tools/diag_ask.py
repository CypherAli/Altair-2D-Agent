"""Chan doan: kh nao trong luong /api/ask_stream bi cham? Chay: python tools/diag_ask.py"""
import json
import sys
import time
import urllib.request

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "C:/Users/trinh/Downloads/Ali_tool"
Q = "cam on"

def mark(t0, msg):
    print(f"{time.time()-t0:7.1f}s  {msg}", flush=True)

t = time.time()
import ali_studio.server as S
mark(t, "import server")

t = time.time()
ctx, sources, intent, npx = S.prepare_ask(REPO, Q)
mark(t, f"prepare_ask -> intent={intent}, num_predict={npx}, ctx={len(ctx)} chars, sources={sources}")

t = time.time()
ok = S._revive_ollama()
mark(t, f"_revive_ollama -> {ok}")

t = time.time()
body = json.dumps({
    "model": "ai-agent",
    "messages": [{"role": "user", "content": ctx}],
    "stream": True,
    "options": {"temperature": 0.2, "num_ctx": 8192,
                "num_predict": npx, "keep_alive": "30m"},
}).encode()
req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=240) as r:
        first = None
        buf = b""
        n = 0
        while True:
            chunk = r.read(512)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line.startswith(b"{"):
                    continue
                try:
                    tok = json.loads(line.decode()).get("message", {}).get("content", "")
                except Exception:
                    tok = ""
                if tok:
                    n += 1
                    if first is None:
                        first = time.time() - t
                        mark(t, f"token DAU TIEN sau {first:.1f}s")
        mark(t, f"xong: {n} token")
except Exception as ex:
    mark(t, f"LOI ollama chat: {ex}")
