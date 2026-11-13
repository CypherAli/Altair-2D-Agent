import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from altair_core import runtime as rt,speech

class SpeechTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.data=rt.DATA;rt.DATA=Path(self.tmp.name);rt.save_settings({'ai_off':'0'});rt._answer_cache.clear()
    def tearDown(self):rt.DATA=self.data;self.tmp.cleanup()
    def test_pair_keeps_languages_separate(self):
        self.assertEqual(speech.split('VI: Em ở đây, chủ nhân.\nJA: ご主人様、ここにおります。'),('Em ở đây, chủ nhân.','ご主人様、ここにおります。'))
    def test_incomplete_translation_is_never_read(self):
        self.assertEqual(speech.split('VI: Kết quả là 4.\nJA: 答えは'),('Kết quả là 4.',None))
    def test_vietnamese_only_stays_text(self):self.assertEqual(speech.split('Em đang ở đây.'),('Em đang ở đây.',None))
    def test_japanese_is_not_mislabeled_as_vietnamese_subtitle(self):
        for raw in ('睡眠は心身の回復と記憶の定着に不可欠です。','VI: 睡眠は心身の回復と記憶の定着に不可欠です。\nJA: 睡眠は大切です。'):
            vi,ja=speech.split(raw)
            self.assertIn('phụ đề tiếng Việt',vi);self.assertIsNone(ja)
    def test_latin_voice_is_not_accepted_as_japanese(self):self.assertIsNone(speech.split('VI: Chào.\nJA: Hello.')[1])
    def test_large_voice_is_not_silently_truncated(self):self.assertIsNone(speech.split('VI: Chào.\nJA: '+'あ'*451+'。')[1])
    def test_unknown_tool_reply_has_no_fake_translation(self):self.assertIsNone(speech.phrase('nhắc gì?', 'Một kết quả rất cụ thể.','conversation-context'))
    def test_greetings_prepare_local_japanese_sample_without_model(self):
        with patch.object(rt,'_local_request',side_effect=AssertionError('Greeting must not load the model')):
            for question in ('xin chào','chào','hello','hi'):
                answer=''.join(rt.stream_chat(question,history=[],remember=False,bilingual=True,web=False))
                metrics=rt.completed_result()['metrics']
                self.assertIn('chủ nhân',answer)
                self.assertEqual(metrics['speech_sample'],'voice-ja-greeting.wav')
                self.assertIn('ご主人様',metrics['speech_text'])
                self.assertEqual(metrics['model_calls'],0)
    def test_text_only_greeting_does_not_schedule_voice(self):
        ''.join(rt.stream_chat('xin chào',history=[],remember=False,bilingual=False,web=False))
        self.assertNotIn('speech_sample',rt.completed_result()['metrics'])
    def test_one_model_call_and_vietnamese_history_only(self):
        raw='VI: Em gợi ý nghỉ mắt hai phút.\nJA: 二分間、目を休めましょう。'
        response=[(json.dumps({'message':{'content':raw}})+'\n').encode(),(json.dumps({'done':True,'eval_count':45})+'\n').encode()]
        class Response(list):
            def close(self):pass
        with patch.object(rt,'_local_request',return_value=Response(response)) as call:
            answer=''.join(rt.stream_chat('Giải thích vì sao ta cần thư giãn.',bilingual=True,web=False))
        self.assertEqual(call.call_count,1);self.assertNotIn('JA:',answer)
        self.assertEqual(rt.completed_result()['metrics']['speech_text'],'二分間、目を休めましょう。')
        self.assertNotIn('二分間',json.dumps(rt.get_history(),ensure_ascii=False))
    def test_bilingual_cache_restores_voice_without_model_reload(self):
        raw='VI: Em gợi ý nghỉ mắt hai phút.\nJA: 二分間、目を休めましょう。'
        class Response(list):
            def close(self):pass
        response=Response([(json.dumps({'message':{'content':raw}})+'\n').encode(),b'{"done":true}\n'])
        with patch.object(rt,'_local_request',return_value=response) as call:
            for _ in range(2):answer=''.join(rt.stream_chat('Giải thích vì sao ta cần thư giãn.',history=[],remember=False,bilingual=True,web=False))
        self.assertEqual(call.call_count,1);self.assertNotIn('JA:',answer);self.assertIn('speech_text',rt.completed_result()['metrics'])
