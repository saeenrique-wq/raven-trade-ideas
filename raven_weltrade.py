# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  RAVEN AI · WELTRADE MT5 SCANNER  — 100% MetaTrader 5                      ║
# ║  Puerto: 8505  |  streamlit run raven_weltrade.py --server.port 8505        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
import streamlit as st
import pandas as pd
import numpy as np
import requests, json, time, threading
from datetime import datetime, timezone

try:
    import MetaTrader5 as mt5
    _MT5 = True
except ImportError:
    _MT5 = False

from ta.trend     import EMAIndicator, MACD, ADXIndicator
from ta.momentum  import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange

st.set_page_config(
    page_title="RAVEN · Weltrade MT5",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
body,.stApp{background:#07070f;color:#d8d8f8}
.block-container{padding:1rem 1.5rem 1rem}
.stTabs [data-baseweb="tab-list"]{background:#0c0c18;border-radius:8px;padding:4px;gap:4px}
.stTabs [data-baseweb="tab"]{background:transparent;color:#555;border-radius:6px;
  padding:8px 18px;font-weight:700;font-size:.8em;text-transform:uppercase;letter-spacing:1.5px}
.stTabs [aria-selected="true"]{background:#1a1a30;color:#d8d8f8}
.sec-hdr{background:linear-gradient(90deg,#12122a,#0c0c18);border-left:3px solid #3d3d7a;
  padding:6px 14px;margin:10px 0 8px;font-size:.72em;text-transform:uppercase;
  letter-spacing:2.5px;color:#555;font-weight:700;border-radius:0 6px 6px 0}
.sig-premium{background:linear-gradient(135deg,#030318,#06062a);border:1px solid #3d3d7a;
  border-left:4px solid #ffd600;border-radius:12px;padding:0;margin:12px 0;overflow:hidden;
  box-shadow:0 4px 30px rgba(100,80,255,.12)}
.sig-alta{background:linear-gradient(135deg,#030318,#06062a);border:1px solid #1e2a1e;
  border-left:4px solid #00e676;border-radius:12px;padding:0;margin:12px 0;overflow:hidden;
  box-shadow:0 4px 20px rgba(0,230,118,.06)}
.sig-obs{background:#09090f;border:1px solid #1a1a30;border-left:3px solid #ff9800;
  border-radius:10px;padding:0;margin:10px 0;overflow:hidden}
.no-sig{background:#09090f;border:1px solid #1a1a30;border-radius:10px;
  padding:18px 20px;text-align:center;color:#252540;margin:10px 0}
.alert-new{background:linear-gradient(90deg,#0d1a0d,#050a05);border:1px solid #1a4d1a;
  border-left:4px solid #00e676;border-radius:8px;padding:10px 16px;margin:6px 0;
  font-size:.85em;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{border-left-color:#00e676}50%{border-left-color:#69f0ae}}
.radar-tbl{width:100%;border-collapse:collapse;font-size:.78em}
.radar-tbl th{background:#0c0c18;color:#383858;padding:7px 10px;font-weight:700;
  text-transform:uppercase;letter-spacing:1.5px;font-size:.68em;border-bottom:1px solid #1a1a30}
.radar-tbl td{border-bottom:1px solid #0e0e1e;vertical-align:middle}
.acc-card{background:#0c0c18;border:1px solid #1a1a30;border-radius:8px;padding:10px 14px;margin:4px 0}
.stButton>button{background:linear-gradient(135deg,#3d1278,#6a0dad);color:#fff;border:none;
  border-radius:8px;font-weight:700;padding:8px 20px;font-size:.85em}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES MT5
# ══════════════════════════════════════════════════════════════════════════════

TF_MAP = {}
if _MT5:
    TF_MAP = {
        "M1":  mt5.TIMEFRAME_M1,
        "M5":  mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "D1":  mt5.TIMEFRAME_D1,
    }

def mt5_conectar():
    if not _MT5: return False, "Instala: pip install MetaTrader5", {}
    if not mt5.initialize(): return False, f"Error: {mt5.last_error()}", {}
    acc = mt5.account_info()
    if acc is None: return False, "Sin cuenta MT5 activa", {}
    info = {
        "nombre":    acc.name,
        "broker":    acc.company,
        "servidor":  acc.server,
        "balance":   acc.balance,
        "equity":    acc.equity,
        "margin":    acc.margin,
        "libre":     acc.margin_free,
        "leverage":  acc.leverage,
        "moneda":    acc.currency,
        "login":     acc.login,
    }
    return True, f"{acc.name} · {acc.company}", info

def mt5_obtener_simbolos():
    if not _MT5: return {}
    syms = mt5.symbols_get()
    if not syms: return {}
    result = {}
    for s in syms:
        if not s.visible: continue
        cat = _categorizar(s.name)
        result.setdefault(cat, []).append(s.name)
    for cat in result:
        result[cat].sort()
    return result

def _categorizar(sym):
    s = sym.upper().replace(".","").replace("-","").replace("_","")
    if any(x in s for x in ["XAU","XAG","XPT","XPD","GOLD","SILVER"]): return "Metales"
    if any(x in s for x in ["BTC","ETH","LTC","XRP","BNB","SOL","ADA","DOT","LINK","BCH"]): return "Crypto"
    if any(x in s for x in ["OIL","WTI","BRENT","NGAS","NG","COCOA","WHEAT","CORN","SOYBEAN"]): return "Energía/Comm"
    if any(x in s for x in ["US30","US100","US500","UK100","GER","GER40","JPN225","NAS","SPX",
                              "DOW","DAX","FTSE","CAC","AUS200","CHINA50","NIKKEI","HSI"]): return "Índices"
    cur = {"USD","EUR","GBP","JPY","AUD","CAD","CHF","NZD","MXN","SGD","HKD","NOK","SEK","DKK",
           "ZAR","TRY","BRL","CNH","CNY","CZK","HUF","PLN","ILS","INR","THB","TWD"}
    if len(s) == 6:
        base = s[:3]; quote = s[3:]
        if base in cur and quote in cur: return "Forex"
    if len(s) <= 8 and any(s.startswith(c) for c in cur) and any(s.endswith(c) for c in cur):
        return "Forex"
    return "Otros"

def mt5_datos(sym, tf="M15", count=300):
    if not _MT5 or tf not in TF_MAP: return None
    try:
        r = mt5.copy_rates_from_pos(sym, TF_MAP[tf], 0, count)
        if r is None or len(r) < 30: return None
        df = pd.DataFrame(r)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time").rename(columns={"tick_volume": "volume"})
        return df[["open","high","low","close","volume"]]
    except Exception:
        return None

def mt5_tick(sym):
    if not _MT5: return None, None, None
    try:
        t = mt5.symbol_info_tick(sym)
        if t is None: return None, None, None
        spread_pts = mt5.symbol_info(sym).spread if mt5.symbol_info(sym) else 0
        point     = mt5.symbol_info(sym).point  if mt5.symbol_info(sym) else 0.00001
        spread_v  = spread_pts * point
        return (t.bid + t.ask) / 2, spread_v, t
    except Exception:
        return None, None, None

# ══════════════════════════════════════════════════════════════════════════════
# INDICADORES
# ══════════════════════════════════════════════════════════════════════════════

def analizar_df(df):
    if df is None or len(df) < 30: return None
    c = df["close"]
    try:
        rsi    = RSIIndicator(c, 14).rsi().iloc[-1]
        macd_o = MACD(c)
        macd_h = macd_o.macd_diff().iloc[-1]
        macd_hp= macd_o.macd_diff().iloc[-2] if len(c) > 2 else 0
        bb     = BollingerBands(c, 20, 2)
        bb_hi  = bb.bollinger_hband().iloc[-1]
        bb_lo  = bb.bollinger_lband().iloc[-1]
        bb_mid = bb.bollinger_mavg().iloc[-1]
        ema9   = EMAIndicator(c,  9).ema_indicator().iloc[-1]
        ema20  = EMAIndicator(c, 20).ema_indicator().iloc[-1]
        ema50  = EMAIndicator(c, 50).ema_indicator().iloc[-1]
        ema200 = EMAIndicator(c, 200).ema_indicator().iloc[-1] if len(c) >= 200 else ema50
        atr    = AverageTrueRange(df["high"], df["low"], c, 14).average_true_range().iloc[-1]
        stoch  = StochasticOscillator(df["high"], df["low"], c, 14, 3).stoch().iloc[-1]
        adx_i  = ADXIndicator(df["high"], df["low"], c, 14)
        adx    = adx_i.adx().iloc[-1]
        dip    = adx_i.adx_neg().iloc[-1]
        dim    = adx_i.adx_pos().iloc[-1]
        price  = c.iloc[-1]
        slope  = (ema20 - EMAIndicator(c,20).ema_indicator().iloc[-4]) / ema20 * 100 if len(c) > 4 else 0
        cuerpo    = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
        mecha_inf = min(df["open"].iloc[-1], df["close"].iloc[-1]) - df["low"].iloc[-1]
        mecha_sup = df["high"].iloc[-1] - max(df["open"].iloc[-1], df["close"].iloc[-1])
        range_c   = df["high"].iloc[-1] - df["low"].iloc[-1]
        vela_ext  = range_c > atr * 2.5
        lateral   = adx < 12
        cierre_alc= df["close"].iloc[-1] > df["open"].iloc[-1]
        max_10    = df["high"].iloc[-10:].max()
        min_10    = df["low"].iloc[-10:].min()
        return {
            "price": price, "rsi": rsi, "macd_h": macd_h, "macd_hp": macd_hp,
            "bb_hi": bb_hi, "bb_lo": bb_lo, "bb_mid": bb_mid,
            "ema9": ema9, "ema20": ema20, "ema50": ema50, "ema200": ema200,
            "atr": atr, "stoch": stoch, "adx": adx, "dip": dip, "dim": dim,
            "slope": slope, "vela_ext": vela_ext, "lateral": lateral,
            "cierre_alc": cierre_alc, "mecha_inf": mecha_inf, "mecha_sup": mecha_sup,
            "cuerpo": cuerpo, "max_10": max_10, "min_10": min_10,
        }
    except Exception:
        return None

def calcular_score(ind_h1, ind_m15, ind_m5):
    if ind_m15 is None: return 0, "neutral", {}
    p   = ind_m15["price"]
    atr = ind_m15["atr"]
    rsi = ind_m15["rsi"]
    adx = ind_m15["adx"]
    score = 0; bd = {}

    buy_pts = sell_pts = 0
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
    dir_   = "buy" if buy_pts >= sell_pts else "sell"
    es_buy = dir_ == "buy"

    # A) Tendencia MTF — 25 pts
    a = 10
    if ind_h1:
        h1_alc  = ind_h1["ema20"]  > ind_h1["ema50"]
        m15_alc = ind_m15["ema20"] > ind_m15["ema50"]
        if h1_alc == m15_alc: a += 5
        if (h1_alc and es_buy) or (not h1_alc and not es_buy): a += 3
        if p > ind_h1["ema200"]: a += 4 if es_buy else 0
        else: a += 4 if not es_buy else 0
        if (ind_h1["slope"] > 0.005) == es_buy: a += 3
    else:
        a += 5
        if (ind_m15["ema20"] > ind_m15["ema50"]) == es_buy: a += 5
    if ind_m5 and (ind_m5["ema20"] > ind_m5["ema50"]) == es_buy: a += 3
    a = min(25, a); bd["A) Tendencia MTF"] = a; score += a

    # B) Setup técnico — 25 pts
    b = 8
    if es_buy:
        if 35 <= rsi <= 55: b += 6
        elif 55 < rsi <= 65: b += 3
        if p <= ind_m15["bb_lo"] + atr * 0.3: b += 6
        elif p > ind_m15["bb_mid"] and p < ind_m15["bb_hi"]: b += 4
        if abs(p - ind_m15["ema20"]) < atr * 0.8: b += 4
        if ind_m15["cierre_alc"]: b += 3
    else:
        if 45 <= rsi <= 65: b += 6
        elif 35 <= rsi < 45: b += 3
        if p >= ind_m15["bb_hi"] - atr * 0.3: b += 6
        elif p < ind_m15["bb_mid"] and p > ind_m15["bb_lo"]: b += 4
        if abs(p - ind_m15["ema20"]) < atr * 0.8: b += 4
        if not ind_m15["cierre_alc"]: b += 3
    if not ind_m15["vela_ext"]: b += 4
    if ind_m5 and (ind_m5["ema20"] > ind_m5["ema50"]) != es_buy: b -= 5
    b = max(0, min(25, b)); bd["B) Setup técnico"] = b; score += b

    # C) Momentum — 20 pts
    c = 5
    macd_align = (ind_m15["macd_h"] > 0) == es_buy
    if macd_align and abs(ind_m15["macd_h"]) > abs(ind_m15["macd_hp"]): c += 5
    elif macd_align: c += 3
    stoch = ind_m15["stoch"]
    if es_buy and stoch < 40: c += 4
    elif not es_buy and stoch > 60: c += 4
    elif 30 < stoch < 70: c += 2
    if adx >= 20: c += 6
    elif adx >= 14: c += 4
    elif adx >= 9:  c += 3
    elif adx >= 6:  c += 1
    c = min(20, c); bd["C) Momentum"] = c; score += c

    # D) Gestión riesgo — 15 pts
    d = 8
    sl_d = atr * 1.2
    rr2  = (atr * 2.0) / sl_d if sl_d > 0 else 0
    if rr2 >= 1.6: d += 4
    elif rr2 >= 1.2: d += 2
    if abs(p - ind_m15["ema20"]) < atr * 0.6: d += 3
    d = min(15, d); bd["D) Riesgo"] = d; score += d

    # E) Limpieza — 15 pts
    e = 6
    if not ind_m15["lateral"]: e += 4
    if not ind_m15["vela_ext"]: e += 3
    if ind_m5 and not ind_m5["vela_ext"]: e += 2
    e = min(15, e); bd["E) Limpieza"] = e; score += e

    return min(100, score), dir_, bd

def clasificar(score):
    if score >= 90: return "PREMIUM",   "#ffd600"
    if score >= 80: return "ALTA PROB.","#00e676"
    if score >= 70: return "OBSERVAR",  "#42a5f5"
    return "NO OPERAR", "#555"

def decision_final(score, ind_m15):
    if ind_m15 and ind_m15["adx"] < 6:      return "BLOQUEADA", "ADX muy bajo"
    if ind_m15 and ind_m15["vela_ext"]:      return "ESPERAR",   "vela extendida"
    if ind_m15 and ind_m15["lateral"]:       return "ESPERAR",   "mercado lateral"
    if score >= 62: return "RECOMENDAR", ""
    if score >= 48: return "ESPERAR",    "esperando confirmación"
    if score >= 35: return "OBSERVAR",   "setup en formación"
    return "NO_OPERAR", "score insuficiente"

# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS DE SÍMBOLO MT5
# ══════════════════════════════════════════════════════════════════════════════

def analizar_simbolo(sym, riesgo_usd=100, spread_max_pips=5.0):
    price, spread, tick = mt5_tick(sym)
    if price is None:
        return {"ok": False, "sym": sym, "error": "sin tick"}

    # Spread máximo
    sinfo = mt5.symbol_info(sym) if _MT5 else None
    digits = sinfo.digits if sinfo else 5
    pip_size = 10 ** -(digits - 1) if digits >= 2 else 0.0001
    spread_pips = spread / pip_size if pip_size > 0 else 999

    if spread_pips > spread_max_pips:
        return {"ok": True, "sym": sym, "price": price, "spread": spread,
                "spread_pips": spread_pips, "decision": "BLOQUEADA",
                "motivo": f"spread {spread_pips:.1f}p > máx", "score": 0, "dir": None}

    df_h1  = mt5_datos(sym, "H1",  300)
    df_m15 = mt5_datos(sym, "M15", 300)
    df_m5  = mt5_datos(sym, "M5",  200)

    ind_h1  = analizar_df(df_h1)
    ind_m15 = analizar_df(df_m15)
    ind_m5  = analizar_df(df_m5)

    if ind_m15 is None:
        return {"ok": False, "sym": sym, "error": "datos insuficientes"}

    score, dir_, bd = calcular_score(ind_h1, ind_m15, ind_m5)
    dec, motivo     = decision_final(score, ind_m15)
    clase, _        = clasificar(score)

    cat = _categorizar(sym)
    atr  = ind_m15["atr"]
    sl_d = atr * 1.2
    units = riesgo_usd / sl_d if sl_d > 0 else 1

    if dir_ == "buy":
        sl  = price - sl_d
        tp1 = price + atr * 0.8;  tp2 = price + atr * 2.0
        tp3 = price + atr * 3.5;  tp4 = price + atr * 5.5
    else:
        sl  = price + sl_d
        tp1 = price - atr * 0.8;  tp2 = price - atr * 2.0
        tp3 = price - atr * 3.5;  tp4 = price - atr * 5.5

    entry = price
    rr1 = abs(tp1-entry)/sl_d if sl_d else 0
    rr2 = abs(tp2-entry)/sl_d if sl_d else 0
    rr3 = abs(tp3-entry)/sl_d if sl_d else 0
    rr4 = abs(tp4-entry)/sl_d if sl_d else 0

    tend_m15 = "▲ alcista" if (ind_m15["ema20"] > ind_m15["ema50"]) else "▼ bajista"
    conf_m5  = ("✓ OK" if ind_m5 and (ind_m5["ema20"] > ind_m5["ema50"]) == (dir_=="buy") else "⚠ débil") if ind_m5 else "—"

    return {
        "ok": True, "sym": sym, "cat": cat,
        "nombre": sym,
        "price": price, "spread": spread, "spread_pips": spread_pips,
        "dir": dir_, "score": score, "clase": clase,
        "decision": dec, "motivo": motivo, "score_bd": bd,
        "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3, "tp4": tp4,
        "dist": sl_d, "units": units, "riesgo_usd": riesgo_usd,
        "rr1": rr1, "rr2": rr2, "rr3": rr3, "rr4": rr4,
        "g1": abs(tp1-entry)*units, "g2": abs(tp2-entry)*units,
        "g3": abs(tp3-entry)*units, "g4": abs(tp4-entry)*units,
        "ind": ind_m15, "digits": digits,
        "tend_m15": tend_m15, "conf_m5": conf_m5,
        "ts_open": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }

# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM
# ══════════════════════════════════════════════════════════════════════════════

def enviar_telegram(r, token, chat_id):
    if not token or not chat_id: return False
    d = r["dir"]; sc = r["score"]
    arrow = "🟢 ▲ LONG / BUY" if d == "buy" else "🔴 ▼ SHORT / SELL"
    msg = (
        f"⚡ *RAVEN AI · WELTRADE MT5*\n"
        f"*{r['sym']}* · {arrow}\n"
        f"Clase: *{r['clase']} · {sc}/100*\n\n"
        f"📍 Entrada: `{_fmt(r['entry'], r['digits'])}`\n"
        f"🛑 SL: `{_fmt(r['sl'], r['digits'])}` (−${r['riesgo_usd']:.0f})\n"
        f"🎯 TP1: `{_fmt(r['tp1'], r['digits'])}` +${r['g1']:.2f} (1:{r['rr1']:.1f})\n"
        f"🎯 TP2: `{_fmt(r['tp2'], r['digits'])}` +${r['g2']:.2f} (1:{r['rr2']:.1f})\n"
        f"💎 TP4: `{_fmt(r['tp4'], r['digits'])}` +${r['g4']:.2f}\n\n"
        f"Spread: `{r['spread_pips']:.1f}p` · M15: {r.get('tend_m15','—')}\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC"
    )
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=8)
        return resp.ok
    except Exception:
        return False

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS UI
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(v, digits=5):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    if digits >= 5: return f"{v:.{digits}f}"
    if abs(v) >= 10000: return f"{v:,.{max(0,digits-4)}f}"
    if abs(v) >= 100:   return f"{v:.{max(1,digits-2)}f}"
    return f"{v:.{digits}f}"

def _cat_icon(cat):
    return {"Forex":"💱","Metales":"🥇","Índices":"📊","Crypto":"₿",
            "Energía/Comm":"🛢️","Otros":"🔹"}.get(cat,"🔹")

def _signal_card(r):
    sc   = r["score"]; is_buy = r["dir"] == "buy"
    ac   = "#00e676" if is_buy else "#ff1744"
    css  = "sig-premium" if sc >= 90 else "sig-alta" if sc >= 80 else "sig-obs"
    dt   = "▲ COMPRAR" if is_buy else "▼ VENDER"
    sc_bg = "#ffd600" if sc >= 90 else "#00e676" if sc >= 80 else "#ff9800"
    pv   = r["price"]
    tend = r.get("tend_m15","—"); conf = r.get("conf_m5","—")
    dec_lbl = "✅ ACTIVA" if r["decision"]=="RECOMENDAR" else "⏳ EN FORMACIÓN"
    dec_bg  = "#002200" if r["decision"]=="RECOMENDAR" else "#1a1000"
    dec_fc  = "#00e676" if r["decision"]=="RECOMENDAR" else "#ffd600"
    spread_c = "#00e676" if r["spread_pips"] <= 2 else "#ffd600" if r["spread_pips"] <= 4 else "#ff9800"

    st.markdown(f"""<div class="{css}">
<div style="background:linear-gradient(135deg,{ac}18,{ac}06,transparent);
  border-bottom:1px solid {ac}20;padding:12px 20px;
  display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <span style="background:{ac};color:{'#000' if is_buy else '#fff'};font-size:.8em;
      font-weight:900;padding:5px 14px;border-radius:20px">{dt}</span>
    <span style="color:#d8d8f8;font-size:1.1em;font-weight:900;font-family:'Courier New',mono">{r['sym']}</span>
    <span style="background:{dec_bg};color:{dec_fc};font-size:.65em;font-weight:700;
      padding:2px 8px;border-radius:10px;border:1px solid {dec_fc}33">{dec_lbl}</span>
    <span style="background:#0a0814;color:#555;font-size:.6em;padding:2px 7px;
      border-radius:4px;border:1px solid #1a1a30">{_cat_icon(r['cat'])} {r['cat']}</span>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <span style="background:{sc_bg};color:#000;font-size:.78em;font-weight:900;
      padding:4px 12px;border-radius:20px">⭐ {sc}/100</span>
    <div style="text-align:right">
      <div style="color:#383858;font-size:.55em;text-transform:uppercase;letter-spacing:1.5px">precio MT5</div>
      <div style="color:#fff;font-size:1.15em;font-weight:900;font-family:'Courier New',mono">{_fmt(pv, r['digits'])}</div>
      <div style="color:{spread_c};font-size:.65em">Spread: {r['spread_pips']:.1f}p</div>
    </div>
  </div>
</div>
<div style="padding:12px 20px">
  <div style="display:flex;align-items:center;justify-content:space-between;
    padding:8px 12px;background:#070713;border:1px solid #14143a;border-radius:7px;margin-bottom:6px">
    <div style="display:flex;align-items:center;gap:10px">
      <span style="color:#42a5f5;font-size:.62em;font-weight:700;text-transform:uppercase;
        letter-spacing:2px;min-width:62px">🎯 ENTRADA</span>
      <span style="color:#82b1ff;font-size:1.05em;font-weight:800;font-family:'Courier New',mono">{_fmt(r['entry'],r['digits'])}</span>
    </div>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;
    padding:8px 12px;background:#0a0404;border:1px solid #280a0a;border-radius:7px;margin-bottom:12px">
    <div style="display:flex;align-items:center;gap:10px">
      <span style="color:#ff5252;font-size:.62em;font-weight:700;text-transform:uppercase;
        letter-spacing:2px;min-width:62px">🛑 STOP</span>
      <span style="color:#ff5252;font-size:1.05em;font-weight:800;font-family:'Courier New',mono">{_fmt(r['sl'],r['digits'])}</span>
    </div>
    <span style="background:#190404;color:#ff5252;border:1px solid #381010;
      padding:3px 10px;border-radius:4px;font-size:.7em;font-weight:800">−${r['riesgo_usd']:.0f}</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
    <div style="background:#020d02;border:1px solid #0a280a;border-radius:7px;padding:9px 12px">
      <div style="color:#1b5e20;font-size:.6em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">TP 1</div>
      <div style="color:#69f0ae;font-size:.92em;font-weight:800;font-family:'Courier New',mono;margin:3px 0">{_fmt(r['tp1'],r['digits'])}</div>
      <div style="color:#2e7d32;font-size:.66em">1:{r['rr1']:.1f} · <span style="color:#43a047">+${r['g1']:.2f}</span></div>
    </div>
    <div style="background:#020d02;border:1px solid #0a280a;border-radius:7px;padding:9px 12px">
      <div style="color:#2e7d32;font-size:.6em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">TP 2</div>
      <div style="color:#69f0ae;font-size:.92em;font-weight:800;font-family:'Courier New',mono;margin:3px 0">{_fmt(r['tp2'],r['digits'])}</div>
      <div style="color:#2e7d32;font-size:.66em">1:{r['rr2']:.1f} · <span style="color:#43a047">+${r['g2']:.2f}</span></div>
    </div>
    <div style="background:#030f03;border:1px solid #0c2e0c;border-radius:7px;padding:9px 12px">
      <div style="color:#388e3c;font-size:.6em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">TP 3</div>
      <div style="color:#69f0ae;font-size:.92em;font-weight:800;font-family:'Courier New',mono;margin:3px 0">{_fmt(r['tp3'],r['digits'])}</div>
      <div style="color:#2e7d32;font-size:.66em">1:{r['rr3']:.1f} · <span style="color:#43a047">+${r['g3']:.2f}</span></div>
    </div>
    <div style="background:#0a0800;border:2px solid #2a2000;border-radius:7px;padding:9px 12px">
      <div style="color:#ffd600;font-size:.6em;font-weight:900;text-transform:uppercase;letter-spacing:1.5px">💎 TP 4</div>
      <div style="color:#ffd600;font-size:.92em;font-weight:900;font-family:'Courier New',mono;margin:3px 0">{_fmt(r['tp4'],r['digits'])}</div>
      <div style="color:#a37900;font-size:.66em">1:{r['rr4']:.1f} · <span style="color:#ffd600">+${r['g4']:.2f}</span></div>
    </div>
  </div>
</div>
<div style="background:#0a0814;border-top:1px solid #1a1a30;padding:8px 20px;
  display:flex;gap:20px;font-size:.7em;flex-wrap:wrap">
  <span style="color:#383858">M15: <b style="color:#ffd600">{tend}</b></span>
  <span style="color:#383858">M5 conf: <b style="color:#82b1ff">{conf}</b></span>
  <span style="color:#383858">RSI: <b style="color:{'#ff5252' if r['ind']['rsi']>70 else '#ff9800' if r['ind']['rsi']>65 else '#00e676' if r['ind']['rsi']<35 else '#555'}">{r['ind']['rsi']:.0f}</b></span>
  <span style="color:#383858">ADX: <b style="color:{'#00e676' if r['ind']['adx']>=20 else '#ffd600' if r['ind']['adx']>=14 else '#383858'}">{r['ind']['adx']:.0f}</b></span>
</div>
</div>""", unsafe_allow_html=True)

def _radar_row(r, syms_sel):
    rows = ""
    for sym in syms_sel:
        r = st.session_state["resultados"].get(sym)
        if not r or not r.get("ok"): continue
        sc = r.get("score",0); dec = r.get("decision","—"); dir_ = r.get("dir")
        p  = r.get("price")
        if dec == "RECOMENDAR" and dir_ == "buy":
            bg="#010d04"; bl="3px solid #00c853"
            d_cell='<span style="background:#00e676;color:#000;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.72em">▲ COMPRA</span>'
        elif dec == "RECOMENDAR" and dir_ == "sell":
            bg="#0d0101"; bl="3px solid #c62828"
            d_cell='<span style="background:#ff1744;color:#fff;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.72em">▼ VENTA</span>'
        elif dec == "ESPERAR" and dir_ == "buy":
            bg="#060e06"; bl="3px solid #143614"
            d_cell='<span style="background:#0a2a0a;color:#69f0ae;font-size:.7em;padding:2px 8px;border-radius:3px;font-weight:700">⏳ POSIBLE BUY</span>'
        elif dec == "ESPERAR" and dir_ == "sell":
            bg="#0e0606"; bl="3px solid #361414"
            d_cell='<span style="background:#2a0a0a;color:#ff8a80;font-size:.7em;padding:2px 8px;border-radius:3px;font-weight:700">⏳ POSIBLE SELL</span>'
        else:
            bg="#09090f"; bl="3px solid #1a1a30"
            d_cell='<span style="color:#252545;font-size:.7em">— NO OPERAR</span>'
        ind = r.get("ind") or {}
        adx = ind.get("adx",0); rsi = ind.get("rsi",50)
        rsi_c = "#ff5252" if rsi>70 else "#ff9800" if rsi>65 else "#00e676" if rsi<35 else "#555"
        sc_c  = "#ffd600" if sc>=90 else "#00e676" if sc>=80 else "#ff9800" if sc>=70 else "#383858"
        spd   = r.get("spread_pips",0)
        spd_c = "#00e676" if spd<=2 else "#ffd600" if spd<=4 else "#ff9800"
        rows += (f'<tr style="background:{bg};border-left:{bl}">'
            f'<td style="padding:7px 10px;color:#d8d8f8;font-weight:800;font-family:monospace">{sym}</td>'
            f'<td style="padding:7px 10px;color:#d8d8f8;font-family:monospace">{_fmt(p, r.get("digits",5)) if p else "—"}</td>'
            f'<td style="padding:7px 10px">{d_cell}</td>'
            f'<td style="padding:7px 10px;color:{sc_c};font-weight:800">{sc}/100</td>'
            f'<td style="padding:7px 10px;color:{rsi_c};font-size:.78em">{rsi:.0f}</td>'
            f'<td style="padding:7px 10px;color:{"#00e676" if adx>=20 else "#ffd600" if adx>=14 else "#383858"};font-size:.78em">{adx:.0f}</td>'
            f'<td style="padding:7px 10px;color:{spd_c};font-size:.78em">{spd:.1f}p</td></tr>')
    return rows

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
def _init():
    defs = {
        "mt5_ok":    False,
        "mt5_info":  "",
        "mt5_acc":   {},
        "simbolos":  {},
        "sel":       {},
        "scanning":  False,
        "resultados":{},
        "nuevas":    [],
        "stats":     {"señales":[], "wins":0,"losses":0,"total":0,"pnl":0.0},
        "scan_count":0,
        "last_scan": "—",
    }
    for k,v in defs.items():
        if k not in st.session_state: st.session_state[k]=v
_init()

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div style="color:#ffd600;font-size:1.1em;font-weight:900;'
                'letter-spacing:2px;margin-bottom:8px">🌐 RAVEN · WELTRADE MT5</div>',
                unsafe_allow_html=True)

    # ── Conexión MT5 ──────────────────────────────────────────────────────────
    if st.button("🔌 Conectar MT5", use_container_width=True):
        ok, info, acc_data = mt5_conectar()
        st.session_state["mt5_ok"]   = ok
        st.session_state["mt5_info"] = info
        st.session_state["mt5_acc"]  = acc_data
        if ok:
            st.session_state["simbolos"] = mt5_obtener_simbolos()
            # Selección por defecto: Forex + Metales (primeros 20 pares de cada cat)
            sel = {}
            for cat, syms in st.session_state["simbolos"].items():
                sel[cat] = syms[:20] if cat in ("Forex","Metales") else []
            st.session_state["sel"] = sel

    c = "#00e676" if st.session_state["mt5_ok"] else "#ff5252"
    t = "✅ CONECTADO" if st.session_state["mt5_ok"] else "❌ DESCONECTADO"
    st.markdown(f'<div style="font-size:.72em;color:{c};margin-bottom:6px">{t} · {st.session_state["mt5_info"]}</div>',
                unsafe_allow_html=True)

    # ── Info cuenta ───────────────────────────────────────────────────────────
    acc = st.session_state.get("mt5_acc", {})
    if acc:
        eq_c = "#00e676" if acc.get("equity",0) >= acc.get("balance",0) else "#ff9800"
        st.markdown(f"""<div class="acc-card">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:.72em">
  <div><span style="color:#383858">Balance</span><br><b style="color:#d8d8f8">${acc.get('balance',0):,.2f}</b></div>
  <div><span style="color:#383858">Equity</span><br><b style="color:{eq_c}">${acc.get('equity',0):,.2f}</b></div>
  <div><span style="color:#383858">Margen libre</span><br><b style="color:#42a5f5">${acc.get('libre',0):,.2f}</b></div>
  <div><span style="color:#383858">Apalancamiento</span><br><b style="color:#d8d8f8">1:{acc.get('leverage',0)}</b></div>
</div></div>""", unsafe_allow_html=True)

    st.divider()

    # ── Selección de símbolos ─────────────────────────────────────────────────
    simbolos = st.session_state.get("simbolos", {})
    sel_updated = {}
    cat_order = ["Forex","Metales","Índices","Crypto","Energía/Comm","Otros"]
    for cat in cat_order:
        syms = simbolos.get(cat, [])
        if not syms: continue
        icon = _cat_icon(cat)
        with st.expander(f"{icon} {cat} ({len(syms)})"):
            if st.button(f"Todo {cat}", key=f"all_{cat}"):
                st.session_state["sel"][cat] = list(syms)
            if st.button(f"Ninguno {cat}", key=f"none_{cat}"):
                st.session_state["sel"][cat] = []
            current = st.session_state.get("sel", {}).get(cat, syms[:15] if cat=="Forex" else [])
            chosen = st.multiselect("Seleccionar:", syms, default=current, key=f"ms_{cat}")
            sel_updated[cat] = chosen

    if sel_updated:
        st.session_state["sel"] = sel_updated

    st.divider()

    # ── Parámetros ────────────────────────────────────────────────────────────
    st.markdown("**⚙️ Parámetros**")
    riesgo_usd   = st.number_input("Riesgo por trade ($):", value=100, step=10, key="riesgo_sl")
    min_score    = st.slider("Score mínimo:", 50, 90, 62, 1, key="min_sc")
    spread_max   = st.number_input("Spread máx (pips):", value=5.0, step=0.5, key="spd_max")
    intervalo    = st.slider("Intervalo auto-scan (seg):", 30, 300, 60, 10, key="intv_sl")

    st.divider()

    # ── Telegram ──────────────────────────────────────────────────────────────
    st.markdown("**📱 Telegram**")
    tg_token = st.text_input("Bot Token:", value="", type="password", key="tg_tok")
    tg_chat  = st.text_input("Chat ID:", value="", key="tg_chat")

    st.divider()

    # ── Control ───────────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    if col_a.button("▶ INICIAR" if not st.session_state["scanning"] else "⏹ DETENER",
                    use_container_width=True):
        st.session_state["scanning"] = not st.session_state["scanning"]
        st.session_state["nuevas"] = []
    if col_b.button("🔄 Scan", use_container_width=True):
        st.session_state["force_scan"] = True

    if st.session_state["scan_count"] > 0:
        st.markdown(f'<div style="color:#252540;font-size:.62em;margin-top:6px">'
                    f'Último: {st.session_state["last_scan"]} · Scans: {st.session_state["scan_count"]}</div>',
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""<div style="background:linear-gradient(135deg,#0d0d1f,#12122a);
border:1px solid #1a1a3a;border-radius:12px;padding:14px 20px;margin-bottom:16px;
display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
<div>
  <div style="color:#252562;font-size:.6em;text-transform:uppercase;letter-spacing:3px">RAVEN AI</div>
  <div style="color:#d8d8f8;font-size:1.3em;font-weight:900">🌐 WELTRADE MT5 SCANNER
  &nbsp;<span style="font-size:.5em;color:#555">Señales 100% MetaTrader 5</span></div>
</div>
<div style="display:flex;gap:16px;font-size:.72em;flex-wrap:wrap">
  <span style="color:#252540">Datos: <b style="color:#42a5f5">MT5 en tiempo real</b></span>
  <span style="color:#252540">TF: <b style="color:#ffd600">M5 · M15 · H1</b></span>
</div>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LÓGICA DE SCAN
# ══════════════════════════════════════════════════════════════════════════════
_scanning  = st.session_state["scanning"]
_force     = st.session_state.pop("force_scan", False)
_first     = st.session_state["scan_count"] == 0

if (_scanning or _force) and st.session_state["mt5_ok"]:
    sel_flat = [sym for syms in st.session_state.get("sel",{}).values() for sym in syms]
    sel_flat = list(dict.fromkeys(sel_flat))  # dedup, preserve order

    if sel_flat:
        nuevos = {}
        lock = threading.Lock()

        def _scan(sym):
            try:
                res = analizar_simbolo(sym, riesgo_usd, spread_max)
                with lock: nuevos[sym] = res
            except Exception as e:
                with lock: nuevos[sym] = {"ok": False, "sym": sym, "error": str(e)}

        threads = [threading.Thread(target=_scan, args=(s,), daemon=True) for s in sel_flat]
        for t in threads: t.start()
        for t in threads: t.join(timeout=20)

        # Detectar nuevas señales
        stats = st.session_state["stats"]
        prev  = {s["sym"] for s in stats["señales"] if s["estado"]=="ABIERTA"}
        st.session_state["nuevas"] = []
        for sym, r in nuevos.items():
            if (r.get("decision")=="RECOMENDAR" and r.get("dir")
                    and r.get("score",0) >= min_score and sym not in prev):
                s_new = {**r, "estado":"ABIERTA", "resultado_usd":0.0, "ts_close":None}
                stats["señales"].insert(0, s_new)
                st.session_state["nuevas"].append(s_new)
                enviar_telegram(r, tg_token, tg_chat)

        st.session_state["resultados"]  = nuevos
        st.session_state["last_scan"]   = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        st.session_state["scan_count"] += 1

elif not st.session_state["mt5_ok"] and (_scanning or _force):
    st.warning("⚠️ Conecta MT5 primero desde el panel lateral.")

# ══════════════════════════════════════════════════════════════════════════════
# ALERTAS DE NUEVAS SEÑALES
# ══════════════════════════════════════════════════════════════════════════════
for s in st.session_state.get("nuevas", []):
    dc = "#00e676" if s["dir"]=="buy" else "#ff1744"
    dt = "▲ COMPRA" if s["dir"]=="buy" else "▼ VENTA"
    st.markdown(
        f'<div class="alert-new">🚨 <b style="color:{dc}">{s["sym"]} · {dt}</b>'
        f'&emsp;Score <b style="color:#00e676">{s["score"]}/100</b>'
        f'&emsp;Entrada: <b style="color:#82b1ff">{_fmt(s["entry"],s.get("digits",5))}</b>'
        f'&emsp;Spread: {s["spread_pips"]:.1f}p</div>',
        unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
resultados = st.session_state.get("resultados", {})
stats      = st.session_state["stats"]
abiertas   = [s for s in stats["señales"] if s["estado"]=="ABIERTA"]

def _n_cat(cat):
    return sum(1 for s in abiertas if s.get("cat")==cat)
def _n_rec(cat=None):
    if cat:
        return sum(1 for r in resultados.values()
                   if r.get("decision")=="RECOMENDAR" and r.get("cat")==cat)
    return sum(1 for r in resultados.values() if r.get("decision")=="RECOMENDAR")

_cats_activas = [c for c in ["Forex","Metales","Índices","Crypto","Energía/Comm"]
                 if st.session_state.get("sel",{}).get(c)]

_tab_labels = [f"{_cat_icon(c)} {c}" + (f" ({_n_rec(c)})" if _n_rec(c) > 0 else "")
               for c in _cats_activas]
_tab_labels += ["📡 RADAR", "📜 HISTORIAL"]

tabs = st.tabs(_tab_labels)

# ── Tabs por categoría ────────────────────────────────────────────────────────
for i, cat in enumerate(_cats_activas):
    with tabs[i]:
        syms_cat = st.session_state.get("sel",{}).get(cat, [])
        activas  = [resultados[s] for s in syms_cat
                    if s in resultados and resultados[s].get("decision")=="RECOMENDAR"
                    and resultados[s].get("score",0) >= min_score]
        esperas  = [resultados[s] for s in syms_cat
                    if s in resultados and resultados[s].get("decision")=="ESPERAR"
                    and resultados[s].get("ok")]

        if activas:
            st.markdown(f'<div class="sec-hdr">{_cat_icon(cat)} SEÑALES ACTIVAS — {cat.upper()}</div>',
                        unsafe_allow_html=True)
            for r in sorted(activas, key=lambda x: x.get("score",0), reverse=True):
                _signal_card(r)
        if esperas:
            st.markdown(f'<div class="sec-hdr" style="margin-top:8px">⏳ EN FORMACIÓN — {cat.upper()} ({len(esperas)})</div>',
                        unsafe_allow_html=True)
            for r in sorted(esperas, key=lambda x: x.get("score",0), reverse=True):
                ac = "#69f0ae" if r.get("dir")=="buy" else "#ff8a80"
                bc = "#020d02" if r.get("dir")=="buy" else "#0d0202"
                brd= "#0a2a0a" if r.get("dir")=="buy" else "#2a0a0a"
                dt = "▲ POSIBLE BUY" if r.get("dir")=="buy" else "▼ POSIBLE SELL"
                motivo = r.get("motivo","esperando confirmación")[:50]
                st.markdown(f"""<div style="background:{bc};border:1px solid {brd};
border-left:4px solid {ac};border-radius:10px;margin:6px 0;padding:10px 16px;
display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
    <span style="color:{ac};font-size:.78em;font-weight:900;background:{ac}1a;
      padding:3px 10px;border-radius:14px;border:1px solid {ac}33">{dt}</span>
    <span style="color:#d8d8f8;font-weight:900;font-family:monospace">{r['sym']}</span>
    <span style="color:#555;font-size:.67em">{motivo}</span>
  </div>
  <span style="background:#1a1a2a;color:#9575cd;padding:3px 10px;border-radius:12px;
    font-size:.72em;font-weight:700">{r['score']}/100</span>
</div>""", unsafe_allow_html=True)

        if not activas and not esperas:
            msg = "Conecta MT5 y presiona ▶ INICIAR" if not st.session_state["mt5_ok"] else "Sin señales activas"
            st.markdown(f'<div class="no-sig">📭 {msg} en {cat}</div>', unsafe_allow_html=True)

# ── Tab RADAR ─────────────────────────────────────────────────────────────────
with tabs[len(_cats_activas)]:
    st.markdown('<div class="sec-hdr">📡 RADAR — TODOS LOS SÍMBOLOS ESCANEADOS</div>',
                unsafe_allow_html=True)
    sel_flat_all = [sym for syms in st.session_state.get("sel",{}).values() for sym in syms]
    rows_html = _radar_row(None, sel_flat_all)
    if rows_html:
        st.markdown(
            f'<table class="radar-tbl"><thead><tr>'
            f'<th>Símbolo</th><th>Precio</th><th>Señal</th>'
            f'<th>Score</th><th>RSI</th><th>ADX</th><th>Spread</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True)
    else:
        st.markdown('<div class="no-sig">Sin datos — conecta MT5 y lanza un scan</div>',
                    unsafe_allow_html=True)

# ── Tab HISTORIAL ─────────────────────────────────────────────────────────────
with tabs[len(_cats_activas) + 1]:
    cerradas = [s for s in stats["señales"] if s["estado"] in ("GANADA","PERDIDA","EXPIRADA")]
    total = stats["total"]; wins = stats["wins"]; losses = stats["losses"]; pnl = stats["pnl"]
    if total > 0:
        tasa = wins/total*100
        c1, c2, c3 = st.columns(3)
        c1.metric("Win Rate", f"{tasa:.1f}%", f"{wins}G · {losses}P")
        c2.metric("P&L Total", f"${pnl:+.2f}", f"{total} cerradas")
        c3.metric("Abiertas", len(abiertas))
    if cerradas:
        st.markdown('<div class="sec-hdr">📜 SEÑALES CERRADAS</div>', unsafe_allow_html=True)
        for s in cerradas[:30]:
            if s["estado"]=="GANADA":
                css="h-win"; badge='<span class="b-win">✅ GANADA</span>'
                res=f'<b style="color:#69f0ae">+${s["resultado_usd"]:.2f}</b>'
            elif s["estado"]=="PERDIDA":
                css="h-loss"; badge='<span class="b-loss">❌ PERDIDA</span>'
                res=f'<b style="color:#ff5252">-${abs(s["resultado_usd"]):.2f}</b>'
            else:
                css="h-exp"; badge='<span class="b-exp">⏱ EXPIRADA</span>'
                res='<span style="color:#333">$0.00</span>'
            dc = "#00e676" if s["dir"]=="buy" else "#ff1744"
            t_op = s.get("ts_open","")[11:16] or "—"
            t_cl = (s.get("ts_close") or "")[11:16] or "—"
            st.markdown(f"""<div class="{css}">
<div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px">
  <div style="display:flex;align-items:center;gap:8px">
    {badge}
    <b style="color:{dc};font-size:.85em">{"▲" if s["dir"]=="buy" else "▼"}</b>
    <b style="color:#d8d8f8;font-family:monospace">{s["sym"]}</b>
    <span style="color:#252540;font-size:.7em">{s.get("score",0)}/100</span>
  </div>
  <div style="display:flex;gap:10px;font-size:.75em;flex-wrap:wrap">
    <span style="color:#444">Entrada: <b style="color:#82b1ff">{_fmt(s["entry"],s.get("digits",5))}</b></span>
    <span style="color:#444">SL: <b style="color:#ff5252">{_fmt(s["sl"],s.get("digits",5))}</b></span>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    {res}
    <span style="color:#1e1e38;font-size:.7em">{t_op} → {t_cl}</span>
  </div>
</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown('<div class="no-sig">Sin señales cerradas todavía.</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AUTO-REFRESH
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["scanning"] and st.session_state["mt5_ok"]:
    time.sleep(intervalo)
    st.rerun()
