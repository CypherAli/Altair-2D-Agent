"""Local Altair HTTP interface; no dependency on the legacy code-review agent."""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import runtime,tts,asr

WEB = Path(__file__).resolve().parent / "web"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, *args):
        pass

    def _json(self, body, code=200):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/status":
            return self._json(runtime.status())
        if path == "/api/settings":
            return self._json({"settings": runtime.load_settings()})
        if path == "/api/history":
            return self._json({"history": runtime.get_history()})
        if path == "/api/notes":
            return self._json({"items": runtime.get_notes()})
        if path == "/api/context":
            return self._json({"context":runtime.get_context()})
        if path == '/api/asr/status':
            return self._json(asr.status())
        if path == '/api/tts/status':
            return self._json(tts.status())
        if path.startswith("/api/"):
            return self._json({"error": "Chức năng này chưa được kết nối trong Altair."}, 404)
        return super().do_GET()

    def do_POST(self):
        # This local app accepts mutation only from its own origin / direct clients.
        origin = self.headers.get("Origin")
        port=self.server.server_port
        if origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
            return self._json({"error": "Origin không hợp lệ."}, 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self._json({"error": "Cross-site request bị từ chối."}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4_300_000:
                return self._json({"error": "Kích thước yêu cầu không hợp lệ."}, 413)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Yêu cầu phải là JSON object.")
            if self.path == "/api/asr":
                return self._json(asr.recognize(data.get("pcm"),data.get("id")))
            if self.path == "/api/asr/stop":
                if not isinstance(data.get("id"),str):raise ValueError("Thiếu mã nhận dạng.")
                asr.cancel(data.get("id"));return self._json({"ok":True})
            if self.path == "/api/stop":
                asr.cancel();tts.cancel()
                runtime.cancel()
                return self._json({"ok": True})
            if self.path=='/api/tts/stop':
                job_id=data.get('id')
                if not isinstance(job_id,str):raise ValueError('Thiếu mã giọng đọc.')
                tts.cancel(job_id)
                return self._json({'ok':True})
            if self.path=='/api/tts':
                audio=tts.synthesize(data.get('text'),data.get('id'),data.get('speed',.95))
                self.send_response(200);self.send_header('Content-Type','audio/wav');self.send_header('Content-Length',str(len(audio)));self.send_header('Cache-Control','no-store');self.end_headers()
                self.wfile.write(audio)
                return
            if self.path == "/api/new":
                asr.cancel();tts.cancel();tts.clear_cache()
                runtime.clear_history()
                return self._json({"ok": True})
            if self.path == "/api/notes":
                runtime.add_note(data.get("text", ""))
                return self._json({"ok": True})
            if self.path == "/api/settings":
                return self._json({"settings": runtime.save_settings(data)})
            if self.path == "/api/ai_off":
                off = bool(data.get("on"))
                runtime.save_settings({"ai_off": "1" if off else "0"})
                if off:
                    asr.cancel();tts.cancel();tts.clear_cache()
                    try:
                        runtime.unload()
                    except OSError as exc:
                        return self._json({"ai_off": True, "unloaded": False, "error": str(exc)}, 503)
                return self._json({"ai_off": off, "unloaded": off})
            if self.path not in ("/api/ask", "/api/ask_stream"):
                return self._json({"error": "Chức năng này chưa được kết nối trong Altair."}, 404)
            question = data.get("q", "")
            if not isinstance(question, str):
                raise ValueError("Câu hỏi phải là chuỗi.")
            if self.path == "/api/ask":
                answer = "".join(runtime.stream_chat(question, data.get("images"), web=data.get("web"),bilingual=data.get("bilingual") is True))
                return self._json({"answer": answer, **runtime.completed_result()})
            return self._stream(question, data.get("images"), data.get("web"), data.get("bilingual") is True)
        except (runtime.BusyError,tts.VoiceBusyError) as exc:
            return self._json({"error": str(exc)}, 409)
        except (ValueError, TypeError) as exc:
            return self._json({"error": str(exc)}, 400)
        except (OSError, RuntimeError) as exc:
            return self._json({"error": str(exc)}, 503)

    def _stream(self, question, images, web=None, bilingual=False):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(value):
            self.wfile.write(("data: " + json.dumps(value, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        generator = runtime.stream_chat(question, images, web=web,bilingual=bilingual)
        try:
            for token in generator:
                emit({"token": token})
            emit({"done": True, **runtime.completed_result()})
        except runtime.CancelledError:
            emit({"done": True, "cancelled": True})
        except (OSError, ValueError, RuntimeError) as exc:
            try:
                emit({"error": str(exc), "done": True})
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        finally:
            generator.close()


H = Handler


def serve():
    ThreadingHTTPServer(("127.0.0.1", 8124), Handler).serve_forever()


if __name__ == "__main__":
    serve()
