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

    def test_discount_split_speed_temperature(self):
        self.assertEqual(everyday.discount('Áo giá 500 nghìn, giảm 20%. Còn bao nhiêu?').facts['result'],'400000')
        self.assertEqual(everyday.discount('Giá 2 triệu, tăng 10% thì sao?').facts['result'],'2200000')
        self.assertEqual(everyday.discount('20% của 250000 đồng là bao nhiêu?').facts['result'],'50000')
        self.assertIsNone(everyday.discount('Tôi giảm cân 5% rồi'))
        self.assertEqual(everyday.split_bill('Hóa đơn 720 nghìn chia 3 người, mỗi người bao nhiêu?').facts['each'],'240000')
        self.assertIsNone(everyday.split_bill('Chia số tiền đó cho 6 người.'))
        self.assertEqual(everyday.speed('Đi 12 km trong 15 phút thì tốc độ là bao nhiêu km/h?').facts['speed_kmh'],'48')
        self.assertEqual(everyday.temperature('30 độ C bằng bao nhiêu độ F?').facts['result'],'86')
        self.assertEqual(everyday.temperature('100 độ F sang độ C là bao nhiêu?').text,'100°F = **37,78°C**.')
        self.assertIsNone(everyday.temperature('Tôi đang ở 30 độ C'))

    def test_age_date_and_compound_time(self):
        self.assertEqual(everyday.age('Tôi sinh năm 2004, năm nay tôi bao nhiêu tuổi?').facts['age'],2026-2004)
        self.assertIsNone(everyday.age('Năm nay bao nhiêu tuổi rồi?'))
        result=everyday.date_offset('Hôm nay 14/11, 3 tuần nữa là ngày nào?')
        self.assertEqual(result.facts['date'],'2026-12-05')
        self.assertEqual(result.text,'3 tuần sau 14/11/2026 là **05/12/2026** (thứ Bảy).')
        self.assertEqual(everyday.date_offset('Từ 14/11/2026, 10 ngày trước là ngày nào?').facts['date'],'2026-11-04')
        self.assertEqual(everyday.date_offset('Từ 31/01/2027, 1 tháng nữa là ngày nào?').facts['date'],'2027-02-28')
        self.assertIsNone(everyday.date_offset('Hôm nay trời đẹp không?'))
        self.assertEqual(everyday.compound_time('2 giờ 30 phút đổi ra phút là bao nhiêu?').facts['result'],'150')

    def test_budget_leftover_and_thousands(self):
        result=everyday.shopping('Tôi có 200 nghìn, mua 2 hộp sữa 35 nghìn và 1 ổ bánh mì 20 nghìn. Còn lại bao nhiêu?')
        self.assertEqual(result.facts['result'],'110000')
        self.assertEqual(everyday.shopping('Mua 5 chai nước, mỗi chai 6000 đồng, đưa 100000 đồng. Tiền thừa bao nhiêu?').facts['result'],'70000')

    def test_ordering_by_noun_and_thousand_budget(self):
        result=reasoning.order_reasoning('Hộp A nặng hơn hộp B. Hộp B nặng hơn hộp C. Hộp nào nặng nhất?')
        self.assertEqual(result.facts['winner'],'A')
        result=reasoning.constraint_choice('Tôi có 100 nghìn và 2 giờ. Chọn A giá 80 nghìn mất 30 phút hay B giá 120 nghìn mất 20 phút. Nên chọn cái nào?')
        self.assertEqual(result.facts['feasible_ids'],['A'])

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
