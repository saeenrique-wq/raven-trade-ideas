# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  RAVEN AI · METALES & FOREX  — Scanner de señales standalone               ║
# ║  Puerto: 8504  |  Ejecutar: streamlit run raven_metals_forex.py --server.port 8504 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
import streamlit as st
import pandas as pd
import numpy as np
import requests, json, time, threading
from datetime import datetime, timezone
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
try:
    import yfinance as yf
    _YF = True
except ImportError:
    _YF = False
try:
    import MetaTrader5 as mt5
    _MT5_LIB = True
except ImportError:
    _MT5_LIB = False

st.set_page_config(
    page_title="RAVEN AI · Metales & Forex",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
body,.stApp{background:#07070f;color:#d8d8f8}
.block-container{padding:1rem 1.5rem 1rem}
.stTabs [data-baseweb="tab-list"]{background:#0c0c18;border-radius:8px;padding:4px;gap:4px}
.stTabs [data-baseweb="tab"]{background:transparent;color:#555;border-radius:6px;
  padding:8px 20px;font-weight:700;font-size:.82em;text-transform:uppercase;letter-spacing:1.5px}
.stTabs [aria-selected="true"]{background:#1a1a30;color:#d8d8f8}
.sec-hdr{background:linear-gradient(90deg,#12122a,#0c0c18);border-left:3px solid #3d3d7a;
  padding:6px 14px;margin:10px 0 8px;font-size:.72em;text-transform:uppercase;
  letter-spacing:2.5px;color:#555;font-weight:700;border-radius:0 6px 6px 0}
.sig-premium{background:linear-gradient(135deg,#030318,#06062a);border:1px solid #3d3d7a;
  border-left:4px solid #ffd600;border-radius:12px;padding:0;margin:12px 0;overflow:hidden;
  box-shadow:0 4px 30px rgba(100,80,255,.12),0 0 0 1px rgba(255,214,0,.04)}
.sig-alta{background:linear-gradient(135deg,#030318,#06062a);border:1px solid #1e2a1e;
  border-left:4px solid #00e676;border-radius:12px;padding:0;margin:12px 0;overflow:hidden;
  box-shadow:0 4px 20px rgba(0,230,118,.06)}
.sig-obs{background:#09090f;border:1px solid #1a1a30;border-left:3px solid #ff9800;
  border-radius:10px;padding:0;margin:10px 0;overflow:hidden}
.sig-wait{background:#090910;border:1px solid #1a1a2a;border-radius:10px;margin:8px 0;overflow:hidden}
.no-signals{background:#09090f;border:1px solid #1a1a30;border-radius:10px;
  padding:18px 20px;text-align:center;color:#252540;margin:10px 0}
.alert-new{background:linear-gradient(90deg,#0d1a0d,#050a05);border:1px solid #1a4d1a;
  border-left:4px solid #00e676;border-radius:8px;padding:10px 16px;margin:6px 0;
  font-size:.85em;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{border-left-color:#00e676}50%{border-left-color:#69f0ae}}
.radar-tbl{width:100%;border-collapse:collapse;font-size:.78em}
.radar-tbl th{background:#0c0c18;color:#383858;padding:7px 10px;font-weight:700;
  text-transform:uppercase;letter-spacing:1.5px;font-size:.68em;border-bottom:1px solid #1a1a30}
.radar-tbl td{border-bottom:1px solid #0e0e1e;vertical-align:middle}
.px-lbl{color:#383858;font-size:.6em;text-transform:uppercase;letter-spacing:2px}
.h-win{background:#030d04;border:1px solid #1a3a1a;border-radius:6px;padding:10px 14px;margin:4px 0}
.h-loss{background:#0d0304;border:1px solid #3a1a1a;border-radius:6px;padding:10px 14px;margin:4px 0}
.h-exp{background:#09090f;border:1px solid #1a1a30;border-radius:6px;padding:10px 14px;margin:4px 0}
.b-win{background:#1a3a1a;color:#69f0ae;border-radius:4px;padding:2px 8px;font-size:.75em;font-weight:700}
.b-loss{background:#3a1a1a;color:#ff5252;border-radius:4px;padding:2px 8px;font-size:.75em;font-weight:700}
.b-exp{background:#1a1a2a;color:#555;border-radius:4px;padding:2px 8px;font-size:.75em;font-weight:700}
.stButton>button{background:linear-gradient(135deg,#3d1278,#6a0dad);color:#fff;border:none;
  border-radius:8px;font-weight:700;padding:8px 20px;font-size:.85em}
</style>""", unsafe_allow_html=True)

# ── PARES ─────────────────────────────────────────────────────────────────────
METALS = {
    "XAUUSD": ("GC=F",    "XAU/USD Oro",    "#ffd600"),
    "XAGUSD": ("SI=F",    "XAG/USD Plata",  "#c0c0c0"),
    "WTIUSD": ("CL=F",    "WTI Petróleo",   "#ff9800"),
}
FOREX = {
    "EURUSD": ("EURUSD=X", "EUR/USD", "#42a5f5"),
    "GBPUSD": ("GBPUSD=X", "GBP/USD", "#ab47bc"),
    "USDJPY": ("USDJPY=X", "USD/JPY", "#26c6da"),
    "AUDUSD": ("AUDUSD=X", "AUD/USD", "#66bb6a"),
    "USDCAD": ("USDCAD=X", "USD/CAD", "#ff7043"),
    "USDMXN": ("MXN=X",    "USD/MXN", "#8d6e63"),
}
ALL_PAIRS = {**METALS, **FOREX}

XAUUSD_VARIANTS = [
    "XAUUSD","XAUUSD.","XAUUSDm","XAUUSDc","XAUUSDpro","GOLD","Gold","gold",
    "XAUUSD.r","XAUUSD_i","XAUUSD-ECN","XAUUSDf","XAUUSD+","XAUUSDs","XAUUSD.pro","XAU/USD"
]

# ── UTILIDADES ────────────────────────────────────────────────────────────────
def fmt(v, key=""):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    cat = ALL_PAIRS.get(key, ("","",""))[1]
    if "forex" in cat.lower() or (isinstance(v, float) and 0 < abs(v) < 10):
        return f"{v:.5f}"
    if abs(v) >= 1000: return f"{v:,.2f}"
    if abs(v) >= 1:    return f"{v:.4f}"
    return f"{v:.6f}"

def dist_fmt(d, key=""):
    if d is None or (isinstance(d, float) and np.isnan(d)): return "—"
    if key in FOREX: return f"{d*10000:.1f}p"
    if key in ("US30","US100","SPX500","GER40","UK100"): return f"{d:.0f}pts"
    return f"{d:.4f}"

def mercado_abierto(key):
    now = datetime.now(timezone.utc)
    wd = now.weekday(); h = now.hour; m = now.minute
    if wd >= 5: return False, "cerrado (fin de semana)"
    if key in FOREX:
        if wd == 4 and (h > 21 or (h == 21 and m >= 50)):
            return False, "forex cerrado (viernes noche)"
        return True, "forex abierto"
    if key in ("XAUUSD","XAGUSD","WTIUSD"):
        if (h == 21 and m >= 45) or (h == 22 and m < 55):
            return False, "pausa mantenimiento"
        return True, "commodities abierto"
    return True, "abierto"

def calcular_entry_status(precio, entry, tp1):
    if tp1 == entry: return "NO ENTRAR", "#ff5252"
    avance = abs(precio - entry) / abs(tp1 - entry) * 100
    if avance < 35:  return "CERCA DE ENTRADA", "#00e676"
    if avance < 50:  return "ESPERAR PULLBACK", "#ffd600"
    return "ENTRADA TARDÍA", "#ff9800"

def clasificar(score):
    if score >= 90: return "PREMIUM", "#ffd600"
    if score >= 80: return "ALTA PROB.", "#00e676"
    if score >= 70: return "OBSERVAR", "#42a5f5"
    return "NO OPERAR", "#555"

# ── DATOS HISTÓRICOS ──────────────────────────────────────────────────────────
def _yahoo_v8(sym, interval="5m", period="5d"):
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
        params = {"interval": interval, "range": period}
        r = requests.get(url, params=params, timeout=8,
                         headers={"User-Agent": "Mozilla/5.0"})
        d = r.json()["chart"]["result"][0]
        ts = pd.to_datetime(d["timestamp"], unit="s", utc=True)
        q  = d["indicators"]["quote"][0]
        df = pd.DataFrame({"open":q["open"],"high":q["high"],"low":q["low"],
                           "close":q["close"],"volume":q.get("volume",[0]*len(ts))}, index=ts)
        return df.dropna()
    except Exception:
        return None

def get_data(sym, interval="15m", period="5d"):
    df = _yahoo_v8(sym, interval, period)
    if df is not None and len(df) >= 30: return df
    if not _YF: return None
    try:
        tk = yf.Ticker(sym)
        df = tk.history(interval=interval, period=period)
        if df is not None and len(df) >= 30: return df
    except Exception:
        pass
    return None

def get_live_price(sym_yf):
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym_yf}"
        r = requests.get(url, params={"interval":"1m","range":"1d"}, timeout=5,
                         headers={"User-Agent": "Mozilla/5.0"})
        d = r.json()["chart"]["result"][0]["meta"]
        return float(d.get("regularMarketPrice") or d.get("previousClose", 0))
    except Exception:
        return None

# ── MT5 GOLD ──────────────────────────────────────────────────────────────────
def mt5_connect():
    if not _MT5_LIB: return False, "MetaTrader5 no instalado"
    if not mt5.initialize(): return False, f"Error: {mt5.last_error()}"
    acc = mt5.account_info()
    if acc is None: return False, "Sin cuenta MT5"
    return True, f"{acc.name} · {acc.company}"

def find_gold_symbol():
    if not _MT5_LIB: return None
    syms = mt5.symbols_get()
    if not syms: return None
    names = [s.name for s in syms]
    for v in XAUUSD_VARIANTS:
        if v in names: return v
    for n in names:
        if "XAU" in n.upper() or n.upper().startswith("GOLD"): return n
    return None

def get_gold_mt5(sym):
    if not _MT5_LIB or not sym: return None
    try:
        tick = mt5.symbol_info_tick(sym)
        if tick is None: return None
        r1  = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1,  0, 200)
        r5  = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5,  0, 200)
        r15 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 200)
        def to_df(r):
            if r is None or len(r) < 30: return None
            df = pd.DataFrame(r)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.set_index("time").rename(columns={"open":"open","high":"high",
                "low":"low","close":"close","tick_volume":"volume"})
            return df
        return {"bid": tick.bid, "ask": tick.ask,
                "spread": round((tick.ask - tick.bid), 2),
                "price": (tick.bid + tick.ask) / 2,
                "m1": to_df(r1), "m5": to_df(r5), "m15": to_df(r15)}
    except Exception:
        return None

# ── INDICADORES ───────────────────────────────────────────────────────────────
def analizar_df(df):
    if df is None or len(df) < 30: return None
    c = df["close"]
    try:
        rsi   = RSIIndicator(c, 14).rsi().iloc[-1]
        macd_ = MACD(c)
        macd_h= macd_.macd_diff().iloc[-1]
        macd_hp = macd_.macd_diff().iloc[-2] if len(c) > 2 else 0
        bb    = BollingerBands(c, 20, 2)
        bb_hi = bb.bollinger_hband().iloc[-1]
        bb_lo = bb.bollinger_lband().iloc[-1]
        bb_mid= bb.bollinger_mavg().iloc[-1]
        ema20 = EMAIndicator(c, 20).ema_indicator().iloc[-1]
        ema50 = EMAIndicator(c, 50).ema_indicator().iloc[-1]
        ema200= EMAIndicator(c, 200).ema_indicator().iloc[-1] if len(c) >= 200 else ema50
        ema9  = EMAIndicator(c, 9).ema_indicator().iloc[-1]
        atr   = AverageTrueRange(df["high"], df["low"], c, 14).average_true_range().iloc[-1]
        stoch = StochasticOscillator(df["high"], df["low"], c, 14, 3).stoch().iloc[-1]
        adx_i = ADXIndicator(df["high"], df["low"], c, 14)
        adx   = adx_i.adx().iloc[-1]
        dip   = adx_i.adx_neg().iloc[-1]
        dim   = adx_i.adx_pos().iloc[-1]
        price = c.iloc[-1]
        slope = (ema20 - EMAIndicator(c, 20).ema_indicator().iloc[-4]) / ema20 * 100 if len(c) > 4 else 0
        range_candle = df["high"].iloc[-1] - df["low"].iloc[-1]
        cuerpo = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
        mecha_inf = df["open"].iloc[-1] - df["low"].iloc[-1] if df["close"].iloc[-1] > df["open"].iloc[-1] else df["close"].iloc[-1] - df["low"].iloc[-1]
        mecha_sup = df["high"].iloc[-1] - max(df["open"].iloc[-1], df["close"].iloc[-1])
        vela_ext  = range_candle > atr * 2.5
        lateral   = adx < 12
        cierre_alc = df["close"].iloc[-1] > df["open"].iloc[-1]
        max_10 = df["high"].iloc[-10:].max()
        min_10 = df["low"].iloc[-10:].min()
        atr_avg = AverageTrueRange(df["high"], df["low"], c, 14).average_true_range().iloc[-5:-1].mean()
        return {
            "price": price, "rsi": rsi, "macd_h": macd_h, "macd_hp": macd_hp,
            "bb_hi": bb_hi, "bb_lo": bb_lo, "bb_mid": bb_mid,
            "ema9": ema9, "ema20": ema20, "ema50": ema50, "ema200": ema200,
            "atr": atr, "atr_avg": atr_avg, "stoch": stoch,
            "adx": adx, "dip": dip, "dim": dim, "slope": slope,
            "vela_ext": vela_ext, "lateral": lateral, "cierre_alc": cierre_alc,
            "mecha_inf": mecha_inf, "mecha_sup": mecha_sup, "cuerpo": cuerpo,
            "max_10": max_10, "min_10": min_10,
        }
    except Exception:
        return None

def calcular_score(ind_h1, ind_m15, ind_m5, key, riesgo_usd=100):
    if ind_m15 is None: return 0, "neutral", {}
    p   = ind_m15["price"]
    atr = ind_m15["atr"]
    rsi = ind_m15["rsi"]
    adx = ind_m15["adx"]
    score = 0; bd = {}

    # Determinar dirección primero (para scoring direccional)
    buy_pts = 0; sell_pts = 0
    if p > ind_m15["ema20"]: buy_pts += 2
    else: sell_pts += 2
    if p > ind_m15["ema50"]: buy_pts += 1
    else: sell_pts += 1
    if ind_m15["macd_h"] > 0: buy_pts += 2
    else: sell_pts += 2
    if rsi > 52: buy_pts += 1
    elif rsi < 48: sell_pts += 1
    if ind_h1 and ind_h1["ema20"] > ind_h1["ema50"]: buy_pts += 2
    elif ind_h1: sell_pts += 2
    if ind_m15["dim"] > ind_m15["dip"]: buy_pts += 1
    else: sell_pts += 1
    dir_ = "buy" if buy_pts >= sell_pts else "sell"
    es_buy = (dir_ == "buy")

    # A) Tendencia MTF — 25 pts (base 10 + bonos)
    a = 10  # base neutral
    if ind_h1:
        h1_alcista = ind_h1["ema20"] > ind_h1["ema50"]
        m15_alcista = ind_m15["ema20"] > ind_m15["ema50"]
        if h1_alcista == m15_alcista: a += 5   # H1 y M15 alineados
        if h1_alcista and es_buy:    a += 3
        elif not h1_alcista and not es_buy: a += 3
        if p > ind_h1["ema200"]: a += 4 if es_buy else 0
        elif p < ind_h1["ema200"]: a += 4 if not es_buy else 0
        slope_pos = ind_h1["slope"] > 0.005
        if slope_pos == es_buy: a += 3
    else:
        a += 5  # sin H1 damos beneficio de la duda
        if ind_m15["ema20"] > ind_m15["ema50"]: a += 5 if es_buy else 0
        elif not (ind_m15["ema20"] > ind_m15["ema50"]): a += 5 if not es_buy else 0
    if ind_m5 and ((ind_m5["ema20"] > ind_m5["ema50"]) == es_buy): a += 3
    a = min(25, a)
    bd["A) Tendencia MTF"] = a; score += a

    # B) Setup técnico — 25 pts (base 8 + bonos)
    b = 8
    if es_buy:
        if 35 <= rsi <= 55: b += 6
        elif 55 < rsi <= 65: b += 3
        if p > ind_m15["bb_mid"] and p < ind_m15["bb_hi"]: b += 4
        elif p <= ind_m15["bb_lo"] + atr * 0.3: b += 6  # oversold bounce
        if abs(p - ind_m15["ema20"]) < atr * 0.8: b += 4
        if ind_m15["cierre_alc"]: b += 3
    else:
        if 45 <= rsi <= 65: b += 6
        elif 35 <= rsi < 45: b += 3
        if p < ind_m15["bb_mid"] and p > ind_m15["bb_lo"]: b += 4
        elif p >= ind_m15["bb_hi"] - atr * 0.3: b += 6  # overbought bounce
        if abs(p - ind_m15["ema20"]) < atr * 0.8: b += 4
        if not ind_m15["cierre_alc"]: b += 3
    if not ind_m15["vela_ext"]: b += 4
    # penalizar si M5 contradice fuertemente
    if ind_m5 and ((ind_m5["ema20"] > ind_m5["ema50"]) != es_buy): b -= 5
    b = max(0, min(25, b))
    bd["B) Setup técnico"] = b; score += b

    # C) Momentum — 20 pts (base 5 + bonos)
    c = 5
    macd_align = (ind_m15["macd_h"] > 0) == es_buy
    if macd_align and abs(ind_m15["macd_h"]) > abs(ind_m15["macd_hp"]): c += 5  # creciente
    elif macd_align: c += 3
    stoch = ind_m15["stoch"]
    if es_buy and stoch < 40: c += 4
    elif not es_buy and stoch > 60: c += 4
    elif 30 < stoch < 70: c += 2
    if adx >= 20: c += 6
    elif adx >= 14: c += 4
    elif adx >= 9:  c += 3
    elif adx >= 6:  c += 1
    c = min(20, c)
    bd["C) Momentum"] = c; score += c

    # D) Gestión riesgo — 15 pts (base 8)
    d = 8
    sl_d = atr * 1.2
    tp2_d = atr * 2.0
    rr2 = tp2_d / sl_d if sl_d > 0 else 0
    units = riesgo_usd / sl_d if sl_d > 0 else 1
    if rr2 >= 1.6: d += 4
    elif rr2 >= 1.2: d += 2
    if abs(p - ind_m15["ema20"]) < atr * 0.6: d += 3
    d = min(15, d)
    bd["D) Gestión riesgo"] = d; score += d

    # E) Limpieza — 15 pts (base 6)
    e = 6
    if not ind_m15["lateral"]: e += 4
    if not ind_m15["vela_ext"]: e += 3
    if ind_m5 and not ind_m5["vela_ext"]: e += 2
    e = min(15, e)
    bd["E) Limpieza"] = e; score += e

    return min(100, score), dir_, bd

def final_decision(score, key, ind_m15):
    abierto, razon = mercado_abierto(key)
    if not abierto: return "BLOQUEADA", razon
    if ind_m15 and ind_m15["adx"] < 6: return "BLOQUEADA", "ADX muy bajo — sin dirección"
    if ind_m15 and ind_m15["vela_ext"]: return "ESPERAR", "vela extendida — esperar retroceso"
    if ind_m15 and ind_m15["lateral"]: return "ESPERAR", "mercado lateral — aguardar breakout"
    if score >= 62: return "RECOMENDAR", ""
    if score >= 48: return "ESPERAR", "esperando confirmación técnica"
    if score >= 35: return "OBSERVAR", "setup en formación"
    return "NO_OPERAR", "score insuficiente"

# ── ANALISAR PAR ──────────────────────────────────────────────────────────────
def analizar_par(key, riesgo_usd=100):
    sym = ALL_PAIRS[key][0]
    df_h1  = get_data(sym, "1h",  "60d")
    df_m15 = get_data(sym, "15m", "5d")
    df_m5  = get_data(sym, "5m",  "5d")
    ind_h1  = analizar_df(df_h1)
    ind_m15 = analizar_df(df_m15)
    ind_m5  = analizar_df(df_m5)
    price = get_live_price(sym) or (ind_m15["price"] if ind_m15 else None)
    if ind_m15 is None or price is None:
        return {"ok": False, "error": "sin datos", "key": key}

    score, dir_, bd = calcular_score(ind_h1, ind_m15, ind_m5, key, riesgo_usd)
    dec, motivo = final_decision(score, key, ind_m15)
    clase, _ = clasificar(score)
    atr  = ind_m15["atr"]
    sl_d = atr * 1.2
    tp1_d= atr * 0.8
    units= riesgo_usd / sl_d if sl_d > 0 else 1
    if dir_ == "buy":
        entry = price; sl = price - sl_d
        tp1 = price + atr * 0.8; tp2 = price + atr * 2.0
        tp3 = price + atr * 3.5; tp4 = price + atr * 5.5
    else:
        entry = price; sl = price + sl_d
        tp1 = price - atr * 0.8; tp2 = price - atr * 2.0
        tp3 = price - atr * 3.5; tp4 = price - atr * 5.5
    rr1 = abs(tp1 - entry) / sl_d if sl_d > 0 else 0
    rr2 = abs(tp2 - entry) / sl_d if sl_d > 0 else 0
    rr3 = abs(tp3 - entry) / sl_d if sl_d > 0 else 0
    rr4 = abs(tp4 - entry) / sl_d if sl_d > 0 else 0
    return {
        "ok": True, "key": key, "nombre": ALL_PAIRS[key][1],
        "price": price, "dir": dir_, "score": score, "clase": clase,
        "decision": dec, "motivo": motivo, "score_bd": bd,
        "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3, "tp4": tp4,
        "dist": sl_d, "units": units, "riesgo_usd": riesgo_usd,
        "rr1": rr1, "rr2": rr2, "rr3": rr3, "rr4": rr4,
        "g1": abs(tp1-entry)*units, "g2": abs(tp2-entry)*units,
        "g3": abs(tp3-entry)*units, "g4": abs(tp4-entry)*units,
        "ind": ind_m15, "ts_open": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }

# ── GOLD M5 VÍA MT5 ──────────────────────────────────────────────────────────
def analizar_gold_m5(gold_sym, min_score=70, spread_max=3.0):
    datos = get_gold_mt5(gold_sym)
    if datos is None:
        return {"ok": False, "error": "MT5 sin datos Gold", "decision": "BLOQUEADA"}
    ind_m1  = analizar_df(datos["m1"])
    ind_m5  = analizar_df(datos["m5"])
    ind_m15 = analizar_df(datos["m15"])
    price = datos["price"]; spread = datos["spread"]
    if ind_m5 is None:
        return {"ok": False, "error": "datos M5 insuficientes", "decision": "BLOQUEADA"}
    if spread > spread_max:
        return {"ok": True, "price": price, "spread": spread, "decision": "BLOQUEADA",
                "motivo": f"spread alto {spread:.2f}", "score": 0, "dir": None}

    score, dir_, bd = calcular_score(ind_m15, ind_m5, ind_m1, "XAUUSD", 100)
    # Bono gold: mecha inferior fuerte = +5
    if ind_m5 and ind_m5["mecha_inf"] > ind_m5["atr"] * 0.4: score = min(100, score + 5)
    if score < min_score:
        dec = "ESPERAR"; motivo = f"score {score} < mínimo {min_score}"
    else:
        dec, motivo = final_decision(score, "XAUUSD", ind_m5)

    clase, _ = clasificar(score)
    atr = ind_m5["atr"]
    sl_d = atr * 1.2
    units = 100 / sl_d if sl_d > 0 else 1
    entry = price
    if dir_ == "buy":
        sl = price - sl_d; tp1 = price + atr*0.8; tp2 = price + atr*2.0
        tp3 = price + atr*3.5; tp4 = price + atr*5.5
    else:
        sl = price + sl_d; tp1 = price - atr*0.8; tp2 = price - atr*2.0
        tp3 = price - atr*3.5; tp4 = price - atr*5.5

    tend_m15 = "buy" if (ind_m15 and ind_m15["ema20"] > ind_m15["ema50"]) else "sell"
    setup_m5 = ("alcista" if ind_m5["cierre_alc"] else "bajista") + f" · RSI {ind_m5['rsi']:.0f}"
    conf_m1  = "OK" if ind_m1 and ((dir_=="buy" and ind_m1["cierre_alc"]) or (dir_=="sell" and not ind_m1["cierre_alc"])) else "débil"
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    return {
        "ok": True, "key": "XAUUSD", "nombre": "XAU/USD Oro",
        "price": price, "bid": datos["bid"], "ask": datos["ask"],
        "spread": spread, "mt5_symbol": gold_sym,
        "dir": dir_, "score": score, "clase": clase,
        "decision": dec, "motivo": motivo, "score_bd": bd,
        "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3, "tp4": tp4,
        "dist": sl_d, "units": units, "riesgo_usd": 100,
        "rr1": abs(tp1-entry)/sl_d, "rr2": abs(tp2-entry)/sl_d,
        "rr3": abs(tp3-entry)/sl_d, "rr4": abs(tp4-entry)/sl_d,
        "g1": abs(tp1-entry)*units, "g2": abs(tp2-entry)*units,
        "g3": abs(tp3-entry)*units, "g4": abs(tp4-entry)*units,
        "tendencia_m15": tend_m15, "setup_m5": setup_m5, "conf_m1": conf_m1,
        "m5_bars": len(datos["m5"]) if datos["m5"] is not None else 0,
        "ts_open": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "ts": ts,
    }

# ── TELEGRAM ──────────────────────────────────────────────────────────────────
def enviar_telegram(r, bot_token, chat_id):
    if not bot_token or not chat_id: return False, "no configurado"
    d = r["dir"]; nombre = r["nombre"]; sc = r["score"]
    dt = "▲ LONG / BUY" if d == "buy" else "▼ SHORT / SELL"
    arrow = "🟢" if d == "buy" else "🔴"
    ts_tag = " ·  M5 MT5" if r.get("mt5_symbol") else ""
    msg = (
        f"⚡ *RAVEN AI · METALES & FOREX*{ts_tag}\n"
        f"*{nombre}* · {arrow} {dt}\n"
        f"Clase: *{r['clase']} · {sc}/100*\n\n"
        f"📍 Entrada: `{r['entry']:.5f}` \n"
        f"🛑 SL: `{r['sl']:.5f}`\n"
        f"🎯 TP1: `{r['tp1']:.5f}` +${r['g1']:.2f} (1:{r['rr1']:.1f})\n"
        f"🎯 TP2: `{r['tp2']:.5f}` +${r['g2']:.2f} (1:{r['rr2']:.1f})\n"
        f"💎 TP4: `{r['tp4']:.5f}` +${r['g4']:.2f}\n\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC"
    )
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=8)
        return resp.ok, "✅ Enviado" if resp.ok else resp.text
    except Exception as e:
        return False, str(e)

# ── SESIÓN STATE ──────────────────────────────────────────────────────────────
def _init_state():
    defs = {
        "scanning": False,
        "resultados": {},
        "gold_result": {},
        "live": {},
        "nuevas": [],
        "stats": {"señales":[], "wins":0, "losses":0, "total":0, "pnl_usd":0.0},
        "mt5_ok": False,
        "mt5_info": "",
        "gold_sym": None,
        "last_scan": "—",
        "scan_count": 0,
    }
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="color:#ffd600;font-size:1.1em;font-weight:900;letter-spacing:2px;margin-bottom:12px">🥇 RAVEN AI · M&F</div>', unsafe_allow_html=True)

    # Control
    col_a, col_b = st.columns(2)
    if col_a.button("▶ INICIAR" if not st.session_state["scanning"] else "⏹ DETENER", use_container_width=True):
        st.session_state["scanning"] = not st.session_state["scanning"]
        st.session_state["nuevas"] = []
    if col_b.button("🔄 Scan ahora", use_container_width=True):
        st.session_state["force_scan"] = True

    st.divider()

    # MT5 Gold
    st.markdown("**🟡 ORO / XAUUSD M5**")
    usar_gold_mt5 = st.checkbox("Usar MT5 para Gold M5", value=True, key="usar_gold_mt5")
    if usar_gold_mt5:
        if st.button("🔌 Conectar MT5", use_container_width=True):
            ok, info = mt5_connect()
            st.session_state["mt5_ok"] = ok
            st.session_state["mt5_info"] = info
            if ok:
                sym = find_gold_symbol()
                st.session_state["gold_sym"] = sym
        c = "#00e676" if st.session_state["mt5_ok"] else "#ff5252"
        t = "CONECTADO" if st.session_state["mt5_ok"] else "DESCONECTADO"
        sym_t = st.session_state.get("gold_sym") or "—"
        st.markdown(f'<div style="font-size:.72em;color:{c};margin-bottom:4px">MT5: {t} · {sym_t}</div>', unsafe_allow_html=True)
        gold_min_score = st.slider("Score mín. Gold:", 60, 90, 70, 5, key="g_min_score")
        gold_spread_max = st.number_input("Spread máx. Gold (USD):", value=3.0, step=0.5, key="g_spread_max")

    st.divider()

    # Pares activos
    st.markdown("**Metales activos**")
    metales_sel = []
    for k in METALS:
        if st.checkbox(ALL_PAIRS[k][1], value=True, key=f"chk_{k}"): metales_sel.append(k)

    st.markdown("**Forex activos**")
    forex_sel = []
    for k in FOREX:
        if st.checkbox(ALL_PAIRS[k][1], value=True, key=f"chk_{k}"): forex_sel.append(k)

    st.divider()

    # Configuración señales
    min_score = st.slider("Score mínimo (no-Gold):", 55, 90, 65, 5, key="min_score_sl")
    riesgo_usd = st.number_input("Riesgo por operación ($):", value=100, step=10, key="riesgo_sl")
    intervalo = st.slider("Intervalo auto-scan (seg):", 30, 300, 60, 10, key="intervalo_sl")

    st.divider()

    # Telegram
    st.markdown("**📱 Telegram**")
    tg_token = st.text_input("Bot Token:", value="", type="password", key="tg_token_input")
    tg_chat  = st.text_input("Chat ID:", value="", key="tg_chat_input")

    st.divider()
    st.markdown(f'<div style="color:#252540;font-size:.65em">Último scan: {st.session_state["last_scan"]}<br>Scans: {st.session_state["scan_count"]}</div>', unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""<div style="background:linear-gradient(135deg,#0d0d1f,#12122a);
border:1px solid #1a1a3a;border-radius:12px;padding:14px 20px;margin-bottom:16px;
display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
<div>
  <div style="color:#252562;font-size:.6em;text-transform:uppercase;letter-spacing:3px">RAVEN AI</div>
  <div style="color:#d8d8f8;font-size:1.3em;font-weight:900">🥇 Metales & Forex &nbsp;<span style="font-size:.55em;color:#555">Señales de alta probabilidad</span></div>
</div>
<div style="display:flex;gap:16px;font-size:.72em;flex-wrap:wrap">
  <span style="color:#252540">Metales: <b style="color:#ffd600">XAUUSD · XAGUSD · WTI</b></span>
  <span style="color:#252540">Forex: <b style="color:#42a5f5">EUR/USD · GBP/USD · USD/JPY · AUD/USD · USD/CAD · USD/MXN</b></span>
</div>
</div>""", unsafe_allow_html=True)

# ── LÓGICA DE SCAN ────────────────────────────────────────────────────────────
_scanning = st.session_state["scanning"]
_force    = st.session_state.pop("force_scan", False)
# Scan automático en primer carga
_first_load = st.session_state.get("scan_count", 0) == 0
if _first_load:
    _force = True

if _scanning or _force:
    pares_no_gold = [k for k in (metales_sel + forex_sel) if k != "XAUUSD"]

    # Scan non-gold pairs (paralelo con threads)
    nuevos_resultados = {}

    def _scan_pair(k):
        try:
            nuevos_resultados[k] = analizar_par(k, riesgo_usd)
        except Exception as e:
            nuevos_resultados[k] = {"ok": False, "key": k, "error": str(e)}

    threads = [threading.Thread(target=_scan_pair, args=(k,), daemon=True) for k in pares_no_gold]
    for t in threads: t.start()
    for t in threads: t.join(timeout=15)

    # Gold M5 via MT5
    if usar_gold_mt5 and "XAUUSD" in metales_sel and st.session_state["mt5_ok"]:
        gold_sym = st.session_state.get("gold_sym")
        if gold_sym:
            gmin = st.session_state.get("g_min_score", 70)
            gspd = st.session_state.get("g_spread_max", 3.0)
            gr = analizar_gold_m5(gold_sym, gmin, gspd)
            st.session_state["gold_result"] = gr
    elif "XAUUSD" in metales_sel:
        gr = analizar_par("XAUUSD", riesgo_usd)
        st.session_state["gold_result"] = {**gr,
            "tendencia_m15": "buy" if (gr.get("ind",{}) or {}).get("ema20", 0) > (gr.get("ind",{}) or {}).get("ema50", 0) else "sell",
            "setup_m5": "yfinance M15", "conf_m1": "—", "ts": datetime.now(timezone.utc).strftime("%H:%M")}

    # Detectar nuevas señales
    stats = st.session_state["stats"]
    prev_keys_recom = {s["key"] for s in stats["señales"] if s["estado"] == "ABIERTA"}
    st.session_state["nuevas"] = []
    for k, r in nuevos_resultados.items():
        if r.get("decision") == "RECOMENDAR" and r.get("dir") and k not in prev_keys_recom:
            s_new = {**r, "estado": "ABIERTA", "resultado_usd": 0.0, "ts_close": None,
                     "cat": "METALES" if k in METALS else "FOREX"}
            stats["señales"].insert(0, s_new)
            st.session_state["nuevas"].append(s_new)
            ok_t, _ = enviar_telegram(r, tg_token, tg_chat)

    _gd = st.session_state.get("gold_result", {})
    if _gd.get("decision") == "RECOMENDAR" and _gd.get("dir") and "XAUUSD" not in prev_keys_recom:
        s_new = {**_gd, "estado": "ABIERTA", "resultado_usd": 0.0, "ts_close": None, "cat": "METALES"}
        stats["señales"].insert(0, s_new)
        st.session_state["nuevas"].append(s_new)
        ok_t, _ = enviar_telegram(_gd, tg_token, tg_chat)

    # Live prices
    _live = {}
    for k, r in nuevos_resultados.items():
        if r.get("price"): _live[k] = r["price"]
    if _gd.get("price"): _live["XAUUSD"] = _gd["price"]
    st.session_state["resultados"] = nuevos_resultados
    st.session_state["live"] = _live
    st.session_state["last_scan"] = datetime.now(timezone.utc).strftime("%H:%M:%S")
    st.session_state["scan_count"] += 1

# Vars de lectura
resultados = st.session_state.get("resultados", {})
live = st.session_state.get("live", {})
stats = st.session_state["stats"]
abiertas = [s for s in stats["señales"] if s["estado"] == "ABIERTA"]
_gd = st.session_state.get("gold_result", {})

# ── ALERTAS ───────────────────────────────────────────────────────────────────
for s in st.session_state.get("nuevas", []):
    dc = "#00e676" if s["dir"] == "buy" else "#ff1744"
    dt = "▲ COMPRA" if s["dir"] == "buy" else "▼ VENTA"
    st.markdown(f'<div class="alert-new">🚨 <b style="color:{dc}">{s["nombre"]} · {dt}</b>'
        f'&emsp;Score <b style="color:#00e676">{s["score"]}/100</b>'
        f'&emsp;Entrada: <b style="color:#82b1ff">{s["entry"]:.5f}</b></div>',
        unsafe_allow_html=True)

# ── HELPER: tarjeta de señal ──────────────────────────────────────────────────
def _signal_card(r):
    pv = live.get(r["key"], r["entry"])
    pnl_v = (pv - r["entry"]) * r["units"] if r["dir"] == "buy" else (r["entry"] - pv) * r["units"]
    pnl_c = "#00e676" if pnl_v >= 0 else "#ff1744"
    is_buy = r["dir"] == "buy"
    ac  = "#00e676" if is_buy else "#ff1744"
    sc  = r["score"]
    css = "sig-premium" if sc >= 90 else "sig-alta" if sc >= 80 else "sig-obs"
    dt  = "▲ COMPRAR" if is_buy else "▼ VENDER"
    es_txt, es_c = calcular_entry_status(pv, r["entry"], r["tp1"])
    avance = abs(pv - r["entry"]) / abs(r["tp1"] - r["entry"]) * 100 if abs(r["tp1"] - r["entry"]) > 0 else 0
    color_par = ALL_PAIRS.get(r["key"], ("","","#fff"))[2]
    sc_bg = "#ffd600" if sc >= 90 else "#00e676" if sc >= 80 else "#ff9800"
    dec = r.get("decision", "RECOMENDAR")
    dec_label = "✅ ACTIVA" if dec == "RECOMENDAR" else "⏳ EN FORMACIÓN"
    dec_bg = "#002200" if dec == "RECOMENDAR" else "#1a1000"
    dec_fc = "#00e676" if dec == "RECOMENDAR" else "#ffd600"
    action_txt = ("ENTRAR — zona óptima de entrada" if es_txt == "CERCA DE ENTRADA"
                  else "ESPERAR pullback hacia zona de entrada" if es_txt == "ESPERAR PULLBACK"
                  else "PRECIO ALEJADO — evaluar con precaución")
    action_icon = "✅" if es_txt == "CERCA DE ENTRADA" else ("⏳" if es_txt == "ESPERAR PULLBACK" else "⚠️")
    mt5_row = (f'<div style="background:#080608;border-top:1px solid #140a12;padding:6px 20px;'
               f'display:flex;gap:16px;font-size:.7em">'
               f'<span style="color:#383858">M15: <b style="color:#ffd600">{r.get("tendencia_m15","—")}</b></span>'
               f'<span style="color:#383858">M5: <b style="color:#555">{r.get("setup_m5","—")}</b></span>'
               f'<span style="color:#383858">M1: <b style="color:#82b1ff">{r.get("conf_m1","—")}</b></span>'
               f'</div>' if r.get("mt5_symbol") else "")
    st.markdown(f"""<div class="{css}">
<div style="background:linear-gradient(135deg,{ac}18,{ac}06,transparent);
  border-bottom:1px solid {ac}20;padding:12px 20px;
  display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <span style="background:{ac};color:{'#000' if is_buy else '#fff'};font-size:.8em;
      font-weight:900;padding:5px 14px;border-radius:20px">{dt}</span>
    <span style="color:{color_par};font-size:1.1em;font-weight:900">{r['nombre']}</span>
    <span style="background:{dec_bg};color:{dec_fc};font-size:.65em;font-weight:700;
      padding:2px 8px;border-radius:10px;border:1px solid {dec_fc}33">{dec_label}</span>
    {f'<span style="background:#1a1000;color:#ffd600;font-size:.62em;padding:2px 7px;border-radius:3px;border:1px solid #3a2800">◆ MT5 M5</span>' if r.get("mt5_symbol") else ""}
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <span style="background:{sc_bg};color:#000;font-size:.78em;font-weight:900;
      padding:4px 12px;border-radius:20px">⭐ {sc}/100</span>
    <div style="text-align:right">
      <div style="color:#383858;font-size:.57em;text-transform:uppercase;letter-spacing:1.5px">precio live</div>
      <div style="color:#fff;font-size:1.2em;font-weight:900;font-family:'Courier New',mono">{fmt(pv,r['key'])}</div>
      <div style="color:{pnl_c};font-size:.7em;font-weight:700">P&L {'+'if pnl_v>=0 else ''}${pnl_v:.2f}</div>
    </div>
  </div>
</div>
<div style="padding:12px 20px">
  <div style="display:flex;align-items:center;justify-content:space-between;
    padding:8px 12px;background:#070713;border:1px solid #14143a;border-radius:7px;margin-bottom:6px">
    <div style="display:flex;align-items:center;gap:10px">
      <span style="color:#42a5f5;font-size:.62em;font-weight:700;text-transform:uppercase;
        letter-spacing:2px;min-width:62px">🎯 ENTRADA</span>
      <span style="color:#82b1ff;font-size:1.05em;font-weight:800;font-family:'Courier New',mono">{fmt(r['entry'],r['key'])}</span>
    </div>
    <span style="color:{es_c};border:1px solid {es_c}44;background:{es_c}0f;
      padding:3px 10px;border-radius:4px;font-size:.68em;font-weight:800">{es_txt}</span>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;
    padding:8px 12px;background:#0a0404;border:1px solid #280a0a;border-radius:7px;margin-bottom:12px">
    <div style="display:flex;align-items:center;gap:10px">
      <span style="color:#ff5252;font-size:.62em;font-weight:700;text-transform:uppercase;
        letter-spacing:2px;min-width:62px">🛑 STOP</span>
      <span style="color:#ff5252;font-size:1.05em;font-weight:800;font-family:'Courier New',mono">{fmt(r['sl'],r['key'])}</span>
    </div>
    <span style="background:#190404;color:#ff5252;border:1px solid #381010;
      padding:3px 10px;border-radius:4px;font-size:.7em;font-weight:800">−${r['riesgo_usd']:.0f}</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
    <div style="background:#020d02;border:1px solid #0a280a;border-radius:7px;padding:9px 12px">
      <div style="color:#1b5e20;font-size:.6em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">TP 1</div>
      <div style="color:#69f0ae;font-size:.94em;font-weight:800;font-family:'Courier New',mono;margin:3px 0">{fmt(r['tp1'],r['key'])}</div>
      <div style="color:#2e7d32;font-size:.66em">1:{r['rr1']:.1f} &nbsp;·&nbsp; <span style="color:#43a047">+${r['g1']:.2f}</span></div>
    </div>
    <div style="background:#020d02;border:1px solid #0a280a;border-radius:7px;padding:9px 12px">
      <div style="color:#2e7d32;font-size:.6em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">TP 2</div>
      <div style="color:#69f0ae;font-size:.94em;font-weight:800;font-family:'Courier New',mono;margin:3px 0">{fmt(r['tp2'],r['key'])}</div>
      <div style="color:#2e7d32;font-size:.66em">1:{r['rr2']:.1f} &nbsp;·&nbsp; <span style="color:#43a047">+${r['g2']:.2f}</span></div>
    </div>
    <div style="background:#030f03;border:1px solid #0c2e0c;border-radius:7px;padding:9px 12px">
      <div style="color:#388e3c;font-size:.6em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">TP 3</div>
      <div style="color:#69f0ae;font-size:.94em;font-weight:800;font-family:'Courier New',mono;margin:3px 0">{fmt(r['tp3'],r['key'])}</div>
      <div style="color:#2e7d32;font-size:.66em">1:{r['rr3']:.1f} &nbsp;·&nbsp; <span style="color:#43a047">+${r['g3']:.2f}</span></div>
    </div>
    <div style="background:#0a0800;border:2px solid #2a2000;border-radius:7px;padding:9px 12px">
      <div style="color:#ffd600;font-size:.6em;font-weight:900;text-transform:uppercase;letter-spacing:1.5px">💎 TP 4</div>
      <div style="color:#ffd600;font-size:.94em;font-weight:900;font-family:'Courier New',mono;margin:3px 0">{fmt(r['tp4'],r['key'])}</div>
      <div style="color:#a37900;font-size:.66em">1:{r['rr4']:.1f} &nbsp;·&nbsp; <span style="color:#ffd600">+${r['g4']:.2f}</span></div>
    </div>
  </div>
</div>
<div style="background:{es_c}0c;border-top:1px solid {es_c}18;padding:9px 20px;
  display:flex;align-items:center;gap:8px">
  <span style="font-size:.9em">{action_icon}</span>
  <span style="color:{es_c};font-weight:800;font-size:.8em">{action_txt}</span>
  {f'<span style="color:#252540;font-size:.66em;margin-left:auto">TP1: {avance:.1f}% recorrido</span>' if avance > 2 else ""}
</div>
{mt5_row}
</div>""", unsafe_allow_html=True)

def _radar_rows(keys):
    rows = ""
    for key in keys:
        r = resultados.get(key) or ({} if key != "XAUUSD" else _gd)
        if key == "XAUUSD" and _gd.get("ok"): r = _gd
        if not r.get("ok"): continue
        p   = live.get(key) or r.get("price")
        sc  = r.get("score", 0); dec = r.get("decision", "—")
        dir_ = r.get("dir")
        color_par = ALL_PAIRS.get(key, ("","","#fff"))[2]
        if dec == "RECOMENDAR" and dir_ == "buy":
            bg="#010d04"; bl="3px solid #00c853"; sc_c="#00e676"
            d_cell='<span style="background:#00e676;color:#000;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.72em">▲ COMPRA</span>'
        elif dec == "RECOMENDAR" and dir_ == "sell":
            bg="#0d0101"; bl="3px solid #c62828"; sc_c="#ff1744"
            d_cell='<span style="background:#ff1744;color:#fff;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.72em">▼ VENTA</span>'
        elif dec == "ESPERAR" and dir_ == "buy":
            bg="#060e06"; bl="3px solid #143614"; sc_c="#69f0ae"
            d_cell='<span style="background:#0a2a0a;color:#69f0ae;font-size:.7em;padding:2px 8px;border-radius:3px;font-weight:700">⏳ POSIBLE BUY</span>'
        elif dec == "ESPERAR" and dir_ == "sell":
            bg="#0e0606"; bl="3px solid #361414"; sc_c="#ff8a80"
            d_cell='<span style="background:#2a0a0a;color:#ff8a80;font-size:.7em;padding:2px 8px;border-radius:3px;font-weight:700">⏳ POSIBLE SELL</span>'
        elif dec == "BLOQUEADA":
            bg="#080808"; bl="3px solid #111"; sc_c="#2a2a2a"
            d_cell='<span style="color:#2a2a2a;font-size:.7em">🔒 BLOQUEADA</span>'
        else:
            bg="#09090f"; bl="3px solid #141428"; sc_c="#252545"
            d_cell='<span style="color:#252545;font-size:.7em">— NO OPERAR</span>'
        abierto, _ = mercado_abierto(key)
        if not abierto: d_cell = '<span style="color:#252545;font-size:.7em">🕒 CERRADO</span>'
        ind_r = r.get("ind") or {}
        adx = ind_r.get("adx", 0)
        rsi = ind_r.get("rsi", 0)
        rsi_c = "#ff5252" if rsi > 70 else "#ff9800" if rsi > 65 else "#00e676" if rsi < 35 else "#ff9800" if rsi < 40 else "#555"
        rows += (f'<tr style="background:{bg};border-left:{bl}">'
            f'<td style="padding:7px 10px;color:{color_par};font-weight:800">{ALL_PAIRS[key][1]}</td>'
            f'<td style="padding:7px 10px;color:#d8d8f8;font-family:monospace">{fmt(p, key) if p else "—"}</td>'
            f'<td style="padding:7px 10px">{d_cell}</td>'
            f'<td style="padding:7px 10px;color:{sc_c};font-weight:800">{sc}/100</td>'
            f'<td style="padding:7px 10px;color:{rsi_c};font-size:.78em">{rsi:.0f}</td>'
            f'<td style="padding:7px 10px;color:{"#00e676" if adx>=20 else "#ffd600" if adx>=14 else "#383858"};font-size:.78em">{adx:.0f}</td></tr>')
    return rows

def _badge(n):
    if n <= 0: return ""
    return f" ({n})"

# ── TABS ──────────────────────────────────────────────────────────────────────
_abiertas_metals = [s for s in abiertas if s.get("key") in METALS]
_abiertas_forex  = [s for s in abiertas if s.get("key") in FOREX]
_n_metals = len(_abiertas_metals) + (1 if _gd.get("decision") == "RECOMENDAR" else 0)
_n_forex  = len(_abiertas_forex)

tab_metals, tab_forex, tab_hist = st.tabs([
    f"🥇 METALES{_badge(_n_metals)}",
    f"💱 FOREX{_badge(_n_forex)}",
    "📜 HISTORIAL",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB: METALES
# ══════════════════════════════════════════════════════════════════════════════
with tab_metals:
    # Panel Gold M5
    if "XAUUSD" in metales_sel and _gd:
        _gd_dec = _gd.get("decision", "—")
        _gd_price = _gd.get("price"); _gd_spread = _gd.get("spread")
        _gd_score = _gd.get("score", 0); _gd_dir = _gd.get("dir")
        _gd_tend = _gd.get("tendencia_m15", "neutral")
        _gd_setup = _gd.get("setup_m5", "—"); _gd_conf = _gd.get("conf_m1", "—")
        _gd_sym = _gd.get("mt5_symbol"); _gd_ts = _gd.get("ts", "—")
        _tend_icon = "▲" if _gd_tend == "buy" else ("▼" if _gd_tend == "sell" else "◆")
        _tend_c = "#00e676" if _gd_tend == "buy" else ("#ff5252" if _gd_tend == "sell" else "#555")
        _spread_c = "#00e676" if (_gd_spread or 0) <= st.session_state.get("g_spread_max", 3.0) else "#ff9800"
        _est_map = {"RECOMENDAR":("SEÑAL ACTIVA","#00e676"),"ESPERAR":("ESPERAR","#ffd600"),
                    "BLOQUEADA":("BLOQUEADA","#ff9800"),"OBSERVAR":("OBSERVAR","#42a5f5")}
        _estado_gold, _estado_c = _est_map.get(_gd_dec, ("SIN DATOS","#555"))
        st.markdown('<div class="sec-hdr">🟡 ORO / XAUUSD M5 &nbsp;<span style="color:#ffd600;font-size:.75em">◆ Metales preciosos</span></div>', unsafe_allow_html=True)
        st.markdown(f"""<div style="background:linear-gradient(135deg,#0a0800,#12100000);
border:1px solid #3a2d00;border-left:5px solid #ffd600;border-radius:12px;
padding:14px 20px;margin:6px 0;box-shadow:0 0 18px rgba(255,214,0,.1)">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px">
  <div>
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:2px">🟡 XAUUSD · ORO M5</div>
    <div style="color:#ffd600;font-size:1.3em;font-weight:900;margin:3px 0">
      {f"{'▲ LONG' if _gd_dir=='buy' else '▼ SHORT'}" if _gd_dir else "◆ Sin señal"}
      &nbsp;<span style="font-size:.65em;color:#888">{_gd.get('clase','—')} · {_gd_score}/100</span>
    </div>
    <div style="color:#555;font-size:.72em">
      <span style="color:{_estado_c};font-weight:800">{_estado_gold}</span>
      {f" &nbsp;·&nbsp; {_gd.get('motivo','')[:40]}" if _gd.get('motivo') else ""}
    </div>
  </div>
  <div style="text-align:right">
    <div style="color:#888;font-size:.65em">📡 {_gd_sym or 'yfinance'} · {_gd_ts}</div>
    <div style="color:#fff;font-size:1.5em;font-weight:900;font-family:'Courier New',mono">{f"{_gd_price:,.2f}" if _gd_price else "—"}</div>
    {f'<div style="color:{_spread_c};font-size:.75em">Spread: {_gd_spread:.2f}</div>' if _gd_spread else ""}
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px;
padding-top:10px;border-top:1px solid #1a1600">
  <div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;padding:7px 12px">
    <div style="color:#252540;font-size:.58em;text-transform:uppercase;letter-spacing:1.5px">M15 Tendencia</div>
    <div style="color:{_tend_c};font-weight:800;font-size:.88em">{_tend_icon} {_gd_tend.upper()}</div>
  </div>
  <div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;padding:7px 12px">
    <div style="color:#252540;font-size:.58em;text-transform:uppercase;letter-spacing:1.5px">M5 Setup</div>
    <div style="color:#ffd600;font-size:.76em;font-weight:700">{_gd_setup[:30] if _gd_setup else '—'}</div>
  </div>
  <div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;padding:7px 12px">
    <div style="color:#252540;font-size:.58em;text-transform:uppercase;letter-spacing:1.5px">M1 Conf.</div>
    <div style="color:#82b1ff;font-size:.76em;font-weight:700">{_gd_conf}</div>
  </div>
</div>
</div>""", unsafe_allow_html=True)
        if _gd_dir and _gd_dec == "RECOMENDAR":
            _signal_card(_gd)

    # XAGUSD / WTIUSD señales
    for key in [k for k in metales_sel if k != "XAUUSD"]:
        r = resultados.get(key)
        if r and r.get("ok") and r.get("decision") in ("RECOMENDAR", "ESPERAR"):
            _signal_card(r)

    # Sin señales
    metals_all_checked = [k for k in metales_sel if k != "XAUUSD"]
    if not _gd.get("decision") and not any(resultados.get(k, {}).get("decision") in ("RECOMENDAR","ESPERAR") for k in metals_all_checked):
        st.markdown('<div class="no-signals"><div style="color:#d8d8f8;font-size:.95em">🚫 Sin señales activas en METALES</div>'
            '<div style="color:#252540;font-size:.78em;margin-top:4px">Presiona ▶ INICIAR para activar el scanner.</div></div>', unsafe_allow_html=True)

    # Radar
    rows_m = _radar_rows(metales_sel)
    if rows_m:
        with st.expander("📡 Radar técnico — METALES", expanded=False):
            st.markdown(f'<table class="radar-tbl"><thead><tr><th>Par</th><th>Precio</th><th>Señal</th><th>Score</th><th>RSI</th><th>ADX</th></tr></thead><tbody>{rows_m}</tbody></table>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: FOREX
# ══════════════════════════════════════════════════════════════════════════════
with tab_forex:
    # Sesión activa
    now_u = datetime.now(timezone.utc); h_u = now_u.hour
    if 22 <= h_u or h_u < 7:     _ses, _ses_c = "🌏 ASIA", "#42a5f5"
    elif 7 <= h_u < 9:            _ses, _ses_c = "🌍+🌏 OVERLAP Asia/Europa", "#ffd600"
    elif 13 <= h_u < 16:          _ses, _ses_c = "🌍+🌎 OVERLAP Europa/NY", "#ffd600"
    elif 9 <= h_u < 16:           _ses, _ses_c = "🌍 EUROPA", "#69f0ae"
    elif 16 <= h_u < 22:          _ses, _ses_c = "🌎 NUEVA YORK", "#ff9800"
    else:                          _ses, _ses_c = "🌙 Pre-sesión", "#555"
    st.markdown(f'<div style="background:#09090f;border:1px solid #1a1a3a;border-radius:8px;'
        f'padding:8px 16px;margin-bottom:12px;font-size:.8em">'
        f'Sesión: <b style="color:{_ses_c}">{_ses}</b> &nbsp;·&nbsp; '
        f'<span style="color:#333">UTC {now_u.strftime("%H:%M")}</span>'
        f'&nbsp;·&nbsp;<span style="color:#252540;font-size:.85em">Los pares en overlap tienen mayor volatilidad</span></div>',
        unsafe_allow_html=True)

    # Señales activas forex
    forex_activas = [resultados[k] for k in forex_sel if k in resultados and resultados[k].get("decision") == "RECOMENDAR"]
    forex_espera  = [resultados[k] for k in forex_sel if k in resultados and resultados[k].get("decision") == "ESPERAR"]

    if forex_activas:
        st.markdown('<div class="sec-hdr">🟢 SEÑALES ACTIVAS PARA ENTRAR — FOREX</div>', unsafe_allow_html=True)
        for r in sorted(forex_activas, key=lambda x: x.get("score", 0), reverse=True):
            _signal_card(r)

    if forex_espera:
        st.markdown(f'<div class="sec-hdr" style="margin-top:8px">🟡 SETUPS EN FORMACIÓN — FOREX &nbsp;<span style="color:#ffd600;font-size:.8em">({len(forex_espera)} pares)</span></div>', unsafe_allow_html=True)
        for r in sorted(forex_espera, key=lambda x: x.get("score", 0), reverse=True):
            pv = live.get(r["key"], r.get("price", 0))
            is_buy = r["dir"] == "buy"
            ac = "#69f0ae" if is_buy else "#ff8a80"
            bc = "#020d02" if is_buy else "#0d0202"
            brd = "#0a2a0a" if is_buy else "#2a0a0a"
            dt = "▲ POSIBLE BUY" if is_buy else "▼ POSIBLE SELL"
            color_par = ALL_PAIRS.get(r["key"], ("","","#fff"))[2]
            ind = r.get("ind") or {}
            atr = ind.get("atr", 0)
            tp1_e = pv + atr*0.8 if is_buy else pv - atr*0.8
            tp2_e = pv + atr*2.0 if is_buy else pv - atr*2.0
            sl_e  = pv - atr*1.2 if is_buy else pv + atr*1.2
            motivo = r.get("motivo", "esperando confirmación")[:48]
            st.markdown(f"""<div style="background:{bc};border:1px solid {brd};border-left:4px solid {ac};
border-radius:10px;margin:8px 0;overflow:hidden">
<div style="padding:10px 16px;display:flex;justify-content:space-between;align-items:center;
  flex-wrap:wrap;gap:8px;border-bottom:1px solid {brd}">
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
    <span style="color:{ac};font-size:.78em;font-weight:900;background:{ac}1a;
      padding:3px 10px;border-radius:14px;border:1px solid {ac}33">{dt}</span>
    <span style="color:{color_par};font-weight:900;font-size:.98em">{r['nombre']}</span>
  </div>
  <div style="display:flex;align-items:center;gap:8px">
    <span style="background:#1a1a2a;color:#9575cd;padding:3px 10px;border-radius:12px;
      font-size:.72em;font-weight:700">{r['score']}/100</span>
    <span style="color:#2a2a48;font-size:.67em">{motivo}</span>
  </div>
</div>
<div style="padding:9px 16px;display:flex;gap:14px;flex-wrap:wrap;
  font-size:.78em;font-family:'Courier New',monospace;align-items:center">
  <span style="color:#383858">📍 <b style="color:#d8d8f8">{fmt(pv,r['key'])}</b></span>
  <span style="color:#1a1a30">│</span>
  <span style="color:#383858">SL <b style="color:#ff5252">{fmt(sl_e,r['key'])}</b></span>
  <span style="color:#1a1a30">│</span>
  <span style="color:#383858">TP1 <b style="color:#69f0ae">{fmt(tp1_e,r['key'])}</b></span>
  <span style="color:#1a1a30">│</span>
  <span style="color:#383858">TP2 <b style="color:#43a047">{fmt(tp2_e,r['key'])}</b></span>
</div>
<div style="padding:4px 16px 8px;font-size:.66em;color:#1e2a1e">
  ⏳ Aguardar confirmación de entrada — setup aún en formación
</div>
</div>""", unsafe_allow_html=True)

    if not forex_activas and not forex_espera:
        scan_msg = "Scanner activo — esperando setup válido." if st.session_state["scanning"] else "Presiona <b>▶ INICIAR</b> para activar el scanner."
        st.markdown(f'<div class="no-signals"><div style="color:#d8d8f8;font-size:.95em">📊 Sin señales en FOREX ahora mismo</div>'
            f'<div style="color:#252540;font-size:.78em;margin-top:4px">{scan_msg}</div></div>', unsafe_allow_html=True)

    # Radar siempre visible si hay datos
    rows_f = _radar_rows(forex_sel)
    if rows_f:
        with st.expander("📡 Radar técnico — todos los pares FOREX", expanded=True):
            st.markdown(f'<table class="radar-tbl"><thead><tr><th>Par</th><th>Precio</th><th>Señal</th><th>Score</th><th>RSI</th><th>ADX</th></tr></thead><tbody>{rows_f}</tbody></table>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: HISTORIAL
# ══════════════════════════════════════════════════════════════════════════════
with tab_hist:
    cerradas = [s for s in stats["señales"] if s["estado"] in ("GANADA","PERDIDA","EXPIRADA")]
    total = stats["total"]; wins = stats["wins"]; losses = stats["losses"]; pnl = stats["pnl_usd"]

    if total > 0:
        tasa = wins / total * 100
        c1, c2, c3 = st.columns(3)
        c1.metric("Win Rate", f"{tasa:.1f}%{'*' if total<30 else ''}", f"{wins}G · {losses}P")
        c2.metric("P&L Total", f"${pnl:+.2f}", f"{total} cerradas")
        c3.metric("Abiertas", f"{len(abiertas)}")

    if cerradas:
        st.markdown('<div class="sec-hdr">📜 SEÑALES CERRADAS</div>', unsafe_allow_html=True)
        for s in cerradas[:30]:
            if s["estado"] == "GANADA":
                css = "h-win"; badge = '<span class="b-win">✅ GANADA</span>'
                res = f'<b style="color:#69f0ae">+${s["resultado_usd"]:.2f}</b>'
            elif s["estado"] == "PERDIDA":
                css = "h-loss"; badge = '<span class="b-loss">❌ PERDIDA</span>'
                res = f'<b style="color:#ff5252">-${abs(s["resultado_usd"]):.2f}</b>'
            else:
                css = "h-exp"; badge = '<span class="b-exp">⏱ EXPIRADA</span>'
                res = '<span style="color:#333">$0.00</span>'
            dc = "#00e676" if s["dir"] == "buy" else "#ff1744"
            color_par = ALL_PAIRS.get(s["key"], ("","","#fff"))[2]
            t_op = s["ts_open"][11:16]
            t_cl = (s.get("ts_close") or "")[11:16] or "—"
            st.markdown(f"""<div class="{css}">
<div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px">
  <div style="display:flex;align-items:center;gap:8px">
    {badge}
    <b style="color:{dc};font-size:.85em">{"▲" if s["dir"]=="buy" else "▼"}</b>
    <b style="color:{color_par}">{s["nombre"]}</b>
    <span style="color:#252540;font-size:.7em">{s.get("score",0)}/100</span>
  </div>
  <div style="display:flex;gap:10px;font-size:.75em;flex-wrap:wrap">
    <span style="color:#444">Entrada: <b style="color:#82b1ff">{fmt(s["entry"],s["key"])}</b></span>
    <span style="color:#444">SL: <b style="color:#ff5252">{fmt(s["sl"],s["key"])}</b></span>
    <span style="color:#444">TP1: <b style="color:#69f0ae">{fmt(s["tp1"],s["key"])}</b></span>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    {res}
    <span style="color:#1e1e38;font-size:.7em">{t_op} → {t_cl}</span>
  </div>
</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown('<div class="no-signals">Sin señales cerradas todavía.</div>', unsafe_allow_html=True)

# ── AUTO-REFRESH ──────────────────────────────────────────────────────────────
if st.session_state["scanning"]:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=intervalo * 1000, key="rf_mf")
    except Exception:
        st.caption(f"Instala streamlit-autorefresh para auto-scan cada {intervalo}s")
