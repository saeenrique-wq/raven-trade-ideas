import subprocess, sys, os, time, webbrowser, re, threading, shutil
import tkinter as tk
from tkinter import font as tkfont

BASE = r"C:\Users\saems"
APP  = os.path.join(BASE, "raven_sinteticos_wt.py")
CF   = os.path.join(BASE, "cloudflared.exe")
PORT = 8506

def find_python():
    candidates = []
    if not getattr(sys, 'frozen', False):
        candidates.append(sys.executable)
    candidates += [
        shutil.which("python"), shutil.which("python3"),
        r"C:\Users\saems\AppData\Local\Programs\Python\Python312\python.exe",
        r"C:\Python313\python.exe", r"C:\Python312\python.exe",
    ]
    for c in candidates:
        if not c or not os.path.isfile(c): continue
        if c.lower() == sys.executable.lower(): continue
        if c.lower().endswith(".exe") and "python" not in os.path.basename(c).lower(): continue
        try:
            r = subprocess.run([c,"--version"], capture_output=True, timeout=3,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode == 0: return c
        except Exception: pass
    return "python"

PYTHON = find_python()
_st = _cf = None

def kill_port():
    try:
        r = subprocess.run(["netstat","-ano"], capture_output=True, text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        for line in r.stdout.splitlines():
            if f":{PORT}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill","/F","/PID",pid], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception: pass

def start_st():
    global _st
    _st = subprocess.Popen(
        [PYTHON,"-m","streamlit","run",APP,f"--server.port={PORT}",
         "--server.headless=true","--browser.gatherUsageStats=false"],
        cwd=BASE, creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_ready(t=25):
    import urllib.request
    d = time.time()+t
    while time.time()<d:
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}", timeout=2); return True
        except Exception: time.sleep(1)
    return False

def get_tunnel():
    global _cf
    if not os.path.isfile(CF): return None
    _cf = subprocess.Popen([CF,"tunnel","--url",f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,cwd=BASE)
    for raw in _cf.stdout:
        m = re.search(r'https://[\w\-]+\.trycloudflare\.com', raw.decode("utf-8","ignore"))
        if m: return m.group(0)
    return None

def cleanup():
    for p in (_cf, _st):
        if p:
            try: p.terminate()
            except Exception: pass

root = tk.Tk()
root.title("RAVEN · Sintéticos Weltrade")
root.geometry("500x310"); root.configure(bg="#07070f"); root.resizable(False,False)
try: root.iconbitmap(default="")
except Exception: pass
root.protocol("WM_DELETE_WINDOW", lambda: [cleanup(), root.destroy()])

f_t = tkfont.Font(family="Segoe UI", size=14, weight="bold")
f_s = tkfont.Font(family="Segoe UI", size=9)
f_st= tkfont.Font(family="Segoe UI", size=10)
f_u = tkfont.Font(family="Courier New",size=10,weight="bold")
f_b = tkfont.Font(family="Segoe UI", size=9,weight="bold")

tk.Label(root,text="⚡  RAVEN · Sintéticos Weltrade",bg="#07070f",fg="#ffd600",font=f_t).pack(pady=(22,3))
tk.Label(root,text="FX Vol · GainX · PainX · BreakX · TrendX · FlipX · 24/7",bg="#07070f",fg="#383858",font=f_s).pack()
tk.Frame(root,bg="#1a1a30",height=1).pack(fill="x",padx=30,pady=12)
sv = tk.StringVar(value="⏳  Iniciando…")
tk.Label(root,textvariable=sv,bg="#07070f",fg="#69f0ae",font=f_st).pack()
uv = tk.StringVar(value="")
ul = tk.Label(root,textvariable=uv,bg="#07070f",fg="#82b1ff",font=f_u,cursor="hand2"); ul.pack(pady=6)
bf = tk.Frame(root,bg="#07070f"); bf.pack(pady=4)
ob = tk.Button(bf,text="🌐  Abrir navegador",
    command=lambda: webbrowser.open(uv.get()) if uv.get() else None,
    bg="#1a2a00",fg="#fff",relief="flat",font=f_b,padx=16,pady=6,state="disabled")
ob.pack(side="left",padx=6)
cb = tk.Button(bf,text="📋  Copiar URL",
    command=lambda: [root.clipboard_clear(),root.clipboard_append(uv.get()),sv.set("✅ Copiada")] if uv.get() else None,
    bg="#1a1a30",fg="#d8d8f8",relief="flat",font=f_b,padx=16,pady=6,state="disabled")
cb.pack(side="left",padx=6)
tk.Frame(root,bg="#1a1a30",height=1).pack(fill="x",padx=30,pady=12)
tk.Label(root,text="Mantén esta ventana abierta mientras usas el scanner",bg="#07070f",fg="#1a1a38",font=f_s).pack()

def launch():
    sv.set("🔧  Liberando puerto 8506…"); kill_port(); time.sleep(1)
    sv.set("▶  Iniciando Streamlit…"); start_st()
    sv.set("⏳  Esperando que arranque…")
    ok = wait_ready(25)
    if ok: webbrowser.open(f"http://localhost:{PORT}"); sv.set("🌐  Conectando túnel…")
    else: sv.set("⚠  Tardó — intentando túnel…")
    tunnel = get_tunnel()
    url = tunnel or f"http://localhost:{PORT}"
    uv.set(url)
    if tunnel:
        sv.set("✅  Activo — accesible desde cualquier dispositivo")
        ul.bind("<Button-1>", lambda e: webbrowser.open(tunnel))
    else:
        sv.set("⚠  Túnel no disponible — solo local")
    ob.config(state="normal"); cb.config(state="normal")

threading.Thread(target=launch,daemon=True).start()
root.mainloop(); cleanup()
