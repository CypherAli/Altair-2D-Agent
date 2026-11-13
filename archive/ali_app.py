"""Ali Desktop v2 - phong cach Forma 3 cot, dark. Chay: python -m agent.ali_app"""
import os, sys, threading, tkinter as tk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.indexer import scan_repo, render_map
from agent.retriever import retrieve, with_line_numbers
from agent.main import build_review_prompt
try:
    from agent.backend import ask
except ModuleNotFoundError:
    from agent.backend_ollama import ask

BG = "#0d1117"; PANEL = "#131a23"; LINE = "#212b36"; TXT = "#e6edf3"
MUT = "#8b949e"; ACC = "#2ee6a8"; WARN = "#f0b429"

entries = []
sessions = ["Review authentication...", "Research API architec...", "Analyze app performa..."]

root = tk.Tk()
root.title("Ali")
root.geometry("1180x700")
root.configure(bg=BG)
try:
    root.iconbitmap(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Ali.ico"))
except Exception:
    pass

# --- 3 cot ---
left = tk.Frame(root, bg=PANEL, width=230)
left.pack(side=tk.LEFT, fill=tk.Y)
mid = tk.Frame(root, bg=BG)
mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
right = tk.Frame(root, bg=PANEL, width=320)
right.pack(side=tk.LEFT, fill=tk.Y)

def lbl(parent, t, fg=TXT, size=11, bold=False):
    return tk.Label(parent, text=t, bg=parent["bg"], fg=fg, font=("Segoe UI", size, "bold" if bold else "normal"))

# LEFT
lbl(left, "◆  Ali", size=16, bold=True).pack(anchor=tk.W, padx=14, pady=12)
lbl(left, "BETA", fg=MUT, size=8).pack(anchor=tk.W, padx=14)
repo_var = tk.StringVar(value="acme-platform")
tk.Label(left, text="WORKSPACE", bg=PANEL, fg=MUT, font=("Segoe UI", 8)).pack(anchor=tk.W, padx=14, pady=(12, 2))
tk.Entry(left, textvariable=repo_var, bg=BG, fg=TXT, insertbackground=TXT, relief=tk.FLAT).pack(fill=tk.X, padx=12, ipady=6)
tk.Button(left, text="+  New session", bg=ACC, fg="#06281c", relief=tk.FLAT, font=("Segoe UI", 10, "bold")).pack(fill=tk.X, padx=12, pady=8)
tk.Label(left, text="SESSIONS", bg=PANEL, fg=MUT, font=("Segoe UI", 8)).pack(anchor=tk.W, padx=14, pady=(6, 2))
sess_box = tk.Listbox(left, bg=PANEL, fg=TXT, relief=tk.FLAT, highlightthickness=0, font=("Segoe UI", 10))
sess_box.pack(fill=tk.X, padx=12)
for s in sessions:
    sess_box.insert(tk.END, "  " + s)
lbl(left, "● Agent ready", fg=ACC, size=9).pack(anchor=tk.W, padx=14, pady=10)
lbl(left, "Ali Nguyen\nPersonal workspace", fg=MUT, size=9).pack(anchor=tk.W, padx=14)

# MID
head = tk.Frame(mid, bg=BG)
head.pack(fill=tk.X, padx=16, pady=12)
lbl(head, "Review authentication flow", size=14, bold=True).pack(side=tk.LEFT)
lbl(head, "LOCAL WORKSPACE", fg=MUT, size=8).pack(side=tk.RIGHT)

conv = tk.Text(mid, bg=BG, fg=TXT, relief=tk.FLAT, wrap=tk.WORD, font=("Segoe UI", 11), height=20)
conv.pack(fill=tk.BOTH, expand=True, padx=16)
conv.insert(tk.END, "⚠  Missing rate limiting on login  [MEDIUM]\n", ("warn",))
conv.insert(tk.END, "The login endpoint accepts unlimited attempts. Add IP-based rate limiter.\n\n", ())
conv.insert(tk.END, "✓  Prepared a suggested fix for session validation.  View changes ↗\n", ("acc",))
conv.tag_config("warn", foreground=WARN)
conv.tag_config("acc", foreground=ACC)
conv.config(state=tk.DISABLED)

bot = tk.Frame(mid, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
bot.pack(fill=tk.X, padx=16, pady=12)
inp = tk.Text(bot, bg=PANEL, fg=TXT, relief=tk.FLAT, font=("Segoe UI", 11), height=3)
inp.pack(fill=tk.X, padx=10, pady=(8, 2))
inp.insert(tk.END, "Ask anything about your code...")
bar = tk.Frame(bot, bg=PANEL)
bar.pack(fill=tk.X, padx=10, pady=8)
tk.Label(bar, text="◉ Read-only access", bg=PANEL, fg=MUT, font=("Segoe UI", 9)).pack(side=tk.LEFT)
go = tk.Button(bar, text="↑", bg=ACC, fg="#06281c", relief=tk.FLAT, width=4, font=("Segoe UI", 12, "bold"))
go.pack(side=tk.RIGHT)

# RIGHT
lbl(right, "Changes  2   Files", size=12, bold=True).pack(anchor=tk.W, padx=14, pady=12)
diff = tk.Text(right, bg=BG, fg=TXT, relief=tk.FLAT, font=("Consolas", 10), height=22, wrap=tk.NONE)
diff.pack(fill=tk.BOTH, expand=True, padx=12)
diff.insert(tk.END, "auth.ts  src/lib              +8 -3\n\nProposed changes\n")
diff.insert(tk.END, " 1  import { createClient } from \"@supabase/ssr\";\n 2  import { cookies } from \"next/headers\";\n 4  export async function getSession() {\n 5    const cookieStore = await cookies();\n")
diff.config(state=tk.DISABLED)
tk.Button(right, text="✓  Accept changes", bg=ACC, fg="#06281c", relief=tk.FLAT, font=("Segoe UI", 11, "bold")).pack(fill=tk.X, padx=12, pady=12)

def append_mid(t, tag=None):
    conv.config(state=tk.NORMAL)
    conv.insert(tk.END, t + "\n", (tag,) if tag else ())
    conv.see(tk.END)
    conv.config(state=tk.NORMAL)
    conv.config(state=tk.DISABLED)

def do_ask():
    q = inp.get("1.0", tk.END).strip()
    if not q or q.startswith("Ask anything"):
        return
    def run():
        global entries
        append_mid("\n› " + q)
        append_mid("Ali đang đọc repo...", "acc")
        try:
            d = repo_var.get().strip() or "."
            if not entries:
                entries = scan_repo(d if os.path.isdir(d) else ".")
            files = retrieve(q, entries)
            prompt = build_review_prompt(q, render_map(entries), files)
            ans = ask(prompt, max_tokens=900)
            append_mid("\n" + ans)
        except Exception as e:
            append_mid(f"\nLỗi (Ollama chưa chạy?): {e}", "warn")
    threading.Thread(target=run, daemon=True).start()

go.config(command=do_ask)
inp.bind("<Control-Return>", lambda e: do_ask())

root.mainloop()
