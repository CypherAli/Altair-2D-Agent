"""Altair terminal entrypoint. Start with python agent/main.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from altair_native import ensure_backend
from altair_core import runtime


def main():
    ensure_backend()
    print("Altair local. /new, /status, /quit hoặc nhập câu hỏi.")
    while True:
        try:
            question = input("Bạn > ").strip()
            if question in ("/quit", "exit"):
                break
            if question == "/new":
                runtime.clear_history()
                continue
            if question == "/status":
                print(runtime.status())
                continue
            if not question:
                continue
            print("Altair > ", end="", flush=True)
            for token in runtime.stream_chat(question):
                print(token, end="", flush=True)
            print()
        except (EOFError, KeyboardInterrupt):
            runtime.cancel()
            break
        except (RuntimeError, ValueError, OSError) as exc:
            print(str(exc))


if __name__ == "__main__":
    main()
