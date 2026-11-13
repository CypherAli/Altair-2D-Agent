"""Ali Desktop - cua so truc quan, khong can terminal. Chay: python -m agent.desktop"""
import os, sys, threading, tkinter as tk
from tkinter import filedialog, scrolledtext
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.indexer import scan_repo, render_map
from agent.retriever import retrieve
from agent.main import build_review_prompt
try:
    from agent.backend import ask
except ModuleNotFoundError:
    from agent.backend_ollama import ask

entries = []

def log(msg):
    out.insert(tk.END, msg + "\n")
    out.see(tk.END)

def do_map():
    d = dir_var.get().strip() or "."
    threading.Thread(target=lambda: _map(d), daemon=True).start()

def _map(d):
    global entries
    status.config(text="Dang index...")
    try:
        entries = scan_repo(d, max_files=300)
        log(render_map(entries)[:5000])
        status.config(text=f"Da index {len(entries)} files")
    except Exception as e:
        status.config(text=f"Loi map: {e}")

def do_review():
    q = query.get("1.0", tk.END).strip()
    if not q:
        status.config(text="Nhap viec can review truoc")
        return
    threading.Thread(target=lambda: _review(q), daemon=True).start()

def _review(q):
    global entries
    if not entries:
        d = dir_var.get().strip() or "."
        entries = scan_repo(d)
    status.config(text="Ali dang doc + review...")
    try:
        files = retrieve(q, entries)
        log(f"[Ali] dang doc {len(files)} file: " + ", ".join(e["path"] for e, _ in files))
        prompt = build_review_prompt(q, render_map(entries), files)
        ans = ask(prompt, max_tokens=900)
        log("\n===== ALI TRA LOI =====\n" + ans + "\n")
        status.config(text="Xong")
    except Exception as e:
        status.config(text=f"Loi: {e}")
        log(f"Loi backend (Ollama chua chay?): {e}")

def pick_dir():
    d = filedialog.askdirectory()
    if d:
        dir_var.set(d)

root = tk.Tk()
root.title("Ali Agent (local)")
root.geometry("860x640")

top = tk.Frame(root)
top.pack(fill=tk.X, padx=8, pady=6)
tk.Label(top, text="Repo:").pack(side=tk.LEFT)
dir_var = tk.StringVar(value=".")
tk.Entry(top, textvariable=dir_var, width=60).pack(side=tk.LEFT, padx=6)
tk.Button(top, text="Chon...", command=pick_dir).pack(side=tk.LEFT)
tk.Button(top, text="Index (/map)", command=do_map).pack(side=tk.LEFT, padx=6)

tk.Label(root, text="Viec can review (vd: review file tools.py, them login Rust):").pack(anchor=tk.W, padx=8)
query = scrolledtext.ScrolledText(root, height=4)
query.pack(fill=tk.X, padx=8)
tk.Button(root, text="Review / Hoi Ali", command=do_review, bg="#2d7d46", fg="white", height=2).pack(fill=tk.X, padx=8, pady=6)

out = scrolledtext.ScrolledText(root, height=22)
out.pack(fill=tk.BOTH, expand=True, padx=8)
status = tk.Label(root, text="San sang. Can ~8GB RAM trong + Ollama dang chay.", anchor=tk.W)
status.pack(fill=tk.X, padx=8, pady=4)

root.mainloop()
