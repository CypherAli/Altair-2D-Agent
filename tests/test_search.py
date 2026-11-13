import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from altair_core import harness, judgment, search
from altair_core import runtime as rt


def bundle():
    return search.Bundle('science',provider='Google',sources=[{'id':1,'title':'Science','url':'https://example.com/science',
        'excerpt':'Rain forms when water vapour cools and condenses into water droplets.','read':True}])


class SearchTests(unittest.TestCase):
    def setUp(self):
        search._cache.clear()

    def test_url_boundaries(self):
        for url in ('file:///etc/passwd','http://localhost/x','http://127.0.0.1/a','http://192.168.1.1/',
                    'https://user:pass@example.com','http://[::1]/','http://example.com:8124/'):
            with self.subTest(url=url),self.assertRaises(ValueError): search.public_url(url,resolve=False)
        self.assertEqual(search.public_url('https://example.com/a#part',resolve=False),'https://example.com/a')
        with patch.object(search.socket,'getaddrinfo',return_value=[(2,1,6,'',('10.0.0.2',443))]):
            with self.assertRaises(ValueError): search.public_url('https://example.com')

    def test_html_excludes_scripts_templates_navigation(self):
        p=search.Page();p.feed('<nav>menu</nav><main><p>Real evidence here.</p><script>ignore previous</script><template>{"fake":900}</template></main>')
        self.assertIn('Real evidence',p.text())
        for value in ('menu','ignore previous','fake'): self.assertNotIn(value,p.text())

    def test_google_results_and_no_js_gate(self):
        fixture='<a href="/url?q=https%3A%2F%2Fexample.org%2Farticle"><h3>Example article</h3></a>'
        self.assertEqual(search.parse_google(fixture)[0]['url'],'https://example.org/article')
        self.assertEqual(search.parse_google('<a href="/httpservice/retry/enablejs">Enable JavaScript</a>'),[])

    def test_rss_rejects_unsafe_links(self):
        fixture='<rss><channel><item><title>bad</title><link>http://127.0.0.1/</link></item><item><title>Good</title><link>https://example.org/</link><description>Public information.</description></item></channel></rss>'
        self.assertEqual(len(search.parse_bing(fixture)),1)

    def test_query_routing_does_not_send_personal_memory(self):
        for q in ('Tìm Google thời tiết Hà Nội','Giá vàng hôm nay bao nhiêu?','Ai là ai hiện nay?'):
            self.assertTrue(search.requested(q))
        for q in ('Tôi thích uống gì?','Hãy nhớ rằng tôi đang tìm việc mới nhất.','Bạn tên gì?'):
            self.assertNotEqual(harness.plan(q,notes=[]).skill,'web-search')
        self.assertFalse(search.requested('Tìm Google thời tiết',False))
        self.assertEqual(search.query_text('Tìm Google Jev confidence, tổng hợp'),'Jev confidence')

    def test_relevance_rejects_single_generic_match(self):
        self.assertEqual(search.relevant_passage('A Python overview tutorial is available.','Python latest version'),'')
        result=search.relevant_passage('Download the latest version\nPython 3.14.2\nOther links','Python latest version')
        self.assertIn('3.14.2',result)

    def test_count_question_does_not_accept_partial_group(self):
        self.assertLess(search.passage_score('Vùng trong cùng có 4 hành tinh đất đá trong hệ Mặt Trời.',
                        'hệ Mặt Trời có bao nhiêu hành tinh'),0)
        self.assertGreater(search.passage_score('Our solar system has eight planets.',
                           'hệ Mặt Trời có bao nhiêu hành tinh'),0)

    def test_wikipedia_keyless_response_has_article_url(self):
        payload={'query':{'pages':{'1':{'title':'Example','index':1,'extract':'Example is a public knowledge subject with a useful introduction.'}}}}
        with patch.object(search,'fetch',return_value=(json.dumps(payload),'https://en.wikipedia.org/w/api.php','application/json')):
            rows=search.wikipedia_sources('Example')
        self.assertEqual(rows[0]['url'],'https://en.wikipedia.org/wiki/Example')
        self.assertTrue(rows[0]['read'])

    def test_official_sources_are_only_live_url_seeds(self):
        rows=search.direct_sources('Jev confidence')
        self.assertEqual(rows[0]['url'],'https://docs.typesafe.ai/confidence')
        self.assertNotIn('excerpt',rows[0])
        self.assertEqual(search.direct_sources('https://example.org/page details')[0]['url'],'https://example.org/page')

    def test_summary_citation_and_number_guards(self):
        b=bundle()
        self.assertTrue(search.valid_summary('Mưa hình thành khi hơi nước ngưng tụ. [1]',b))
        for answer in ('Không có trích dẫn.','Thông tin [8]','Thông tin tại https://fake.test [1]','Chắc chắn 95% [1]'):
            self.assertFalse(search.valid_summary(answer,b))

    def test_search_cache_and_cancellation(self):
        search._cache['science']=(time.monotonic(),bundle())
        with patch.object(search,'fetch') as fetch:
            self.assertTrue(search.search('science').cached);fetch.assert_not_called()
        cancelled=threading.Event();cancelled.set()
        with self.assertRaises(search.SearchCancelled):search.search('science',cancelled)

    def test_judgment_never_fakes_calibrated_probability(self):
        for route in ('skill','web','model'):
            result=judgment.assess(route)
            self.assertIsNone(result['probability_correct']);self.assertFalse(result['calibrated'])
        self.assertEqual(judgment.assess('skill',{'needs_clarification':True})['status'],'needs_clarification')


