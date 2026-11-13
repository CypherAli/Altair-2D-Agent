"""NaO API ngoai (khi user gan key): OpenAI-compatible (OpenRouter/Gemini-openai). Stdlib only."""
import hashlib
import json
import os
import urllib.request

SET_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ali_studio", ".settings.json")
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ali_studio", ".apicache.jsonl")

def settings():
    try:
        with open(SET_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(patch: dict) -> dict:
    s = settings()
    s.update(patch)
    with open(SET_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False)
    return s

def _cache_key(prompt: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode())
    h.update(b"\x00")
    h.update(" ".join(prompt.split()).encode())  # chuan hoa whitespace
    return h.hexdigest()

def cached_answer(prompt: str, model: str):
    """Cau giong het da hoi -> tra ngay, khoi ton tien/token."""
    if not os.path.isfile(CACHE_FILE):
        return None
    key = _cache_key(prompt, model)
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("key") == key:
                    return rec.get("answer", "")
    except OSError:
        pass
    return None

def _store_cache(prompt: str, model: str, answer: str):
    try:
        with open(CACHE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": _cache_key(prompt, model),
                                "answer": answer[:6000]}, ensure_ascii=False) + "\n")
    except OSError:
        pass

def _bump_usage(est_tokens: int):
    try:
        s = settings()
        s["api_calls"] = int(s.get("api_calls", 0)) + 1
        s["api_est_tokens"] = int(s.get("api_est_tokens", 0)) + est_tokens
        with open(SET_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False)
    except Exception:
        pass

def call_api(prompt: str, max_tokens: int = 800) -> str:
    s = settings()
    key = s.get("api_key", "")
    if not key:
        raise RuntimeError("Chua gan API key (sidebar -> API key).")
    base = s.get("api_base", "https://openrouter.ai/api/v1").rstrip("/")
    model = s.get("api_model", "meta-llama/llama-3.3-70b-instruct:free")
    hit = cached_answer(prompt, model)
    if hit:
        return hit + "\n\n(lay tu cache - khong ton API)"
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.2, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key,
                                          "HTTP-Referer": "http://localhost:8123",
                                          "X-Title": "Ali Studio"})
    with urllib.request.urlopen(req, timeout=180) as r:
        ans = json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()
    _store_cache(prompt, model, ans)
    _bump_usage(len(prompt) // 4 + len(ans) // 4)
    return ans
