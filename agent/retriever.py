"""Retriever keyword nhe (khong embedding -> khong lag)."""
import os, re
from collections import Counter

def read_capped(path: str, max_chars: int = 12000) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read(max_chars)
    except OSError as e:
        return f"<khong doc duoc {path}: {e}>"

def score_file(text: str, keywords: list[str]) -> int:
    """Cu (giu de khong gianh API): dem tu khoa thong thuong."""
    low = text.lower()
    s = 0
    for kw in keywords:
        s += low.count(kw.lower()) * (3 if len(kw) > 4 else 1)
    return s

def bm25(text: str, kws: list, df: dict, avgdl: float, N: int) -> float:
    """BM25 (k1=1.5, b=0.75) - hoc rieng (2025): tu khoa HIEM quan trong hon tu thuong,
    chieu dai van ban duoc chuan hoa (file dai khong duoc diem thang vi nhieu tu).
    Stdlib only, khong embedding, khong lag."""
    import math
    k1, b = 1.5, 0.75
    low = text.lower()
    dl = max(1, len(text.split()))
    s = 0.0
    for kw in kws:
        tf = low.count(kw)
        if not tf:
            continue
        n = df.get(kw, 0)
        idf = math.log(1.0 + (N - n + 0.5) / (n + 0.5))
        s += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(avgdl, 1.0)))
    return s

IMPORT_PAT = re.compile(
    r"^\s*(?:import|from|require\(|use |include |mod )[\s\"'\(]*([\w\-./\\]+)",
    re.MULTILINE)

def _resolve_import(imp: str, src_entry, by_path: dict):
    """Tim file duoc import trong entries (khop duoi duong dan)."""
    cand = imp.replace("/", os.sep).strip(" .\"'")
    if len(cand) < 3:
        return None
    for key, e in by_path.items():
        if key.endswith(cand) or cand in key:
            if e["full"] != src_entry["full"]:
                return e
    return None

def expand_neighbors(picked, entries, max_total: int = 3):
    """Them file ke: file duoc import + file import no (1 nhay). Data day hon."""
    by_path = {e["path"].replace("/", os.sep): e for e in entries}
    seen = {e["full"] for e, _ in picked}
    extra = []
    for e, _ in picked:
        try:
            with open(e["full"], encoding="utf-8", errors="ignore") as f:
                head = f.read(8000)
        except OSError:
            continue
        for m in IMPORT_PAT.finditer(head):
            hit = _resolve_import(m.group(1), e, by_path)
            if hit and hit["full"] not in seen:
                seen.add(hit["full"])
                extra.append((hit, read_capped(hit["full"], max_chars=3000)))
                if len(picked) + len(extra) >= max_total:
                    return picked + extra
    return picked + extra

def with_line_numbers(text: str, max_lines: int = 220) -> str:
    out = []
    for i, line in enumerate(text.splitlines()[:max_lines], 1):
        out.append(f"{i:4d}| {line}")
    return "\n".join(out)

def retrieve(query: str, entries, top_k: int = 3, max_chars_each: int = 4000):
    # uu tien 1: query neu chi ro file cu the (vd src/cli.mjs) -> doc thang, KHONG search.
    # Lay TAT CA ten file duoc neu (truoc chi lay 1 -> hoi 2 file ma chi doc duoc 1).
    import os
    PAT = r"[\w\-./\\]+\.(?:mjs|cjs|js|ts|tsx|py|rs|go|html|css|json|toml|md)"
    cands = []
    for m in re.finditer(PAT, query):
        cand = m.group(0).replace("/", os.sep).strip(".")
        if cand and cand not in cands:
            cands.append(cand)
    if cands:
        picked = []
        for cand in cands:
            for e in entries:
                ep = e["path"].replace("/", os.sep)
                if ep.endswith(cand) or cand in ep:
                    if all(x["full"] != e["full"] for x in picked):
                        picked.append(e)
                    break
            else:
                # thu doc truc tiep tu repo hien tai
                fp = cand if os.path.isabs(cand) else os.path.join(os.path.dirname(entries[0]["full"]) if entries else ".", cand)
                if not os.path.isfile(fp):
                    fp = cand
                if os.path.isfile(fp):
                    picked.append({"path": cand, "full": fp, "ext": os.path.splitext(cand)[1],
                                   "lines": 0, "symbols": []})
        if picked:
            return [(e, read_capped(e["full"], max_chars=max_chars_each)) for e in picked[:3]]
    kws = [w for w in re.split(r"\W+", query.lower()) if len(w) >= 3][:12]
    # BM25: can IDF (df toan corpus) + do dai binh quan truoc khi cham tung file
    docs = []
    for e in entries:
        bonus = 2 if e["ext"] in (".rs", ".go", ".py", ".ts", ".tsx", ".js") else 0
        docs.append((e, read_capped(e["full"], max_chars=20000), bonus))
    N = max(1, len(docs))
    df = {kw: sum(1 for _e, t, _b in docs if kw in t.lower()) for kw in kws}
    avgdl = sum(len(t.split()) for _e, t, _b in docs) / N
    scored = []
    for e, text, bonus in docs:
        sc = bm25(text, kws, df, avgdl, N) + bonus
        # van uu tien ten file / symbol trung query (exact match manh)
        if any(k in e["path"].lower() for k in kws):
            sc += 5
        if any(k in (s.lower() for s in e["symbols"]) for k in kws):
            sc += 4
        scored.append((sc, e, text[:max_chars_each]))
    scored.sort(key=lambda x: -x[0])
    picked = [(e, t) for sc, e, t in scored[:top_k] if sc > 0] or [(e, t) for _, e, t in scored[:2]]
    try:
        from agent.so_tags import detect as _so
        qt = set(_so(query))
        if qt:
            rescored = []
            for e, t in picked:
                overlap = qt & set(_so(t[:4000]))
                rescored.append((len(overlap), e, t))
            rescored.sort(key=lambda x: -x[0])
            picked = [(e, t) for _o, e, t in rescored]
    except Exception:
        pass
    try:
        picked = expand_neighbors(picked, entries, max_total=max(top_k, 3))
    except Exception:
        pass
    return picked