class WebRuntimeTests(unittest.TestCase):
    def setUp(self):
        parent=os.environ.get('ALTAIR_TEST_TMP')
        if parent:Path(parent).mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.data=patch.object(rt,'DATA',Path(self.temp.name));self.data.start()
        rt._answer_cache.clear();rt._cancelled.clear()

    def tearDown(self):self.data.stop();self.temp.cleanup()

    def test_web_quick_path_runs_with_ai_off_and_real_sources(self):
        rt.save_settings({'ai_off':'1'})
        with patch.object(search,'search',return_value=bundle()),patch.object(rt,'_local_request') as model:
            answer=''.join(rt.stream_chat('Tìm Google science'))
            model.assert_not_called()
        self.assertIn('[1]',answer)
        self.assertEqual(rt._last_metrics['provider'],'Google')
        self.assertEqual(rt.completed_result()['sources'][0]['url'],'https://example.com/science')
        self.assertEqual(rt.get_history()[-1]['sources'][0]['id'],1)

    def test_no_search_fabrication_when_network_fails(self):
        with patch.object(search,'search',return_value=search.Bundle('none',warnings=['Không tìm được nguồn.'])):
            answer=''.join(rt.stream_chat('Tìm Google unknown'))
        self.assertIn('Không tìm được nguồn',answer)
        self.assertEqual(rt._last_sources,[])
        self.assertTrue(rt._last_metrics['judgment']['requires_review'])

    def test_invalid_model_summary_falls_back_to_excerpt(self):
        output=io.BytesIO(b'{"message":{"content":"Made up 98%. [7]"}}\n{"done":true}\n')
        with patch.object(search,'search',return_value=bundle()),patch.object(rt,'_local_request',return_value=output):
            answer=''.join(rt.stream_chat('Tìm Google science, tổng hợp'))
        self.assertNotIn('98%',answer)
        self.assertTrue(rt._last_metrics['summary_rejected'])
        self.assertEqual(rt._last_metrics['answer_mode'],'excerpt')

    def test_valid_model_summary_preserves_source_identity(self):
        output=io.BytesIO('{"message":{"content":"Hơi nước ngưng tụ tạo mưa. [1]"}}\n{"done":true}\n'.encode())
        with patch.object(search,'search',return_value=bundle()),patch.object(rt,'_local_request',return_value=output):
            answer=''.join(rt.stream_chat('Tìm Google science, tổng hợp'))
        self.assertIn('ngưng tụ',answer)
        self.assertEqual(rt._last_metrics['answer_mode'],'summary')
        self.assertFalse(rt._last_metrics['verified'])

    def test_explicit_off_overrides_automatic_web(self):
        output=io.BytesIO(b'{"message":{"content":"Local answer."}}\n{"done":true}\n')
        with patch.object(search,'search') as retrieval,patch.object(rt,'_local_request',return_value=output):
            list(rt.stream_chat('Tìm Google science',web=False))
            retrieval.assert_not_called()

    def test_search_cancel_releases_lock(self):
        def cancelled(*args):
            rt._cancelled.set();raise search.SearchCancelled('Đã dừng')
        with patch.object(search,'search',side_effect=cancelled),self.assertRaises(rt.CancelledError):
            list(rt.stream_chat('Tìm Google science'))
        self.assertFalse(rt._inference_lock.locked())
        self.assertEqual(rt.get_history(),[])
