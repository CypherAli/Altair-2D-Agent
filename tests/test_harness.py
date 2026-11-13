import io
import json
import os
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from altair_core import harness, skills, toolkit
from altair_core import runtime as rt


PUZZLE = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
SOLUTION = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"


class ToolsTests(unittest.TestCase):
    def test_arithmetic_exact_and_precedence(self):
        for expression, expected in [("(125000 * 3 - 50000) / 2", Fraction(162500)),
                                     ("2,5 × 4", Fraction(10)), ("20,5% * 200", Fraction(41)),
                                     ("1.000 + 250", Fraction(1250)), ("2^-2", Fraction(1, 4)),
                                     ("0.1+0.2", Fraction(3, 10))]:
            with self.subTest(expression=expression):
                self.assertEqual(toolkit.calculate(expression), expected)

    def test_unsafe_or_unbounded_expressions_are_rejected(self):
        for expression in ("__import__('os').system('echo test')", "2**999999", "1/0", "[1]*10000", "(1+2", "1e100"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                toolkit.calculate(expression)

    def test_percentage_and_invalid_expression_response(self):
        self.assertEqual(toolkit.arithmetic("20% của 250000").facts["result"], "50000")
        self.assertTrue(toolkit.arithmetic("Tính 1/0").facts["error"])
        self.assertIsNone(toolkit.arithmetic("Tôi đang tính đi chơi vào cuối tuần"))

    def test_roundtrip_variants_against_independent_budget(self):
        for budget in (30, 60, 90, 120):
            for travel in (0, 5, 10, 17):
                for activity in (15, 40, 45):
                    question = f"Tôi có {budget} phút. Đi bộ mất {travel} phút mỗi chiều và chơi {activity} phút. Có kịp không?"
                    result = toolkit.time_plan(question)
                    with self.subTest(budget=budget, travel=travel, activity=activity):
                        self.assertEqual(Fraction(result.facts["total_minutes"]), travel + activity + travel)
                        self.assertEqual(result.facts["feasible"], budget >= travel + activity + travel)

    def test_hour_minutes_and_roundtrip_already_combined(self):
        result = toolkit.time_plan("Tôi có 1 giờ 30 phút. Đi lại 20 phút khứ hồi và chơi 60 phút. Có kịp không?")
        self.assertEqual(result.facts["total_minutes"], "80")
        self.assertEqual(result.facts["remaining_minutes"], "10")

    def test_repeated_budget_in_question_is_not_an_activity(self):
        for budget in (30, 60, 90, 120):
            question = f"Tôi có {budget} phút rảnh. Đi bộ ra công viên mất 10 phút mỗi chiều. Tôi muốn ngồi chơi 45 phút. Có kịp về trong {budget} phút không? Giải thích ngắn."
            result = toolkit.time_plan(question)
            self.assertEqual(result.facts["total_minutes"], "65")
            self.assertEqual(result.facts["feasible"], budget >= 65)
        conflict = toolkit.time_plan("Tôi có 60 phút. Đi mất 10 phút và chơi 45 phút. Có kịp về trong 30 phút không?")
        self.assertTrue(conflict.facts["needs_clarification"])

    def test_time_clarifies_missing_or_negated_budget(self):
        for question in ("Đi 10 phút mỗi chiều, chơi 45 phút, có kịp không?",
                         "Tôi không có 60 phút. Đi 10 phút và chơi 45 phút, có kịp không?"):
            self.assertTrue(toolkit.time_plan(question).facts["needs_clarification"])
        self.assertIsNone(toolkit.time_plan("Giải thích tại sao tôi luôn không kịp việc"))

    def test_unit_conversion_and_dimension_check(self):
        self.assertEqual(toolkit.convert_units("Đổi 2,5 km sang m").facts["result"], "2500")
        self.assertEqual(toolkit.convert_units("90 phút bằng bao nhiêu giờ?").facts["result"], "3/2")
        self.assertTrue(toolkit.convert_units("2 kg sang m").facts["error"])

    def test_sudoku_solution_validates_all_units_and_givens(self):
        result = toolkit.sudoku("Giải sudoku " + PUZZLE)
        grid = result.facts["solution"]
        self.assertEqual("".join(map(str, grid)), SOLUTION)
        self.assertEqual(result.facts["solutions"], 1)
        for row in range(9):
            self.assertEqual(set(grid[row * 9:row * 9 + 9]), set(range(1, 10)))
            self.assertEqual({grid[row + 9 * index] for index in range(9)}, set(range(1, 10)))
        self.assertLess(result.facts["nodes"], 30000)

    def test_sudoku_invalid_multiple_and_hint(self):
        self.assertTrue(toolkit.sudoku("sudoku " + "55" + PUZZLE[2:]).facts["invalid"])
        self.assertEqual(toolkit.sudoku("sudoku " + "0" * 81).facts["solutions"], 2)
        self.assertIn("value", toolkit.sudoku("Gợi ý sudoku " + PUZZLE).facts)
        self.assertTrue(toolkit.sudoku("giải sudoku giúp tôi").facts["needs_grid"])

    def test_identity_and_commands_do_not_overmatch_general_questions(self):
        self.assertIsNotNone(harness.plan("Bạn tên gì?").result)
        self.assertIsNone(harness.plan("Tên nhân vật này là gì?").result)
        self.assertIsNone(harness.plan("Tại sao cần nhắc tôi uống nước?").result)
        self.assertFalse(harness.plan("Nhắc tôi uống nước sau 5 phút").result.facts["executed"])

    def test_only_selected_skill_and_relevant_notes_are_disclosed(self):
        self.assertGreaterEqual(len(skills.catalog()), 10)
        prompt = harness.system_prompt("explain")
        self.assertIn('name="explain"', prompt)
        self.assertNotIn("Sudoku", prompt)
        notes = [{"text": "Tôi thích trà không đường."}, {"text": "Mật khẩu ví dụ không được đưa vào câu hỏi thời tiết."}]
        selected = harness.relevant_notes("Tôi thích uống gì?", notes)
        self.assertEqual(selected, [notes[0]["text"]])


class RuntimeHarnessTests(unittest.TestCase):
    def setUp(self):
        if os.environ.get("ALTAIR_TEST_TMP"):
            Path(os.environ["ALTAIR_TEST_TMP"]).mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("ALTAIR_TEST_TMP"))
        self.patch = patch.object(rt, "DATA", Path(self.temp.name)); self.patch.start()
        rt._answer_cache.clear()

    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()

    def test_tools_do_not_load_model_even_when_ai_off(self):
        rt.save_settings({"ai_off": "1"})
        with patch.object(rt, "_local_request") as request:
            answer = "".join(rt.stream_chat("Tính 125 * 3"))
            self.assertIn("375", answer)
            request.assert_not_called()
        self.assertEqual(rt._last_metrics["model_calls"], 0)

    def test_fast_duration_is_correct_and_persisted(self):
        question = "Tôi có 60 phút. Đi 10 phút mỗi chiều và chơi 45 phút. Có kịp không?"
        with patch.object(rt, "_local_request") as request:
            answer = "".join(rt.stream_chat(question))
            self.assertTrue(answer.startswith("Không kịp"))
            request.assert_not_called()
        self.assertEqual(rt.get_history()[-1]["intent"], "time-planning")

    def test_cache_is_context_aware_and_bounded(self):
        event = {"message": {"content": "Mưa do hơi nước ngưng tụ."}}
        output = io.BytesIO((json.dumps(event) + '\n{"done":true}\n').encode())
        with patch.object(rt, "_local_request", return_value=output) as request:
            first = "".join(rt.stream_chat("Giải thích ngắn vì sao có mưa.", remember=False))
            second = "".join(rt.stream_chat("Giải thích ngắn vì sao có mưa.", remember=False))
            self.assertEqual(first, second)
            self.assertEqual(request.call_count, 1)
            self.assertTrue(rt._last_metrics["cache_hit"])

    def test_explicit_note_save_is_not_merely_claimed(self):
        with patch.object(rt, "_local_request") as request:
            self.assertIn("Đã lưu", "".join(rt.stream_chat("Hãy nhớ rằng tôi thích trà.")))
            request.assert_not_called()
        self.assertEqual(rt.get_notes()[0]["text"], "tôi thích trà.")

    def test_unrelated_history_does_not_enter_model_context(self):
        messages = rt._messages("Giải thích vì sao có mưa.", [{"q": "PRIVATE OLD TOPIC", "a": "old"}], None)
        self.assertEqual(len(messages), 2)
        self.assertNotIn("PRIVATE OLD TOPIC", str(messages))
        self.assertLess(len(messages[0]["content"].encode()), 1000)


if __name__ == "__main__":
    unittest.main()
