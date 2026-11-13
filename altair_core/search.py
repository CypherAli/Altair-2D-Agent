"""Bounded public-web retrieval: Google first, clearly labelled Bing RSS fallback.

No account, paid API, browser engine, JavaScript execution or background crawler.
Web content is data only. Direct excerpts work without loading the language model.
"""
from __future__ import annotations
import concurrent.futures
import copy
import html
import ipaddress
import json
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from functools import lru_cache

from .toolkit import normalize

MAX_BYTES = 350_000
_cache = OrderedDict()
_lock = threading.Lock()
_google_retry = 0.0


class SearchCancelled(RuntimeError):
    pass


def check_cancel(cancel):
    if cancel and cancel.is_set():
        raise SearchCancelled("Đã dừng tìm kiếm.")


def public_url(url, resolve=True):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("URL không hợp lệ.")
    if parts.port not in (None, 80, 443) or len(url) > 2000:
        raise ValueError("URL ngoài giới hạn.")
    host = parts.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
        raise ValueError("Chỉ đọc trang web công khai.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal and not literal.is_global:
        raise ValueError("Không đọc địa chỉ mạng nội bộ.")
    if resolve:
        addresses = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ValueError("Đích đến không phải mạng công khai.")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


class Redirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 3
    max_repeats = 2

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, public_url(newurl))


def fetch(url, timeout=3, cancel=None, max_bytes=MAX_BYTES):
    check_cancel(cancel)
    deadline=time.monotonic()+timeout
    url = public_url(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), Redirect())
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AltairPersonal/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/xml,text/plain",
        "Accept-Encoding": "identity", "Accept-Language": "vi,en;q=0.7"})
    with opener.open(request, timeout=max(.3, timeout)) as response:
        final = public_url(response.url)
        kind = response.headers.get_content_type()
        if kind not in ("text/html", "application/xhtml+xml", "application/rss+xml", "application/xml", "text/xml", "text/plain", "application/json"):
            raise ValueError("Chưa hỗ trợ loại tài liệu này.")
        if int(response.headers.get("Content-Length", "0")) > 4_000_000:
            raise ValueError("Trang quá lớn cho chế độ nhẹ.")
        chunks, count = [], 0
        while count < max_bytes:
            check_cancel(cancel)
            if time.monotonic()>deadline:raise TimeoutError('Hết thời gian đọc trang trong chế độ nhẹ.')
            chunk = response.read1(min(16384, max_bytes - count))
            if not chunk:
                break
            chunks.append(chunk); count += len(chunk)
        raw = b"".join(chunks)
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            data = raw.decode(charset, "replace")
        except LookupError:
            data = raw.decode("utf-8", "replace")
        return data, final, kind


