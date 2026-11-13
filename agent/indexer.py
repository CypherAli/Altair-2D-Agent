"""Indexer nhe: quet repo -> map (khong ton LLM)."""
import os, re

SKIP_DIRS = {".git", "target", "node_modules", ".cache", "__pycache__", ".venv", "dist", "build", ".next", "out", "vendor", "Pods", ".idea", ".vscode", "tmp", "temp", ".tmp"}
CODE_EXTS = {".rs", ".go", ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".toml", ".md"}

FUNC_PATTERNS = {
    ".py": re.compile(r"^\s*(?:def|class)\s+(\w+)"),
    ".rs": re.compile(r"^\s*(?:pub\s+)?fn\s+(\w+)"),
    ".go": re.compile(r"^\s*func\s+(?:\(\w+\s+[\w*]+\s*\)\s*)?(\w+)"),
    ".js": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)|^\s*(?:const|let|var)\s+(\w+)\s*="),
    ".ts": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)|^\s*(?:const|let)\s+(\w+)\s*[:=]"),
}

def scan_repo(root: str, max_files: int = 300, max_bytes_per_file: int = 120_000):
    """Tra ve list dict {path, ext, lines, symbols}."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in CODE_EXTS:
                continue
            fp = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(fp) > max_bytes_per_file:
                    continue
            except OSError:
                continue
            symbols = []
            lines = 0
            try:
                pat = FUNC_PATTERNS.get(ext)
                with open(fp, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        lines += 1
                        if lines > 2000:
                            break
                        if pat:
                            m = pat.search(line)
                            if m:
                                name = next((g for g in m.groups() if g), None)
                                if name:
                                    symbols.append(name)
                        if len(symbols) > 40:
                            break
            except OSError:
                continue
            rel = os.path.relpath(fp, root)
            out.append({"path": rel, "full": fp, "ext": ext, "lines": lines, "symbols": symbols[:40]})
            if len(out) >= max_files:
                return out
    return out

def render_map(entries) -> str:
    lines = [f"- {e['path']} ({e['lines']} lines) {', '.join(e['symbols'][:8])}" for e in entries]
    return f"REPO MAP ({len(entries)} files):\n" + "\n".join(lines)
