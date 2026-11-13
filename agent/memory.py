"""Memory vault-mini (hoc obsidian-mind + claude-mem), stdlib only."""
import os, json, time

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory")

FILES = {
    "north_star.md": "# North Star - Ali\n\nMuc tieu: tro ly code local Rieng cua Trinh. Chuyen web + Rust/Go/Python.\nNguyen tac: ngan gon, trung thuc, khong bia.\n",
    "decisions.md": "# Decisions (ADR mini)\n\n",
    "gotchas.md": "# Gotchas (bai hoc xuong mau)\n\n- Repo Ali_tool 15k file: khong quet full, chi doc file duoc chi dinh.\n- Prompt review cung khong dung cho cau hoi mo ta.\n",
    "patterns.md": "# Patterns\n\n",
}

def ensure():
    os.makedirs(BASE, exist_ok=True)
    for name, default in FILES.items():
        fp = os.path.join(BASE, name)
        if not os.path.exists(fp):
            with open(fp, "w", encoding="utf-8") as f:
                f.write(default)
    obs = os.path.join(BASE, "observations.jsonl")
    if not os.path.exists(obs):
        open(obs, "w", encoding="utf-8").close()

def briefing(budget: int = 4000) -> str:
    """Ghep north_star + gotchas + decisions + 5 obs gan nhat, duoi budget bytes."""
    ensure()
    parts = []
    for name in ("north_star.md", "gotchas.md", "decisions.md"):
        try:
            with open(os.path.join(BASE, name), encoding="utf-8") as f:
                parts.append(f"--- {name} ---\n" + f.read(1200))
        except OSError:
            pass
    try:
        with open(os.path.join(BASE, "observations.jsonl"), encoding="utf-8") as f:
            lines = f.readlines()[-5:]
        if lines:
            parts.append("--- recent observations ---\n" + "".join(lines)[:1200])
    except OSError:
        pass
    out = "\n".join(parts)
    return out[:budget]

def remember(type_: str, title: str, narrative: str, files: list | None = None, dedupe: bool = False):
    ensure()
    fp = os.path.join(BASE, "observations.jsonl")
    if dedupe:
        try:
            with open(fp, encoding="utf-8") as f:
                last = None
                for line in f:
                    if line.strip():
                        last = line
            if last and json.loads(last).get("title") == title[:60]:
                return  # cau lap lai lien tiep -> khong ghi rac
        except (OSError, ValueError):
            pass
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M"), "type": type_,
           "title": title[:60], "narrative": narrative[:500], "files": files or []}
    with open(fp, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

STOPWORDS = {"la", "gi", "nay", "cai", "cua", "va", "the", "gli", "what", "does", "with",
             "from", "nay", "thi", "ma", "de", "trong", "cho", "mot", "cac", "nhung"}

def search(query: str, limit: int = 10) -> str:
    """Grep don gian tren observations + decisions + gotchas -> index gon."""
    ensure()
    q = query.lower()
    words = [w for w in q.split() if len(w) > 2 and w not in STOPWORDS]
    if not words:
        return "(khong co memory lien quan)"
    hits = []
    for name in ("observations.jsonl", "decisions.md", "gotchas.md"):
        try:
            with open(os.path.join(BASE, name), encoding="utf-8") as f:
                for line in f:
                    if any(w in line.lower() for w in words):
                        hits.append(f"{name}: {line.strip()[:150]}")
                        if len(hits) >= limit:
                            return "\n".join(hits)
        except OSError:
            pass
    return "\n".join(hits) or "(khong co memory lien quan)"
