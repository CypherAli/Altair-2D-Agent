"""Tim kiem tri thuc StackOverflow offline (SQLite FTS5). Stdlib only."""
import os
import re
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE_DIR, "so_data", "so.sqlite")


def _tokens(q, n=8):
    words = [w for w in re.split(r"\W+", q.lower()) if len(w) > 3]
    seen, out = set(), []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append('"%s"' % w)
    return " OR ".join(out[:n])


def search(query, limit=2):
    """Tra [{title, abody, link}]. Tieu de trong so gap 3 + uu tien tag trung mien hoi."""
    if not os.path.isfile(DB):
        return []
    mt = _tokens(query)
    if not mt:
        return []
    try:
        from agent.so_tags import detect as _so
        qt = set(_so(query))
    except Exception:
        qt = set()
    try:
        db = sqlite3.connect(DB)
        rows = db.execute(
            "SELECT qa.title, qa.abody, qa.link, qa.tag FROM qa_fts "
            "JOIN qa ON qa.qid = qa_fts.rowid "
            "WHERE qa_fts MATCH ? ORDER BY bm25(qa_fts, 3.0, 1.0) LIMIT ?",
            (mt, limit * 4)).fetchall()
        db.close()
    except Exception:
        return []
    scored = []
    for t, a, l, tag in rows:
        bonus = 0
        if qt and tag and any(tag in _t or _t in tag for _t in qt):
            bonus = 2
        scored.append((bonus, {"title": t, "abody": (a or "")[:1500], "link": l}))
    scored.sort(key=lambda x: -x[0])
    return [h for _b, h in scored[:limit]]


def context_block(query, max_chars=1500):
    hits = search(query)
    if not hits:
        return ""
    parts = []
    for h in hits:
        parts.append(f"- {h['title']}\n  Dap an duyet: {h['abody'][:700]}\n  ({h['link']})")
    return "Kien thuc StackOverflow offline:\n" + "\n".join(parts)[:max_chars]
