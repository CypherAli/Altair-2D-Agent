"""Keo StackOverflow top Q&A theo tag -> SQLite offline cho Ali. Stdlib only.
Chay: python agent/so_fetch.py [pages-per-tag] . 1 request = 100 cau (quota free 300/ngay)."""
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE_DIR, "so_data", "so.sqlite")
API = "https://api.stackexchange.com/2.3"
SITE = dict(site="stackoverflow", pagesize="100", filter="withbody")

TAGS = ["python", "javascript", "typescript", "rust", "go"]
EXTRA_TAGS = ["sql", "node.js", "reactjs", "docker", "git", "regex", "css", "html"]

STRIP_RE = re.compile(r"<pre>(.*?)</pre>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def clean_body(raw):
    parts = []

    def keep_code(m):
        code = TAG_RE.sub("", m.group(1))
        parts.append(("code", html.unescape(code).strip()[:2000]))
        return "\n[CODE]\n"

    text = STRIP_RE.sub(keep_code, raw or "")
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()[:4000]
    return text, [c for _k, c in parts]


def get(url, params):
    qs = urllib.parse.urlencode(dict(SITE, **params))
    req = urllib.request.Request(API + url + "?" + qs,
                                 headers={"User-Agent": "AliStudio/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    if data.get("backoff"):
        time.sleep(int(data["backoff"]) + 1)
    return data


def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    db = sqlite3.connect(DB)
    db.execute("""CREATE TABLE IF NOT EXISTS qa(
        qid INTEGER PRIMARY KEY, tag TEXT, title TEXT, score INTEGER,
        qbody TEXT, abody TEXT, link TEXT)""")
    db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS qa_fts USING fts5(
        title, body)""")
    return db


def fetch_tag(db, tag, pages):
    have = {r[0] for r in db.execute("SELECT qid FROM qa WHERE tag=?", (tag,))}
    got = 0
    for page in range(1, pages + 1):
        try:
            data = get("/questions", dict(order="desc", sort="votes",
                                          tagged=tag, page=str(page)))
        except Exception as ex:
            print(f"[{tag}] p{page} LOI: {ex}")
            break
        items = [it for it in data.get("items", [])
                 if it.get("is_answered") and it.get("accepted_answer_id")
                 and it["question_id"] not in have]
        if not items:
            print(f"[{tag}] p{page}: het cau moi")
            if not data.get("has_more"):
                break
            continue
        aids = [str(it["accepted_answer_id"]) for it in items]
        try:
            adata = get("/answers/" + ";".join(aids), dict(order="desc", sort="votes"))
        except Exception as ex:
            print(f"[{tag}] answers LOI: {ex}")
            break
        amap = {a["answer_id"]: a.get("body", "") for a in adata.get("items", [])}
        for it in items:
            abody = amap.get(it["accepted_answer_id"], "")
            if not abody:
                continue
            qb, _qc = clean_body(it.get("body", ""))
            ab, _ac = clean_body(abody)
            link = f"https://stackoverflow.com/q/{it['question_id']}"
            db.execute("INSERT OR IGNORE INTO qa VALUES (?,?,?,?,?,?,?)",
                       (it["question_id"], tag, it.get("title", ""),
                        it.get("score", 0), qb, ab, link))
            db.execute("INSERT OR IGNORE INTO qa_fts(rowid,title,body) VALUES (?,?,?)",
                       (it["question_id"], it.get("title", ""), qb + "\n" + ab))
            have.add(it["question_id"])
            got += 1
        db.commit()
        print(f"[{tag}] p{page}: +{len(items)} (tong {got})", flush=True)
        if not data.get("has_more"):
            break
        time.sleep(2)
    return got


if __name__ == "__main__":
    import sys as _s
    pages = int(_s.argv[1]) if len(_s.argv) > 1 else 3
    only = [a for a in _s.argv[2:] if not a.startswith("-")]
    tags = only or (TAGS + (EXTRA_TAGS if "--extra" in _s.argv else []))
    db = init_db()
    total = sum(fetch_tag(db, t, pages) for t in tags)
    n = db.execute("SELECT COUNT(*) FROM qa").fetchone()[0]
    print(f"XONG: them {total}, tong DB {n} cau")
    db.close()
