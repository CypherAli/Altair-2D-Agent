"""Sandbox + route_tool (hoc context-mode), stdlib only."""
import subprocess, os, time, re

LOGDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
ALLOW_BASH = ("git ", "ls", "dir", "cargo check", "cargo test", "cargo clippy",
              "go vet", "go test", "go build", "pytest", "python -m pytest",
              "python -m py_compile", "npm test", "npm run build", "tsc --noEmit")
BLOCK_PAT = re.compile(r"curl|wget|rm\s+-rf|mkfs|format\s+[a-z]:|del\s+/[fs]|shutdown", re.I)

def route_tool(kind: str, cmd: str) -> tuple[str, str]:
    """Tra ve (allow|deny, ly do). Chan output khung lo truoc khi chay."""
    if BLOCK_PAT.search(cmd):
        return ("deny", "Lenh nguy hiem / output khung lo (curl/wget/xoa). Dung sandbox doc file rieng hoac hoi user.")
    if kind == "shell" and not cmd.startswith(ALLOW_BASH):
        return ("deny", f"Chi cho phep: {ALLOW_BASH}. Con lai can user duyet.")
    return ("allow", "")

def pick_check(manifest: str) -> str:
    """Chon lenh kiem tra nhanh nhat theo loai repo. Tra '' neu khong biet."""
    m = manifest or ""
    if "Cargo.toml" in m:
        return "cargo check"
    if "go.mod" in m:
        return "go vet ./..."
    if "package.json" in m:
        return "npm test"
    if "requirements.txt" in m or "pyproject.toml" in m:
        return "pytest -q"
    return ""


def syntax_gate(path: str, content: str) -> tuple[bool, str]:
    """Cua kiem cu phap truoc khi ghi: chan rac som, khoi ton 1 round chay test.
    Tra (ok, loi). Ngon ngu khac tra (True, '')."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        try:
            compile(content, path, "exec")
            return True, ""
        except SyntaxError as ex:
            return False, f"SyntaxError dong {ex.lineno}: {ex.msg}"
    if ext in (".js", ".mjs"):
        import tempfile
        try:
            with tempfile.NamedTemporaryFile("w", suffix=ext, delete=False,
                                             encoding="utf-8") as f:
                f.write(content)
                tmp = f.name
            r = subprocess.run(["node", "--check", tmp], capture_output=True,
                               text=True, timeout=30)
            os.unlink(tmp)
            if r.returncode != 0:
                return False, (r.stderr or "").strip()[-500:]
            return True, ""
        except Exception as ex:
            return True, ""  # khong ket luan duoc -> cho qua, test that se bat
    return True, ""


def sandbox_exec(cmd: str, cwd: str = ".", timeout: int = 90) -> str:
    """Chay lenh, chi tra tail-30 + EXIT vao context, full log ra file."""
    os.makedirs(LOGDIR, exist_ok=True)
    lid = time.strftime("%Y%m%d-%H%M%S")
    logfp = os.path.join(LOGDIR, f"ctx_{lid}.log")
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        full = f"$ {cmd}\nEXIT={r.returncode}\n" + (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        full = f"$ {cmd}\nTIMEOUT sau {timeout}s"
    except Exception as e:
        full = f"$ {cmd}\nLOI: {e}"
    with open(logfp, "w", encoding="utf-8", errors="replace") as f:
        f.write(full)
    tail = "\n".join(full.splitlines()[-30:])
    return f"{tail}\n(full log: {logfp})"
