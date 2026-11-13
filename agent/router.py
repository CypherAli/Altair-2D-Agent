"""Router hieu nghi cau user: intent theo DIEM, focus file, van de dang noi chuyen.
Stdlib only. Hieu ca tieng Viet co dau, tieng Anh, chat gon, cau vang ro.
Thay vi "danh dau tu khoa dau tien" (sai voi 'viet test cho file nay'), tong diem
cac tu khoa quyet dinh intent -> hieu dung hon nhieu truong hop hon.
"""
import unicodedata, re, string

def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

# (tu khoa, diem). Diem cao = ro y dinh hon. "test"/"check" cho diem thap vi xanh dua
# ("viet test cho router.py" phai la WRITE, khong phai REVIEW).
REVIEW_KEYS = {
    "review": 3, "bug": 3, "crash": 3, "audit": 3, "bao mat": 3, "security": 3,
    "lo hong": 3, "deadlock": 3, "race": 3, "nhieu loi": 3, "xau": 2,
    "sua loi": 3, "fix": 3, "loi": 2, "toi uu": 2, "performance": 2, "slow": 2,
    "sua": 2, "check": 1, "test": 1, "kiem tra": 1, "kiem dinh": 2, "rate limit": 2,
}
WRITE_KEYS = {
    "refactor": 3, "implement": 3, "viet lai": 3, "dung lai": 2, "build": 2,
    "viet": 2, "tao": 2, "them": 2, "write": 2, "create": 2, "add": 2, "lap": 2,
    "tinh nang": 2, "hoan thien": 2, "lam": 1, "sua doi": 1, "chuyen doi": 2,
}
ASK_KEYS = {
    "giai thich": 3, "explain": 3, "how does": 3, "what does": 3, "describe": 2,
    "mo ta": 2, "what is": 2, "la gi": 2, "lam gi": 2, "de lam gi": 2, "hoat dong": 2,
    "tom tat": 2, "summar": 2, "tai sao": 3, "why": 3, "o dau": 2, "where": 2,
    "nghi gi": 2, "hieu": 1, "khac gi": 2, "chuc nang": 2,
}
# chat thuong (chao cam on...) -> tra loi 1-2 cau, khong checklist
CHAT_KEYS = ("cam on", "thanks", "thank you", "hello", "hi ", "chao", "ok nhe",
             "hay qua", "giai lai", "tuyet voi", "hieu roi", "oke", "yal", "lol")

# Dung char class tu string + re.escape(chr(92)) tranh loi escaping backslash.
_P = chr(92)  # mot backslash that
_EXT = "mjs|cjs|js|ts|tsx|jsx|py|rs|go|java|html|css|scss|json|toml|yaml|yml|md|sql|sh"
DOT = re.escape(chr(92) + ".")   # mot backslash + cham, da escape cho regex
WB = re.escape(chr(92) + "b")    # word boundary
# Nhan dien file KHONG dung backslash regex (tranh loi escaping) -> substring + endswith.
EXTS = ('mjs', 'cjs', 'js', 'ts', 'tsx', 'jsx', 'py', 'rs', 'go', 'java', 'html', 'css', 'scss', 'json', 'toml', 'yaml', 'yml', 'md', 'sql', 'sh')

def focus_files(q: str) -> list:
    out = []
    for tok in re.split(r"[^0-9A-Za-z_./\-]+", q):
        t = tok.strip("./")
        if "." not in t:
            continue
        if t.lower().endswith(EXTS) and len(t) > 3 and t not in out:
            out.append(t)
    return out[:5]

_REF_WORDS = ("no", "cai do", "cai tren", "file do", "van do", "cai nay", "tiep theo",
              "nhu vay", "how about it", "that file", "the file", "above")

def _mentions_file(q: str) -> bool:
    return bool(focus_files(q))



def _hit_count(text: str, table: dict) -> int:
    s = 0
    for k, w in table.items():
        if k in text:
            s += w
    return s


def detect_intent(q: str) -> str:
    """Tra ve ask | review | write | chat. Cham theo tong diem tu khoa."""
    n = " " + norm(q).strip() + " "
    if not n.strip():
        return "ask"
    sc = {
        "review": _hit_count(n, REVIEW_KEYS),
        "write": _hit_count(n, WRITE_KEYS),
        "ask": _hit_count(n, ASK_KEYS),
    }
    # cau hoi (la gi / tai sao / how does) chi co y dinh hoi dap
    if sc["ask"] >= max(sc.values()) and sc["ask"] > 0:
        return "ask"
    best = max(sc.values())
    if best == 0:
        if any(k in n for k in CHAT_KEYS) and len(n.strip()) < 40:
            return "chat"
        return "ask"
    if sc["review"] == best and sc["write"] == best:
        return "review" if re.search(r"sua loi|fix|review|bug|crash", n) else "write"
    if sc["review"] == best:
        return "review"
    if sc["write"] == best:
        return "write"
    return "ask"


def rewrite_query(q: str, history: list) -> str:
    """Noi van de dang noi chuyen vao cau hoi gon ('no', 'cai do', 'file do'...).
    Khong co lich su thi giu nguyen. Khong goi LLM -> khong cham."""
    if not history:
        return q
    nq = norm(q)
    if not any(w in nq for w in _REF_WORDS):
        return q
    last = history[-1]
    return (f"[Ngu dung cuoc noi chuyen] Truoc do user hoi: \"{last.get('q', '')[:180]}\" "
            f"(Ali da tra loi: \"{last.get('a', '')[:200]}\").\n"
            f"Cau hoi moi (co the dung tu chi/nhan xet): {q}")


