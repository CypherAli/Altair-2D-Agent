import unittest
from altair_core import harness,conversation
class PersonaTests(unittest.TestCase):
    def test_weekday_uses_local_clock_without_search(self):
        for q in ('hôm nay là thứ mấy','hôm nay thứ mấy?'):
            plan=harness.plan(q)
            self.assertEqual(plan.skill,'clock');self.assertIn('Hôm nay là',plan.result.text)
    def test_requested_address_used_for_identity_and_context(self):
        for q in ('Em tên gì?','Chào em','Em làm được gì?'):
            result=harness.plan(q).result
            self.assertIsNotNone(result);self.assertIn('chủ nhân',result.text.lower())
        result=conversation.prepare('Cái đó là gì?').result
        self.assertIn('Chủ nhân',result.text);self.assertIn('Em',result.text)
    def test_persona_does_not_rewrite_quoted_user_memory(self):
        note='Bạn của tôi gọi mình là Qwen; đó là nguyên văn.'
        result=harness.plan('Xem ghi nhớ',notes=[{'text':note}]).result
        self.assertIn(note,result.text)
    def test_open_model_gets_address_instruction(self):
        self.assertIn('xưng em',harness.SYSTEM);self.assertIn('chủ nhân',harness.SYSTEM)
    def test_user_abbreviations_are_not_changed_to_assistant(self):
        self.assertEqual(conversation.abbreviations('mik muốn mua tai nghe'),'mình muốn mua tai nghe')
