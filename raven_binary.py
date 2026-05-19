# raven_binary.py  ·  RAVEN BINARY OPTIONS v2
# Scanner de opciones binarias: FOREX REAL + OTC
# Señales CALL/PUT · M1 y M5 · Gestión de riesgo · Plan de trading · Telegram

import streamlit as st
import streamlit.components.v1 as _stc
import pandas as pd
import numpy as np
import requests, json, os, time, traceback
from datetime import datetime, timezone, timedelta

from ta.trend     import EMAIndicator, MACD, ADXIndicator
from ta.momentum  import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange

try:
    import yfinance as yf
    _YF = True
except ImportError:
    _YF = False

# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════
RESULTS_FILE = r"C:\Users\saems\raven_binary_results.json"
CFG_FILE     = r"C:\Users\saems\raven_binary_cfg.json"
REFRESH      = 30   # segundos entre actualizaciones
MIN_PROB     = 65   # probabilidad mínima para mostrar señal

# ═══════════════════════════════════════════════════════════════════════
# PARES
# ═══════════════════════════════════════════════════════════════════════
REAL_PAIRS = {
    "EURUSD": ("EURUSD=X", "💶 EUR/USD"),
    "GBPUSD": ("GBPUSD=X", "💷 GBP/USD"),
    "USDJPY": ("USDJPY=X", "🇯🇵 USD/JPY"),
    "AUDUSD": ("AUDUSD=X", "🦘 AUD/USD"),
    "USDCAD": ("USDCAD=X", "🍁 USD/CAD"),
    "USDCHF": ("USDCHF=X", "🇨🇭 USD/CHF"),
    "NZDUSD": ("NZDUSD=X", "🥝 NZD/USD"),
    "EURGBP": ("EURGBP=X", "🇪🇺 EUR/GBP"),
    "EURJPY": ("EURJPY=X", "🇪🇺 EUR/JPY"),
    "GBPJPY": ("GBPJPY=X", "💷 GBP/JPY"),
    "AUDJPY": ("AUDJPY=X", "🦘 AUD/JPY"),
    "CADJPY": ("CADJPY=X", "🍁 CAD/JPY"),
}

# OTC = mismos pares disponibles 24/7 (precios proxy del mercado real)
OTC_PAIRS = {
    f"{k}-OTC": (v[0], f"{v[1]} OTC")
    for k, v in REAL_PAIRS.items()
}

# Horario mercado real (UTC)
def _real_open():
    now = datetime.now(timezone.utc)
    wd = now.weekday()    # 0=lunes, 6=domingo
    h  = now.hour + now.minute/60
    if wd >= 5: return False
    if wd == 4 and h >= 21.83: return False
    return True