def clarify_needed(q: str, intent: str) -> str:
    """Cau qua ngan + khong ro doi tuong -> yeu cau model hoi lai 1 cau, khong doan bua."""
    n = norm(q).strip()
    if intent in ("review", "write") and not _mentions_file(q) and len(n) < 30:
        return ("CAU HINH RO: user chua noi ro file/van de nao. "
                "Hoi NGAY 1 cau ngan (ten file hoac mo ta van de), dung tra loi doan.\n")
    if len(n) < 3:
        return "Cau qua ngan, hoi 1 cau ro y dinh cua user truoc khi tra loi.\n"
    return ""


def build_prompt(intent: str, query: str, repo_map: str, files, history: list) -> str:
    from agent.retriever import with_line_numbers
    hist = ""
    if history:
        hist = ("Cuoc noi chuyen truoc (dung de hieu tu/chu de dang noi):\n"
                + "\n".join(f"- Hoi: {h['q'][:200]}\n- Dap: {h['a'][:300]}"
                            for h in history[-2:]) + "\n\n")
    if intent == "chat":
        # khong nạp CODE -> ton ~100s eval prompt vo ich cho chuyen thuong
        return (f"{hist}CAU HOI CUA USER: {query}\n\n"
                "Day la chat thuong (chao/ghi chu cam on). Tra loi 1-2 cau tu nhien bang "
                "tieng Viet, khong checklist, khong can code. Neu user dang hoi ky nghe "
                "gioi thieu thi hoi 1 cau ngan cho ro.\n")
    ctx = "\n\n".join(f"===== {e['path']} =====\n{with_line_numbers(t, 120)}" for e, t in files)
    # Lost-in-the-Middle: cau hoi o DAU + CUOI -> model khong bo qua khi context dai
    base = (f"{hist}CAU HOI CUA USER: {query}\n\n"
            f"Repo:\n{repo_map[:1200]}\n\nCODE:\n{ctx[:5000]}\n\n"
            f"Nho lai CAU HOI: {query}\n\n")
    try:
        from agent.so_tags import context_line as _soline
        _so = _soline(query)
        if _so:
            base += _so + " Dung dung ten API/thu vien theo mien nay, khong doan dai.\n\n"
    except Exception:
        pass
    if intent in ("ask", "review"):
        try:
            from agent.so_search import context_block as _soblock
            _sob = _soblock(query)
            if _sob:
                base += _sob + "\n\n"
        except Exception:
            pass
    ground = ("Luat bat buoc: chi noi nhung gi co trong CODE tren. Trich dan FILE:DONG. "
               "Khong doan ten thu vien/ham ngoai CODE. Khong chac thi noi 'khong ro'.\n"
               "[MEMORY] chi la tinh cach/nguyen tac lam viec, KHONG phai noi dung code - "
               "khong mo ta file/noi dung khong xuat hien trong CODE.\n"
               "Ngon ngu: tra loi bang tieng Viet neu user hoi tieng Viet, tieng Anh neu user hoi tieng Anh. "
               "Dung dung ngon ngu trong cau hoi cua user.\n"
               "Hieu y dinh: neu user dang keo dai 1 van de (xem cuoc noi chuyen tren) "
               "thi tra loi TIEP van de do, dung bat dau lai tu dau.\n")
    if intent == "review":
        return (base + ground +
                "Ban la senior reviewer. Chi list loi that kem FILE:DONG, trich 1 dong loi, "
                "code sua toi thieu, lenh kiem tra. Khong thay loi thi noi ro. Ngan gon.\n"
                "Vi du dung:\nagent/tools.py:12 - shell=True cho phep injection qua ';'. Sua: shell=False + args list.\n"
                + clarify_needed(query, intent))
    if intent == "write":
        return (base + ground +
                "De xuat phuong an sua theo muc: file nao, doi gi, code mau ngan. "
                "Hoi xac nhan truoc khi sua, khong tu sua. Ngan gon.\n"
                "Khi user dong y, xuat file theo format may doc (full noi dung file moi):\n"
                "@@ FILE: duong/dan/tuong/doi\n```ngonngu\n<toan bo code file>\n```\n"
                + clarify_needed(query, intent))
    return (base + ground +
            "Tra loi truc tiep cau hoi, dung so dong/file cu the. "
            "Hoi 'bao nhieu bullets' thi dung so luong do. Ngan gon, khong checklist review.\n"
            "Cach nghi: (1) liet ke 2-4 su kien co trich dan FILE:DONG, (2) roi moi ket luan. "
            "Khong du du kien thi ket luan 'chua du du lieu' thay vi doan.\n"
            "Vi du dung:\nHoi: What does src/cli.mjs do? 5 bullets max.\nDap:\n"
            "- CLI entry: parse args xuat PDF\n- Goi build-extension truoc khi export\n"
            "- Dung Playwright render trang\n- Ghi file ra out/ (cli.mjs:31)\n"
            "- Loi in ra stderr, exit 1 (cli.mjs:44)\n")
