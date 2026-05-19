import subprocess, sys, os, time, webbrowser, re, threading, shutil
import tkinter as tk
from tkinter import font as tkfont

BASE  = r"C:\Users\saems"
APP   = os.path.join(BASE, "raven_binary.py")
CF    = os.path.join(BASE, "cloudflared.exe")
PORT  = 8508

def find_python():
    candidates = []
    if not getattr(sys, 'frozen', False):
        candidates.append(sys.executable)
    candidates += [
        shutil.which("python"), shutil.which("python3"),
        r"C:\Users\saems\AppData\Local\Programs\Python\Python312\python.exe",
        r"C:\Users\saems\AppData\Local\Programs\Python\Python313\python.exe",
        r"C:\Python312\python.exe", r"C:\Python311\python.exe", r"C:\Python310\python.exe",
    ]
    for c in candidates:
        if not c or not os.path.isfile(c): continue
        if c.lower() == sys.executable.lower(): continue
        if c.lower().endswith(".exe") and "python" not in os.path.basename(c).lower(): continue
        try:
            r = subprocess.run([c, "--version"], capture_output=True, timeout=3,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode == 0: return c
        except Exception: pass
    return "python"

PYTHON = find_python()
_streamlit_proc = None
_tunnel_proc    = None

def kill_port():
    try:
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        for line in r.stdout.splitlines():
            if f":{PORT}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception: pass

def start_streamlit():
    global _streamlit_proc
    _streamlit_proc = subprocess.Popen(
        [PYTHON, "-m", "streamlit", "run", APP,
         f"--server.port={PORT}", "--server.headless=true",
         "--browser.gatherUsageStats=false"],
        cwd=BASE, creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_ready(timeout=25):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}", timeout=2)
            return True
        except Exception: time.sleep(1)
    return False

def get_tunnel_url():
    global _tunnel_proc
    _tunnel_proc = subprocess.Popen(
        [CF, "tunnel", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW, cwd=BASE)
    for raw in _tunnel_proc.stdout:
        line = raw.decode("utf-8", errors="ignore")
        m = re.search(r'https://[\w\-]+\.trycloudflare\.com', line)
        if m: return m.group(0)
    return None

def cleanup():
    for p in (_tunnel_proc, _streamlit_proc):
        if p:
            try: p.terminate()
            except Exception: pass

# ── UI ────────────────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("RAVEN BINARY OPTIONS")
root.geometry("500x310")
root.configure(bg="#05050d")
root.resizable(False, False)
try: root.iconbitmap(default="")
except Exception: pass

def on_close():
    cleanup(); root.destroy()
root.protocol("WM_DELETE_WINDOW", on_close)

f_title  = tkfont.Font(family="Segoe UI", size=14, weight="bold")
f_sub    = tkfont.Font(family="Segoe UI", size=9)
f_status = tkfont.Font(family="Segoe UI", size=10)
f_url    = tkfont.Font(family="Courier New", size=10, weight="bold")
f_btn    = tkfont.Font(family="Segoe UI", size=9, weight="bold")

tk.Label(root, text="📊  RAVEN BINARY OPTIONS",
         bg="#05050d", fg="#00e676", font=f_title).pack(pady=(22, 3))
tk.Label(root, text="FOREX REAL · OTC · CALL/PUT · 1 min · 5 min · IQ Option · Quotex",
         bg="#05050d", fg="#1a1a30", font=f_sub).pack()
tk.Frame(root, bg="#0c0c20", height=1).pack(fill="x", padx=30, pady=12)

status_var = tk.StringVar(value="⏳  Iniciando…")
tk.Label(root, textvariable=status_var,
         bg="#05050d", fg="#69f0ae", font=f_status).pack()

url_var = tk.StringVar(value="")
url_lbl = tk.Label(root, textvariable=url_var, bg="#05050d", fg="#82b1ff",
                   font=f_url, cursor="hand2")
url_lbl.pack(pady=6)

btn_frame = tk.Frame(root, bg="#05050d")
btn_frame.pack(pady=4)

def open_browser():
    u = url_var.get()
    if u: webbrowser.open(u)

def copy_url():
    u = url_var.get()
    if u:
        root.clipboard_clear(); root.clipboard_append(u)
        status_var.set("✅  URL copiada al portapapeles")

open_btn = tk.Button(btn_frame, text="🌐  Abrir en navegador", command=open_browser,
                     bg="#0a2a1a", fg="#00e676", relief="flat", font=f_btn,
                     padx=16, pady=6, state="disabled")
open_btn.pack(side="left", padx=6)

copy_btn = tk.Button(btn_frame, text="📋  Copiar URL", command=copy_url,
                     bg="#0c0c20", fg="#d8d8f8", relief="flat", font=f_btn,
                     padx=16, pady=6, state="disabled")
copy_btn.pack(side="left", padx=6)

tk.Frame(root, bg="#0c0c20", height=1).pack(fill="x", padx=30, pady=12)
tk.Label(root, text="Mantén esta ventana abierta mientras usas el scanner",
         bg="#05050d", fg="#0c0c20", font=f_sub).pack()

def launch_all():
    status_var.set("🔧  Liberando puerto…")
    kill_port(); time.sleep(1)
    status_var.set("▶  Iniciando Streamlit…")
    start_streamlit()
    status_var.set("⏳  Esperando arranque…")
    ready = wait_ready(timeout=30)
    if ready:
        webbrowser.open(f"http://localhost:{PORT}")
        status_var.set("🌐  Conectando túnel Cloudflare…")
    else:
        status_var.set("⚠  Streamlit tardó — intentando túnel…")
    tunnel_url = get_tunnel_url()
    if tunnel_url:
        url_var.set(tunnel_url)
        status_var.set("✅  App activa — accesible desde cualquier dispositivo")
        open_btn.config(state="normal"); copy_btn.config(state="normal")
        url_lbl.bind("<Button-1>", lambda e: webbrowser.open(tunnel_url))
    else:
        url_var.set(f"http://localhost:{PORT}")
        status_var.set("⚠  Sin túnel — funcionando en local")
        open_btn.config(state="normal")

threading.Thread(target=launch_all, daemon=True).start()
root.mainloop()
cleanup()
