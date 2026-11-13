"""Tool an toan, allowlist lenh chay."""
import subprocess, os

ALLOWED_PREFIXES = (
    "cargo check", "cargo test", "cargo clippy",
    "go vet", "go test", "go build",
    "pytest", "python -m pytest", "python -m py_compile",
    "npm run build", "npm test", "tsc --noEmit",
)

BLOCKED = ("rm -rf", "format", "mkfs", ":(){", "del /f", "shutdown", "rd /s")

def safe_run(cmd: str, cwd: str = ".", timeout: int = 120) -> str:
    if any(b in cmd for b in BLOCKED):
        return "BLOCKED: lenh nguy hiem, tu choi."
    if not cmd.startswith(ALLOWED_PREFIXES):
        return f"BLOCKED: chi cho phep: {ALLOWED_PREFIXES}"
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        return out[-6000:] or "(khong output)"
    except subprocess.TimeoutExpired:
        return "TIMEOUT sau 120s"
    except Exception as e:
        return f"LOI: {e}"
