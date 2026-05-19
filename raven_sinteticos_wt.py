# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  RAVEN AI · SINTÉTICOS WELTRADE  — FX Vol · GainX · PainX · BreakX · etc  ║
# ║  Puerto: 8506  |  streamlit run raven_sinteticos_wt.py --server.port 8506  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
import streamlit as st
import pandas as pd
import numpy as np
import requests, time, threading
from datetime import datetime, timezone

try:
    import MetaTrader5 as mt5
    _MT5 = True
except ImportError:
    _MT5 = False

from ta.trend      import EMAIndicator, MACD, ADXIndicator
from ta.momentum   import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange

st.set_page_config(
    page_title="RAVEN · Sintéticos Weltrade",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
body,.stApp{background:#07070f;color:#d8d8f8}
.block-container{padding:1rem 1.5rem}
.stTabs [data-baseweb="tab-list"]{background:#0c0c18;border-radius:8px;padding:4px;gap:3px}
.stTabs [data-baseweb="tab"]{background:transparent;color:#555;border-radius:6px;
  padding:7px 14px;font-weight:700;font-size:.75em;text-transform:uppercase;letter-spacing:1.2px}
.stTabs [aria-selected="true"]{background:#1a1a30;color:#d8d8f8}
.sec-hdr{background:linear-gradient(90deg,#12122a,#0c0c18);border-left:3px solid #3d3d7a;
  padding:6px 14px;margin:10px 0 8px;font-size:.7em;text-transform:uppercase;
  letter-spacing:2.5px;color:#555;font-weight:700;border-radius:0 6px 6px 0}
.sig-prem{background:linear-gradient(135deg,#030318,#06062a);border:1px solid #3d3d7a;
  border-left:4px solid #ffd600;border-radius:12px;padding:0;margin:10px 0;overflow:hidden;
  box-shadow:0 4px 24px rgba(100,80,255,.14)}
.sig-alta{background:linear-gradient(135deg,#030318,#06062a);border:1px solid #1e2a1e;
  border-left:4px solid #00e676;border-radius:12px;padding:0;margin:10px 0;overflow:hidden}
.sig-obs{background:#09090f;border:1px solid #1a1a30;border-left:3px solid #ff9800;
  border-radius:10px;padding:0;margin:8px 0;overflow:hidden}
.sig-wait{background:#0a0a12;border:1px solid #14142a;border-radius:10px;margin:6px 0;
  padding:10px 16px;overflow:hidden}
.no-sig{background:#09090f;border:1px solid #1a1a30;border-radius:10px;
  padding:16px 20px;text-align:center;color:#252540;margin:8px 0}
.alert-new{background:linear-gradient(90deg,#0d1a0d,#050a05);border:1px solid #1a4d1a;
  border-left:4px solid #00e676;border-radius:8px;padding:10px 16px;margin:5px 0;
  font-size:.84em;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{border-left-color:#00e676}50%{border-left-color:#69f0ae}}
.radar-tbl{width:100%;border-collapse:collapse;font-size:.77em}
.radar-tbl th{background:#0c0c18;color:#383858;padding:6px 10px;font-weight:700;
  text-transform:uppercase;letter-spacing:1.2px;font-size:.67em;border-bottom:1px solid #1a1a30}
.radar-tbl td{border-bottom:1px solid #0e0e1e;vertical-align:middle}
.stButton>button{background:linear-gradient(135deg,#3d1278,#6a0dad);color:#fff;border:none;
  border-radius:8px;font-weight:700;padding:8px 18px;font-size:.84em}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CATÁLOGO DE INSTRUMENTOS WELTRADE
# ══════════════════════════════════════════════════════════════════════════════
GRUPOS = {
    "FX Volatility": {
        "color": "#42a5f5",
        "icon":  "📈",
        "desc":  "Índices de volatilidad FX — 24/7",
        "syms":  ["FX Vol 20","FX Vol 40","FX Vol 60","FX Vol 80","FX Vol 99",
                  "SFX Vol 20","SFX Vol 40","SFX Vol 60","SFX Vol 80","SFX Vol 99"],
    },
    "GainX": {
        "color": "#00e676",
        "icon":  "📈",
        "desc":  "Índices alcistas directionales",
        "syms":  ["GainX 400","GainX 600","GainX 800","GainX 999","GainX 1200"],
    },
    "PainX": {
        "color": "#ff5252",
        "icon":  "📉",
        "desc":  "Índices bajistas directionales",
        "syms":  ["PainX 400","PainX 600","PainX 800","PainX 999","PainX 1200"],
    },
    "BreakX": {
        "color": "#ff9800",
        "icon":  "💥",
        "desc":  "Índices de ruptura",
        "syms":  ["BreakX 600","BreakX 1200","BreakX 1800"],
    },
    "TrendX": {
        "color": "#ab47bc",
        "icon":  "🔺",
        "desc":  "Índices de tendencia fuerte",
        "syms":  ["TrendX 600","TrendX 1200","TrendX 1800"],
    },
    "SwitchX": {
        "color": "#ffd600",
        "icon":  "🔄",
        "desc":  "Índices de cambio de dirección",
        "syms":  ["SwitchX 600","SwitchX 1200","SwitchX 1800"],
    },
    "FlipX / Especiales": {
        "color": "#26c6da",
        "icon":  "⚡",
        "desc":  "FlipX, FiboX, QuadX, PlusX",
        "syms":  ["FlipX 1","FlipX 2","FlipX 3","FlipX 4","FlipX 5",
                  "PlusX 1","FiboX","QuadX"],
    },
}

ALL_SYMS = [s for g in GRUPOS.values() for s in g["syms"]]

def grupo_de(sym):
    for g, info in GRUPOS.items():
        if sym in info["syms"]: return g, info["color"]
    return "Otros", "#555"

# ══════════════════════════════════════════════════════════════════════════════
# MT5 UTILS
# ══════════════════════════════════════════════════════════════════════════════
TF = {}
if _MT5:
    TF = {"M1":mt5.TIMEFRAME_M1,"M5":mt5.TIMEFRAME_M5,
          "M15":mt5.TIMEFRAME_M15,"H1":mt5.TIMEFRAME_H1}

def mt5_conectar():
    if not _MT5: return False, "MetaTrader5 no instalado", {}
    if not mt5.initialize(): return False, f"Error MT5: {mt5.last_error()}", {}
    acc = mt5.account_info()
    if acc is None: return False, "Sin cuenta activa", {}
    # Verificar que sea Weltrade
    if "weltrade" not in acc.company.lower():
        return False, f"Cuenta no es Weltrade: {acc.company}", {}
    info = {"nombre":acc.name,"broker":acc.company,"servidor":acc.server,
            "balance":acc.balance,"equity":acc.equity,"libre":acc.margin_free,
            "leverage":acc.leverage,"moneda":acc.currency,"login":acc.login}
    return True, f"{acc.name} · {acc.company}", info

def mt5_datos(sym, tf="M15", count=300):
    if not _MT5 or tf not in TF: return None
    try:
        r = mt5.copy_rates_from_pos(sym, TF[tf], 0, count)
        if r is None or len(r) < 30: return None
        df = pd.DataFrame(r)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time")
        df = df.rename(columns={"tick_volume":"volume"})
        return df[["open","high","low","close","volume"]]
    except Exception:
        return None

def mt5_tick(sym):
    if not _MT5: return None, None
    try:
        t = mt5.symbol_info_tick(sym)
        si = mt5.symbol_info(sym)
        if t is None or si is None: return None, None
        price  = (t.bid + t.ask) / 2
        spread = si.spread * si.trade_tick_size
        return price, spread
    except Exception:
        return None, None

# ══════════════════════════════════════════════════════════════════════════════
# INDICADORES
# ══════════════════════════════════════════════════════════════════════════════
def indicadores(df):
    if df is None or len(df) < 35: return None
    c = df["close"]
    try:
        rsi    = RSIIndicator(c, 14).rsi().iloc[-1]
        macd_o = MACD(c)
        macd_h = macd_o.macd_diff().iloc[-1]
        macd_p = macd_o.macd_diff().iloc[-2] if len(c) > 2 else 0
        bb     = BollingerBands(c, 20, 2)
        bb_hi  = bb.bollinger_hband().iloc[-1]
        bb_lo  = bb.bollinger_lband().iloc[-1]
        bb_mid = bb.bollinger_mavg().iloc[-1]
        ema9   = EMAIndicator(c,  9).ema_indicator().iloc[-1]
        ema20  = EMAIndicator(c, 20).ema_indicator().iloc[-1]
        ema50  = EMAIndicator(c, 50).ema_indicator().iloc[-1]
        ema200 = EMAIndicator(c,200).ema_indicator().iloc[-1] if len(c)>=200 else ema50
        atr    = AverageTrueRange(df["high"],df["low"],c,14).average_true_range().iloc[-1]
        stoch  = StochasticOscillator(df["high"],df["low"],c,14,3).stoch().iloc[-1]
        adx_o  = ADXIndicator(df["high"],df["low"],c,14)
        adx    = adx_o.adx().iloc[-1]
        dip    = adx_o.adx_neg().iloc[-1]
        dim    = adx_o.adx_pos().iloc[-1]
        price  = c.iloc[-1]
        slope  = (ema20 - EMAIndicator(c,20).ema_indicator().iloc[-4])/ema20*100 if len(c)>4 else 0
        mecha_i= min(df["open"].iloc[-1],df["close"].iloc[-1]) - df["low"].iloc[-1]
        mecha_s= df["high"].iloc[-1] - max(df["open"].iloc[-1],df["close"].iloc[-1])
        range_c= df["high"].iloc[-1] - df["low"].iloc[-1]
        alc    = df["close"].iloc[-1] > df["open"].iloc[-1]
        vela_x = range_c > atr * 2.5
        lateral= adx < 12
        return {"price":price,"rsi":rsi,"macd_h":macd_h,"macd_p":macd_p,
                "bb_hi":bb_hi,"bb_lo":bb_lo,"bb_mid":bb_mid,
                "ema9":ema9,"ema20":ema20,"ema50":ema50,"ema200":ema200,
                "atr":atr,"stoch":stoch,"adx":adx,"dip":dip,"dim":dim,
                "slope":slope,"vela_x":vela_x,"lateral":lateral,
                "alc":alc,"mecha_i":mecha_i,"mecha_s":mecha_s}
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════════════════
# SCORING
# ══════════════════════════════════════════════════════════════════════════════
def calcular_score(ind_h1, ind_m15, ind_m5, grupo):
    if ind_m15 is None: return 0, "neutral", {}
    p   = ind_m15["price"]
    rsi = ind_m15["rsi"]
    adx = ind_m15["adx"]
    bd  = {}

    # Determinar dirección
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

    # Ajuste por tipo de instrumento
    if grupo == "GainX":
        buy_pts += 3   # sesgo alcista estructural
    elif grupo == "PainX":
        sell_pts += 3  # sesgo bajista estructural
    elif grupo == "TrendX":
        # el que lleva la tendencia gana más puntos
        if p > ind_m15["ema50"]: buy_pts += 2
        else: sell_pts += 2

    dir_   = "buy" if buy_pts >= sell_pts else "sell"
    es_buy = dir_ == "buy"
    score  = 0

    # A) Tendencia MTF — 25 pts
    a = 10
    if ind_h1:
        h1_alc  = ind_h1["ema20"]  > ind_h1["ema50"]
        m15_alc = ind_m15["ema20"] > ind_m15["ema50"]
        if h1_alc == m15_alc: a += 5
        if (h1_alc and es_buy) or (not h1_alc and not es_buy): a += 3
        if (p > ind_h1["ema200"] and es_buy) or (p < ind_h1["ema200"] and not es_buy): a += 4
        if (ind_h1["slope"] > 0.002) == es_buy: a += 3
    else:
        a += 5
        if (ind_m15["ema20"] > ind_m15["ema50"]) == es_buy: a += 5
    if ind_m5 and (ind_m5["ema20"] > ind_m5["ema50"]) == es_buy: a += 3
    a = min(25, a); bd["Tendencia MTF"] = a; score += a

    # B) Setup técnico — 25 pts
    b = 8
    atr = ind_m15["atr"]
    if es_buy:
        if 35 <= rsi <= 55: b += 6
        elif 55 < rsi <= 65: b += 3
        if p <= ind_m15["bb_lo"] + atr*0.3: b += 6
        elif p > ind_m15["bb_mid"] and p < ind_m15["bb_hi"]: b += 4
        if abs(p - ind_m15["ema20"]) < atr*0.8: b += 4
        if ind_m15["alc"]: b += 3
    else:
        if 45 <= rsi <= 65: b += 6
        elif 35 <= rsi < 45: b += 3
        if p >= ind_m15["bb_hi"] - atr*0.3: b += 6
        elif p < ind_m15["bb_mid"] and p > ind_m15["bb_lo"]: b += 4
        if abs(p - ind_m15["ema20"]) < atr*0.8: b += 4
        if not ind_m15["alc"]: b += 3
    if not ind_m15["vela_x"]: b += 4
    if ind_m5 and (ind_m5["ema20"] > ind_m5["ema50"]) != es_buy: b -= 5
    b = max(0, min(25, b)); bd["Setup técnico"] = b; score += b

    # C) Momentum — 20 pts
    c = 5
    macd_al = (ind_m15["macd_h"] > 0) == es_buy
    if macd_al and abs(ind_m15["macd_h"]) > abs(ind_m15["macd_p"]): c += 5
    elif macd_al: c += 3
    stoch = ind_m15["stoch"]
    if es_buy and stoch < 40: c += 4
    elif not es_buy and stoch > 60: c += 4
    elif 30 < stoch < 70: c += 2
    if adx >= 20: c += 6
    elif adx >= 14: c += 4
    elif adx >= 9: c += 3
    elif adx >= 6: c += 1
    c = min(20, c); bd["Momentum"] = c; score += c

    # D) R:R — 15 pts
    d = 8
    sl_d = atr * 1.2
    rr2  = (atr*2.0)/sl_d if sl_d > 0 else 0
    if rr2 >= 1.6: d += 4
    elif rr2 >= 1.2: d += 2
    if abs(p - ind_m15["ema20"]) < atr*0.6: d += 3
    d = min(15, d); bd["R:R"] = d; score += d

    # E) Limpieza — 15 pts
    e = 6
    if not ind_m15["lateral"]: e += 4
    if not ind_m15["vela_x"]: e += 3
    if ind_m5 and not ind_m5["vela_x"]: e += 2
    e = min(15, e); bd["Limpieza"] = e; score += e

    return min(100, score), dir_, bd

def clasificar(score):
    if score >= 90: return "PREMIUM",   "#ffd600"
    if score >= 80: return "ALTA PROB.","#00e676"
    if score >= 70: return "OBSERVAR",  "#42a5f5"
    return "DÉBIL", "#555"

def decision_final(score, ind_m15):
    if ind_m15 and ind_m15["adx"] < 6:   return "BLOQUEADA", "ADX muy bajo"
    if ind_m15 and ind_m15["vela_x"]:    return "ESPERAR",   "vela extendida"
    if ind_m15 and ind_m15["lateral"]:   return "ESPERAR",   "mercado lateral"
    if score >= 62: return "RECOMENDAR", ""
    if score >= 48: return "ESPERAR",    "esperando confirmación"
    if score >= 35: return "OBSERVAR",   "setup débil"
    return "NO_OPERAR", "score insuficiente"

# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS COMPLETO DE UN SÍNTÉTICO
# ══════════════════════════════════════════════════════════════════════════════
def analizar(sym, riesgo_usd=100):
    grupo, color = grupo_de(sym)
    price, spread = mt5_tick(sym)
    if price is None:
        return {"ok":False,"sym":sym,"grupo":grupo,"error":"sin tick MT5"}

    df_h1  = mt5_datos(sym,"H1",  300)
    df_m15 = mt5_datos(sym,"M15", 300)
    df_m5  = mt5_datos(sym,"M5",  200)

    ind_h1  = indicadores(df_h1)
    ind_m15 = indicadores(df_m15)
    ind_m5  = indicadores(df_m5)

    if ind_m15 is None:
        return {"ok":False,"sym":sym,"grupo":grupo,"error":"datos insuficientes M15"}

    score, dir_, bd = calcular_score(ind_h1, ind_m15, ind_m5, grupo)
    dec, motivo     = decision_final(score, ind_m15)
    clase, _        = clasificar(score)

    atr   = ind_m15["atr"]
    sl_d  = atr * 1.2
    entry = price

    # Valor en dólares: tick_val=0.01/tick, tick_size=0.01 → $1 por 1.0 de movimiento por lote
    # Para riesgo_usd: lots = riesgo_usd / sl_d (aproximado, 1 lote = $1 por punto)
    lots  = riesgo_usd / sl_d if sl_d > 0 else 0

    if dir_ == "buy":
        sl  = price - sl_d
        tp1 = price + atr*0.8;  tp2 = price + atr*2.0
        tp3 = price + atr*3.5;  tp4 = price + atr*5.5
    else:
        sl  = price + sl_d
        tp1 = price - atr*0.8;  tp2 = price - atr*2.0
        tp3 = price - atr*3.5;  tp4 = price - atr*5.5

    def rr(tp): return abs(tp-entry)/sl_d if sl_d > 0 else 0
    def gn(tp): return abs(tp-entry)*lots

    tend_h1 = ("▲ alcista" if (ind_h1["ema20"]>ind_h1["ema50"]) else "▼ bajista") if ind_h1 else "—"
    conf_m5 = ("✓ confirma" if ind_m5 and (ind_m5["ema20"]>ind_m5["ema50"])==(dir_=="buy") else "⚠ débil") if ind_m5 else "—"

    return {
        "ok":True,"sym":sym,"grupo":grupo,"color":color,
        "price":price,"spread":spread,
        "dir":dir_,"score":score,"clase":clase,
        "decision":dec,"motivo":motivo,"bd":bd,
        "entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,"tp4":tp4,
        "sl_d":sl_d,"lots":lots,"riesgo_usd":riesgo_usd,
        "rr1":rr(tp1),"rr2":rr(tp2),"rr3":rr(tp3),"rr4":rr(tp4),
        "g1":gn(tp1),"g2":gn(tp2),"g3":gn(tp3),"g4":gn(tp4),
        "ind":ind_m15,"tend_h1":tend_h1,"conf_m5":conf_m5,
        "ts_open":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }

# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM
# ══════════════════════════════════════════════════════════════════════════════
def enviar_tg(r, token, chat_id):
    if not token or not chat_id: return False
    arrow = "🟢 ▲ BUY" if r["dir"]=="buy" else "🔴 ▼ SELL"
    grupo_emoji = GRUPOS.get(r["grupo"],{}).get("icon","⚡")
    msg = (
        f"⚡ *RAVEN · SINTÉTICOS WELTRADE*\n"
        f"{grupo_emoji} *{r['sym']}* · {arrow}\n"
        f"Grupo: {r['grupo']} · Score: *{r['score']}/100*\n\n"
        f"📍 Entrada: `{r['entry']:,.2f}`\n"
        f"🛑 SL: `{r['sl']:,.2f}` (−${r['riesgo_usd']:.0f})\n"
        f"🎯 TP1: `{r['tp1']:,.2f}` +${r['g1']:.2f} (1:{r['rr1']:.1f})\n"
        f"🎯 TP2: `{r['tp2']:,.2f}` +${r['g2']:.2f} (1:{r['rr2']:.1f})\n"
        f"💎 TP4: `{r['tp4']:,.2f}` +${r['g4']:.2f}\n\n"
        f"H1: {r['tend_h1']} · M5: {r['conf_m5']}\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%H:%M')} UTC"
    )
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id":chat_id,"text":msg,"parse_mode":"Markdown"},timeout=8)
        return resp.ok
    except Exception:
        return False

# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def fmt(v):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "—"
    return f"{v:,.2f}"

def _texto_senal(r):
    dir_txt = "▲ BUY  /  COMPRA" if r["dir"]=="buy" else "▼ SELL  /  VENTA"
    icon    = GRUPOS.get(r["grupo"],{}).get("icon","⚡")
    ts      = datetime.now(timezone.utc).strftime("%d/%m/%Y  %H:%M UTC")
    return (
        f"⚡ RAVEN AI · SINTÉTICOS WELTRADE\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{dir_txt}\n"
        f"{icon}  {r['sym']}  |  {r['grupo']}\n"
        f"Score: {r['score']}/100  ({r['clase']})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Entrada:  {fmt(r['entry'])}\n"
        f"🛑 Stop:     {fmt(r['sl'])}   (−${r['riesgo_usd']:.0f})\n"
        f"🎯 TP1:      {fmt(r['tp1'])}   +${r['g1']:.2f}  (1:{r['rr1']:.1f})\n"
        f"🎯 TP2:      {fmt(r['tp2'])}   +${r['g2']:.2f}  (1:{r['rr2']:.1f})\n"
        f"🎯 TP3:      {fmt(r['tp3'])}   +${r['g3']:.2f}  (1:{r['rr3']:.1f})\n"
        f"💎 TP4:      {fmt(r['tp4'])}   +${r['g4']:.2f}  (1:{r['rr4']:.1f})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"H1: {r.get('tend_h1','—')}  |  M5: {r.get('conf_m5','—')}\n"
        f"⏰  {ts}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

def _signal_card(r):
    sc     = r["score"]
    is_buy = r["dir"] == "buy"
    ac     = "#00e676" if is_buy else "#ff1744"
    css    = "sig-prem" if sc>=90 else "sig-alta" if sc>=80 else "sig-obs"
    dt     = "▲ COMPRAR" if is_buy else "▼ VENDER"
    sc_bg  = "#ffd600" if sc>=90 else "#00e676" if sc>=80 else "#ff9800"
    grupo_color = r.get("color","#555")
    grupo_icon  = GRUPOS.get(r["grupo"],{}).get("icon","⚡")
    dec_lbl = "✅ ACTIVA" if r["decision"]=="RECOMENDAR" else "⏳ EN FORMACIÓN"
    dec_bg  = "#002200" if r["decision"]=="RECOMENDAR" else "#1a1000"
    dec_fc  = "#00e676" if r["decision"]=="RECOMENDAR" else "#ffd600"
    tend    = r.get("tend_h1","—")
    conf    = r.get("conf_m5","—")
    ind     = r.get("ind",{}) or {}
    rsi_c   = "#ff5252" if ind.get("rsi",50)>70 else "#ff9800" if ind.get("rsi",50)>65 else "#00e676" if ind.get("rsi",50)<35 else "#555"
    adx_c   = "#00e676" if ind.get("adx",0)>=20 else "#ffd600" if ind.get("adx",0)>=14 else "#383858"

    st.markdown(f"""<div class="{css}">
<div style="background:linear-gradient(135deg,{ac}18,{ac}06,transparent);
  border-bottom:1px solid {ac}20;padding:12px 20px;
  display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <span style="background:{ac};color:{'#000' if is_buy else '#fff'};font-size:.8em;
      font-weight:900;padding:5px 14px;border-radius:20px">{dt}</span>
    <div>
      <div style="color:#d8d8f8;font-size:1.1em;font-weight:900;font-family:'Courier New',mono">{r['sym']}</div>
      <div style="color:{grupo_color};font-size:.62em;font-weight:700">{grupo_icon} {r['grupo']}</div>
    </div>
    <span style="background:{dec_bg};color:{dec_fc};font-size:.65em;font-weight:700;
      padding:2px 8px;border-radius:10px;border:1px solid {dec_fc}33">{dec_lbl}</span>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <span style="background:{sc_bg};color:#000;font-size:.78em;font-weight:900;
      padding:4px 12px;border-radius:20px">⭐ {sc}/100</span>
    <div style="text-align:right">
      <div style="color:#383858;font-size:.55em;text-transform:uppercase;letter-spacing:1.5px">precio live</div>
      <div style="color:#fff;font-size:1.15em;font-weight:900;font-family:'Courier New',mono">{fmt(r['price'])}</div>
      <div style="color:#555;font-size:.62em">Spread: {fmt(r['spread'])}</div>
    </div>
  </div>
</div>
<div style="padding:12px 20px">
  <div style="display:flex;gap:8px;margin-bottom:8px">
    <div style="flex:1;padding:8px 12px;background:#070713;border:1px solid #14143a;border-radius:7px;
      display:flex;align-items:center;justify-content:space-between">
      <span style="color:#42a5f5;font-size:.62em;font-weight:700;text-transform:uppercase;letter-spacing:2px">🎯 ENTRADA</span>
      <span style="color:#82b1ff;font-size:1.05em;font-weight:800;font-family:'Courier New',mono">{fmt(r['entry'])}</span>
    </div>
    <div style="flex:1;padding:8px 12px;background:#0a0404;border:1px solid #280a0a;border-radius:7px;
      display:flex;align-items:center;justify-content:space-between">
      <span style="color:#ff5252;font-size:.62em;font-weight:700;text-transform:uppercase;letter-spacing:2px">🛑 STOP</span>
      <span style="color:#ff5252;font-size:1.05em;font-weight:800;font-family:'Courier New',mono">{fmt(r['sl'])}</span>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
    <div style="background:#020d02;border:1px solid #0a280a;border-radius:7px;padding:8px 12px">
      <div style="color:#1b5e20;font-size:.58em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">TP 1</div>
      <div style="color:#69f0ae;font-size:.9em;font-weight:800;font-family:'Courier New',mono;margin:2px 0">{fmt(r['tp1'])}</div>
      <div style="color:#2e7d32;font-size:.64em">1:{r['rr1']:.1f} · <span style="color:#43a047">+${r['g1']:.2f}</span></div>
    </div>
    <div style="background:#020d02;border:1px solid #0a280a;border-radius:7px;padding:8px 12px">
      <div style="color:#2e7d32;font-size:.58em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">TP 2</div>
      <div style="color:#69f0ae;font-size:.9em;font-weight:800;font-family:'Courier New',mono;margin:2px 0">{fmt(r['tp2'])}</div>
      <div style="color:#2e7d32;font-size:.64em">1:{r['rr2']:.1f} · <span style="color:#43a047">+${r['g2']:.2f}</span></div>
    </div>
    <div style="background:#030f03;border:1px solid #0c2e0c;border-radius:7px;padding:8px 12px">
      <div style="color:#388e3c;font-size:.58em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">TP 3</div>
      <div style="color:#69f0ae;font-size:.9em;font-weight:800;font-family:'Courier New',mono;margin:2px 0">{fmt(r['tp3'])}</div>
      <div style="color:#2e7d32;font-size:.64em">1:{r['rr3']:.1f} · <span style="color:#43a047">+${r['g3']:.2f}</span></div>
    </div>
    <div style="background:#0a0800;border:2px solid #2a2000;border-radius:7px;padding:8px 12px">
      <div style="color:#ffd600;font-size:.58em;font-weight:900;text-transform:uppercase;letter-spacing:1.5px">💎 TP 4</div>
      <div style="color:#ffd600;font-size:.9em;font-weight:900;font-family:'Courier New',mono;margin:2px 0">{fmt(r['tp4'])}</div>
      <div style="color:#a37900;font-size:.64em">1:{r['rr4']:.1f} · <span style="color:#ffd600">+${r['g4']:.2f}</span></div>
    </div>
  </div>
</div>
<div style="background:#0a0814;border-top:1px solid #1a1a30;padding:7px 20px;
  display:flex;gap:20px;font-size:.68em;flex-wrap:wrap">
  <span style="color:#383858">H1: <b style="color:#ffd600">{tend}</b></span>
  <span style="color:#383858">M5: <b style="color:#82b1ff">{conf}</b></span>
  <span style="color:#383858">RSI: <b style="color:{rsi_c}">{ind.get('rsi',0):.0f}</b></span>
  <span style="color:#383858">ADX: <b style="color:{adx_c}">{ind.get('adx',0):.0f}</b></span>
  <span style="color:#383858">ATR: <b style="color:#555">{fmt(ind.get('atr'))}</b></span>
</div>
</div>""", unsafe_allow_html=True)
    # Botón copiar señal
    _key = f"cp_{r['sym'].replace(' ','_')}_{r['score']}"
    if st.button("📋 Copiar señal como texto", key=_key, use_container_width=False):
        st.session_state[f"show_{_key}"] = not st.session_state.get(f"show_{_key}", False)
    if st.session_state.get(f"show_{_key}", False):
        st.code(_texto_senal(r), language=None)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
def _init():
    defs = {
        "mt5_ok":False,"mt5_info":"","mt5_acc":{},
        "scanning":False,"resultados":{},"nuevas":[],
        "stats":{"señales":[],"wins":0,"losses":0,"total":0,"pnl":0.0},
        "scan_count":0,"last_scan":"—","syms_sel":list(ALL_SYMS),
    }
    for k,v in defs.items():
        if k not in st.session_state: st.session_state[k]=v
_init()

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div style="color:#ffd600;font-size:1em;font-weight:900;'
                'letter-spacing:2px;margin-bottom:8px">⚡ RAVEN · SINTÉTICOS WELTRADE</div>',
                unsafe_allow_html=True)

    # Conexión MT5
    if st.button("🔌 Conectar MT5", use_container_width=True):
        ok, info, acc_data = mt5_conectar()
        st.session_state.update({"mt5_ok":ok,"mt5_info":info,"mt5_acc":acc_data})
        if not ok: st.error(info)

    c = "#00e676" if st.session_state["mt5_ok"] else "#ff5252"
    t = "✅ CONECTADO" if st.session_state["mt5_ok"] else "❌ DESCONECTADO"
    st.markdown(f'<div style="font-size:.7em;color:{c};margin-bottom:6px">{t} · {st.session_state["mt5_info"]}</div>',
                unsafe_allow_html=True)

    acc = st.session_state.get("mt5_acc",{})
    if acc:
        eq_c = "#00e676" if acc.get("equity",0) >= acc.get("balance",0) else "#ff9800"
        st.markdown(f"""<div style="background:#0c0c18;border:1px solid #1a1a30;
border-radius:8px;padding:10px 14px;margin:4px 0">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:.7em">
  <div><span style="color:#383858">Balance</span><br><b style="color:#d8d8f8">${acc.get('balance',0):,.2f}</b></div>
  <div><span style="color:#383858">Equity</span><br><b style="color:{eq_c}">${acc.get('equity',0):,.2f}</b></div>
  <div><span style="color:#383858">Libre</span><br><b style="color:#42a5f5">${acc.get('libre',0):,.2f}</b></div>
  <div><span style="color:#383858">1:{acc.get('leverage',0)}</span><br><b style="color:#555">{acc.get('moneda','USD')}</b></div>
</div></div>""", unsafe_allow_html=True)

    st.divider()

    # Selección de grupos
    st.markdown("**Grupos activos**")
    syms_sel = []
    for grupo, info in GRUPOS.items():
        icon = info["icon"]; color = info["color"]
        activo = st.checkbox(f"{icon} {grupo} ({len(info['syms'])})", value=True, key=f"grp_{grupo}")
        if activo:
            with st.expander(f"Seleccionar de {grupo}"):
                elegidos = st.multiselect("",info["syms"], default=info["syms"], key=f"ms_{grupo}")
                syms_sel.extend(elegidos)
        else:
            syms_sel.extend([])
    st.session_state["syms_sel"] = syms_sel

    st.divider()

    # Parámetros
    st.markdown("**⚙️ Parámetros**")
    riesgo_usd = st.number_input("Riesgo por trade ($):", value=100, step=10, key="riesgo")
    min_score  = st.slider("Score mínimo:", 50, 90, 62, 1, key="min_sc")
    intervalo  = st.slider("Intervalo scan (seg):", 30, 300, 60, 10, key="intv")

    st.divider()

    # Telegram
    st.markdown("**📱 Telegram**")
    tg_token = st.text_input("Bot Token:", value="", type="password", key="tg_tok")
    tg_chat  = st.text_input("Chat ID:", value="", key="tg_chat")

    st.divider()

    # Control
    col_a, col_b = st.columns(2)
    lbl = "▶ INICIAR" if not st.session_state["scanning"] else "⏹ DETENER"
    if col_a.button(lbl, use_container_width=True):
        st.session_state["scanning"] = not st.session_state["scanning"]
        st.session_state["nuevas"]   = []
    if col_b.button("🔄 Scan", use_container_width=True):
        st.session_state["force_scan"] = True

    if st.session_state["scan_count"] > 0:
        st.markdown(f'<div style="color:#252540;font-size:.6em;margin-top:6px">'
                    f'Último: {st.session_state["last_scan"]} · #{st.session_state["scan_count"]}</div>',
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
syms_activos = len(st.session_state.get("syms_sel",[]))
st.markdown(f"""<div style="background:linear-gradient(135deg,#0d0d1f,#12122a);
border:1px solid #1a1a3a;border-radius:12px;padding:14px 20px;margin-bottom:16px;
display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
<div>
  <div style="color:#252562;font-size:.6em;text-transform:uppercase;letter-spacing:3px">RAVEN AI</div>
  <div style="color:#d8d8f8;font-size:1.3em;font-weight:900">⚡ SINTÉTICOS WELTRADE
  &nbsp;<span style="font-size:.5em;color:#555">100% MetaTrader 5 · 24/7</span></div>
</div>
<div style="display:flex;gap:16px;font-size:.72em;flex-wrap:wrap">
  <span style="color:#252540">Instrumentos: <b style="color:#ffd600">{syms_activos}/{len(ALL_SYMS)}</b></span>
  <span style="color:#252540">Timeframes: <b style="color:#42a5f5">M5 · M15 · H1</b></span>
</div>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SCAN
# ══════════════════════════════════════════════════════════════════════════════
_scanning = st.session_state["scanning"]
_force    = st.session_state.pop("force_scan", False)
_first    = st.session_state["scan_count"] == 0

if (_scanning or _force or _first) and st.session_state["mt5_ok"]:
    syms_sel = st.session_state.get("syms_sel", ALL_SYMS)
    if not syms_sel: syms_sel = ALL_SYMS

    nuevos = {}
    lock = threading.Lock()

    def _scan(sym):
        try:
            res = analizar(sym, riesgo_usd)
            with lock: nuevos[sym] = res
        except Exception as e:
            with lock: nuevos[sym] = {"ok":False,"sym":sym,"grupo":grupo_de(sym)[0],"error":str(e)}

    threads = [threading.Thread(target=_scan,args=(s,),daemon=True) for s in syms_sel]
    for t in threads: t.start()
    for t in threads: t.join(timeout=25)

    # Detectar señales nuevas
    stats = st.session_state["stats"]
    prev  = {s["sym"] for s in stats["señales"] if s["estado"]=="ABIERTA"}
    st.session_state["nuevas"] = []

    for sym, r in nuevos.items():
        if (r.get("decision")=="RECOMENDAR" and r.get("dir")
                and r.get("score",0) >= min_score and sym not in prev):
            s_new = {**r,"estado":"ABIERTA","resultado_usd":0.0,"ts_close":None}
            stats["señales"].insert(0, s_new)
            st.session_state["nuevas"].append(s_new)
            enviar_tg(r, tg_token, tg_chat)

    st.session_state["resultados"]  = nuevos
    st.session_state["last_scan"]   = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    st.session_state["scan_count"] += 1

elif (_scanning or _force) and not st.session_state["mt5_ok"]:
    st.warning("⚠️ Conecta MT5 primero — asegúrate que Weltrade MT5 esté abierto.")

# ══════════════════════════════════════════════════════════════════════════════
# ALERTAS
# ══════════════════════════════════════════════════════════════════════════════
for s in st.session_state.get("nuevas",[]):
    dc = "#00e676" if s["dir"]=="buy" else "#ff1744"
    dt = "▲ COMPRA" if s["dir"]=="buy" else "▼ VENTA"
    st.markdown(
        f'<div class="alert-new">🚨 <b style="color:{dc}">{s["sym"]} · {dt}</b>'
        f'&emsp;Score <b style="color:#00e676">{s["score"]}/100</b>'
        f'&emsp;Entrada: <b style="color:#82b1ff">{fmt(s["entry"])}</b>'
        f'&emsp;{GRUPOS.get(s["grupo"],{}).get("icon","⚡")} {s["grupo"]}</div>',
        unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
resultados = st.session_state.get("resultados", {})
stats      = st.session_state["stats"]
abiertas   = [s for s in stats["señales"] if s["estado"]=="ABIERTA"]

def _n_rec_grupo(grupo):
    return sum(1 for r in resultados.values()
               if r.get("decision")=="RECOMENDAR" and r.get("grupo")==grupo
               and r.get("score",0) >= min_score)

grupos_activos = [g for g,i in GRUPOS.items()
                  if any(s in st.session_state.get("syms_sel",[]) for s in i["syms"])]

tab_labels = []
for g in grupos_activos:
    n = _n_rec_grupo(g)
    icon = GRUPOS[g]["icon"]
    tab_labels.append(f"{icon} {g}" + (f" ({n})" if n > 0 else ""))
tab_labels += ["📡 RADAR", "📜 HISTORIAL"]

tabs = st.tabs(tab_labels)

# Tabs por grupo
for i, grupo in enumerate(grupos_activos):
    with tabs[i]:
        info_g = GRUPOS[grupo]
        syms_g = [s for s in info_g["syms"] if s in st.session_state.get("syms_sel",[])]
        color_g = info_g["color"]

        activas = [resultados[s] for s in syms_g
                   if s in resultados and resultados[s].get("decision")=="RECOMENDAR"
                   and resultados[s].get("score",0) >= min_score]
        esperas = [resultados[s] for s in syms_g
                   if s in resultados and resultados[s].get("decision")=="ESPERAR"
                   and resultados[s].get("ok")]

        if activas:
            st.markdown(f'<div class="sec-hdr">{info_g["icon"]} SEÑALES ACTIVAS — {grupo.upper()}</div>',
                        unsafe_allow_html=True)
            for r in sorted(activas, key=lambda x: x.get("score",0), reverse=True):
                _signal_card(r)

        if esperas:
            st.markdown(f'<div class="sec-hdr" style="margin-top:6px">⏳ EN FORMACIÓN — {grupo.upper()} ({len(esperas)})</div>',
                        unsafe_allow_html=True)
            for r in sorted(esperas, key=lambda x: x.get("score",0), reverse=True):
                ac  = "#69f0ae" if r.get("dir")=="buy" else "#ff8a80"
                bc  = "#020d02" if r.get("dir")=="buy" else "#0d0202"
                brd = "#0a2a0a" if r.get("dir")=="buy" else "#2a0a0a"
                dt  = "▲ POSIBLE BUY" if r.get("dir")=="buy" else "▼ POSIBLE SELL"
                st.markdown(f"""<div class="sig-wait" style="background:{bc};border:1px solid {brd};
border-left:4px solid {ac}">
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
    <div style="display:flex;align-items:center;gap:8px">
      <span style="color:{ac};font-size:.76em;font-weight:900;background:{ac}1a;
        padding:3px 10px;border-radius:14px;border:1px solid {ac}33">{dt}</span>
      <span style="color:#d8d8f8;font-weight:900;font-family:monospace">{r['sym']}</span>
      <span style="color:#555;font-size:.65em">{r.get('motivo','')[:45]}</span>
    </div>
    <span style="background:#1a1a2a;color:#9575cd;padding:3px 10px;
      border-radius:12px;font-size:.72em;font-weight:700">{r['score']}/100</span>
  </div>
</div>""", unsafe_allow_html=True)

        if not activas and not esperas:
            connected = st.session_state["mt5_ok"]
            msg = "Conecta MT5 y presiona ▶ INICIAR" if not connected else "Sin señales activas ahora"
            st.markdown(f'<div class="no-sig">📭 {msg}</div>', unsafe_allow_html=True)

# Tab RADAR
with tabs[len(grupos_activos)]:
    st.markdown('<div class="sec-hdr">📡 RADAR — TODOS LOS SINTÉTICOS</div>', unsafe_allow_html=True)
    syms_all = st.session_state.get("syms_sel", ALL_SYMS)
    rows_html = ""
    for sym in syms_all:
        r = resultados.get(sym)
        if not r or not r.get("ok"): continue
        sc   = r.get("score",0); dec = r.get("decision","—"); dir_ = r.get("dir")
        p    = r.get("price"); grupo = r.get("grupo","")
        gclr = r.get("color","#555")
        icon = GRUPOS.get(grupo,{}).get("icon","⚡")

        if dec=="RECOMENDAR" and dir_=="buy":
            bg="#010d04"; bl="3px solid #00c853"
            d_cell='<span style="background:#00e676;color:#000;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.72em">▲ COMPRA</span>'
        elif dec=="RECOMENDAR" and dir_=="sell":
            bg="#0d0101"; bl="3px solid #c62828"
            d_cell='<span style="background:#ff1744;color:#fff;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.72em">▼ VENTA</span>'
        elif dec=="ESPERAR" and dir_=="buy":
            bg="#060e06"; bl="3px solid #143614"
            d_cell='<span style="background:#0a2a0a;color:#69f0ae;font-size:.7em;padding:2px 8px;border-radius:3px">⏳ BUY</span>'
        elif dec=="ESPERAR" and dir_=="sell":
            bg="#0e0606"; bl="3px solid #361414"
            d_cell='<span style="background:#2a0a0a;color:#ff8a80;font-size:.7em;padding:2px 8px;border-radius:3px">⏳ SELL</span>'
        else:
            bg="#09090f"; bl="3px solid #1a1a30"
            d_cell='<span style="color:#252545;font-size:.7em">—</span>'

        ind  = r.get("ind",{}) or {}
        adx  = ind.get("adx",0); rsi = ind.get("rsi",50)
        rsi_c= "#ff5252" if rsi>70 else "#ff9800" if rsi>65 else "#00e676" if rsi<35 else "#555"
        sc_c = "#ffd600" if sc>=90 else "#00e676" if sc>=80 else "#ff9800" if sc>=70 else "#383858"
        rows_html += (
            f'<tr style="background:{bg};border-left:{bl}">'
            f'<td style="padding:6px 10px;color:{gclr};font-weight:800;font-family:monospace">{icon} {sym}</td>'
            f'<td style="padding:6px 10px;color:#d8d8f8;font-family:monospace">{fmt(p)}</td>'
            f'<td style="padding:6px 10px">{d_cell}</td>'
            f'<td style="padding:6px 10px;color:{sc_c};font-weight:800">{sc}/100</td>'
            f'<td style="padding:6px 10px;color:{rsi_c};font-size:.76em">{rsi:.0f}</td>'
            f'<td style="padding:6px 10px;color:{"#00e676" if adx>=20 else "#ffd600" if adx>=14 else "#383858"};font-size:.76em">{adx:.0f}</td>'
            f'</tr>'
        )

    if rows_html:
        st.markdown(
            f'<table class="radar-tbl"><thead><tr>'
            f'<th>Instrumento</th><th>Precio</th><th>Señal</th>'
            f'<th>Score</th><th>RSI</th><th>ADX</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True)
    else:
        st.markdown('<div class="no-sig">Sin datos — conecta MT5 y lanza un scan</div>',
                    unsafe_allow_html=True)

# Tab HISTORIAL
with tabs[len(grupos_activos) + 1]:
    cerradas = [s for s in stats["señales"] if s["estado"] in ("GANADA","PERDIDA","EXPIRADA")]
    total = stats["total"]; wins = stats["wins"]; losses = stats["losses"]; pnl = stats["pnl"]
    if total > 0:
        c1,c2,c3 = st.columns(3)
        c1.metric("Win Rate",  f"{wins/total*100:.1f}%", f"{wins}G · {losses}P")
        c2.metric("P&L Total", f"${pnl:+.2f}", f"{total} cerradas")
        c3.metric("Abiertas",  len(abiertas))
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
            gclr = s.get("color","#555"); icon = GRUPOS.get(s.get("grupo",""),{}).get("icon","⚡")
            t_op = s.get("ts_open","")[11:16] or "—"
            t_cl = (s.get("ts_close") or "")[11:16] or "—"
            st.markdown(f"""<div class="{css}">
<div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px">
  <div style="display:flex;align-items:center;gap:8px">
    {badge}
    <b style="color:{dc}">{"▲" if s["dir"]=="buy" else "▼"}</b>
    <b style="color:{gclr};font-family:monospace">{icon} {s["sym"]}</b>
    <span style="color:#252540;font-size:.68em">{s.get("score",0)}/100</span>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    {res}
    <span style="color:#1e1e38;font-size:.68em">{t_op} → {t_cl}</span>
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
