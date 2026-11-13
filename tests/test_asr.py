import base64,json,unittest
from unittest.mock import MagicMock,patch
from altair_core import asr,runtime as rt
PCM=base64.b64encode(b'\0\0'*1600).decode()
class ASRTests(unittest.TestCase):
    def tearDown(self):asr._active=None;asr._cancelled.clear()
    def test_audio_validation(self):
        for value in (None,123,'bad','!'*900,base64.b64encode(b'x'*641).decode(),'a'*640004):
            with self.assertRaises(ValueError):asr.validate_audio(value)
        self.assertEqual(len(asr.validate_audio(PCM)),3200)
    def test_model_lock_prevents_parallel_ASR(self):
        with patch.object(asr,'installed',return_value=True):
            rt._inference_lock.acquire()
            try:
                with self.assertRaises(rt.BusyError):asr.recognize(PCM)
            finally:rt._inference_lock.release()
        self.assertFalse(asr._lock.locked())
    def test_low_ram_does_not_spawn(self):
        with patch.object(asr,'installed',return_value=True),patch('altair_core.litert_backend.available_bytes',return_value=100),patch.object(asr.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'RAM'):asr.recognize(PCM)
            spawn.assert_not_called()
        self.assertFalse(rt._inference_lock.locked())
    def test_worker_returns_japanese_and_exits(self):
        process=MagicMock();process.communicate.return_value=(json.dumps({'text':'こんにちは'},ensure_ascii=False).encode(),b'');process.returncode=0;process.poll.return_value=0
        with patch.object(asr,'installed',return_value=True),patch('altair_core.litert_backend.available_bytes',return_value=2*1024**3),patch.object(asr.subprocess,'Popen',return_value=process):
            self.assertEqual(asr.recognize(PCM)['text'],'こんにちは')
        self.assertFalse(rt._inference_lock.locked());self.assertFalse(asr._lock.locked())
    def test_wrong_job_stop_cannot_kill_new_recognition(self):
        process=MagicMock();asr._active=('a'*32,process);asr.cancel('b'*32);process.terminate.assert_not_called()
    def test_cancel_before_spawn_is_honored(self):
        asr.cancel('a'*32)
        with patch.object(asr,'installed',return_value=True),patch('altair_core.litert_backend.available_bytes',return_value=2*1024**3),patch.object(asr.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'dừng'):asr.recognize(PCM,'a'*32)
            spawn.assert_not_called()
    def test_broken_worker_releases_shared_lock(self):
        process=MagicMock();process.communicate.return_value=(b'bad',b'');process.returncode=1;process.poll.return_value=0
        with patch.object(asr,'installed',return_value=True),patch('altair_core.litert_backend.available_bytes',return_value=2*1024**3),patch.object(asr.subprocess,'Popen',return_value=process):
            with self.assertRaises(RuntimeError):asr.recognize(PCM)
        self.assertFalse(rt._inference_lock.locked());self.assertFalse(asr._lock.locked())
