import unittest
from altair_core import everyday,harness,reasoning,search

class PracticalTests(unittest.TestCase):
    def test_cart_quantity_and_change(self):
        result=everyday.shopping('Tôi mua 2 hộp sữa giá 15000 đồng một hộp và một bánh 9000 đồng. Tổng hết bao nhiêu?')
        self.assertEqual(result.facts['total'],'39000')
        result=everyday.shopping('Mua 5 chai nước, mỗi chai 6000 đồng, đưa 100000 đồng. Tiền thừa bao nhiêu?')
        self.assertEqual(result.facts['result'],'70000')
        self.assertIsNone(everyday.shopping('Mua 2 áo giá 100000 đồng, giảm 20%. Tổng hết bao nhiêu?'))

    def test_clock_buffer_and_day_boundary(self):
        result=everyday.clock_plan('Chuyến xe 9:00. Đi mất 20 phút và đến trước 10 phút. Muộn nhất rời đi mấy giờ?')
        self.assertEqual(result.facts['time'],'08:30')
        result=everyday.clock_plan('Bắt đầu 23:50, làm 30 phút. Kết thúc mấy giờ?')
        self.assertEqual(result.facts['time'],'00:20');self.assertEqual(result.facts['day_offset'],1)

    def test_parallel_tasks_are_not_summed(self):
        result=everyday.simultaneous('Giặt 35 phút và nấu cơm 20 phút bắt đầu cùng lúc. Bao lâu thì xong?')
        self.assertEqual(result.facts['result'],'35')

    def test_shipping_and_two_dimensions(self):
        result=reasoning.constraint_choice('Có 100000 đồng. A giá 85000 đồng, phí giao hàng 25000 đồng. B giá 98000 đồng, miễn phí giao hàng. Chọn phương án.')
        self.assertEqual(result.facts['choice'],'B')
        result=reasoning.constraint_choice('Ngân sách 90000 đồng và tối đa 40 phút. A giá 80000 đồng, mất 45 phút. B giá 95000 đồng, mất 30 phút. Chọn phương án.')
        self.assertEqual(result.facts['feasible_ids'],[])
        result=reasoning.constraint_choice('Tối đa 70000 đồng và 20 phút. A giá 60000 đồng, mất 25 phút. B giá 80000 đồng, mất 15 phút. Chọn phương án.')
        self.assertEqual(result.facts['feasible_ids'],[])

    def test_names_commas_and_all_relations(self):
        result=reasoning.order_reasoning('Nguyễn An cao hơn Trần Bình, Trần Bình cao hơn Lê Chi. Ai thấp nhất?')
        self.assertEqual(result.facts['winner'],'Lê Chi')
        result=reasoning.order_reasoning('A đến trước B, B đến trước C. Ai đến cuối cùng?')
        self.assertEqual(result.facts['winner'],'C')

    def test_references_and_capability_status(self):
        for q in ('Chia số tiền đó cho 6 người.','Còn phương án B thì sao?','Lượt về cũng mất từng ấy.'):
            self.assertTrue(harness.uses_history(q))
        self.assertFalse(harness.plan('Bạn đã đặt báo thức cho tôi chưa?').result.facts['executed'])
        self.assertFalse(harness.web_followup('Tôi thích màu xanh.'))
        self.assertFalse(harness.web_followup('Tìm Google một chủ đề khác, tổng hợp'))
        self.assertTrue(harness.web_followup('Nói rõ hơn một chút.'))

    def test_creator_definition_and_numeric_focus(self):
        self.assertLess(search.passage_score('The World Wide Web was conceived as a universal information system.',
                        'ai sáng lập World Wide Web'),0)
        definition=search.relevant_passage('Example là một thư viện cho xử lý dữ liệu.\nHiện Example có hai phiên bản.', 'Example là gì')
        self.assertIn('thư viện',definition)
        self.assertTrue(search.numeric_fact('tốc độ ánh sáng','Giá trị là 299 792 458 m/s.'))
        self.assertLess(search.passage_score('Sản phẩm phần mềm tải xuống, bảng giá dịch vụ.', 'giá sản phẩm ABC_2394 hiện nay'),0)

    def test_summary_cannot_invent_place_name(self):
        bundle=search.Bundle('thủ đô quốc gia Example',sources=[{'id':1,'title':'Danh sách quốc gia',
            'excerpt':'Danh sách các quốc gia và thủ đô trên thế giới.'}])
        self.assertFalse(search.valid_summary('Thủ đô của Example là MadeUpCity [1].',bundle))

    def test_initials_and_hyphenated_author_are_preserved(self):
        excerpt=search.relevant_passage('Harry Potter is written by J. K. Rowling. More information is available.', 'Harry Potter')
        self.assertIn('J. K. Rowling',excerpt)
        bundle=search.Bundle('tác giả',sources=[{'id':1,'title':'Book','excerpt':'Written by Antoine de Saint-Exupéry.'}])
        self.assertTrue(search.valid_summary('Antoine de Saint-Exupéry [1].',bundle))
