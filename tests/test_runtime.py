import base64
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from altair_core import runtime as rt


def events(*records):
    return io.BytesIO(b"".join(json.dumps(row, ensure_ascii=False).encode() + b"\n" for row in records))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        test_root = os.environ.get("ALTAIR_TEST_TMP")
        if test_root:
            Path(test_root).mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.data = patch.object(rt, "DATA", Path(self.temp.name))
        self.data.start()
        rt._cancelled.clear()
        rt._answer_cache.clear()

    def tearDown(self):
        self.data.stop()
        self.temp.cleanup()

    def test_rejects_paid_api_and_excessive_context(self):
        with self.assertRaises(ValueError):
            rt.save_settings({"mode": "api"})
        with self.assertRaises(ValueError):
            rt.save_settings({"num_ctx": 32768})
        rt.save_settings({"mode": "auto", "num_thread": 2})
        self.assertEqual(rt.load_settings()["mode"], "local")
        self.assertEqual(rt.load_settings()["num_thread"], 2)

    def test_message_budget_retains_current_question(self):
        history = [{"q": "q" * 5000, "a": "a" * 5000}]
        messages = rt._messages("Tôi muốn ăn món gì?", history, None)
        self.assertEqual(messages[-1]["content"], "Tôi muốn ăn món gì?")
        self.assertEqual(len(messages), 2)
        with self.assertRaises(ValueError):
            rt._messages("a" * 3001, [], None)

    def test_image_validation(self):
        with self.assertRaises(ValueError):
            rt._messages("Xem ảnh", [], ["invalid!"])
        text = base64.b64encode(b"this is not an image").decode()
        with self.assertRaises(ValueError):
            rt._messages("Xem ảnh", [], [text])
        image = base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode()
        self.assertEqual(rt._messages("Xem ảnh", [], [image])[-1]["images"], [image])

    def test_streams_utf8_and_records_complete_result(self):
        output = events({"message": {"content": "Mình là "}},
                        {"message": {"content": "Altair."}},
                        {"done": True, "eval_count": 6, "eval_duration": 1_000_000_000})
        with patch.object(rt, "_local_request", return_value=output) as request:
            self.assertEqual("".join(rt.stream_chat("Giải thích sự bay hơi.")), "Mình là Altair.")
        body = request.call_args.args[1]
        self.assertEqual(body["model"], "altair")
        self.assertFalse(body["think"])
        self.assertEqual(body["options"]["num_ctx"], 2048)
        self.assertEqual(rt.get_history()[-1]["a"], "Mình là Altair.")

    def test_truncated_stream_is_not_saved(self):
        with patch.object(rt, "_local_request", return_value=events({"message": {"content": "partial"}})):
            with self.assertRaisesRegex(RuntimeError, "kết thúc"):
                list(rt.stream_chat("Một câu hỏi"))
        self.assertEqual(rt.get_history(), [])
        self.assertFalse(rt._inference_lock.locked())

    def test_reasoning_question_does_not_silently_enable_expensive_mode(self):
        output = events({"message": {"content": "Cần tính bằng công cụ."}}, {"done": True})
        with patch.object(rt, "_local_request", return_value=output) as request:
            list(rt.stream_chat("Tổng bao nhiêu phút? Có kịp không?"))
        self.assertFalse(request.call_args.args[1]["think"])

    def test_early_close_releases_lock_without_saving(self):
        output = events({"message": {"content": "partial"}}, {"done": True})
        with patch.object(rt, "_local_request", return_value=output):
            generator = rt.stream_chat("Câu hỏi")
            self.assertEqual(next(generator), "partial")
            with self.assertRaises(rt.BusyError):
                list(rt.stream_chat("Không chạy song song"))
            generator.close()
        self.assertFalse(rt._inference_lock.locked())
        self.assertEqual(rt.get_history(), [])

    def test_cancellation_is_not_saved(self):
        output = events({"message": {"content": "partial"}}, {"done": True})
        with patch.object(rt, "_local_request", return_value=output):
            generator = rt.stream_chat("Câu hỏi")
            next(generator)
            rt.cancel()
            with self.assertRaises(rt.CancelledError):
                list(generator)
        self.assertEqual(rt.get_history(), [])
        self.assertFalse(rt._inference_lock.locked())

    def test_ai_off_never_calls_model(self):
        rt.save_settings({"ai_off": "1"})
        with patch.object(rt, "_local_request") as request:
            with self.assertRaisesRegex(RuntimeError, "đang tắt"):
                list(rt.stream_chat("Giải thích sự bay hơi."))
            request.assert_not_called()

    def test_note_survives_restart_and_is_in_context(self):
        rt.add_note("Tôi thích trà không đường.")
        self.assertIn("trà không đường", rt.get_notes()[0]["text"])
        self.assertIn("trà không đường", rt._messages("Tôi thích uống gì?", [], None)[0]["content"])

    def test_new_session_clears_persistent_history(self):
        rt._write("history.json", [{"q": "cũ", "a": "cũ"}])
        rt.clear_history()
        self.assertEqual(rt.get_history(), [])


if __name__ == "__main__":
    unittest.main()
