"""Install an isolated LiteRT runtime and a hash-verified mobile model."""
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".altair-runtime"
MODEL = DATA / "litert/altair.litertlm"
REPO = "litert-community/gemma-4-E2B-it-litert-lm"
FILE = "gemma-4-E2B-it.litertlm"
SHA256 = "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c"
SIZE = 2588147712


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main():
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dependencies = DATA / "python"
    if not (dependencies / "litert_lm").is_dir():
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "--target",
                        str(dependencies), "litert-lm-api==0.19.0"], check=True)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    valid = MODEL.is_file() and MODEL.stat().st_size == SIZE and digest(MODEL) == SHA256
    if not valid:
        temporary = MODEL.with_suffix(".download")
        downloaded, last = 0, -1
        url = "https://huggingface.co/" + REPO + "/resolve/main/" + FILE
        with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(4 * 1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                progress = int(downloaded * 100 / SIZE) // 10
                if progress != last:
                    print(f"Model: {progress * 10}%", flush=True)
                    last = progress
        if downloaded != SIZE or digest(temporary) != SHA256:
            raise RuntimeError("Model không khớp SHA256 đã kiểm tra. Giữ file hiện có; cần xem lại bản phát hành.")
        temporary.replace(MODEL)
    MODEL.with_suffix(".source.json").write_text(json.dumps({"repository": REPO, "file": FILE,
        "sha256": SHA256, "size": SIZE}, indent=2), encoding="utf-8")
    print("Altair đã sẵn sàng. Chạy AltairStudio.bat.")


if __name__ == "__main__":
    main()
