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
