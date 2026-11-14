import itertools
import unittest
from altair_core import harness, reasoning, toolkit

class DecisionTests(unittest.TestCase):
    def test_transitive_order_across_name_permutations(self):
        for a,b,c,d in itertools.permutations(('An','Binh','Chi','Dung')):
            q=f'{a} cao hơn {b}. {c} thấp hơn {b}. {d} thấp hơn {c}. Ai cao nhất? Chỉ trả lời tên.'
            self.assertEqual(reasoning.order_reasoning(q).facts['winner'],a)
            self.assertEqual(reasoning.order_reasoning(q.replace('cao nhất','thấp nhất')).facts['winner'],d)

    def test_cycle_disconnected_and_unsupported_names(self):
        for q in ('An cao hơn Binh. Binh cao hơn An. Ai cao nhất?',
                  'An cao hơn Binh. Chi cao hơn Dung. Ai cao nhất?'):
            self.assertTrue(reasoning.order_reasoning(q).facts['needs_clarification'])
        self.assertEqual(reasoning.order_reasoning('Nguyễn Văn An cao hơn Lê Minh. Ai cao nhất?').facts['winner'],'Nguyễn Văn An')
        self.assertIsNone(reasoning.order_reasoning('An không cao hơn Binh. Ai cao nhất?'))

    def test_choices_are_independent_against_budget(self):
        for budget,a,b in itertools.product((30,60,100),(20,65,120),(10,55,110)):
            q=f'Có {budget} phút. Phương án A cần {a} phút, B cần {b} phút. Chọn phương án kịp thời gian.'
            result=reasoning.constraint_choice(q)
            expected=[key for key,value in (('A',a),('B',b)) if value<=budget]
            self.assertEqual(result.facts['feasible_ids'],expected)
            if len(expected)==1:self.assertEqual(result.facts['choice'],expected[0])
            if len(expected)>1:self.assertTrue(result.facts['needs_clarification'])

    def test_currency_and_mixed_time_units(self):
        result=reasoning.constraint_choice('Chọn phương án trong ngân sách 100000 đồng: A giá 150000, B giá 80000. Chỉ trả lời A hoặc B.')
        self.assertEqual(result.text,'B')
        self.assertEqual(result.facts['choice'],'B')
        result=reasoning.constraint_choice('Có 1 giờ. A cần 90 phút, B cần 0,5 giờ. Chọn phương án kịp thời gian.')
        self.assertEqual(result.facts['choice'],'B')

    def test_no_arbitrary_choice_and_no_adding_alternatives(self):
        question='Có 60 phút. Phương án A cần 65 phút, B cần 55 phút. Chọn phương án kịp thời gian. Chỉ trả lời A hoặc B.'
        self.assertIsNone(toolkit.time_plan(question))
        self.assertEqual(harness.plan(question).result.text,'B')
        multiple=reasoning.constraint_choice('Có 60 phút. A cần 30 phút, B cần 40 phút. Chọn phương án.')
        self.assertTrue(multiple.facts['needs_clarification'])


class SyllogismTests(unittest.TestCase):
    def test_positive_chain(self):
        result = reasoning.syllogism('Mọi mèo là động vật. Miu là mèo. Miu có phải là động vật không?')
        self.assertEqual(result.facts['answer'], 'yes')
        self.assertIn('Miu', result.text)
        deep = reasoning.syllogism('Mọi chó là động vật. Mọi động vật là sinh vật. Lu là chó. Lu có phải là sinh vật không?')
        self.assertEqual(deep.facts['chain'], ['lu', 'cho', 'dong vat', 'sinh vat'])

    def test_negative_and_contradiction(self):
        result = reasoning.syllogism('Không con mèo nào là chim. Miu là mèo. Miu có phải là chim không?')
        self.assertEqual(result.facts['answer'], 'no')
        clash = reasoning.syllogism('Mọi mèo là động vật. Miu là mèo. Miu không phải là động vật. Miu có phải là động vật không?')
        self.assertTrue(clash.facts['needs_clarification'])
        self.assertEqual(clash.facts['answer'], 'conflict')

    def test_missing_premise_asks_instead_of_guessing(self):
        for question in ('Miu là mèo. Miu có phải là động vật không?',
                         'Mọi mèo là động vật. Miu là mèo. Miu có phải là chim không?',
                         'Một số mèo là đen. Miu là mèo. Miu có phải là đen không?'):
            with self.subTest(question=question):
                result = reasoning.syllogism(question)
                self.assertTrue(result.facts['needs_clarification'])
                self.assertEqual(result.facts['answer'], 'unknown')
                self.assertIn('tiền đề', result.text)

    def test_refuses_non_categorical_questions(self):
        for question in ('Giải thích vì sao trời mưa', 'Hôm nay trời đẹp không?', 'Mọi mèo',
                         'Nếu trời mưa thì đường ướt. Trời mưa. Đường có ướt không?'):
            with self.subTest(question=question):
                self.assertIsNone(reasoning.syllogism(question))

    def test_what_question_and_unaccented_input(self):
        result = reasoning.syllogism('Mọi mèo là động vật. Miu là mèo. Miu là gì?')
        self.assertEqual(result.facts['chain'], ['meo', 'dong vat'])
        plain = reasoning.syllogism('moi meo la dong vat. miu la meo. miu co phai la dong vat khong?')
        self.assertEqual(plain.facts['answer'], 'yes')

    def test_harness_answers_without_the_model(self):
        plan = harness.plan('Mọi mèo là động vật. Miu là mèo. Miu có phải là động vật không?')
        self.assertEqual(plan.skill, 'syllogism')
        self.assertEqual(plan.result.facts['answer'], 'yes')
        wrapped = harness.plan('Nếu tất cả mèo đều là động vật và Miu là mèo thì Miu có phải động vật không?')
        self.assertEqual(wrapped.skill, 'syllogism')
