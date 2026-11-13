"""Local LiteRT adapter exposing the small transport contract used by runtime.py."""
from __future__ import annotations
import base64
import io
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(os.environ.get("ALTAIR_ROOT", Path(__file__).resolve().parents[1]))
MODEL_PATH = Path(os.environ.get("ALTAIR_MODEL_PATH", ROOT / ".altair-runtime/litert/altair.litertlm"))
DEPS = Path(os.environ.get("ALTAIR_PYTHON_DEPS", ROOT / ".altair-runtime/python"))
_lock = threading.RLock()
_engine = None
_configuration = None
_conversation = None
_timer = None
_cached = None
_cached_prefix = None
_idle_deadline = 0.0
_idle = threading.Event()
_idle.set()


def installed():
    return MODEL_PATH.is_file() and (DEPS / "litert_lm").is_dir()


def memory_bytes():
    if sys.platform != "win32":
        return 0
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
            "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    process = kernel.GetCurrentProcess()
    if get_memory(process, ctypes.byref(counters), counters.cb):
        return counters.WorkingSetSize
    return 0


def loaded():
    with _lock:
        return [{"name": "altair", "size": memory_bytes(), "size_vram": 0}] if _engine else []


def available_bytes():
    if sys.platform != "win32":
        return None
    import ctypes
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    return status.available if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None


def _clear_cached():
    global _cached, _cached_prefix
    if _cached is not None:
        _cached.close()
    _cached = _cached_prefix = None


def reset_session():
    with _lock:
        if _idle.is_set():
            _clear_cached()


def _module():
    if not installed():
        raise RuntimeError("Chưa cài Gemma mobile/LiteRT. Chạy SetupAltair.bat.")
    if str(DEPS) not in sys.path:
        sys.path.insert(0, str(DEPS))
    import litert_lm
    litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)
    return litert_lm


def _get_engine(options):
    global _engine, _configuration, _timer
    lm = _module()
    configuration = (int(options.get("num_ctx", 2048)), int(options.get("num_thread", 4)))
    with _lock:
        if _timer:
            _timer.cancel()
            _timer = None
        if _engine and _configuration != configuration:
            _clear_cached()
            _engine.close()
            _engine = None
        if _engine is None:
            free = available_bytes()
            if free is not None and free < 1300 * 1024**2:
                raise RuntimeError("RAM trống đang thấp. Đóng bớt ứng dụng để hỏi model; tính toán và Sudoku vẫn dùng được khi tắt AI.")
            cache = MODEL_PATH.parent / "cache"
            cache.mkdir(parents=True, exist_ok=True)
            _engine = lm.Engine(str(MODEL_PATH),
                backend=lm.Backend.CPU(thread_count=configuration[1]),
                vision_backend=lm.Backend.CPU(thread_count=configuration[1]),
                max_num_tokens=configuration[0], max_num_images=1,
                cache_dir=str(cache), enable_benchmark=True)
            _configuration = configuration
        return lm, _engine


def cancel():
    with _lock:
        if _conversation is not None:
            _conversation.cancel_process()


def unload():
    global _engine, _configuration, _timer
    cancel()
    if not _idle.wait(15):
        raise RuntimeError("Model vẫn đang dừng, chưa thể xác nhận đã giải phóng RAM.")
    with _lock:
        if _timer:
            _timer.cancel()
            _timer = None
        _clear_cached()
        if _engine is not None:
            _engine.close()
            _engine = None
        _configuration = None


def _idle_unload():
    global _timer
    with _lock:
        if not _idle.is_set():
            return
        free = available_bytes()
        if time.monotonic() >= _idle_deadline or (free is not None and free < 900 * 1024**2):
            unload()
        else:
            _timer = threading.Timer(min(10, max(.1, _idle_deadline - time.monotonic())), _idle_unload)
            _timer.daemon = True
            _timer.start()


class Stream:
    def __init__(self, body):
        self.body = body
        self.cancelled = threading.Event()

    def close(self):
        self.cancelled.set()
        cancel()

    def __iter__(self):
        global _conversation, _timer, _cached, _cached_prefix, _idle_deadline
        options = self.body["options"]
        _idle.clear()
        conv = None
        complete = False
        reply = []
        records = self.body["messages"]
        has_image = bool(records[-1].get("images"))
        prefix = [(row["role"], row["content"]) for row in records[:-1]]
        reused = False
        try:
            lm, engine = _get_engine(options)
            if self.cancelled.is_set():
                return
            messages = [lm.Message(row["role"], lm.Contents.of(row["content"])) for row in records[:-1]]
            with _lock:
                if not has_image and _cached is not None and _cached_prefix == prefix and _cached.token_count < 1200:
                    conv, reused = _cached, True
                    _cached = _cached_prefix = None
                else:
                    _clear_cached()
            if conv is None:
                conv = engine.create_conversation(messages=messages,
                    thinking_config=lm.ThinkingConfig(enable_thinking=False, thinking_token_budget=0),
                    sampler_config=lm.SamplerConfig(temperature=.2, top_k=40, top_p=.9, seed=42),
                    max_output_tokens=int(options.get("num_predict", 160)))
            with _lock:
                _conversation = conv
            if self.cancelled.is_set():
                return
            last = records[-1]
            parts = [last["content"]]
            parts.extend(lm.Content.ImageBytes(bytes=base64.b64decode(image)) for image in last.get("images", []))
            for chunk in conv.send_message_async(lm.Contents.of(*parts), max_output_tokens=int(options.get("num_predict", 160))):
                if self.cancelled.is_set():
                    return
                for content in chunk.get("content", []):
                    if content.get("type") == "text" and content.get("text"):
                        reply.append(content["text"])
                        yield (json.dumps({"message": {"content": content["text"]}}, ensure_ascii=False) + "\n").encode()
            if not self.cancelled.is_set():
                metrics = conv.get_benchmark_info()
                count = metrics.last_decode_token_count
                speed = metrics.last_decode_tokens_per_second
                complete = True
                yield (json.dumps({"done": True, "eval_count": count,
                    "eval_duration": int(count / speed * 1e9) if speed else 0,
                    "done_reason": "limit_or_stop", "prefix_reused": reused}) + "\n").encode()
        finally:
            with _lock:
                _conversation = None
                if conv and complete and not self.cancelled.is_set() and not has_image and conv.token_count < 1200:
                    _cached = conv
                    _cached_prefix = [(row["role"], row["content"]) for row in records] + [("assistant", "".join(reply).strip())]
                elif conv:
                    conv.close()
                _idle.set()
                free = available_bytes()
                _idle_deadline = time.monotonic() + (180 if free is None or free >= 2 * 1024**3 else 45)
                if _engine is not None:
                    _timer = threading.Timer(10, _idle_unload)
                    _timer.daemon = True
                    _timer.start()


def request(path, body=None, timeout=5):
    del timeout
    if path == "/api/chat":
        return Stream(body)
    if path == "/api/tags":
        data = {"models": [{"name": "altair"}] if installed() else []}
    elif path == "/api/ps":
        data = {"models": loaded()}
    elif path == "/api/generate" and body.get("keep_alive") == 0:
        unload()
        data = {"done": True}
    else:
        raise ValueError("Unsupported local LiteRT transport request: " + path)
    return io.BytesIO(json.dumps(data).encode())
