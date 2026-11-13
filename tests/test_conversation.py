import copy,io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from altair_core import conversation as c,runtime as rt,search

def stream(text='Phản hồi thử'):
    return io.BytesIO((json.dumps({'message':{'content':text}},ensure_ascii=False)+'\n'+json.dumps({'done':True})+'\n').encode())

class ContextTests(unittest.TestCase):
    def setUp(self):
        parent=os.environ.get('ALTAIR_TEST_TMP');self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.data=patch.object(rt,'DATA',Path(self.temp.name));self.data.start();rt._answer_cache.clear()
    def tearDown(self):self.data.stop();self.temp.cleanup()
    def say(self,q,**kw):return ''.join(rt.stream_chat(q,**kw))

    def test_latest_values_supersede_old_in_prompt(self):
        self.say('Tôi muốn ăn tối, ngân sách 100k');self.say('Sửa ngân sách thành 120k')
        with patch.object(rt,'_local_request',return_value=stream()) as call:self.say('Gợi ý món phù hợp đi',web=False)
        system=call.call_args.args[1]['messages'][0]['content']
        self.assertIn('120000',system);self.assertNotIn('100000',system)

    def test_correction_uses_context_without_old_raw_history(self):
        self.say('Tôi muốn ăn tối, ngân sách 100k')
        with patch.object(rt,'_local_request',return_value=stream()) as call:self.say('Sửa ngân sách thành 120k, gợi ý bữa tối',web=False)
        messages=call.call_args.args[1]['messages']
        self.assertEqual(len(messages),2);self.assertIn('120000',messages[0]['content']);self.assertNotIn('100000',messages[0]['content'])

    def test_recommendation_is_not_replaced_by_acknowledgement(self):
        with patch.object(rt,'_local_request',return_value=stream('Gợi ý thử')) as call:
            answer=self.say('Tôi có 100k muốn ăn tối, gợi ý món phù hợp',web=False)
        self.assertTrue(call.called);self.assertEqual(answer,'Gợi ý thử');self.assertEqual(c.active(rt.get_context())['slots']['budget'],'100000')

    def test_cancel_context_update_does_not_commit(self):
        self.say('Ngân sách 100k');before=rt.get_context()
        gen=rt.stream_chat('Sửa ngân sách thành 120k');next(gen);rt.cancel()
        with self.assertRaises(rt.CancelledError):list(gen)
        self.assertEqual(before,rt.get_context())

    def test_failed_model_does_not_commit_partial_context(self):
        self.say('Ngân sách 100k');before=rt.get_context()
        with patch.object(rt,'_local_request',side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):self.say('Tôi có 200k, gợi ý món phù hợp',web=False)
        self.assertEqual(before,rt.get_context())

    def test_forget_cannot_resurrect_old_history(self):
        self.say('Tôi muốn ăn tối, ngân sách 100k');rt.add_note('Ghi nhớ riêng thử nghiệm')
        self.say('Quên hết bối cảnh');self.assertFalse(rt.get_context()['frames'])
        self.assertEqual(len(rt.get_history()),1);self.assertEqual(len(rt.get_notes()),1)
        self.assertIn('chưa có đủ bối cảnh',self.say('Cái đó bao nhiêu?'))

    def test_new_session_clears_context_and_cache(self):
        self.say('Ngân sách 100k');rt._answer_cache['fixture']=(0,'a');rt.clear_history()
        self.assertFalse(rt.get_context()['frames']);self.assertFalse(rt._answer_cache)

    def test_context_survives_disk_reload(self):
        self.say('Tôi muốn ăn tối, ngân sách 100k');self.say('Sửa ngân sách thành 120k')
        saved=json.loads((rt.DATA/'conversation.json').read_text(encoding='utf-8'))
        self.assertEqual(c.active(c.bounded(saved))['slots']['budget'],'120000')

    def test_more_than_history_limit_keeps_current_budget(self):
        self.say('Tôi muốn ăn tối, ngân sách 100k');self.say('A 80k, B 120k');self.say('Sửa ngân sách thành 110k')
        for _ in range(8):self.say('Còn A?')
        self.assertEqual(len(rt.get_history()),6);self.assertEqual(c.active(rt.get_context())['slots']['budget'],'110000')

    def test_remember_false_never_writes_context(self):
        self.say('Tôi muốn ăn tối, ngân sách 100k',history=[],remember=False)
        self.assertFalse((rt.DATA/'conversation.json').exists());self.assertFalse(rt.get_history())

    def test_replay_uses_user_statements_only(self):
        state=c.from_history([{'q':'Tôi có 100k muốn ăn tối','a':'Ngân sách của bạn 9999999'}])
        self.assertEqual(c.active(state)['slots']['budget'],'100000');self.assertNotIn('9999999',c.summary(state))

    def test_topic_limit_and_unavailable_resume(self):
        state=c.empty()
        for q in ('Tôi muốn ăn tối','Tôi muốn mua laptop','Tôi muốn mua điện thoại','Tôi muốn mua tai nghe','Tôi có lịch hẹn ngày mai'):state=c.prepare(q,state).state
        self.assertEqual(len(state['frames']),4)
        self.assertTrue(c.prepare('Quay lại ăn tối',state).result.facts['needs_clarification'])

    def test_pending_correction_does_not_leak_across_topics(self):
        self.say('Ngân sách 100k. A 80k, B 90k');self.say('Tóm tắt bối cảnh');self.say('Sửa thành 85k')
        self.say('Tôi muốn mua điện thoại, ngân sách 5tr');self.say('Ngân sách giờ bao nhiêu?')
        self.assertEqual(c.active(rt.get_context())['slots']['budget'],'5000000')

    def test_duplicate_old_amount_asks_instead_of_guessing(self):
        self.say('Ngân sách 100k. A 100k, B 90k')
        self.assertIn('nhiều chỗ',self.say('Không phải 100k mà 120k'))
        frame=c.active(rt.get_context());self.assertEqual(frame['slots']['budget'],'100000');self.assertEqual(frame['options']['A']['cost'],'100000')

    def test_abbreviations_do_not_change_prices_or_resolution(self):
        self.assertEqual(c.abbreviations('100k 1080p B vs A ko đc'),'100k 1080p B với A không được')

    def test_preparation_is_transactional_and_summary_is_pure(self):
        state=c.prepare('Tôi có 100k muốn ăn tối').state;before=copy.deepcopy(state)
        c.prepare('Sửa ngân sách thành 120k',state);c.summary(state);self.assertEqual(before,state)

    def test_corrupt_state_is_recovered(self):
        for state in (None,[],{'version':1,'frames':None},{'version':1,'turn':'bad','frames':[{'id':'x','slots':[],'focus':[],'options':{'A':{'cost':'bad'}},'facts':None}]}):
            c.prepare('Cái đó là gì?',state)

    def test_state_and_prompt_strict_byte_bounds(self):
        state=c.empty()
        for i in range(8):
            frame=c.frame_new(str(i),'界'*90,i);frame['goal']='界'*140;frame['facts']=['界'*220]*3;frame['slots']={'place':'界'*90,'budget':'123456789000'}
            frame['options']={k:{'cost':'999999999999','fee':'999999999999','minutes':'9999'} for k in 'ABCDEF'};state['frames'].append(frame)
        state['active']='7';state=c.bounded(state)
        self.assertLessEqual(len(json.dumps(state,ensure_ascii=False).encode()),c.MAX_BYTES)
        self.assertLessEqual(len(c.summary(state).encode()),c.MAX_PROMPT_BYTES)
        self.assertTrue(json.loads(c.summary(state)).get('omitted_details'))

    def test_oversize_file_does_not_load(self):
        (rt.DATA/'conversation.json').write_text(' '*14000,encoding='utf-8');self.assertFalse(rt.get_context()['frames'])

    def test_open_preference_question_is_not_saved_as_fact(self):
        self.say('Tôi thích uống trà');before=c.active(rt.get_context())['facts']
        with patch.object(rt,'_local_request',return_value=stream()):self.say('Tôi thích uống gì?',web=False)
        self.assertEqual(before,c.active(rt.get_context())['facts'])

    def test_search_followup_sends_public_query_only(self):
        self.say('Tôi muốn ăn tối, ngân sách 100k')
        fixture=search.Bundle('Hà Nội',provider='fixture',sources=[])
        with patch.object(search,'search',return_value=fixture) as call:
            self.say('Tìm Google Hà Nội',web=True);self.say('Tóm tắt nguồn đó',web=True)
        for request in call.call_args_list:
            self.assertNotIn('100k',request.args[0]);self.assertNotIn('ăn tối',request.args[0])
        self.assertIn('Hà Nội',call.call_args.args[0])

    def test_responds_with_ai_disabled_and_no_model_calls(self):
        rt.save_settings({'ai_off':'1'})
        with patch.object(rt,'_local_request',side_effect=AssertionError('Model forbidden')):
            self.say('Ngân sách 100k. A 80k, B 120k');answer=self.say('Chọn phương án nào?')
        self.assertIn('A',answer);self.assertEqual(rt.completed_result()['metrics']['model_calls'],0)

    def test_recalling_a_revision_is_not_a_new_revision(self):
        self.say('Tôi thích màu đỏ');self.say('Không, xanh cơ');before=c.active(rt.get_context())['facts']
        with patch.object(rt,'_local_request',return_value=stream()) as call:self.say('Gợi ý phụ kiện theo màu tôi vừa sửa.',web=False)
        self.assertEqual(before,c.active(rt.get_context())['facts'])
        self.assertIn('xanh',call.call_args.args[1]['messages'][0]['content'])

    def test_topic_words_match_whole_words(self):
        self.assertEqual(c.subject('Tôi muốn đi chơi, thời gian tối đa 40 phút')[0],'trip')
        self.assertIsNone(c.subject('Thời gian tối đa 40 phút'))

    def test_explaining_chosen_option_checks_both_limits(self):
        self.say('Tôi muốn đi chơi, ngân sách 100k và thời gian tối đa 40 phút')
        self.say('A 90k mất 50 phút, B 80k mất 35 phút');self.say('Chọn phương án nào?')
        answer=self.say('Vì sao nên chọn phương án đó? Giải thích ngắn.')
        self.assertIn('35 phút ≤ 40 phút',answer);self.assertIn('50 phút > 40 phút',answer)
        self.assertEqual(c.active(rt.get_context())['id'],'trip')

    def test_personal_context_reaches_open_model(self):
        self.say('Tôi đang học lớp 10');self.say('Tôi muốn học tiếng Anh giao tiếp')
        with patch.object(rt,'_local_request',return_value=stream()) as call:self.say('Gợi ý lịch học phù hợp',web=False)
        system=call.call_args.args[1]['messages'][0]['content']
        self.assertIn('lớp 10',system);self.assertIn('tiếng Anh giao tiếp',system)

    def test_short_duration_revision_keeps_units(self):
        self.say('Tôi muốn đi chơi, thời gian tối đa 1 tiếng');self.say('Nhầm, 45p thôi')
        self.assertEqual(c.active(rt.get_context())['slots']['minutes'],'45')

    def test_money_revision_does_not_overwrite_duration(self):
        self.say('Tôi muốn đi chơi, thời gian tối đa 1 tiếng')
        answer=self.say('Nhầm, 120k thôi')
        self.assertIn('ngân sách',answer);self.assertEqual(c.active(rt.get_context())['slots']['minutes'],'60')

if __name__=='__main__':unittest.main()
