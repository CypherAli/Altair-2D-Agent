import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from altair_core import litert_backend as native


class FakeConversation:
    def __init__(self):
        self.token_count = 100
        self.closed = False
        self.cancelled = False
        self.calls = 0

    def send_message_async(self, *args, **kwargs):
        self.calls += 1
        yield {"content": [{"type": "text", "text": "Trả lời."}]}

    def get_benchmark_info(self):
        return SimpleNamespace(last_decode_token_count=5, last_decode_tokens_per_second=5)

    def close(self):
        self.closed = True

    def cancel_process(self):
        self.cancelled = True


class NativeLifecycleTests(unittest.TestCase):
    def setUp(self):
        native.unload()
        self.engine = Mock()
        self.convs = []
        def create(**kwargs):
            conv = FakeConversation()
            self.convs.append(conv)
            return conv
        self.engine.create_conversation.side_effect = create
        lm = SimpleNamespace(Message=lambda *a: a, Contents=SimpleNamespace(of=lambda *a: a),
            Content=SimpleNamespace(ImageBytes=lambda **kw: kw),
            ThinkingConfig=lambda **kw: kw, SamplerConfig=lambda **kw: kw)
        self.patches = [patch.object(native, "_get_engine", return_value=(lm, self.engine)),
                        patch.object(native.threading, "Timer"),
                        patch.object(native, "available_bytes", return_value=4 * 1024**3)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        native.unload()
        for item in reversed(self.patches):
            item.stop()

    def stream(self, records):
        return native.Stream({"options": {"num_predict": 64}, "messages": records})

    def test_exact_prefix_reuses_one_conversation(self):
        records = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
        stream = self.stream(records)
        self.assertFalse(json.loads(list(stream)[-1])["prefix_reused"])
        stream.close()
        self.assertIsNotNone(native._cached)
        following = records + [{"role": "assistant", "content": "Trả lời."}, {"role": "user", "content": "tiếp"}]
        self.assertTrue(json.loads(list(self.stream(following))[-1])["prefix_reused"])
        self.assertEqual(len(self.convs), 1)
        self.assertEqual(self.convs[0].calls, 2)

    def test_different_system_closes_old_cache(self):
        list(self.stream([{"role": "system", "content": "a"}, {"role": "user", "content": "q"}]))
        list(self.stream([{"role": "system", "content": "b"}, {"role": "user", "content": "q"}]))
        self.assertTrue(self.convs[0].closed)
        self.assertEqual(len(self.convs), 2)

    def test_image_conversation_is_not_cached(self):
        list(self.stream([{"role": "user", "content": "xem", "images": ["aGk="]}]))
        self.assertIsNone(native._cached)
        self.assertTrue(self.convs[0].closed)

    def test_cancel_discards_incomplete_session(self):
        stream = self.stream([{"role": "user", "content": "q"}])
        generator = iter(stream)
        next(generator)
        stream.close()
        list(generator)
        self.assertTrue(self.convs[0].cancelled)
        self.assertTrue(self.convs[0].closed)
        self.assertIsNone(native._cached)
        self.assertTrue(native._idle.is_set())

    def test_reset_releases_cached_conversation(self):
        list(self.stream([{"role": "user", "content": "q"}]))
        native.reset_session()
        self.assertTrue(self.convs[0].closed)
        self.assertIsNone(native._cached)

    def test_memory_pressure_releases_idle_engine_and_session(self):
        list(self.stream([{"role": "user", "content": "q"}]))
        native._engine = self.engine
        native._idle_deadline = time.monotonic() + 180
        with patch.object(native, "available_bytes", return_value=500 * 1024**2):
            native._idle_unload()
        self.engine.close.assert_called_once()
        self.assertTrue(self.convs[0].closed)
        self.assertIsNone(native._engine)
