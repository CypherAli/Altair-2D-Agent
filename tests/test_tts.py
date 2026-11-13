import io,threading,unittest,wave
from unittest.mock import patch,MagicMock
from altair_core import tts,runtime as rt
def wav_bytes():
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as wav:wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(b'\0\0'*2205)
    return buffer.getvalue()
class VoiceTests(unittest.TestCase):
    def setUp(self):tts.clear_cache();tts._cancelled.clear()
    def tearDown(self):tts._active=None;tts.clear_cache();tts._cancelled.clear()
    def test_text_limit_and_cleanup(self):
        for value in ('',' '*5,'a'*501,None,123):
            with self.assertRaises(ValueError):tts.prepare_text(value)
        self.assertEqual(tts.prepare_text('**Chào chủ nhân** [1] https://example.com'),'Chào chủ nhân')
    def test_speed_and_ids_are_validated_without_starting_worker(self):
        for speed in (False,None,-1,100,'abc',float('nan')):
            with self.assertRaises(ValueError):tts.synthesize('Chào chủ nhân',speed=speed)
        with self.assertRaises(ValueError):tts.synthesize('Xin chào',job_id='../bad')
    def test_cancel_does_not_kill_different_job(self):
        process=MagicMock();tts._active=('a'*32,process)
        tts.cancel('b'*32);process.terminate.assert_not_called()
    def test_pre_cancelled_job_does_not_spawn(self):
        tts.cancel('a'*32)
        with patch.object(tts,'installed',return_value=True),patch.object(tts.subprocess,'Popen') as popen:
            with self.assertRaises(tts.VoiceCancelled):tts.synthesize('Chào chủ nhân',job_id='a'*32)
            popen.assert_not_called()
    def test_no_overlap_with_language_model(self):
        with patch.object(tts,'installed',return_value=True):
            rt._inference_lock.acquire()
            try:
                with self.assertRaises(tts.VoiceBusyError):tts.synthesize('Chào chủ nhân')
            finally:rt._inference_lock.release()
        self.assertFalse(tts._lock.locked())
    def test_wave_cache_reuses_audio_without_reloading_model(self):
        process=MagicMock();process.communicate.return_value=(wav_bytes(),b'');process.returncode=0;process.poll.return_value=0
        with patch.object(tts,'installed',return_value=True),patch('altair_core.litert_backend.available_bytes',return_value=2*1024**3),patch.object(tts.subprocess,'Popen',return_value=process) as popen:
            a=tts.synthesize('Chào chủ nhân');b=tts.synthesize('Chào chủ nhân')
            self.assertEqual(a,b);self.assertEqual(popen.call_count,1);self.assertTrue(tts.status()['last']['cached'])
        self.assertFalse(rt._inference_lock.locked());self.assertFalse(tts._lock.locked())
    def test_broken_audio_releases_both_locks(self):
        process=MagicMock();process.communicate.return_value=(b'x'*100,b'');process.returncode=0;process.poll.return_value=0
        with patch.object(tts,'installed',return_value=True),patch('altair_core.litert_backend.available_bytes',return_value=2*1024**3),patch.object(tts.subprocess,'Popen',return_value=process):
            with self.assertRaises(RuntimeError):tts.synthesize('Chào chủ nhân')
        self.assertFalse(rt._inference_lock.locked());self.assertFalse(tts._lock.locked())
    def test_low_ram_does_not_spawn(self):
        with patch.object(tts,'installed',return_value=True),patch('altair_core.litert_backend.available_bytes',return_value=100),patch.object(tts.subprocess,'Popen') as popen:
            with self.assertRaisesRegex(RuntimeError,'RAM'):tts.synthesize('Chào chủ nhân')
            popen.assert_not_called()
        self.assertFalse(rt._inference_lock.locked())