class Page(HTMLParser):
    SKIP = ("script", "style", "noscript", "svg", "nav", "footer", "form", "template", "aside", "button")
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0; self.parts = []; self.title = []; self.in_title = False
        self.links = []; self.anchor = None; self.link_text = []; self.heading = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title": self.in_title = True
        if tag in ("p", "div", "li", "h1", "h2", "h3", "br", "tr"):
            self.parts.append("\n")
        if tag == "a":
            self.anchor = values.get("href"); self.link_text = []; self.heading = False
        if self.anchor and tag in ("h2", "h3"):
            self.heading = True

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        if tag == "title": self.in_title = False
        if tag in ("p", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")
        if tag == "a" and self.anchor:
            self.links.append((self.anchor, " ".join(self.link_text).strip(), self.heading))
            self.anchor = None

    def handle_data(self, data):
        if self.skip: return
        if self.in_title: self.title.append(data)
        else: self.parts.append(data)
        if self.anchor: self.link_text.append(data)

    def text(self):
        return "\n".join(line for part in "".join(self.parts).splitlines() if (line := " ".join(part.split())))


def parse_google(data):
    parser = Page(); parser.feed(data)
    results, seen = [], set()
    for href, title, heading in parser.links:
        if href.startswith("/url?"):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
            href = (query.get("q") or query.get("url") or [""])[0]
        if not heading or not title: continue
        try: url = public_url(href, resolve=False)
        except ValueError: continue
        host = urllib.parse.urlsplit(url).hostname
        if host.endswith(("google.com", "google.com.vn", "googleusercontent.com")) or url in seen: continue
        results.append({"title": title[:160], "url": url, "snippet": ""}); seen.add(url)
    return results[:5]


def parse_bing(data):
    root = ET.fromstring(data)
    results, seen = [], set()
    for item in root.findall("./channel/item"):
        try: url = public_url(item.findtext("link", ""), resolve=False)
        except ValueError: continue
        if url in seen: continue
        parser = Page(); parser.feed(item.findtext("description", ""))
        results.append({"title": item.findtext("title", "")[:160], "url": url, "snippet": parser.text()[:600]})
        seen.add(url)
    return results[:5]


def query_text(question):
    query = re.sub(r"^(?:altair[, ]+)?(?:hãy\s+)?(?:tìm\s+(?:kiếm\s+)?(?:trên\s+)?(?:google|web)?|tra\s+cứu|search|google)\s*[:,-]?\s*", "", question.strip(), flags=re.I)
    query = re.sub(r"(?:[,;.]\s*)?(?:rồi\s+)?(?:tóm tắt|tổng hợp|trả lời có nguồn|kèm nguồn|có nguồn|chỉ lấy nguồn|tìm nhanh)\s*[.!?]*$", "", query, flags=re.I)
    return " ".join(query.split())[:240].strip()


def requested(question, mode=None):
    if mode is False: return False
    if mode is True: return True
    text = normalize(question)
    explicit = re.search(r"\b(?:tim (?:kiem |tren )?(?:google|web)|tim kiem|tra cuu|search|google|kem nguon|co nguon)\b", text)
    factual = re.search(r"\b(?:moi nhat|hien nay|hien tai|hom nay|tin tuc|thoi tiet|la ai|ai tao|ai sang lap|nam nao|o dau|bao gio|thong tin ve|thong so|gia bao nhieu|latest|current|today|weather)\b", text)
    return bool(explicit or (factual and not re.search(r"\b(?:toi|minh|ghi nho|bao thuc|nhac nho)\b", text)))


def terms_for(query):
    stop = {"tim", "kiem", "google", "web", "toi", "ban", "hay", "thong", "tin", "ve", "la", "gi", "cua", "cho", "va", "co", "the", "official", "site", "com", "org", "www", "https", "ai", "developer", "bao", "nhieu"}
    text = normalize(query)
    terms = set(re.findall(r"[a-z0-9_]+", text)) - stop
    terms-={'viet','tat','noi','tieng','nghien','cuu','su','dung'}
    if re.search(r'\bai (?:tao ra|sang lap)\b',text):
        entities=re.findall(r'\b[A-Z][A-Za-z]{2,}\b',query)
        if entities: terms={normalize(entity) for entity in entities} | {'created','developed','founded','conceived','invented','launched','creator','tao','thiet','phat','sang'}
    if "phien ban" in text: terms.update(("version", "release"))
    if "moi nhat" in text: terms.update(("latest", "release"))
    if "do chac" in text or "tin cay" in text: terms.update(("confidence", "probability"))
    if "confidence" in terms: terms.update(("probabilities", "distribution", "computed", "statistic"))
    if 'he mat troi' in text:terms.update(('solar','system'))
    if 'hanh tinh' in text:terms.add('planets')
    if 'thu do' in text:terms.add('capital')
    return terms


def passage_score(line, query):
    anchor_query=re.sub(r'https?://\S+','',normalize(query))
    anchors=re.findall(r'\b(?:[a-z0-9]+_[a-z0-9_]+|(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)[a-z0-9-]{4,})\b',anchor_query)
    if any(anchor not in normalize(line) for anchor in anchors):return -1
    terms = terms_for(query)
    words = set(re.findall(r"[a-z0-9_]+", normalize(line)))
    overlap = terms & words
    # Reject weak one-word matches for multi-concept questions.
    if len(overlap) < min(2, len(terms)): return -1
    attributes = {"confidence", "calibration", "probability", "version", "latest", "release", "action_set_alarm", "api"}
    required = terms & attributes
    if required and not (required & words): return -1
    count=re.search(r'\bbao nhieu\s+([a-z]+(?:\s+[a-z]+)?)',normalize(query))
    if count:
        noun='(?:hanh tinh|planets)' if count[1]=='hanh tinh' else re.escape(count[1])
        if not re.search(r'\b(?:\d+|mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi|one|two|three|four|five|six|seven|eight|nine|ten)\s+'+noun+r'\b',normalize(line)):return -1
        if not re.search(r'vung|region|inner|outer',normalize(query)) and re.search(r'vung trong|vung ngoai|inner|outer|dat da',normalize(line)):return -1
    for phrase, alternatives in {'thu do':('thu do','capital'), 'tao ra':('tao ra','tao boi','thiet ke','created','creator','sang lap')}.items():
        if phrase in normalize(query) and not any(item in normalize(line) for item in alternatives):return -1
    if re.search(r'\bai (?:tao ra|sang lap)\b',normalize(query)):
        if not re.search(r'\b(?:created|developed|founded|conceived|invented|launched)\b.{0,65}\bby\b|\b(?:do|duoc)\b.{0,80}\b(?:tao ra|thiet ke|phat trien|sang lap)\b',normalize(line)):
            return -1
        # A definition mentioning 'created' is not yet an answer about its author.
        tokens=re.findall(r'\b\w+\b',line)
        names=any(tokens[i][0].isupper() and ((tokens[i+1][0].isupper() and tokens[i+1][1:].islower()) or
                 (tokens[i+1] in ('van','von','de') and i+2<len(tokens) and tokens[i+2][0].isupper())) for i in range(len(tokens)-1))
        if not names:return -1
        english_by=list(re.finditer(r'\b(?:created|developed|founded|conceived|invented|launched)\b.{0,65}\bby\s+([^\W\d_])',line,flags=re.I))
        if english_by and not any(match[1].isupper() for match in english_by):return -1
        entities=re.findall(r'\b[A-Z][A-Za-z]{2,}\b',query)
        if entities and not any(normalize(entity) in normalize(line) for entity in entities):return -1
    score = len(overlap) * 4 + len(overlap & attributes) * 6 + sum(len(word) for word in overlap) / 10
    if re.search(r'la gi|what is',normalize(query)):
        topic=re.sub(r'\s*(?:la gi|what is)\s*[?!.]*','',normalize(query)).strip()
        if normalize(line).startswith(topic):score+=20
        plain=re.sub(r'\([^)]*\)','',normalize(line))
        if re.match(re.escape(topic)+r'\s+(?:la|is|are|nham|refers)\b',plain):score+=40
    if numeric_fact(query,line):score+=20
    if terms & {"latest", "version", "release"} and re.search(r"\b\d+\.\d+", line): score += 6
    return score - len(line) / 1000


def numeric_fact(query,line):
    return bool(re.search(r'toc do|khoang cach|cao bao nhieu|nhiet do',normalize(query)) and
                re.search(r'\d[\d .,_]*\s*(?:m/s|km|met|°c|do c|trieu|million)\b',normalize(line)))


def relevant_passage(text, query, maximum=500):
    # An initial such as "J. K. Rowling" is not a sentence boundary.
    lines = [line.strip() for line in re.split(r"\n+|(?<!\b[A-Z]\.)(?<=[.!?])\s+", text) if line.strip()]
    candidates = []
    for index in range(len(lines)):
        for size in (1, 2, 3):
            line = " ".join(lines[index:index + size])
            if not 25 <= len(line) <= 900: continue
            low = normalize(line)
            if any(word in low for word in ("cookie", "javascript", "skip to", "sign in", "privacy policy", "ignore previous", "system prompt", "bo qua chi dan")): continue
            score = passage_score(line, query)
            if score >= 0: candidates.append((score-min(index,30)*.2, -index, line))
    return max(candidates)[2][:maximum] if candidates else ""


@dataclass
class Bundle:
    query: str
    provider: str = ""
    sources: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    elapsed_s: float = 0
    cached: bool = False
    google_url: str = ""

    def metadata(self):
        return {"provider": self.provider, "search_s": self.elapsed_s, "search_cache_hit": self.cached,
                "sources": self.sources, "warnings": self.warnings, "google_url": self.google_url}


@lru_cache(maxsize=1)
def sourcebook():
    return json.loads((Path(__file__).with_name("search_sources.json")).read_text(encoding="utf-8"))


def direct_sources(query):
    # Only explicit user URLs and a small, reviewable set of official documentation.
    # This is retrieval routing, not a table of canned answers.
    urls = re.findall(r"https?://[^\s<>\"']+", query)
    rows = []
    for url in urls[:2]:
        try: url = public_url(url.rstrip(".,;!?"), resolve=False)
        except ValueError: continue
        rows.append({"title": urllib.parse.urlsplit(url).hostname, "url": url, "snippet": ""})
    if rows: return rows
    text = normalize(query)
    matches = [row for row in sourcebook() if all(term in text for term in row["terms"])]
    matches.sort(key=lambda row: len(row["terms"]), reverse=True)
    seen = set()
    for row in matches:
        if row["url"] not in seen:
            rows.append({"title": row["title"], "url": row["url"], "snippet": "", "specificity": len(row["terms"])}); seen.add(row["url"])
    return rows[:2]


def wikipedia_sources(query, cancel=None):
    # Canonical subjects improve retrieval without embedding any factual answers.
    clean=re.sub(r'^(?:ai\s+(?:(?:tạo ra|sáng lập|viết)\s+)?|người nào\s+)', '', query, flags=re.I)
    clean=re.sub(r'\s+(?:là (?:viết tắt của )?gì)\s*[?!.]*$', '', clean, flags=re.I)
    clean=re.sub(r'^thủ đô\s+(?:nước\s+)?','',clean,flags=re.I)
    clean=re.split(r'\s+(?:có\s+)?bao nhiêu\s+|\s+nổi tiếng\s+|\s+sử dụng\s+',clean,maxsplit=1,flags=re.I)[0]
    clean=re.sub(r'^(?:cây|thực vật)\s+','',clean,flags=re.I)
    creator=bool(re.search(r'\bai (?:tao ra|sang lap)\b',normalize(query)))
    if creator:
        entities=re.findall(r'\b[A-Z][A-Za-z]{2,}\b',query)
        if entities:clean=' '.join(entities)
    language='vi' if any(ord(c)>127 for c in query) else 'en'
    if creator and re.search(r'\b[A-Z][A-Za-z]{2,}\b',query):
        language='en'
        if 'ngon ngu' in normalize(query):clean+=' programming language'
    if re.fullmatch(r'[A-Z]{2,8}',clean):language='en'
    host=language+'.wikipedia.org'
    base={'action':'query','prop':'extracts','explaintext':1,'exintro':1,'format':'json','redirects':1}
    def retrieve(params):
        data,_,_=fetch('https://'+host+'/w/api.php?'+urllib.parse.urlencode(params),cancel=cancel)
        pages=json.loads(data).get('query',{}).get('pages',{}).values();rows=[]
        for page in sorted(pages,key=lambda row:row.get('index',99)):
            if 'missing' in page:continue
            text=page.get('extract','')[:12000];excerpt=relevant_passage(text,query)
            if not excerpt:continue
            rows.append({'title':page['title']+' — Wikipedia','url':'https://'+host+'/wiki/'+urllib.parse.quote(page['title'].replace(' ','_')),
                         'snippet':'','excerpt':excerpt,'read':True,'fetched_at':time.strftime('%Y-%m-%d %H:%M:%S'),'retrieval':'public_article_extract_api',
                         'topic_match':normalize(page['title'])==normalize(clean)})
        return rows
    try:
        # Exact title/redirect first, then one bounded full-text search if needed.
        rows=retrieve({**base,'titles':clean})
        if rows:return rows
        rows=retrieve({**base,'generator':'search','gsrsearch':clean,'gsrlimit':2,'gsrnamespace':0})
        if rows:return rows
        if language=='vi' and re.search(r'\b[A-Z][A-Za-z]{2,}\b',clean):
            host='en.wikipedia.org'
            return retrieve({**base,'titles':clean})
        return []
    except SearchCancelled:raise
    except (OSError,ValueError,KeyError):return []


def search(question, cancel=None):
    global _google_retry
    start = time.monotonic(); query = query_text(question)
    bundle = Bundle(query, google_url="https://www.google.com/search?" + urllib.parse.urlencode({"q": query}))
    if len(query) < 3 or normalize(query) in ("no", "cai nay", "gi", "tim"):
        bundle.warnings.append("Chủ nhân muốn tìm thông tin về chủ đề nào? Hãy nêu tên hoặc câu hỏi cụ thể.")
        return bundle
    with _lock:
        cached = _cache.get(query)
        if cached and start - cached[0] < 300:
            result = copy.deepcopy(cached[1]); result.cached = True
            result.elapsed_s = round(time.monotonic() - start, 4)
            check_cancel(cancel); return result
    results = []
    if start >= _google_retry:
        try:
            data, final, _ = fetch(bundle.google_url + "&gbv=1&num=5", cancel=cancel)
            results = parse_google(data)
            if not results:
                raise ValueError("Google không cung cấp kết quả HTML có thể đọc trong chế độ nhẹ.")
            bundle.provider = "Google"
        except SearchCancelled: raise
        except (OSError, ValueError, ET.ParseError):
            _google_retry = time.monotonic() + 300
    if not results:
        results = direct_sources(query)
        if results:
            bundle.provider = "Nguồn chính thức trực tiếp" if not re.search(r"https?://", query) else "Trang được chỉ định"
    sites = re.findall(r"\bsite:([a-z0-9.-]+)", query.lower())
    volatile=re.search(r'\b(?:moi nhat|hien nay|hien tai|hom nay|tin tuc|thoi tiet|latest|current|today|weather)\b',normalize(query))
    if not results and not sites and not volatile:
        bundle.sources=wikipedia_sources(query,cancel)
        if bundle.sources:bundle.provider='Wikipedia'
    if not results and not bundle.sources:
        try:
            data, _, _ = fetch("https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "format": "rss"}), cancel=cancel)
            results = parse_bing(data); bundle.provider = "Bing"
        except SearchCancelled: raise
        except (OSError, ValueError, ET.ParseError):
            bundle.warnings.append("Không lấy được kết quả tìm kiếm. Có thể mở Google bằng liên kết bên dưới.")
    if bundle.provider != "Google":
        bundle.warnings.insert(0, "Google chưa đọc được trong chế độ nhẹ; nguồn thực dùng: " + (bundle.provider or "chưa có") + ".")
    check_cancel(cancel)
    if sites:
        results = [row for row in results if any(urllib.parse.urlsplit(row["url"]).hostname == site or
                   urllib.parse.urlsplit(row["url"]).hostname.endswith("." + site) for site in sites)]
    # Prefer a domain explicitly named by the query, not claims of 'official' in a title.
    terms = terms_for(query)
    def ranking(row):
        host = urllib.parse.urlsplit(row["url"]).hostname
        domain_terms = set(re.findall(r"[a-z0-9_]+", host)) & terms
        return len(domain_terms) * 5 + len(terms & set(re.findall(r"[a-z0-9_]+", normalize(row["title"])))) + row.get("specificity", 0) * 20 + int(row.get('topic_match',False))*30
    results.sort(key=ranking, reverse=True)
    results=[row for row in results if passage_score(row['title']+' '+row['snippet'],query)>=0 or row.get('specificity') or bundle.provider in ('Google','Trang được chỉ định')]
    # Keep no more than two external pages in memory at once, no crawling.
    def read_page(item):
        source = dict(item); source.update(read=False, excerpt="", fetched_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            budget = 1_250_000 if urllib.parse.urlsplit(source["url"]).hostname == "developer.android.com" else MAX_BYTES
            data, final, _ = fetch(source["url"], timeout=4 if budget>MAX_BYTES else 3, cancel=cancel, max_bytes=budget)
            page = Page(); page.feed(data)
            excerpt = relevant_passage(page.text(), query)
            if excerpt:
                source.update(url=final, excerpt=excerpt, read=True)
        except SearchCancelled: raise
        except (OSError, ValueError) as exc:
            source["read_error"] = type(exc).__name__
        if not source["excerpt"]:
            source["excerpt"] = relevant_passage(source["snippet"], query)
        return source
    with concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="altair-web") as pool:
        pending = [pool.submit(read_page, item) for item in results[:3]]
        for future in pending:
            check_cancel(cancel)
            source = future.result()
            if source["excerpt"]: bundle.sources.append(source)
    # Relevance and domain preference do not establish truth or source agreement.
    bundle.sources.sort(key=lambda row: passage_score(row["excerpt"], query) + ranking(row) / 4, reverse=True)
    bundle.sources = bundle.sources[:3]
    for index, source in enumerate(bundle.sources, 1): source["id"] = index
    bundle.elapsed_s = round(time.monotonic() - start, 3)
    if not bundle.sources:
        bundle.warnings.append("Chưa đọc được nguồn chứa thông tin liên quan đủ rõ.")
    with _lock:
        _cache[query] = (time.monotonic(), copy.deepcopy(bundle))
        _cache.move_to_end(query)
        while len(_cache) > 16: _cache.popitem(last=False)
    return bundle


def quick_answer(bundle):
    if not bundle.sources:
        return "\n".join(bundle.warnings) + "\n\nMở Google: " + bundle.google_url
    parts = ["Thông tin tìm được (trích nguồn, chưa phải kết luận tổng hợp):"]
    domains = set()
    for source in bundle.sources:
        host = urllib.parse.urlsplit(source["url"]).hostname
        if host in domains: continue
        domains.add(host)
        # Short excerpts, not full articles. Full source is a separate clickable link.
        words = source["excerpt"].split()
        windows = [" ".join(words[start:start + 22]) for start in range(max(1, len(words) - 21))]
        excerpt = max(windows, key=lambda line: passage_score(line, bundle.query)+int(numeric_fact(bundle.query,line))*100)
        label = "trang nguồn" if source["read"] else "đoạn mô tả tìm kiếm; chưa đọc được trang"
        parts.append(f"[{source['id']}] {excerpt}… ({label})")
    if bundle.warnings: parts.append(bundle.warnings[0])
    return "\n\n".join(parts)


def model_context(bundle):
    return "\n".join(f"[{source['id']}] {source['title'][:90]} ({'đã đọc trang' if source['read'] else 'chỉ mô tả tìm kiếm'}): {source['excerpt'][:500]}" for source in bundle.sources[:2])[:1400]


def valid_summary(answer, bundle):
    ids = {str(row["id"]) for row in bundle.sources[:2]}
    refs = re.findall(r"\[(\d+)\]", answer)
    if not refs or not set(refs) <= ids or re.search(r"https?://|www\.", answer): return False
    facts = " ".join(row["excerpt"] for row in bundle.sources[:2])
    # A basic guard only; citation existence does not verify semantic entailment.
    if any(number not in facts for number in re.findall(r"\b\d+(?:[.,]\d+)*\b", re.sub(r"\[\d+\]", "", answer))): return False
    # Catch new place/person/product names that are absent from the supplied evidence.
    allowed=set(re.findall(r'\b[^\W\d_][\w-]*\b',normalize(facts+' '+bundle.query+' '+' '.join(row['title'] for row in bundle.sources[:2]))))
    first_words={'thu','the','nguoi','ngon','bo','day','cac','mot','chung','no','thong','ket','co','khong','vi','theo','khi','nhu','ban','phien','gia','toc','khoang','so','giao','ung','trinh','he','phan','diem','tu','chua','neu','voi','hoi','mua','nuoc','tac','chuc','tinh','thuoc','noi','tai','ten','dia','quyen'}
    for sentence in re.split(r'(?<=[.!?])\s+|\n+',answer):
        tokens=re.findall(r'\b[^\W\d_][\w-]*\b',sentence)
        for index,token in enumerate(tokens):
            key=normalize(token)
            if token[0].isupper() and key not in allowed and not (index==0 and key in first_words):return False
    return True