# ═══════════════════════════════════════════════════════════════════════
# PÁGINA + CSS
# ═══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="RAVEN BINARY",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#05050d}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#07070f}
.block-container{padding:.5rem 1.2rem;max-width:1300px}
.stTabs [data-baseweb="tab-list"]{background:#09091a;border-radius:8px;padding:4px;gap:3px}
.stTabs [data-baseweb="tab"]{background:transparent;color:#3a3a5a;border-radius:6px;
  padding:7px 20px;font-weight:700;font-size:.8em;text-transform:uppercase;letter-spacing:1.5px}
.stTabs [aria-selected="true"]{background:#12122e;color:#d8d8f8}
div[data-testid="stButton"]>button{background:#10101e;color:#888;border:1px solid #1c1c32;
  border-radius:6px;font-size:.78em;padding:3px 10px}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# PERSISTENCIA
# ═══════════════════════════════════════════════════════════════════════
def _load_results():
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_results(data):
    try:
        with open(RESULTS_FILE,"w",encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _add_result(pair, direction, expiry, prob, result):
    data = _load_results()
    data.append({
        "ts":        datetime.now(timezone.utc).isoformat(),
        "pair":      pair,
        "direction": direction,
        "expiry":    expiry,
        "prob":      prob,
        "result":    result,   # "WIN" | "LOSS"
    })
    _save_results(data)

def _stats(pair=None):
    data = _load_results()
    if pair:
        data = [d for d in data if d["pair"]==pair]
    wins  = sum(1 for d in data if d.get("result")=="WIN")
    losses= sum(1 for d in data if d.get("result")=="LOSS")
    total = wins + losses
    today = datetime.now(timezone.utc).date().isoformat()
    today_data  = [d for d in data if d.get("ts","")[:10]==today]
    today_wins  = sum(1 for d in today_data if d.get("result")=="WIN")
    today_losses= sum(1 for d in today_data if d.get("result")=="LOSS")
    return {
        "wins":wins,"losses":losses,"total":total,
        "pct": round(wins/total*100) if total else 0,
        "today_wins":today_wins,"today_losses":today_losses,
        "today_total":today_wins+today_losses,
        "today_pct": round(today_wins/(today_wins+today_losses)*100) if (today_wins+today_losses)>0 else 0,
    }

def _load_cfg():
    try:
        if os.path.exists(CFG_FILE):
            with open(CFG_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_cfg(d):
    try:
        with open(CFG_FILE,"w",encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════
# GESTIÓN DE RIESGO — PLAN DE TRADING
# ═══════════════════════════════════════════════════════════════════════
def _rm_defaults():
    return {"capital":1000,"pct_trade":2,"max_loss_pct":6,
            "profit_goal_pct":4,"max_trades":10}

def _load_rm():
    cfg = _load_cfg()
    d = _rm_defaults()
    for k in d:
        if k in cfg: d[k] = cfg[k]
    return d

def _save_rm(rm):
    cfg = _load_cfg()
    cfg.update(rm)
    _save_cfg(cfg)

def _daily_pnl(rm):
    """P&L estimado del día. Payout 80% en WIN, -100% en LOSS."""
    data  = _load_results()
    today = datetime.now(timezone.utc).date().isoformat()
    per   = rm["capital"] * rm["pct_trade"] / 100
    pnl   = 0; trades = 0
    for d in data:
        if d.get("ts","")[:10] != today: continue
        if   d.get("result")=="WIN":  pnl += per * 0.80; trades += 1
        elif d.get("result")=="LOSS": pnl -= per;        trades += 1
    return round(pnl, 2), trades

def _session_ok(rm):
    """Retorna (permitido, mensaje, pnl, trades_hoy)."""
    stop_amt = rm["capital"] * rm["max_loss_pct"]   / 100
    goal_amt = rm["capital"] * rm["profit_goal_pct"] / 100
    pnl, trades = _daily_pnl(rm)
    if pnl <= -stop_amt:
        return False, f"⛔ Pérdida máxima alcanzada: ${abs(pnl):.2f}", pnl, trades
    if pnl >= goal_amt:
        return False, f"🎯 Meta del día lograda: +${pnl:.2f}", pnl, trades
    if trades >= rm["max_trades"]:
        return False, f"⛔ Máx. operaciones del día ({trades}/{rm['max_trades']})", pnl, trades
    return True, "✅ Sesión activa", pnl, trades

# ═══════════════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════════════
def _tg(msg):
    cfg = _load_cfg()
    tok = cfg.get("tg_token","").strip()
    cid = cfg.get("tg_chatid","").strip()
    if not tok or not cid: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            json={"chat_id":cid,"text":msg,"parse_mode":"HTML"},
            timeout=5
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════
# DATOS
# ═══════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=20, show_spinner=False)
def _bars(yticker, interval, period):
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yticker}"
        r = requests.get(url, params={"interval":interval,"range":period},
                        timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code != 200:
            raise ValueError(f"HTTP {r.status_code}")
        d = r.json()["chart"]["result"][0]
        ts = pd.to_datetime(d["timestamp"], unit="s", utc=True)
        q  = d["indicators"]["quote"][0]
        df = pd.DataFrame({
            "open":  q.get("open",[]),
            "high":  q.get("high",[]),
            "low":   q.get("low",[]),
            "close": q.get("close",[]),
            "volume":q.get("volume",[0]*len(ts))
        }, index=ts)
        return df.dropna()
    except Exception:
        pass
    if _YF:
        try:
            df = yf.Ticker(yticker).history(interval=interval, period=period)
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]
                df.index = pd.to_datetime(df.index, utc=True)
                return df[["open","high","low","close","volume"]].dropna()
        except Exception:
            pass
    return None

@st.cache_data(ttl=15, show_spinner=False)
def _price(yticker):
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yticker}"
        r = requests.get(url, params={"interval":"1m","range":"1d"},
                        timeout=5, headers={"User-Agent":"Mozilla/5.0"})
        meta = r.json()["chart"]["result"][0]["meta"]
        p = meta.get("regularMarketPrice") or meta.get("previousClose",0)
        return float(p) if p else None
    except Exception:
        pass
    if _YF:
        try:
            return float(yf.Ticker(yticker).fast_info.last_price)
        except Exception:
            pass
    return None

def _fetch_pair(yticker):
    """Retorna (precio, df_m1, df_m5, df_m15) para un par."""
    precio = _price(yticker)
    df_m1  = _bars(yticker, "2m",  "1d")   # proxy M1
    df_m5  = _bars(yticker, "5m",  "5d")
    df_m15 = _bars(yticker, "15m", "5d")
    return precio, df_m1, df_m5, df_m15

# ═══════════════════════════════════════════════════════════════════════
# INDICADORES
# ═══════════════════════════════════════════════════════════════════════
def _ind(df, fast=9, slow=21, rsi_n=14):
    if df is None or len(df) < max(slow+5, 20):
        return None
    try:
        c = df["close"].astype(float)
        h = df["high"].astype(float)
        l = df["low"].astype(float)
        o = df["open"].astype(float)
        n = len(c)
        ef  = EMAIndicator(c, min(fast, n-1)).ema_indicator()
        es  = EMAIndicator(c, min(slow, n-1)).ema_indicator()
        e50 = EMAIndicator(c, min(50, n-1)).ema_indicator()
        rsi = RSIIndicator(c, min(rsi_n, n-1)).rsi()
        mc  = MACD(c)
        bb  = BollingerBands(c, min(20, n-1), 2)
        stoch = StochasticOscillator(h, l, c, min(14,n-1), min(3,n-1))
        atr   = AverageTrueRange(h, l, c, min(14,n-1)).average_true_range()
        adx_o = ADXIndicator(h, l, c, min(14,n-1))
        return {
            "p":   float(c.iloc[-1]),
            "ef":  float(ef.iloc[-1]),
            "ef2": float(ef.iloc[-2]) if n>2 else float(ef.iloc[-1]),
            "es":  float(es.iloc[-1]),
            "es2": float(es.iloc[-2]) if n>2 else float(es.iloc[-1]),
            "e50": float(e50.iloc[-1]),
            "rsi": float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50,
            "macd_h": float(mc.macd_diff().iloc[-1]),
            "macd_h2":float(mc.macd_diff().iloc[-2]) if n>2 else 0,
            "bb_hi":  float(bb.bollinger_hband().iloc[-1]),
            "bb_lo":  float(bb.bollinger_lband().iloc[-1]),
            "bb_mid": float(bb.bollinger_mavg().iloc[-1]),
            "stoch":  float(stoch.stoch().iloc[-1]),
            "stoch2": float(stoch.stoch().iloc[-2]) if n>2 else 50,
            "atr":    float(atr.iloc[-1]),
            "adx":    float(adx_o.adx().iloc[-1]),
            "o":float(o.iloc[-1]),"c":float(c.iloc[-1]),
            "o2":float(o.iloc[-2]),"c2":float(c.iloc[-2]),
            "o3":float(o.iloc[-3]) if n>3 else float(o.iloc[-1]),
            "c3":float(c.iloc[-3]) if n>3 else float(c.iloc[-1]),
        }
    except Exception:
        return None

# ═══════════════════════════════════════════════════════════════════════
# MOTOR DE SEÑALES BINARIAS
# ═══════════════════════════════════════════════════════════════════════
def _vote(condition_call, condition_put, weight=1.0):
    """Retorna (call_pts, put_pts) según condición."""
    if condition_call:   return weight, 0
    if condition_put:    return 0, weight
    return 0, 0

def _signal_m5(im5, im15):
    """Señal para expiración 5 minutos."""
    if im5 is None: return None
    votes_c = 0; votes_p = 0

    # 1. EMA rápida vs lenta — peso 2
    c,p = _vote(im5["ef"]>im5["es"], im5["ef"]<im5["es"], 2)
    votes_c+=c; votes_p+=p

    # 2. RSI M5 — peso 2
    c,p = _vote(im5["rsi"]>55, im5["rsi"]<45, 2)
    votes_c+=c; votes_p+=p

    # 3. MACD histogram — peso 1.5
    c,p = _vote(im5["macd_h"]>0 and im5["macd_h"]>im5["macd_h2"],
                im5["macd_h"]<0 and im5["macd_h"]<im5["macd_h2"], 1.5)
    votes_c+=c; votes_p+=p

    # 4. Precio vs BB media — peso 1
    c,p = _vote(im5["p"]>im5["bb_mid"], im5["p"]<im5["bb_mid"], 1)
    votes_c+=c; votes_p+=p

    # 5. Stochastic — peso 1.5
    c,p = _vote(im5["stoch"]<25 and im5["stoch"]>im5["stoch2"],
                im5["stoch"]>75 and im5["stoch"]<im5["stoch2"], 1.5)
    votes_c+=c; votes_p+=p

    # 6. Precio vs EMA50 — peso 1
    c,p = _vote(im5["p"]>im5["e50"], im5["p"]<im5["e50"], 1)
    votes_c+=c; votes_p+=p

    # 7. Última vela M5 — peso 1
    c,p = _vote(im5["c"]>im5["o"], im5["c"]<im5["o"], 1)
    votes_c+=c; votes_p+=p

    # 8. Contexto M15 — peso 1.5
    if im15:
        c,p = _vote(im15["ef"]>im15["es"] and im15["rsi"]>50,
                    im15["ef"]<im15["es"] and im15["rsi"]<50, 1.5)
        votes_c+=c; votes_p+=p

    total = votes_c + votes_p
    if total < 3: return None
    net = (votes_c - votes_p) / (total if total > 0 else 1)
    prob = round(50 + net * 45)

    razones_call = []
    razones_put  = []
    if im5["ef"]>im5["es"]:      razones_call.append("EMAs subiendo")
    elif im5["ef"]<im5["es"]:    razones_put.append("EMAs bajando")
    if im5["rsi"]>55:            razones_call.append(f"RSI {im5['rsi']:.0f} fuerte")
    elif im5["rsi"]<45:          razones_put.append(f"RSI {im5['rsi']:.0f} débil")
    if im5["macd_h"]>0:          razones_call.append("MACD positivo")
    elif im5["macd_h"]<0:        razones_put.append("MACD negativo")
    if im5["stoch"]<25:          razones_call.append("Stoch sobrevendido")
    elif im5["stoch"]>75:        razones_put.append("Stoch sobrecomprado")
    if im5["p"]<im5["bb_lo"]:    razones_call.append("Precio bajo Bollinger")
    elif im5["p"]>im5["bb_hi"]:  razones_put.append("Precio sobre Bollinger")

    if prob >= MIN_PROB:
        razon = " · ".join(razones_call[:3]) or "Múltiples indicadores CALL"
        return {"dir":"CALL","prob":prob,"razon":razon,"expiry":"5 min",
                "votes_c":votes_c,"votes_p":votes_p,"adx":im5["adx"]}
    if prob <= (100-MIN_PROB):
        razon = " · ".join(razones_put[:3]) or "Múltiples indicadores PUT"
        return {"dir":"PUT","prob":100-prob,"razon":razon,"expiry":"5 min",
                "votes_c":votes_c,"votes_p":votes_p,"adx":im5["adx"]}
    return {"dir":"ESPERAR","prob":max(prob,100-prob),"razon":"Señales mixtas — espera confirmación",
            "expiry":"5 min","votes_c":votes_c,"votes_p":votes_p,"adx":im5["adx"]}

def _signal_m1(im1, im5):
    """Señal para expiración 1 minuto (más agresiva)."""
    if im1 is None: return None
    votes_c = 0; votes_p = 0

    # EMA rápida (3 vs 8 en M1) — peso 2
    c,p = _vote(im1["ef"]>im1["es"], im1["ef"]<im1["es"], 2)
    votes_c+=c; votes_p+=p

    # RSI(7) M1 — peso 2
    c,p = _vote(im1["rsi"]>60, im1["rsi"]<40, 2)
    votes_c+=c; votes_p+=p

    # Stochastic M1 — peso 1.5
    c,p = _vote(im1["stoch"]<20 and im1["stoch"]>im1["stoch2"],
                im1["stoch"]>80 and im1["stoch"]<im1["stoch2"], 1.5)
    votes_c+=c; votes_p+=p

    # Últimas 2 velas M1 — peso 1.5
    last2_bull = (im1["c"]>im1["o"]) and (im1["c2"]>im1["o2"])
    last2_bear = (im1["c"]<im1["o"]) and (im1["c2"]<im1["o2"])
    c,p = _vote(last2_bull, last2_bear, 1.5)
    votes_c+=c; votes_p+=p

    # BB position — peso 1
    c,p = _vote(im1["p"]<im1["bb_lo"], im1["p"]>im1["bb_hi"], 1)
    votes_c+=c; votes_p+=p

    # Contexto M5 — peso 1.5
    if im5:
        c,p = _vote(im5["ef"]>im5["es"] and im5["rsi"]>52,
                    im5["ef"]<im5["es"] and im5["rsi"]<48, 1.5)
        votes_c+=c; votes_p+=p

    total = votes_c + votes_p
    if total < 3: return None
    net = (votes_c - votes_p) / (total if total > 0 else 1)
    prob = round(50 + net * 45)

    razones_call = []
    razones_put  = []
    if im1["ef"]>im1["es"]:   razones_call.append("EMA sube M1")
    elif im1["ef"]<im1["es"]: razones_put.append("EMA baja M1")
    if im1["rsi"]>60:         razones_call.append(f"RSI M1: {im1['rsi']:.0f}")
    elif im1["rsi"]<40:       razones_put.append(f"RSI M1: {im1['rsi']:.0f}")
    if last2_bull:            razones_call.append("2 velas alcistas")
    if last2_bear:            razones_put.append("2 velas bajistas")
    if im1["stoch"]<20:       razones_call.append("Stoch extremo bajo")
    elif im1["stoch"]>80:     razones_put.append("Stoch extremo alto")

    if prob >= MIN_PROB:
        razon = " · ".join(razones_call[:3]) or "Momentum CALL"
        return {"dir":"CALL","prob":prob,"razon":razon,"expiry":"1 min",
                "votes_c":votes_c,"votes_p":votes_p,"adx":im1["adx"]}
    if prob <= (100-MIN_PROB):
        razon = " · ".join(razones_put[:3]) or "Momentum PUT"
        return {"dir":"PUT","prob":100-prob,"razon":razon,"expiry":"1 min",
                "votes_c":votes_c,"votes_p":votes_p,"adx":im1["adx"]}
    return {"dir":"ESPERAR","prob":max(prob,100-prob),"razon":"Sin momentum claro en M1",
            "expiry":"1 min","votes_c":votes_c,"votes_p":votes_p,"adx":im1["adx"]}

# ═══════════════════════════════════════════════════════════════════════
# NOTICIAS
# ═══════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_news():
    ev = []
    for url in ["https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                "https://nfs.faireconomy.media/ff_calendar_nextweek.json"]:
        try:
            r = requests.get(url, timeout=6, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code != 200: continue
            for e in r.json():
                if e.get("impact")=="High" and e.get("country") in ("USD","EUR","GBP","JPY","AUD","CAD","CHF","NZD"):
                    try:
                        dt = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
                        ev.append({"dt":dt,"titulo":e.get("title",""),"moneda":e.get("country","")})
                    except Exception:
                        pass
        except Exception:
            pass
    return sorted(ev, key=lambda x: x["dt"])

def _news_risk(ev, pair=""):
    now = datetime.now(timezone.utc)
    monedas_par = set()
    base = pair.replace("-OTC","")
    if len(base)==6:
        monedas_par = {base[:3], base[3:]}
    for e in ev:
        d = (e["dt"]-now).total_seconds()/60
        if -15 <= d <= 15 and (not monedas_par or e.get("moneda","") in monedas_par):
            return "PELIGRO", f"🔴 {e['titulo']} ({e.get('moneda','')})"
        if 15 < d <= 60 and (not monedas_par or e.get("moneda","") in monedas_par):
            return "PRECAUCION", f"🟡 Noticia en {int(d)} min: {e['titulo']}"
    return "SEGURO", ""

# ═══════════════════════════════════════════════════════════════════════
# UI — HELPERS
# ═══════════════════════════════════════════════════════════════════════
def _he(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# ═══════════════════════════════════════════════════════════════════════
# UI — TARJETA DE PAR
# ═══════════════════════════════════════════════════════════════════════
def _render_pair_card(pair, label, yticker, ev, is_otc=False, rm=None):
    # Fetch data
    with st.spinner(""):
        precio, df_m1, df_m5, df_m15 = _fetch_pair(yticker)

    if precio is None:
        st.markdown(f"""
<div style="background:#07070d;border:1px solid #111118;border-radius:8px;
  padding:.6rem 1rem;margin:.3rem 0;opacity:.4">
  <span style="color:#333;font-size:.82em">{_he(label)}</span>
  <span style="color:#222;font-size:.72em;margin-left:8px">Sin datos</span>
</div>""", unsafe_allow_html=True)
        return

    im1  = _ind(df_m1, fast=3, slow=8,  rsi_n=7)   if df_m1  is not None else None
    im5  = _ind(df_m5, fast=9, slow=21, rsi_n=14)  if df_m5  is not None else None
    im15 = _ind(df_m15,fast=9, slow=21, rsi_n=14)  if df_m15 is not None else None

    sig_m5 = _signal_m5(im5, im15)
    sig_m1 = _signal_m1(im1, im5)

    news_lvl, news_txt = _news_risk(ev, pair)
    bloqueado = news_lvl == "PELIGRO"

    # Estadísticas del par
    st_pair = _stats(pair)

    # Formateo precio
    dec = 3 if "JPY" in pair else 5
    precio_txt = f"{precio:.{dec}f}"

    # Flags de señal activa (calculados antes del HTML)
    m5_bloq  = bloqueado and sig_m5 and sig_m5["dir"] in ("CALL","PUT")
    m1_bloq  = bloqueado and sig_m1 and sig_m1["dir"] in ("CALL","PUT")
    active_m5 = bool(sig_m5 and sig_m5["dir"] in ("CALL","PUT") and not m5_bloq)
    active_m1 = bool(sig_m1 and sig_m1["dir"] in ("CALL","PUT") and not m1_bloq)

    # Colores señal
    def sig_color(s):
        if not s: return "#333"
        if s["dir"]=="CALL":   return "#00e676"
        if s["dir"]=="PUT":    return "#ff5252"
        return "#555"

    def sig_icon(s):
        if not s: return "—"
        if s["dir"]=="CALL":   return "▲ CALL"
        if s["dir"]=="PUT":    return "▼ PUT"
        return "⏸ ESPERAR"

    def prob_bar(prob, color, width=80):
        return (f'<div style="background:#0e0e18;border-radius:3px;height:4px;'
                f'width:{width}px;overflow:hidden;display:inline-block;vertical-align:middle;margin-left:4px">'
                f'<div style="background:{color};height:4px;width:{prob}%;border-radius:3px"></div></div>')

    # Badge de noticia
    news_badge = ""
    if news_lvl == "PELIGRO":
        news_badge = '<span style="background:#c62828;color:#fff;padding:1px 6px;border-radius:4px;font-size:.6em;margin-left:6px;font-weight:700">⛔ NOTICIA</span>'
    elif news_lvl == "PRECAUCION":
        news_badge = f'<span style="background:#7a4500;color:#ff9800;padding:1px 6px;border-radius:4px;font-size:.6em;margin-left:6px">⚠️ {news_txt}</span>'

    # Badge de estadísticas
    pct_color = "#00e676" if st_pair["today_pct"]>=65 else ("#ffd600" if st_pair["today_pct"]>=50 else "#ff5252")
    stat_badge = ""
    if st_pair["today_total"]>0:
        stat_badge = (f'<span style="background:#0a0a14;border:1px solid #1a1a2a;color:{pct_color};'
                     f'padding:1px 7px;border-radius:4px;font-size:.62em;margin-left:6px">'
                     f'{st_pair["today_wins"]}W/{st_pair["today_losses"]}L hoy '
                     f'<b>{st_pair["today_pct"]}%</b></span>')

    otc_badge = '<span style="background:#1a0e30;color:#ab47bc;padding:1px 5px;border-radius:4px;font-size:.6em;margin-left:4px">OTC</span>' if is_otc else ""

    # Bloque M5
    m5_color = sig_color(sig_m5)
    m5_dir   = sig_icon(sig_m5)
    m5_prob  = sig_m5["prob"] if sig_m5 else 0
    m5_razon = _he(sig_m5["razon"]) if sig_m5 else "Calculando…"
    m5_adx   = f"ADX {sig_m5['adx']:.0f}" if sig_m5 else ""

    # Bloque M1
    m1_color = sig_color(sig_m1)
    m1_dir   = sig_icon(sig_m1)
    m1_prob  = sig_m1["prob"] if sig_m1 else 0
    m1_razon = _he(sig_m1["razon"]) if sig_m1 else "Calculando…"

    container_border = "#c6282822" if bloqueado else "#14142a"

    st.markdown(f"""
<div style="background:#08080f;border:1px solid {container_border};border-radius:10px;
  padding:.8rem 1.1rem;margin:.3rem 0">

  <!-- Header -->
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div>
      <span style="color:#d8d8f8;font-size:.92em;font-weight:700">{_he(label)}</span>
      {otc_badge}
      {news_badge}
      {stat_badge}
    </div>
    <span style="color:#666;font-size:.82em;font-weight:700">{precio_txt}</span>
  </div>

  <!-- Señales -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">

    <!-- M5 -->
    <div style="background:#0c0c1a;border:1px solid {'#1e3a1e' if active_m5 and sig_m5 and sig_m5['dir']=='CALL' else ('#3a1e1e' if active_m5 and sig_m5 and sig_m5['dir']=='PUT' else '#14142a')};
      border-radius:8px;padding:8px 10px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
        <span style="color:#252540;font-size:.6em;font-weight:700;text-transform:uppercase">5 MINUTOS</span>
        <span style="color:{m5_color if not m5_bloq else '#c62828'};font-size:.82em;font-weight:900">
          {'⛔ NO OPERAR' if m5_bloq else m5_dir}
        </span>
      </div>
      {'<div style="display:flex;align-items:center;margin-bottom:2px"><span style="color:'+m5_color+';font-size:.75em;font-weight:700">'+str(m5_prob)+'%</span>'+prob_bar(m5_prob, m5_color)+'</div>' if not m5_bloq else ''}
      <div style="color:#333;font-size:.68em;line-height:1.3">{m5_razon if not m5_bloq else "⛔ Noticia de alto impacto próxima — NO OPERAR"}</div>
      {'<div style="color:#1a1a30;font-size:.6em;margin-top:2px">'+m5_adx+'</div>' if m5_adx and not m5_bloq else ''}
    </div>

    <!-- M1 -->
    <div style="background:#0c0c1a;border:1px solid {'#1e3a1e' if active_m1 and sig_m1 and sig_m1['dir']=='CALL' else ('#3a1e1e' if active_m1 and sig_m1 and sig_m1['dir']=='PUT' else '#14142a')};
      border-radius:8px;padding:8px 10px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
        <span style="color:#252540;font-size:.6em;font-weight:700;text-transform:uppercase">1 MINUTO</span>
        <span style="color:{m1_color if not m1_bloq else '#c62828'};font-size:.82em;font-weight:900">
          {'⛔ NO OPERAR' if m1_bloq else m1_dir}
        </span>
      </div>
      {'<div style="display:flex;align-items:center;margin-bottom:2px"><span style="color:'+m1_color+';font-size:.75em;font-weight:700">'+str(m1_prob)+'%</span>'+prob_bar(m1_prob, m1_color)+'</div>' if not m1_bloq else ''}
      <div style="color:#333;font-size:.68em;line-height:1.3">{m1_razon if not m1_bloq else "⛔ Noticia de alto impacto próxima — NO OPERAR"}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── BLOQUE DE ENTRADA / SALIDA / RIESGO ─────────────────────────────
    if rm and (active_m5 or active_m1):
        now_utc   = datetime.now(timezone.utc)
        per_trade = round(rm["capital"] * rm["pct_trade"] / 100, 2)
        ganancia  = round(per_trade * 0.80, 2)
        blocks    = []

        if active_m5 and sig_m5:
            exp_m5 = (now_utc + timedelta(minutes=5)).strftime("%H:%M")
            dc     = "#00e676" if sig_m5["dir"]=="CALL" else "#ff5252"
            dt     = "▲ CALL" if sig_m5["dir"]=="CALL" else "▼ PUT"
            blocks.append(f"""
<div style="background:#060611;border:1px solid #10102a;border-radius:8px;
  padding:6px 10px;margin:.12rem 0;display:flex;justify-content:space-between;
  align-items:center;flex-wrap:wrap;gap:6px">
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <span style="color:{dc};font-size:.72em;font-weight:900">M5 {dt}</span>
    <span style="color:#1e1e3a;font-size:.65em">Entrada: <b style="color:#c8c8e8">{precio_txt}</b></span>
    <span style="color:#1e1e3a;font-size:.65em">Expira: <b style="color:#ffd600">{exp_m5} UTC</b></span>
  </div>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <span style="color:#1e1e3a;font-size:.65em">Invertir: <b style="color:#ffd600">${per_trade:.2f}</b></span>
    <span style="color:#00e676;font-size:.65em;font-weight:700">WIN +${ganancia:.2f}</span>
    <span style="color:#ff5252;font-size:.65em;font-weight:700">LOSS -${per_trade:.2f}</span>
  </div>
</div>""")

        if active_m1 and sig_m1:
            exp_m1 = (now_utc + timedelta(minutes=1)).strftime("%H:%M")
            dc     = "#00e676" if sig_m1["dir"]=="CALL" else "#ff5252"
            dt     = "▲ CALL" if sig_m1["dir"]=="CALL" else "▼ PUT"
            blocks.append(f"""
<div style="background:#060611;border:1px solid #10102a;border-radius:8px;
  padding:6px 10px;margin:.12rem 0;display:flex;justify-content:space-between;
  align-items:center;flex-wrap:wrap;gap:6px">
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <span style="color:{dc};font-size:.72em;font-weight:900">M1 {dt}</span>
    <span style="color:#1e1e3a;font-size:.65em">Entrada: <b style="color:#c8c8e8">{precio_txt}</b></span>
    <span style="color:#1e1e3a;font-size:.65em">Expira: <b style="color:#ffd600">{exp_m1} UTC</b></span>
  </div>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <span style="color:#1e1e3a;font-size:.65em">Invertir: <b style="color:#ffd600">${per_trade:.2f}</b></span>
    <span style="color:#00e676;font-size:.65em;font-weight:700">WIN +${ganancia:.2f}</span>
    <span style="color:#ff5252;font-size:.65em;font-weight:700">LOSS -${per_trade:.2f}</span>
  </div>
</div>""")

        if blocks:
            st.markdown("".join(blocks), unsafe_allow_html=True)

    # ── BOTONES DE RESULTADO ─────────────────────────────────────────────
    if active_m5 or active_m1:
        cols = st.columns([1,1,1,1,2])
        if active_m5:
            with cols[0]:
                if st.button(f"✅ M5", key=f"w5_{pair}_{int(time.time())//60}", help="Gané en M5"):
                    _add_result(pair, sig_m5["dir"], "5m", sig_m5["prob"], "WIN")
                    _tg(f"✅ <b>WIN</b> · {pair} · {sig_m5['dir']} M5 · {sig_m5['prob']}%")
                    st.toast(f"✅ WIN registrado {pair} M5")
            with cols[1]:
                if st.button(f"❌ M5", key=f"l5_{pair}_{int(time.time())//60}", help="Perdí en M5"):
                    _add_result(pair, sig_m5["dir"], "5m", sig_m5["prob"], "LOSS")
                    st.toast(f"❌ LOSS registrado {pair} M5")
        if active_m1:
            with cols[2]:
                if st.button(f"✅ M1", key=f"w1_{pair}_{int(time.time())//60}", help="Gané en M1"):
                    _add_result(pair, sig_m1["dir"], "1m", sig_m1["prob"], "WIN")
                    _tg(f"✅ <b>WIN</b> · {pair} · {sig_m1['dir']} M1 · {sig_m1['prob']}%")
                    st.toast(f"✅ WIN registrado {pair} M1")
            with cols[3]:
                if st.button(f"❌ M1", key=f"l1_{pair}_{int(time.time())//60}", help="Perdí en M1"):
                    _add_result(pair, sig_m1["dir"], "1m", sig_m1["prob"], "LOSS")
                    st.toast(f"❌ LOSS registrado {pair} M1")

    # Telegram si hay señal nueva activa
    sk = f"_tg_sent_{pair}"
    sig_key = f"{sig_m5['dir'] if sig_m5 else ''}{sig_m1['dir'] if sig_m1 else ''}"
    if sig_key != st.session_state.get(sk,""):
        st.session_state[sk] = sig_key
        if active_m5 and sig_m5:
            _tg(f"📊 <b>RAVEN BINARY · {pair}</b>\n"
                f"{'▲ CALL' if sig_m5['dir']=='CALL' else '▼ PUT'} · 5 MIN · <b>{sig_m5['prob']}%</b>\n"
                f"{sig_m5['razon']}")
        if active_m1 and sig_m1:
            _tg(f"⚡ <b>RAVEN BINARY · {pair}</b>\n"
                f"{'▲ CALL' if sig_m1['dir']=='CALL' else '▼ PUT'} · 1 MIN · <b>{sig_m1['prob']}%</b>\n"
                f"{sig_m1['razon']}")

# ═══════════════════════════════════════════════════════════════════════
# PANEL DE ESTADÍSTICAS GLOBAL
# ═══════════════════════════════════════════════════════════════════════
def _render_stats_panel():
    st_all = _stats()
    if st_all["total"] == 0:
        return
    pct_color   = "#00e676" if st_all["pct"]>=65 else ("#ffd600" if st_all["pct"]>=50 else "#ff5252")
    today_color = "#00e676" if st_all["today_pct"]>=65 else ("#ffd600" if st_all["today_pct"]>=50 else "#ff5252")

    # Top pares
    all_results = _load_results()
    pair_stats = {}
    for d in all_results:
        p = d.get("pair","")
        if p not in pair_stats: pair_stats[p] = {"w":0,"l":0}
        if d.get("result")=="WIN": pair_stats[p]["w"]+=1
        elif d.get("result")=="LOSS": pair_stats[p]["l"]+=1
    sorted_pairs = sorted(pair_stats.items(),
                          key=lambda x: x[1]["w"]/(x[1]["w"]+x[1]["l"]) if (x[1]["w"]+x[1]["l"])>3 else 0,
                          reverse=True)

    best_html = ""
    for p, s in sorted_pairs[:5]:
        t = s["w"]+s["l"]
        if t < 2: continue
        pct = round(s["w"]/t*100)
        c = "#00e676" if pct>=65 else ("#ffd600" if pct>=50 else "#ff5252")
        best_html += (f'<div style="display:flex;justify-content:space-between;'
                      f'padding:3px 0;border-bottom:1px solid #0c0c18;font-size:.75em">'
                      f'<span style="color:#444">{p.replace("-OTC"," OTC")}</span>'
                      f'<span style="color:{c};font-weight:700">{pct}% ({s["w"]}W/{s["l"]}L)</span></div>')

    st.markdown(f"""
<div style="background:#08080f;border:1px solid #12122a;border-radius:10px;
  padding:.8rem 1.2rem;margin-bottom:.5rem">
  <div style="color:#1a1a30;font-size:.65em;font-weight:700;text-transform:uppercase;
    letter-spacing:.1em;margin-bottom:8px">Historial de resultados</div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-bottom:10px">
    <div style="text-align:center">
      <div style="color:{today_color};font-size:1.5em;font-weight:900">{st_all["today_pct"]}%</div>
      <div style="color:#1e1e30;font-size:.65em">HOY ({st_all["today_wins"]}W/{st_all["today_losses"]}L)</div>
    </div>
    <div style="text-align:center">
      <div style="color:{pct_color};font-size:1.5em;font-weight:900">{st_all["pct"]}%</div>
      <div style="color:#1e1e30;font-size:.65em">TOTAL ({st_all["wins"]}W/{st_all["losses"]}L)</div>
    </div>
    <div style="text-align:center">
      <div style="color:#42a5f5;font-size:1.5em;font-weight:900">{st_all["wins"]}</div>
      <div style="color:#1e1e30;font-size:.65em">GANADAS</div>
    </div>
    <div style="text-align:center">
      <div style="color:#ff5252;font-size:1.5em;font-weight:900">{st_all["losses"]}</div>
      <div style="color:#1e1e30;font-size:.65em">PERDIDAS</div>
    </div>
  </div>
  {('<div style="color:#1e1e30;font-size:.65em;font-weight:700;text-transform:uppercase;margin-bottom:4px">Mejores pares</div>'+best_html) if best_html else ''}
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# PANEL DE PLAN DE TRADING
# ═══════════════════════════════════════════════════════════════════════
def _render_plan_panel(rm):
    capital   = rm["capital"]
    pct       = rm["pct_trade"]
    per_trade = round(capital * pct / 100, 2)
    goal_amt  = round(capital * rm["profit_goal_pct"] / 100, 2)
    stop_amt  = round(capital * rm["max_loss_pct"]    / 100, 2)
    ok, msg, pnl, trades = _session_ok(rm)

    pnl_sign  = "+" if pnl >= 0 else ""
    pnl_color = "#00e676" if pnl > 0 else ("#ff5252" if pnl < 0 else "#555")
    remaining = max(0, rm["max_trades"] - trades)
    panel_bg  = "#07080f" if ok else "#0f0605"
    border    = "#12122a" if ok else "#3a1010"

    # Barra de progreso hacia la meta
    if goal_amt > 0:
        prog = min(100, max(0, round(pnl / goal_amt * 100))) if pnl > 0 else 0
        loss_prog = min(100, max(0, round(abs(pnl) / stop_amt * 100))) if pnl < 0 else 0
    else:
        prog = 0; loss_prog = 0

    prog_bar_html = ""
    if pnl > 0 and goal_amt > 0:
        prog_bar_html = (f'<div style="background:#0a0a18;border-radius:3px;height:3px;width:100%;margin-top:4px">'
                         f'<div style="background:#00e676;height:3px;width:{prog}%;border-radius:3px"></div></div>')
    elif pnl < 0 and stop_amt > 0:
        prog_bar_html = (f'<div style="background:#0a0a18;border-radius:3px;height:3px;width:100%;margin-top:4px">'
                         f'<div style="background:#ff5252;height:3px;width:{loss_prog}%;border-radius:3px"></div></div>')

    st.markdown(f"""
<div style="background:{panel_bg};border:1px solid {border};border-radius:10px;
  padding:.7rem 1.2rem;margin-bottom:.5rem">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">

    <!-- Datos del plan -->
    <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">
      <div>
        <div style="color:#1e1e38;font-size:.58em;text-transform:uppercase;font-weight:700">Capital</div>
        <div style="color:#c8c8e8;font-size:.88em;font-weight:700">${capital:,}</div>
      </div>
      <div>
        <div style="color:#1e1e38;font-size:.58em;text-transform:uppercase;font-weight:700">Por operación</div>
        <div style="color:#ffd600;font-size:.88em;font-weight:700">${per_trade:.2f} <span style="color:#2a2a4a;font-weight:400">({pct}%)</span></div>
      </div>
      <div>
        <div style="color:#1e1e38;font-size:.58em;text-transform:uppercase;font-weight:700">Meta día</div>
        <div style="color:#00e676;font-size:.88em;font-weight:700">+${goal_amt:.2f}</div>
      </div>
      <div>
        <div style="color:#1e1e38;font-size:.58em;text-transform:uppercase;font-weight:700">Stop día</div>
        <div style="color:#ff5252;font-size:.88em;font-weight:700">-${stop_amt:.2f}</div>
      </div>
      <div>
        <div style="color:#1e1e38;font-size:.58em;text-transform:uppercase;font-weight:700">P&amp;L hoy</div>
        <div style="color:{pnl_color};font-size:.88em;font-weight:700">{pnl_sign}${abs(pnl):.2f}</div>
      </div>
    </div>

    <!-- Estado de sesión -->
    <div style="text-align:right">
      <div style="color:{'#00e676' if ok else '#ff5252'};font-size:.82em;font-weight:700">{_he(msg)}</div>
      <div style="color:#1e1e38;font-size:.63em;margin-top:2px">
        {trades} operaciones hoy &nbsp;·&nbsp; {remaining} restantes
      </div>
    </div>

  </div>
  {prog_bar_html}
</div>""", unsafe_allow_html=True)

    if not ok:
        st.warning(f"🛑 {msg} — Sesión bloqueada para proteger tu capital. Ajusta el plan en el panel lateral o reinicia mañana.")

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════
def _sidebar(ev):
    with st.sidebar:
        st.markdown('<div style="color:#00e676;font-size:1em;font-weight:900;margin-bottom:10px">📊 RAVEN BINARY</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div style="color:#555;font-size:.72em">Score mínimo: <b style="color:#ffd600">{MIN_PROB}%</b></div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div style="color:#555;font-size:.72em">Actualiza cada <b>{REFRESH}s</b></div>',
                    unsafe_allow_html=True)

        # ── PLAN DE TRADING ─────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div style="color:#ffd600;font-size:.8em;font-weight:700;margin-bottom:6px">💰 PLAN DE TRADING</div>',
                    unsafe_allow_html=True)
        rm = _load_rm()
        capital       = st.number_input("Capital ($)", min_value=10, max_value=1_000_000,
                                         value=int(rm["capital"]), step=50, key="rm_cap")
        pct_trade     = st.slider("Riesgo por operación (%)", 1, 10,
                                   int(rm["pct_trade"]), key="rm_pct")
        max_loss_pct  = st.slider("Pérdida máx. diaria (%)", 2, 30,
                                   int(rm["max_loss_pct"]), key="rm_loss")
        profit_goal   = st.slider("Meta de ganancia diaria (%)", 1, 30,
                                   int(rm["profit_goal_pct"]), key="rm_goal")
        max_trades    = st.number_input("Máx. operaciones/día", 1, 100,
                                         int(rm["max_trades"]), step=1, key="rm_maxt")

        if st.button("💾 Guardar plan", key="rm_save"):
            new_rm = {"capital":capital,"pct_trade":pct_trade,
                      "max_loss_pct":max_loss_pct,"profit_goal_pct":profit_goal,
                      "max_trades":max_trades}
            _save_rm(new_rm)
            st.success("Plan guardado ✅")

        per_t = round(capital * pct_trade / 100, 2)
        stop_ = round(capital * max_loss_pct / 100, 2)
        goal_ = round(capital * profit_goal  / 100, 2)
        st.markdown(f"""
<div style="background:#0a0a18;border-radius:7px;padding:.5rem .8rem;margin-top:5px">
  <div style="color:#1a1a30;font-size:.6em;font-weight:700;text-transform:uppercase;margin-bottom:3px">Resumen</div>
  <div style="color:#ffd600;font-size:.75em">Por operación: <b>${per_t:.2f}</b></div>
  <div style="color:#00e676;font-size:.75em">Meta del día: <b>+${goal_:.2f}</b></div>
  <div style="color:#ff5252;font-size:.75em">Stop del día: <b>-${stop_:.2f}</b></div>
</div>""", unsafe_allow_html=True)

        # ── TELEGRAM ────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div style="color:#42a5f5;font-size:.78em;font-weight:700;margin-bottom:5px">📱 TELEGRAM</div>',
                    unsafe_allow_html=True)
        cfg = _load_cfg()
        tok = st.text_input("Token del bot", value=cfg.get("tg_token",""), type="password", key="btok")
        cid = st.text_input("Chat ID",       value=cfg.get("tg_chatid",""), key="bcid")
        c1,c2 = st.columns(2)
        with c1:
            if st.button("💾 Guardar", key="bsave"):
                cfg["tg_token"]=tok.strip(); cfg["tg_chatid"]=cid.strip()
                _save_cfg(cfg); st.success("OK")
        with c2:
            if st.button("🧪 Test", key="btest"):
                cfg["tg_token"]=tok.strip(); cfg["tg_chatid"]=cid.strip()
                _save_cfg(cfg)
                _tg("📊 <b>RAVEN BINARY</b> — Conexión OK ✅")
                st.success("Enviado")

        # ── NOTICIAS ────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div style="color:#ff5252;font-size:.78em;font-weight:700;margin-bottom:5px">📰 Noticias activas</div>',
                    unsafe_allow_html=True)
        now = datetime.now(timezone.utc)
        shown = 0
        for e in ev[:8]:
            d = (e["dt"]-now).total_seconds()/60
            if abs(d) > 180: continue
            c = "#ff5252" if abs(d)<30 else ("#ff9800" if d<60 else "#333")
            st.markdown(
                f'<div style="color:{c};font-size:.68em;padding:2px 0">'
                f'{e.get("moneda","")} · {e["titulo"][:28]} '
                f'{"+" if d>0 else ""}{int(d)}m</div>',
                unsafe_allow_html=True
            )
            shown += 1
        if shown == 0:
            st.markdown('<div style="color:#1a1a30;font-size:.7em">Sin noticias próximas</div>',
                        unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🗑 Borrar historial", key="bclr"):
            _save_results([])
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════
def main():
    ev = _fetch_news()
    _sidebar(ev)

    rm        = _load_rm()
    real_open = _real_open()
    hora_utc  = datetime.now(timezone.utc).strftime("%H:%M UTC")

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#06060d,#0c0a12);
  border:1px solid #1a1230;border-radius:12px;padding:.8rem 1.4rem;
  margin-bottom:.5rem;display:flex;align-items:center;justify-content:space-between">
  <div>
    <div style="color:#00e676;font-size:1.3em;font-weight:900">📊 RAVEN BINARY OPTIONS</div>
    <div style="color:#1e1e2e;font-size:.78em;margin-top:1px">
      Forex Real &amp; OTC · CALL/PUT · 1min y 5min · IQ Option · Quotex
    </div>
  </div>
  <div style="text-align:right">
    <div style="color:{'#00e676' if real_open else '#ab47bc'};font-size:.85em;font-weight:700">
      {'🌐 MERCADO ABIERTO' if real_open else '📴 MERCADO CERRADO — OTC ACTIVO'}
    </div>
    <div style="color:#1a1a30;font-size:.7em">{hora_utc}</div>
  </div>
</div>""", unsafe_allow_html=True)

    _render_plan_panel(rm)
    _render_stats_panel()

    tab_real, tab_otc = st.tabs(["🌐 FOREX REAL","📴 OTC (24/7)"])

    # ── FOREX REAL ──────────────────────────────────────────────────────
    with tab_real:
        if not real_open:
            st.markdown("""
<div style="background:#080810;border:1px solid #1a1a30;border-radius:10px;
  padding:1.2rem;text-align:center;color:#555;margin:.5rem 0">
  <div style="font-size:1em;font-weight:700;margin-bottom:4px">⛔ Mercado Forex cerrado</div>
  <div style="font-size:.8em">Lunes a viernes 00:00–21:50 UTC</div>
  <div style="color:#ab47bc;font-size:.8em;margin-top:4px">→ Usa la pestaña OTC para operar ahora</div>
</div>""", unsafe_allow_html=True)
        else:
            pairs = list(REAL_PAIRS.items())
            col1, col2 = st.columns(2)
            for i, (pair, (yticker, label)) in enumerate(pairs):
                with (col1 if i%2==0 else col2):
                    try:
                        _render_pair_card(pair, label, yticker, ev, is_otc=False, rm=rm)
                    except Exception as ex:
                        st.error(f"{pair}: {ex}")

    # ── OTC ─────────────────────────────────────────────────────────────
    with tab_otc:
        st.markdown("""
<div style="background:#0d0814;border:1px solid #1a1230;border-radius:8px;
  padding:.5rem 1rem;margin-bottom:.5rem;font-size:.75em">
  <span style="color:#ab47bc;font-weight:700">📴 OTC</span>
  <span style="color:#252535"> — Disponible 24/7. Usa estos pares cuando el mercado real está cerrado.
  Los precios son de mercado real (proxy). Puede haber pequeñas diferencias con tu broker.</span>
</div>""", unsafe_allow_html=True)

        pairs_otc = list(OTC_PAIRS.items())
        col1, col2 = st.columns(2)
        for i, (pair, (yticker, label)) in enumerate(pairs_otc):
            with (col1 if i%2==0 else col2):
                try:
                    _render_pair_card(pair, label, yticker, ev, is_otc=True, rm=rm)
                except Exception as ex:
                    st.error(f"{pair}: {ex}")

    st.markdown("""
<div style="color:#0a0a14;font-size:.65em;text-align:center;margin-top:1rem;
  padding-top:.5rem;border-top:1px solid #080810">
  RAVEN BINARY · Solo educativo · Las opciones binarias implican riesgo de pérdida total
</div>""", unsafe_allow_html=True)

    _stc.html(
        f'<script>setTimeout(function(){{window.parent.location.reload();}},{REFRESH*1000});</script>',
        height=0
    )

if __name__ == "__main__":
    main()
