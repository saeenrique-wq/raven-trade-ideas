# raven_pro.py  ·  RAVEN TRADE IDEAS PRO
# Scanner unificado: ORO · ÍNDICES · FOREX · MATERIAS · CRYPTO · WELTRADE
# Una señal por activo · Máquina de estados · Score 100pts · MTF · Telegram

import streamlit as st
import streamlit.components.v1 as _stc
import pandas as pd
import numpy as np
import requests, json, os, time, traceback
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from ta.trend     import EMAIndicator, MACD, ADXIndicator
from ta.momentum  import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange

try:
    import MetaTrader5 as _mt5lib
    _MT5 = True
except Exception:
    _MT5 = False

try:
    import yfinance as yf
    _YF = True
except ImportError:
    _YF = False

# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════
MIN_SCORE_SHOW   = 70
MIN_SCORE_ENTRY  = 80
LATE_PULLBACK    = 0.35
LATE_CANCEL      = 0.62
COOLDOWN_MIN     = 15
REFRESH          = 45
STATE_FILE       = r"C:\Users\saems\raven_pro_state.json"
CFG_FILE         = r"C:\Users\saems\raven_pro_cfg.json"

# ═══════════════════════════════════════════════════════════════════════
# MERCADOS
# ═══════════════════════════════════════════════════════════════════════
# key → (yahoo_ticker, label, decimals, pip_value, is_gold)
MDEF = {
    "XAUUSD": ("GC=F",     "🥇 Oro XAUUSD",   2, 10,  True),
    "US30":   ("^DJI",     "📈 Dow Jones",     0,  1,  False),
    "US100":  ("^IXIC",    "📊 NASDAQ",        0,  1,  False),
    "SPX500": ("^GSPC",    "📉 S&P 500",       0,  1,  False),
    "GER40":  ("^GDAXI",   "🇩🇪 DAX",          0,  1,  False),
    "UK100":  ("^FTSE",    "🇬🇧 FTSE 100",     0,  1,  False),
    "EURUSD": ("EURUSD=X", "💶 EUR/USD",       5, 10,  False),
    "GBPUSD": ("GBPUSD=X", "💷 GBP/USD",       5, 10,  False),
    "USDJPY": ("USDJPY=X", "🇯🇵 USD/JPY",      3,  7,  False),
    "AUDUSD": ("AUDUSD=X", "🦘 AUD/USD",       5, 10,  False),
    "USDCAD": ("USDCAD=X", "🍁 USD/CAD",       5, 10,  False),
    "USDMXN": ("MXN=X",    "🇲🇽 USD/MXN",      4,  1,  False),
    "XAGUSD": ("SI=F",     "🥈 Plata",         3,  5,  False),
    "WTIUSD": ("CL=F",     "🛢️ Petróleo WTI",  2, 10,  False),
    "BTCUSD": ("BTC-USD",  "₿ Bitcoin",        0,  1,  False),
    "ETHUSD": ("ETH-USD",  "Ξ Ethereum",       2,  1,  False),
    "SOLUSD": ("SOL-USD",  "◎ Solana",         2,  1,  False),
    "XRPUSD": ("XRP-USD",  "⬡ XRP",            4,  1,  False),
    "BNBUSD": ("BNB-USD",  "🔵 BNB",           2,  1,  False),
}

TABS_DEF = {
    "🥇 ORO":      ["XAUUSD"],
    "📈 ÍNDICES":  ["US30","US100","SPX500","GER40","UK100"],
    "💱 FOREX":    ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDMXN"],
    "🛢️ MATERIAS": ["XAGUSD","WTIUSD"],
    "₿ CRYPTO":   ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD"],
    "⚡ WELTRADE": [],   # llenado dinámicamente desde MT5
}

# Horarios UTC por categoría
def mercado_abierto(key):
    now = datetime.now(timezone.utc)
    wd = now.weekday(); h = now.hour + now.minute/60
    if wd >= 5:
        return False, "⛔ Cerrado (fin de semana)"
    if key in ("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDMXN"):
        if wd == 4 and h >= 21.83:
            return False, "⛔ Forex cerrado"
        return True, "🟢 Forex abierto"
    if key in ("XAUUSD","XAGUSD","WTIUSD"):
        if 21.75 <= h < 23.0:
            return False, "⏸️ Pausa mantenimiento"
        return True, "🟢 Commodities abierto"
    if key in ("US30","US100","SPX500"):
        if 13.5 <= h < 20.0:
            return True, "🟢 Bolsa US abierta"
        return False, f"⛔ Bolsa US cerrada"
    if key == "GER40":
        return (True,"🟢 DAX abierto") if 7.0 <= h < 17.5 else (False,"⛔ DAX cerrado")
    if key == "UK100":
        return (True,"🟢 FTSE abierto") if 8.0 <= h < 16.5 else (False,"⛔ FTSE cerrado")
    if key in ("BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD"):
        return True, "🟢 Crypto 24/7"
    return True, "🟢 Abierto"

# ═══════════════════════════════════════════════════════════════════════
# ESTADOS
# ═══════════════════════════════════════════════════════════════════════
_SC = {
    "BUSCANDO_SETUP":     ("🔍","SIN SEÑAL — analizando...",     "#555555","#08080e"),
    "IDEA_EN_FORMACION":  ("🟡","SEÑAL FORMÁNDOSE — espera",     "#ffd600","#100e00"),
    "ESPERANDO_PULLBACK": ("⏳","ESPERA RETROCESO al precio",    "#ff9800","#100800"),
    "ENTRADA_VALIDA":     ("🟢","¡ENTRA AHORA!",                 "#00e676","#001410"),
    "EN_OPERACION":       ("🔵","EN OPERACIÓN — gestiona SL/TPs","#42a5f5","#001020"),
    "TP1_ALCANZADO":      ("✅","TP1 LOGRADO — mueve SL",        "#69f0ae","#001a0c"),
    "TP2_ALCANZADO":      ("✅","TP2 LOGRADO — deja correr",     "#00e676","#002014"),
    "TP3_ALCANZADO":      ("🏆","¡OBJETIVO COMPLETO! Cierra",    "#ffd600","#141000"),
    "STOP_LOSS":          ("❌","STOP ALCANZADO — nueva señal",  "#ff5252","#180000"),
    "INVALIDADA":         ("⛔","SEÑAL CANCELADA",               "#ff5252","#120000"),
    "CANCELAR_IDEA":      ("🚫","MUY TARDE — espera otra",       "#ff9800","#100800"),
}
_ACCION = {
    "BUSCANDO_SETUP":     "Sin setup válido ahora mismo. El scanner sigue buscando.",
    "IDEA_EN_FORMACION":  "La señal se está formando. Espera más confirmación antes de entrar.",
    "ESPERANDO_PULLBACK": "El precio avanzó. Espera que regrese al punto de entrada original.",
    "ENTRADA_VALIDA":     "🟢 El precio está en zona de entrada. Puedes ejecutar la operación.",
    "EN_OPERACION":       "Trade abierto. Mantén el SL y sigue los TPs. No muevas el SL hacia abajo.",
    "TP1_ALCANZADO":      "¡Primer objetivo! Mueve el SL a tu precio de entrada (breakeven).",
    "TP2_ALCANZADO":      "¡Segundo objetivo! Mueve el SL al TP1. Deja el resto correr hacia TP3.",
    "TP3_ALCANZADO":      "¡Objetivo máximo logrado! Cierra toda la posición.",
    "STOP_LOSS":          "El trade fue en contra. Cierra y espera una nueva señal del scanner.",
    "INVALIDADA":         "La dirección del mercado cambió. Esta señal ya no es válida.",
    "CANCELAR_IDEA":      "El movimiento ya ocurrió. Demasiado tarde para entrar. Espera otra.",
}
_PUEDE_ENTRAR_TARDE = {
    "EN_OPERACION": "⚠️ Trade activo. Si quieres seguirlo: usa el mismo SL y solo TP2 como objetivo.",
    "TP1_ALCANZADO": "⚠️ TP1 logrado. Puedes entrar solo si hay pullback al nivel de entrada con nuevo setup.",
}
_CLOSED = {"STOP_LOSS","TP3_ALCANZADO","INVALIDADA","CANCELAR_IDEA"}

# ═══════════════════════════════════════════════════════════════════════
# PÁGINA + CSS
# ═══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="RAVEN TRADE IDEAS PRO",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#06060e}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#080810}
.block-container{padding:.6rem 1.4rem;max-width:1200px}
.stTabs [data-baseweb="tab-list"]{background:#0a0a16;border-radius:8px;padding:4px;gap:3px}
.stTabs [data-baseweb="tab"]{background:transparent;color:#444;border-radius:6px;
  padding:7px 16px;font-weight:700;font-size:.78em;text-transform:uppercase;letter-spacing:1.5px}
.stTabs [aria-selected="true"]{background:#14142a;color:#d8d8f8}
div[data-testid="stButton"]>button{background:#12121e;color:#888;border:1px solid #1e1e32;
  border-radius:6px;font-size:.8em;padding:4px 12px}
div[data-testid="metric-container"]{background:#08080f;border:1px solid #12122a;border-radius:8px;padding:7px 11px}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# PERSISTENCIA + CONFIG
# ═══════════════════════════════════════════════════════════════════════
def _load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_state(data):
    try:
        with open(STATE_FILE,"w",encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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

def _get_ast(sym):
    return _load_state().get(sym, {"signal":None,"closed_at":None,"cooldown_until":None})

def _set_ast(sym, data):
    st_data = _load_state()
    st_data[sym] = data
    _save_state(st_data)

def _log_change(sig, new_state, msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
    sig.setdefault("log",[]).append({"ts":ts,"state":new_state,"msg":msg})
    sig["state"] = new_state
    sig["updated_at"] = datetime.now(timezone.utc).isoformat()
    return sig

# ═══════════════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════════════
def _tg_send(msg):
    cfg = _load_cfg()
    tok = cfg.get("tg_token","").strip()
    cid = cfg.get("tg_chatid","").strip()
    if not tok or not cid:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            json={"chat_id": cid, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except Exception:
        pass

def _tg_signal(sym, sig):
    state = sig.get("state","")
    ic, lbl, col, _ = _SC.get(state, _SC["BUSCANDO_SETUP"])
    d = sig.get("dir","buy")
    entry = sig.get("entry",0)
    sl = sig.get("sl",0)
    tp1 = sig.get("tp1",0)
    tp2 = sig.get("tp2",0)
    tp3 = sig.get("tp3",0)
    score = sig.get("score",0)
    arrow = "▲ COMPRA" if d=="buy" else "▼ VENTA"
    msg = (
        f"{ic} <b>RAVEN PRO · {sym}</b>\n"
        f"Estado: <b>{lbl}</b>\n"
        f"Dirección: <b>{arrow}</b>\n"
        f"Score: <b>{score}/100</b>\n\n"
        f"📍 Entrada: <b>{entry:.4f}</b>\n"
        f"🛑 Stop Loss: <b>{sl:.4f}</b>\n"
        f"🎯 TP1: <b>{tp1:.4f}</b>\n"
        f"🎯 TP2: <b>{tp2:.4f}</b>\n"
        f"🎯 TP3: <b>{tp3:.4f}</b>\n\n"
        f"Estrategia: {sig.get('estrategia','')}\n"
        f"{sig.get('tipo_razon','')}"
    )
    _tg_send(msg)

# ═══════════════════════════════════════════════════════════════════════
# DATOS — Yahoo Finance v8 (directo) + MT5
# ═══════════════════════════════════════════════════════════════════════
_YF_TF = {
    "M5":"5m","M15":"15m","H1":"1h","H4":"1h",  # H4 = resample H1
}
_YF_PERIOD = {
    "M5":"5d","M15":"5d","H1":"60d","H4":"60d",
}

@st.cache_data(ttl=30, show_spinner=False)
def _yf_v8(yticker, interval, period):
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yticker}"
        r = requests.get(url, params={"interval":interval,"range":period},
                        timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code != 200:
            return None
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
        return None

@st.cache_data(ttl=30, show_spinner=False)
def _yf_fallback(yticker, interval, period):
    if not _YF:
        return None
    try:
        df = yf.Ticker(yticker).history(interval=interval, period=period)
        if df is None or df.empty:
            return None
        df.columns = [c.lower() for c in df.columns]
        df.index = pd.to_datetime(df.index, utc=True)
        return df[["open","high","low","close","volume"]].dropna()
    except Exception:
        return None

def _get_bars(yticker, tf_key, n=300):
    iv = _YF_TF.get(tf_key,"15m")
    pd_ = _YF_PERIOD.get(tf_key,"5d")
    df = _yf_v8(yticker, iv, pd_)
    if df is None or len(df) < 20:
        df = _yf_fallback(yticker, iv, pd_)
    if df is None or len(df) < 20:
        return None
    if tf_key == "H4":
        agg_cols = {c: ("first" if c=="open" else "max" if c=="high" else
                        "min" if c=="low" else "last" if c=="close" else "sum")
                    for c in ["open","high","low","close","volume"] if c in df.columns}
        df = df.resample("4h").agg(agg_cols).dropna()
    return df.tail(n) if df is not None and len(df) > 0 else None

@st.cache_data(ttl=20, show_spinner=False)
def _live_price(yticker):
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yticker}"
        r = requests.get(url, params={"interval":"1m","range":"1d"},
                        timeout=5, headers={"User-Agent":"Mozilla/5.0"})
        d = r.json()["chart"]["result"][0]["meta"]
        p = d.get("regularMarketPrice") or d.get("previousClose",0)
        return float(p) if p else None
    except Exception:
        pass
    if _YF:
        try:
            p = yf.Ticker(yticker).fast_info.last_price
            return float(p) if p and p > 0 else None
        except Exception:
            pass
    return None

# MT5 helpers
@st.cache_resource
def _mt5_init():
    if not _MT5:
        return False
    try:
        return _mt5lib.initialize()
    except Exception:
        return False

def _mt5_price(sym):
    if not _mt5_init():
        return None
    try:
        _mt5lib.symbol_select(sym, True)
        tick = _mt5lib.symbol_info_tick(sym)
        if tick and tick.bid > 0:
            return (tick.bid + tick.ask) / 2
    except Exception:
        pass
    return None

def _mt5_bars(sym, tf_key, n=300):
    if not _mt5_init():
        return None
    TF_MAP = {"M5":_mt5lib.TIMEFRAME_M5,"M15":_mt5lib.TIMEFRAME_M15,
              "H1":_mt5lib.TIMEFRAME_H1,"H4":_mt5lib.TIMEFRAME_H4}
    tf = TF_MAP.get(tf_key)
    if tf is None:
        return None
    try:
        _mt5lib.symbol_select(sym, True)
        r = _mt5lib.copy_rates_from_pos(sym, tf, 0, n)
        if r is None or len(r) < 20:
            return None
        df = pd.DataFrame(r)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time")
        df = df.rename(columns={"tick_volume":"volume"})
        return df[["open","high","low","close","volume"]]
    except Exception:
        return None

# Función unificada de datos para un activo
def _fetch_all(sym_key):
    yft, label, dec, pp, is_gold = MDEF.get(sym_key, ("","","",1,False))

    # Precio live
    mt5_sym = None
    if _mt5_init():
        # Intentar encontrar símbolo en MT5
        try:
            syms = [s.name for s in (_mt5lib.symbols_get() or [])]
            cands = [sym_key, sym_key+".","{}m".format(sym_key)]
            for c in cands:
                if c in syms:
                    mt5_sym = c
                    break
        except Exception:
            pass

    if mt5_sym:
        price = _mt5_price(mt5_sym)
        src = "MT5"
    else:
        price = _live_price(yft)
        src = "Yahoo"

    if not price:
        return None, None, None, None, None

    # Barras
    def _pick(mt5_df, yf_df):
        if mt5_df is not None and len(mt5_df) >= 20:
            return mt5_df
        return yf_df

    if mt5_sym:
        df_m5  = _pick(_mt5_bars(mt5_sym,"M5"),  _get_bars(yft,"M5"))
        df_m15 = _pick(_mt5_bars(mt5_sym,"M15"), _get_bars(yft,"M15"))
        df_h1  = _pick(_mt5_bars(mt5_sym,"H1"),  _get_bars(yft,"H1"))
        df_h4  = _pick(_mt5_bars(mt5_sym,"H4"),  _get_bars(yft,"H4"))
    else:
        df_m5  = _get_bars(yft,"M5")
        df_m15 = _get_bars(yft,"M15")
        df_h1  = _get_bars(yft,"H1")
        df_h4  = _get_bars(yft,"H4")

    return price, src, df_m5, df_m15, df_h1, df_h4

# ═══════════════════════════════════════════════════════════════════════
# INDICADORES (ta library)
# ═══════════════════════════════════════════════════════════════════════
def _ind(df):
    if df is None or len(df) < 22:
        return None
    try:
        # normalizar columnas
        cols = {c.lower(): c for c in df.columns}
        c = df[cols.get("close","close")].astype(float)
        h = df[cols.get("high","high")].astype(float)
        l = df[cols.get("low","low")].astype(float)
        o = df[cols.get("open","open")].astype(float)
        n = len(c)

        e9  = EMAIndicator(c, min(9,n-1)).ema_indicator()
        e20 = EMAIndicator(c, min(20,n-1)).ema_indicator()
        e50 = EMAIndicator(c, min(50,n-1)).ema_indicator()
        e200= EMAIndicator(c, min(200,n-1)).ema_indicator()
        rsi = RSIIndicator(c, min(14,n-1)).rsi()
        macd_o = MACD(c)
        bb  = BollingerBands(c, min(20,n-1), 2)
        atr = AverageTrueRange(h, l, c, min(14,n-1)).average_true_range()
        adx_o = ADXIndicator(h, l, c, min(14,n-1))

        return {
            "price": float(c.iloc[-1]),
            "rsi":   float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50,
            "macd_h":float(macd_o.macd_diff().iloc[-1]),
            "bb_hi": float(bb.bollinger_hband().iloc[-1]),
            "bb_lo": float(bb.bollinger_lband().iloc[-1]),
            "bb_mid":float(bb.bollinger_mavg().iloc[-1]),
            "e9":    float(e9.iloc[-1]),
            "e9p":   float(e9.iloc[-2]) if n>2 else float(e9.iloc[-1]),
            "e20":   float(e20.iloc[-1]),
            "e50":   float(e50.iloc[-1]),
            "e200":  float(e200.iloc[-1]),
            "atr":   float(atr.iloc[-1]),
            "atr_avg":float(atr.iloc[-20:].mean()) if n>=20 else float(atr.iloc[-1]),
            "adx":   float(adx_o.adx().iloc[-1]),
            "adx_p": float(adx_o.adx_pos().iloc[-1]),
            "adx_m": float(adx_o.adx_neg().iloc[-1]),
            "o":float(o.iloc[-1]),"h":float(h.iloc[-1]),
            "l":float(l.iloc[-1]),"c":float(c.iloc[-1]),
            "o2":float(o.iloc[-2]),"h2":float(h.iloc[-2]),
            "l2":float(l.iloc[-2]),"c2":float(c.iloc[-2]),
        }
    except Exception:
        return None

def _mtf_ctx(im5, im15, ih1, ih4):
    def _tf(ind, fast_k, slow_k):
        if not ind:
            return {"label":"Sin datos","color":"#252535","bull":0,"bear":0,"rsi":50}
        ef = ind.get(fast_k, ind["price"])
        es = ind.get(slow_k, ind["price"])
        p  = ind["price"]
        rsi= ind.get("rsi",50)
        if   p>ef>es: return {"label":"▲ ALCISTA","color":"#00e676","bull":1,"bear":0,"rsi":rsi}
        elif p<ef<es: return {"label":"▼ BAJISTA","color":"#ff5252","bull":0,"bear":1,"rsi":rsi}
        elif ef>es:   return {"label":"↗ NEUTRAL+","color":"#ffd600","bull":0.5,"bear":0,"rsi":rsi}
        else:         return {"label":"↘ NEUTRAL−","color":"#ff9800","bull":0,"bear":0.5,"rsi":rsi}
    return {
        "H4":  _tf(ih4,  "e20","e50"),
        "H1":  _tf(ih1,  "e20","e50"),
        "M15": _tf(im15, "e9","e20"),
        "M5":  _tf(im5,  "e9","e20"),
    }

# ═══════════════════════════════════════════════════════════════════════
# RIESGO
# ═══════════════════════════════════════════════════════════════════════
def _risk(entry, sl, direction, pp=10):
    d = abs(entry - sl)
    if d < 0.00001:
        return None
    s = 1 if direction == "buy" else -1
    return dict(
        sl_d=d,
        tp1=entry+s*d*1.5, rr1=1.5, g1=d*1.5*pp,
        tp2=entry+s*d*2.5, rr2=2.5, g2=d*2.5*pp,
        tp3=entry+s*d*4.0, rr3=4.0, g3=d*4.0*pp,
        tp4=entry+s*d*6.0, rr4=6.0, g4=d*6.0*pp,
        riesgo=d*pp,
    )

def _fmt(v, dec=2):
    return f"{v:,.{dec}f}"

def _he(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _entry_type(d, precio, entry):
    """Detecta si la orden es LIMIT, STOP o MARKET."""
    if not entry or entry <= 0: return "MARKET"
    diff = abs(precio - entry) / entry
    if diff < 0.0005: return "MARKET"
    if d == "buy":
        return "LIMIT" if precio > entry else "STOP"
    else:
        return "LIMIT" if precio < entry else "STOP"

# ═══════════════════════════════════════════════════════════════════════
# INDICADORES AUXILIARES (para estrategias)
# ═══════════════════════════════════════════════════════════════════════
def _ema_s(s, n):
    return s.ewm(span=n, adjust=False).mean()

def _atr_s(df, n=14):
    h,l,c = df.high,df.low,df.close
    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

def _rsi_s(s, n=14):
    d = s.diff()
    g = d.where(d>0,0).rolling(n).mean()
    lo= (-d.where(d<0,0)).rolling(n).mean()
    return 100 - 100/(1+g/lo.replace(0,np.nan))

def _swing_lows(df, n=3):
    return [i for i in range(n,len(df)-n)
            if df.low.iloc[i]==df.low.iloc[i-n:i+n+1].min()]

def _swing_highs(df, n=3):
    return [i for i in range(n,len(df)-n)
            if df.high.iloc[i]==df.high.iloc[i-n:i+n+1].max()]

def _norm_df(df):
    """Normaliza columnas a minúsculas."""
    if df is None: return None
    df2 = df.copy()
    df2.columns = [c.lower() for c in df2.columns]
    return df2

# ═══════════════════════════════════════════════════════════════════════
# ESTRATEGIAS
# ═══════════════════════════════════════════════════════════════════════
def strat_london_breakout(df_h1, precio, is_gold):
    if not is_gold: return None
    df_h1 = _norm_df(df_h1)
    if df_h1 is None or len(df_h1)<10: return None
    ahora = datetime.now(timezone.utc); h=ahora.hour
    if not (7<=h<10): return None
    hoy = ahora.replace(hour=0,minute=0,second=0,microsecond=0)
    asian = df_h1[(df_h1.index>=hoy)&(df_h1.index<hoy.replace(hour=7))]
    if len(asian)<3: return None
    a_hi=asian.high.max(); a_lo=asian.low.min(); a_rng=a_hi-a_lo
    if a_rng<5: return None
    at=_atr_s(df_h1).iloc[-1]; thr=a_rng*0.12
    for direction,cond,sl_ref in [
        ("buy", precio>a_hi+thr, a_lo-at*0.5),
        ("sell",precio<a_lo-thr, a_hi+at*0.5),
    ]:
        if not cond: continue
        r=_risk(precio,sl_ref,direction)
        if r is None: continue
        sc=60
        ld=df_h1[df_h1.index>=hoy.replace(hour=7)]
        breaks=(ld.high>a_hi).sum() if direction=="buy" else (ld.low<a_lo).sum()
        if breaks<=1: sc+=10
        if at>_atr_s(df_h1).rolling(20).mean().iloc[-1]*1.1: sc+=8
        return dict(estrategia="LONDON BREAKOUT",icon="🇬🇧",dir=direction,tipo="INTRADAY",
                    dur="~1-4h",entry=precio,sl=sl_ref,score_base=min(sc,88),
                    ctx=f"Rango asiático {a_lo:.2f}-{a_hi:.2f} ({a_rng:.1f} pts)",**r)
    return None

def strat_trend_pullback(df_d1, df_h4, df_h1, df_m15, precio):
    df_h1=_norm_df(df_h1); df_h4=_norm_df(df_h4)
    df_d1=_norm_df(df_d1); df_m15=_norm_df(df_m15)
    for df,n in [(df_h1,60),(df_h4,50),(df_m15,20)]:
        if df is None or len(df)<n: return None
    e20h=_ema_s(df_h1.close,20).iloc[-1]; e50h=_ema_s(df_h1.close,50).iloc[-1]
    e20h4=_ema_s(df_h4.close,20).iloc[-1]; e50h4=_ema_s(df_h4.close,50).iloc[-1]
    at=_atr_s(df_h1).iloc[-1]; rs=_rsi_s(df_m15.close).iloc[-1]
    h1b=e20h>e50h; h4b=e20h4>e50h4; h1s=e20h<e50h; h4s=e20h4<e50h4
    bull=sum([h1b,h4b]); bear=sum([h1s,h4s])
    if bull<2 and bear<2: return None
    direction="buy" if bull>=bear else "sell"
    if direction=="buy":
        if not (-at*0.9<=precio-e20h<=at*0.4): return None
        if not (35<=rs<=58): return None
        sl=e50h-at*0.3; sc=65+bull*8+(5 if 40<=rs<=50 else 0)
    else:
        if not (-at*0.9<=e20h-precio<=at*0.4): return None
        if not (42<=rs<=65): return None
        sl=e50h+at*0.3; sc=65+bear*8+(5 if 50<=rs<=60 else 0)
    r=_risk(precio,sl,direction)
    if r is None: return None
    return dict(estrategia="PULLBACK TENDENCIA",icon="📐",dir=direction,tipo="SWING",
                dur="~4-24h",entry=precio,sl=sl,score_base=min(sc,92),
                ctx=f"H4:{'▲' if h4b else '▼'} H1:{'▲' if h1b else '▼'} RSI M15:{rs:.0f}",**r)

def strat_ema_momentum(df_h1, df_m15, precio):
    df_h1=_norm_df(df_h1); df_m15=_norm_df(df_m15)
    if df_h1 is None or len(df_h1)<30 or df_m15 is None or len(df_m15)<20: return None
    e9=_ema_s(df_h1.close,9); e21=_ema_s(df_h1.close,21); e50=_ema_s(df_h1.close,50)
    at=_atr_s(df_h1).iloc[-1]; at_avg=_atr_s(df_h1).rolling(20).mean().iloc[-1]
    if at<at_avg*0.65: return None
    rh=_rsi_s(df_h1.close).iloc[-1]; rm=_rsi_s(df_m15.close).iloc[-1]
    cb=e9.iloc[-2]<e21.iloc[-2] and e9.iloc[-1]>e21.iloc[-1]
    cs=e9.iloc[-2]>e21.iloc[-2] and e9.iloc[-1]<e21.iloc[-1]
    if not cb and not cs:
        cb=e9.iloc[-3]<e21.iloc[-3] and e9.iloc[-2]>e21.iloc[-2] and precio>e9.iloc[-1]
        cs=e9.iloc[-3]>e21.iloc[-3] and e9.iloc[-2]<e21.iloc[-2] and precio<e9.iloc[-1]
    if not cb and not cs: return None
    if cb and 48<=rh<=72 and precio>e21.iloc[-1]*0.998:
        sl=e21.iloc[-1]-at*0.5; r=_risk(precio,sl,"buy")
        if r is None: return None
        sc=63+(8 if precio>e50.iloc[-1] else 0)+(5 if 52<rh<65 else 0)+(4 if 52<rm<65 else 0)
        return dict(estrategia="CRUCE EMA MOMENTUM",icon="⚡",dir="buy",tipo="INTRADAY",
                    dur="~1-4h",entry=precio,sl=sl,score_base=min(sc,85),
                    ctx=f"Cruce EMA9/21 H1 ↑ RSI:{rh:.0f} M15:{rm:.0f}",**r)
    if cs and 28<=rh<=52 and precio<e21.iloc[-1]*1.002:
        sl=e21.iloc[-1]+at*0.5; r=_risk(precio,sl,"sell")
        if r is None: return None
        sc=63+(8 if precio<e50.iloc[-1] else 0)+(5 if 35<rh<48 else 0)+(4 if 35<rm<48 else 0)
        return dict(estrategia="CRUCE EMA MOMENTUM",icon="⚡",dir="sell",tipo="INTRADAY",
                    dur="~1-4h",entry=precio,sl=sl,score_base=min(sc,85),
                    ctx=f"Cruce EMA9/21 H1 ↓ RSI:{rh:.0f} M15:{rm:.0f}",**r)
    return None

def strat_supply_demand(df_h4, df_h1, precio):
    df_h4=_norm_df(df_h4); df_h1=_norm_df(df_h1)
    if df_h4 is None or len(df_h4)<50 or df_h1 is None or len(df_h1)<20: return None
    at4=_atr_s(df_h4).iloc[-1]; rh=_rsi_s(df_h1.close).iloc[-1]
    for idx in _swing_lows(df_h4,n=4)[-8:]:
        z=df_h4.low.iloc[idx]; zt,zb=z+at4,z-at4*0.3
        if zb<=precio<=zt and rh<45:
            sl=z-at4*0.45; r=_risk(precio,sl,"buy")
            if r is None: continue
            tests=sum(1 for i in range(len(df_h4)) if zb<=df_h4.low.iloc[i]<=zt)
            sc=66+(10 if tests<=2 else 0)+(10 if rh<35 else 0)
            return dict(estrategia="ZONA DEMANDA S&D",icon="🏛️",dir="buy",tipo="SWING",
                        dur="~4-24h",entry=precio,sl=sl,score_base=min(sc,92),
                        ctx=f"Zona demanda {z:.4f} RSI:{rh:.0f} {tests}x testeada",**r)
    for idx in _swing_highs(df_h4,n=4)[-8:]:
        z=df_h4.high.iloc[idx]; zb,zt=z-at4,z+at4*0.3
        if zb<=precio<=zt and rh>55:
            sl=z+at4*0.45; r=_risk(precio,sl,"sell")
            if r is None: continue
            tests=sum(1 for i in range(len(df_h4)) if zb<=df_h4.high.iloc[i]<=zt)
            sc=66+(10 if tests<=2 else 0)+(10 if rh>65 else 0)
            return dict(estrategia="ZONA OFERTA S&D",icon="🏛️",dir="sell",tipo="SWING",
                        dur="~4-24h",entry=precio,sl=sl,score_base=min(sc,92),
                        ctx=f"Zona oferta {z:.4f} RSI:{rh:.0f} {tests}x testeada",**r)
    return None

def strat_bb_squeeze(df_h1, precio):
    df_h1=_norm_df(df_h1)
    if df_h1 is None or len(df_h1)<30: return None
    c=df_h1.close; h=df_h1.high; l=df_h1.low
    bbu=BollingerBands(c,20,2).bollinger_hband()
    bbd=BollingerBands(c,20,2).bollinger_lband()
    bbm=BollingerBands(c,20,2).bollinger_mavg()
    at=AverageTrueRange(h,l,c,14).average_true_range()
    kcu=EMAIndicator(c,20).ema_indicator()+at*1.5
    kcd=EMAIndicator(c,20).ema_indicator()-at*1.5
    rh=_rsi_s(c).iloc[-1]
    sq=(bbu.iloc[-2]<kcu.iloc[-2] and bbd.iloc[-2]>kcd.iloc[-2]) or \
       (bbu.iloc[-3]<kcu.iloc[-3] and bbd.iloc[-3]>kcd.iloc[-3])
    if not sq: return None
    rel=bbu.iloc[-1]>kcu.iloc[-1] or bbd.iloc[-1]<kcd.iloc[-1]
    if not rel: return None
    atr_v=at.iloc[-1]
    roc=(c.iloc[-1]/c.iloc[-6]-1)*100
    if roc>0.1 and precio>bbm.iloc[-1] and rh>50:
        sl=bbm.iloc[-1]-atr_v*0.5; r=_risk(precio,sl,"buy")
        if r is None: return None
        sc=68+(7 if roc>0.3 else 0)+(5 if rh>55 else 0)
        return dict(estrategia="BB SQUEEZE BREAKOUT",icon="💥",dir="buy",tipo="INTRADAY",
                    dur="~1-3h",entry=precio,sl=sl,score_base=min(sc,88),
                    ctx=f"Squeeze ↑ ROC:{roc:.2f}% RSI:{rh:.0f}",**r)
    if roc<-0.1 and precio<bbm.iloc[-1] and rh<50:
        sl=bbm.iloc[-1]+atr_v*0.5; r=_risk(precio,sl,"sell")
        if r is None: return None
        sc=68+(7 if roc<-0.3 else 0)+(5 if rh<45 else 0)
        return dict(estrategia="BB SQUEEZE BREAKOUT",icon="💥",dir="sell",tipo="INTRADAY",
                    dur="~1-3h",entry=precio,sl=sl,score_base=min(sc,88),
                    ctx=f"Squeeze ↓ ROC:{roc:.2f}% RSI:{rh:.0f}",**r)
    return None

def strat_precio_accion(df_h1, precio):
    df_h1=_norm_df(df_h1)
    if df_h1 is None or len(df_h1)<5: return None
    at=_atr_s(df_h1).iloc[-1]; rh=_rsi_s(df_h1.close).iloc[-1]
    o2,h2,l2,c2=df_h1[["open","high","low","close"]].iloc[-2].values
    o1,h1_,l1,c1=df_h1[["open","high","low","close"]].iloc[-1].values
    b2=abs(c2-o2); b1=abs(c1-o1); rng1=h1_-l1
    if rng1<at*0.3: return None
    hammer  =(b1>0)and(c1-l1)>b1*2.5 and(c1>o1)and(h1_-c1)<b1*0.4
    shooting=(b1>0)and(h1_-c1)>b1*2.5 and(c1<o1)and(c1-l1)<b1*0.4
    eng_bull=(c2<o2)and(c1>o1)and(c1>o2)and(o1<c2)and b1>b2*1.1
    eng_bear=(c2>o2)and(c1<o1)and(c1<o2)and(o1>c2)and b1>b2*1.1
    buy_pat=hammer or eng_bull; sell_pat=shooting or eng_bear
    if not buy_pat and not sell_pat: return None
    if buy_pat and rh<65:
        sl=(l1 if hammer else min(l1,l2))-at*0.3; r=_risk(c1,sl,"buy")
        if r is None: return None
        patron="Engulfing Alcista" if eng_bull else "Martillo"
        sc=63+(8 if eng_bull else 0)+(8 if rh<35 else 0)
        return dict(estrategia=f"PRECIO ACCION-{patron}",icon="🕯️",dir="buy",tipo="INTRADAY",
                    dur="~1-4h",entry=c1,sl=sl,score_base=min(sc,88),
                    ctx=f"{patron} RSI:{rh:.0f}",**r)
    if sell_pat and rh>35:
        sl=(h1_ if shooting else max(h1_,h2))+at*0.3; r=_risk(c1,sl,"sell")
        if r is None: return None
        patron="Engulfing Bajista" if eng_bear else "Estrella Fugaz"
        sc=63+(8 if eng_bear else 0)+(8 if rh>65 else 0)
        return dict(estrategia=f"PRECIO ACCION-{patron}",icon="🕯️",dir="sell",tipo="INTRADAY",
                    dur="~1-4h",entry=c1,sl=sl,score_base=min(sc,88),
                    ctx=f"{patron} RSI:{rh:.0f}",**r)
    return None

def strat_scalp_ema(df_m5, df_m15, df_h1, precio):
    df_m5=_norm_df(df_m5); df_m15=_norm_df(df_m15); df_h1=_norm_df(df_h1)
    if any(df is None or len(df)<30 for df in [df_m5,df_m15,df_h1]): return None
    e9=_ema_s(df_m5.close,9); e21=_ema_s(df_m5.close,21)
    at5=_atr_s(df_m5).iloc[-1]; at5avg=_atr_s(df_m5).rolling(20).mean().iloc[-1]
    if at5<at5avg*0.6: return None
    rh1=_rsi_s(df_h1.close).iloc[-1]; rm=_rsi_s(df_m15.close).iloc[-1]
    e20h1=_ema_s(df_h1.close,20).iloc[-1]; e50h1=_ema_s(df_h1.close,50).iloc[-1]
    cb=e9.iloc[-2]<e21.iloc[-2] and e9.iloc[-1]>e21.iloc[-1]
    cs=e9.iloc[-2]>e21.iloc[-2] and e9.iloc[-1]<e21.iloc[-1]
    if not cb and not cs:
        cb=(e9.iloc[-3]<e21.iloc[-3] and e9.iloc[-2]>e21.iloc[-2] and precio>e9.iloc[-1])
        cs=(e9.iloc[-3]>e21.iloc[-3] and e9.iloc[-2]<e21.iloc[-2] and precio<e9.iloc[-1])
    if not cb and not cs: return None
    if cb and e20h1>e50h1 and 48<=rm<=72:
        sl=e21.iloc[-1]-at5*1.2
        if abs(precio-sl) < at5*0.3: return None
        r=_risk(precio,sl,"buy")
        if r is None: return None
        sc=66+(7 if rm>55 else 0)+(5 if rh1>50 else 0)
        return dict(estrategia="EMA SCALP M5",icon="🏹",dir="buy",tipo="SCALP",
                    dur="~5-20 min",entry=precio,sl=sl,score_base=min(sc,86),
                    ctx=f"EMA9/21 M5 ↑ RSI M15:{rm:.0f}",**r)
    if cs and e20h1<e50h1 and 28<=rm<=52:
        sl=e21.iloc[-1]+at5*1.2
        if abs(precio-sl) < at5*0.3: return None
        r=_risk(precio,sl,"sell")
        if r is None: return None
        sc=66+(7 if rm<45 else 0)+(5 if rh1<50 else 0)
        return dict(estrategia="EMA SCALP M5",icon="🏹",dir="sell",tipo="SCALP",
                    dur="~5-20 min",entry=precio,sl=sl,score_base=min(sc,86),
                    ctx=f"EMA9/21 M5 ↓ RSI M15:{rm:.0f}",**r)
    return None

def strat_momentum_m15(df_m15, df_h1, precio):
    df_m15=_norm_df(df_m15); df_h1=_norm_df(df_h1)
    if df_m15 is None or len(df_m15)<10 or df_h1 is None or len(df_h1)<20: return None
    at15=_atr_s(df_m15).iloc[-1]; rm=_rsi_s(df_m15.close).iloc[-1]
    e20h1=_ema_s(df_h1.close,20).iloc[-1]; e50h1=_ema_s(df_h1.close,50).iloc[-1]
    o,h,l,c=df_m15[["open","high","low","close"]].iloc[-2].values
    body=abs(c-o); rng=h-l
    if rng<at15*1.3 or body<rng*0.65: return None
    if c>o and e20h1>e50h1 and 50<rm<80 and precio<=c+body*0.3:
        sl=l-at15*0.3
        if abs(precio-sl) < at15*0.2: return None
        r=_risk(precio,sl,"buy")
        if r is None: return None
        sc=68+(7 if rm>60 else 0)+(5 if body>rng*0.8 else 0)
        return dict(estrategia="MOMENTUM M15",icon="🚀",dir="buy",tipo="SCALP",
                    dur="~15-45 min",entry=precio,sl=sl,score_base=min(sc,88),
                    ctx=f"Vela M15 alcista {body:.2f}pts RSI:{rm:.0f}",**r)
    if c<o and e20h1<e50h1 and 20<rm<50 and precio>=c-body*0.3:
        sl=h+at15*0.3
        if abs(precio-sl) < at15*0.2: return None
        r=_risk(precio,sl,"sell")
        if r is None: return None
        sc=68+(7 if rm<40 else 0)+(5 if body>rng*0.8 else 0)
        return dict(estrategia="MOMENTUM M15",icon="🚀",dir="sell",tipo="SCALP",
                    dur="~15-45 min",entry=precio,sl=sl,score_base=min(sc,88),
                    ctx=f"Vela M15 bajista {body:.2f}pts RSI:{rm:.0f}",**r)
    return None

# ═══════════════════════════════════════════════════════════════════════
# SCORE PROFESIONAL — 100 pts
# ═══════════════════════════════════════════════════════════════════════
def _score_pro(sig, im5, im15, ih1, ih4, precio):
    d = sig.get("dir","buy")
    pts = {}

    # 1. Tendencia H4/H1 — 25 pts
    th4=0; th1=0
    if ih4:
        e20=ih4.get("e20",ih4["price"]); e50=ih4.get("e50",ih4["price"])
        th4 = 12 if (e20>e50 if d=="buy" else e20<e50) else 0
    if ih1:
        e20=ih1.get("e20",ih1["price"]); e50=ih1.get("e50",ih1["price"]); p=ih1["price"]
        if d=="buy":  th1 = 13 if p>e20>e50 else (6 if p>e50 else 0)
        else:         th1 = 13 if p<e20<e50 else (6 if p<e50 else 0)
    pts["tendencia"] = th4+th1  # max 25

    # 2. Confirmación M15 — 20 pts
    m15p=0
    if im15:
        e9=im15.get("e9",im15["price"]); e20=im15.get("e20",im15["price"])
        rsi15=im15.get("rsi",50); p=im15["price"]
        if d=="buy":  m15p = 20 if p>e9>e20 and rsi15>50 else (10 if p>e20 else 0)
        else:         m15p = 20 if p<e9<e20 and rsi15<50 else (10 if p<e20 else 0)
    pts["conf_m15"] = m15p  # max 20

    # 3. Setup M5 — 20 pts (basado en score_base de estrategia)
    raw = sig.get("score_base", 65)
    pts["setup_m5"] = max(0, min(20, int((raw-55)/35*20)))

    # 4. Momentum — 15 pts
    momp=0
    if im5:
        rsi5=im5.get("rsi",50)
        adx=im5.get("adx",0); macd=im5.get("macd_h",0)
        if d=="buy":  momp = 15 if 50<=rsi5<=70 and adx>20 else (8 if 40<=rsi5<50 else 0)
        else:         momp = 15 if 30<=rsi5<=50 and adx>20 else (8 if 50<rsi5<=60 else 0)
    pts["momentum"] = momp  # max 15

    # 5. Volatilidad ATR — 10 pts
    volp=0
    if ih1:
        atr=ih1.get("atr",1); avg=ih1.get("atr_avg",1)
        if avg>0:
            r=atr/avg
            volp = 10 if 0.75<=r<=1.6 else (5 if r>1.6 else 3)
    pts["vol_atr"] = volp  # max 10

    # 6. Entrada limpia — 10 pts
    entry=sig.get("entry",precio); tp1=sig.get("tp1",precio); dist=abs(tp1-entry)
    if dist > 0:
        prog=(precio-entry)/dist if d=="buy" else (entry-precio)/dist
        cleanp = 10 if prog<=0.05 else (8 if prog<=0.15 else (5 if prog<=0.30 else (2 if prog<=0.50 else 0)))
    else:
        cleanp=0
    pts["entrada_limpia"] = cleanp  # max 10

    return min(sum(pts.values()), 100), pts

def _score_label(score):
    if score>=90: return "PREMIUM",           "#ffd600"
    if score>=80: return "ALTA PROBABILIDAD", "#00e676"
    if score>=70: return "OBSERVAR",          "#42a5f5"
    return               "NO OPERAR",         "#ff5252"

def _progreso(sig, precio):
    e=sig.get("entry",0); tp1=sig.get("tp1",0); dist=abs(tp1-e)
    if dist<=0: return 0
    return ((precio-e)/dist) if sig.get("dir","buy")=="buy" else ((e-precio)/dist)

# ═══════════════════════════════════════════════════════════════════════
# MÁQUINA DE ESTADOS
# ═══════════════════════════════════════════════════════════════════════
def _transition(sig, precio, ih1, im15):
    state=sig.get("state","IDEA_EN_FORMACION")
    d=sig.get("dir","buy")
    e=sig.get("entry",0); sl=sig.get("sl",0)
    tp1=sig.get("tp1",0); tp2=sig.get("tp2",0); tp3=sig.get("tp3",0)
    if not e or not sl or not tp1: return None, None

    if (d=="buy" and precio>=tp3) or (d=="sell" and precio<=tp3):
        return "TP3_ALCANZADO", f"Precio tocó TP3 ({tp3:.4f})"
    if state not in ("TP3_ALCANZADO","TP2_ALCANZADO"):
        if (d=="buy" and precio>=tp2) or (d=="sell" and precio<=tp2):
            return "TP2_ALCANZADO", f"Precio tocó TP2 ({tp2:.4f})"
    if state not in ("TP3_ALCANZADO","TP2_ALCANZADO","TP1_ALCANZADO"):
        if (d=="buy" and precio>=tp1) or (d=="sell" and precio<=tp1):
            return "TP1_ALCANZADO", f"Precio tocó TP1 ({tp1:.4f})"
    if (d=="buy" and precio<=sl) or (d=="sell" and precio>=sl):
        return "STOP_LOSS", f"Precio tocó Stop Loss ({sl:.4f})"

    if state in ("IDEA_EN_FORMACION","ESPERANDO_PULLBACK","ENTRADA_VALIDA"):
        prog=_progreso(sig, precio)
        if prog > LATE_CANCEL:
            return "CANCELAR_IDEA", f"Avanzó {prog*100:.0f}% hacia TP1 sin entrar — tarde"
        if prog > LATE_PULLBACK and state != "ESPERANDO_PULLBACK":
            return "ESPERANDO_PULLBACK", f"Avanzó {prog*100:.0f}% — espera retroceso a {e:.4f}"
        if prog <= 0.12 and state == "ESPERANDO_PULLBACK":
            return "ENTRADA_VALIDA", "Precio regresó a zona de entrada tras retroceso"
        if ih1 and ih1.get("e50"):
            e50h1=ih1["e50"]
            if d=="buy" and precio < e50h1*0.9995:
                return "INVALIDADA", "EMA50 H1 roto bajista — setup compra inválido"
            if d=="sell" and precio > e50h1*1.0005:
                return "INVALIDADA", "EMA50 H1 roto alcista — setup venta inválido"
        if state=="ENTRADA_VALIDA":
            if (d=="buy" and precio>=e) or (d=="sell" and precio<=e):
                return "EN_OPERACION", f"Precio cruzó nivel de entrada ({e:.4f})"
    return None, None

# ═══════════════════════════════════════════════════════════════════════
# MOTOR DE ANÁLISIS
# ═══════════════════════════════════════════════════════════════════════
def _razon_tipo(tipo, ctx_mtf):
    h1  = ctx_mtf.get("H1",{}).get("label","?")
    m15 = ctx_mtf.get("M15",{}).get("label","?")
    m5  = ctx_mtf.get("M5",{}).get("label","?")
    if tipo == "SCALP":
        return f"Scalp: M5 {m5} con H1 {h1}. Duración estimada: minutos. Entrada muy precisa."
    if tipo == "SWING":
        return f"Swing: Tendencia clara en H4/H1 ({h1}). Duración: varias horas o días."
    return f"Intraday: H1 {h1} · M15 {m15} · setup en M5 {m5}. Duración: 30 min a pocas horas."

def _razones_no_trade(ctx_mtf, score_max, im5, ih1):
    r = []
    h1=ctx_mtf.get("H1",{}); m15=ctx_mtf.get("M15",{})
    if score_max < MIN_SCORE_SHOW:
        r.append(f"Score más alto detectado: {score_max}/100 — mínimo requerido: {MIN_SCORE_SHOW}/100")
    if h1.get("bull",0)>0.3 and m15.get("bear",0)>0.3:
        r.append("Conflicto: H1 sube pero M15 baja — esperar que se alineen")
    elif h1.get("bear",0)>0.3 and m15.get("bull",0)>0.3:
        r.append("Conflicto: H1 baja pero M15 sube — esperar que se alineen")
    rsi_h1=h1.get("rsi",50)
    if 44<=rsi_h1<=56:
        r.append(f"RSI H1 en zona neutral ({rsi_h1:.0f}) — sin fuerza clara de compra ni venta")
    if im5 and im5.get("atr") and im5.get("atr_avg"):
        if im5["atr_avg"]>0 and im5["atr"]<im5["atr_avg"]*0.65:
            r.append("Mercado quieto en M5 — poca volatilidad, señales poco confiables")
    if "LATERAL" in h1.get("label",""):
        r.append(f"H1 lateral — sin tendencia definida, mejor esperar")
    if not r:
        r.append("Sin setup limpio ahora mismo — todos los filtros requieren más confirmación")
        r.append("Espera: ruptura de zona clave, pullback a EMA o alineación de todos los tiempos")
    return r

def _analyze_asset(sym_key, pen):
    """Analiza un activo y retorna (ast, ctx_mtf, precio, meta_dict) o (None,None,None,None)."""
    try:
        result = _fetch_all(sym_key)
        if result is None or len(result)<6:
            return None,None,None,None
        precio, src, df_m5, df_m15, df_h1, df_h4 = result
        if not precio:
            return None,None,None,None

        yft, label, dec, pp, is_gold = MDEF.get(sym_key, ("","",2,1,False))

        im5  = _ind(df_m5)
        im15 = _ind(df_m15)
        ih1  = _ind(df_h1)
        ih4  = _ind(df_h4)
        ctx_mtf = _mtf_ctx(im5, im15, ih1, ih4)

        ast = _get_ast(sym_key)
        sig = ast.get("signal")

        # Actualizar señal activa
        if sig and sig.get("state") not in _CLOSED:
            new_st, motivo = _transition(sig, precio, ih1, im15)
            if new_st and new_st != sig.get("state"):
                prev_st = sig.get("state")
                sig = _log_change(sig, new_st, motivo)
                ast["signal"] = sig
                if new_st in _CLOSED:
                    ast["closed_at"] = datetime.now(timezone.utc).isoformat()
                    ast["cooldown_until"] = (
                        datetime.now(timezone.utc)+timedelta(minutes=COOLDOWN_MIN)
                    ).isoformat()
                _set_ast(sym_key, ast)
                _tg_signal(sym_key, sig)

        # ¿Buscar nueva señal?
        sig_act = ast.get("signal")
        en_cd = False
        cd = ast.get("cooldown_until")
        if cd:
            try:
                en_cd = datetime.fromisoformat(cd) > datetime.now(timezone.utc)
            except Exception:
                pass

        necesita_nueva = (sig_act is None or sig_act.get("state") in _CLOSED) and not en_cd

        # Candidatos de estrategias (cada una en try/except para no bloquear las demás)
        d1_df = None
        def _try(fn, *args):
            try: return fn(*args)
            except Exception: return None

        candidatos = [
            _try(strat_london_breakout, df_h1, precio, is_gold),
            _try(strat_trend_pullback, d1_df, df_h4, df_h1, df_m15, precio),
            _try(strat_ema_momentum, df_h1, df_m15, precio),
            _try(strat_supply_demand, df_h4, df_h1, precio),
            _try(strat_bb_squeeze, df_h1, precio),
            _try(strat_precio_accion, df_h1, precio),
            _try(strat_scalp_ema, df_m5, df_m15, df_h1, precio),
            _try(strat_momentum_m15, df_m15, df_h1, precio),
        ]

        # Score máximo posible (para panel no-trade)
        score_max = 0
        scored_cands = []
        for s in candidatos:
            if s is None: continue
            sc, det = _score_pro(s, im5, im15, ih1, ih4, precio)
            sc = max(sc - pen, 0)
            if sc > score_max: score_max = sc
            if sc >= MIN_SCORE_SHOW:
                prog = _progreso(s, precio)
                if prog <= LATE_CANCEL:
                    s["score"] = sc
                    s["score_detail"] = det
                    scored_cands.append(s)

        if necesita_nueva and scored_cands:
            scored_cands.sort(
                key=lambda x: (x["score"], x.get("score_detail",{}).get("entrada_limpia",0)),
                reverse=True
            )
            mejor = scored_cands[0]
            d = mejor.get("sl_d", 0)
            mejor.update(g1=d*1.5*pp, g2=d*2.5*pp, g3=d*4.0*pp, riesgo=d*pp)
            prog = _progreso(mejor, precio)

            if mejor["score"] >= MIN_SCORE_ENTRY and prog <= LATE_PULLBACK:
                init = "ENTRADA_VALIDA"
            elif mejor["score"] >= MIN_SCORE_ENTRY and prog <= LATE_CANCEL:
                init = "ESPERANDO_PULLBACK"
            elif mejor["score"] >= MIN_SCORE_SHOW:
                init = "IDEA_EN_FORMACION"
            else:
                init = None

            if init:
                mejor["tipo_razon"] = _razon_tipo(mejor.get("tipo","INTRADAY"), ctx_mtf)
                now = datetime.now(timezone.utc)
                mejor["id"] = f"{sym_key}_{mejor['dir']}_{now.strftime('%H%M')}"
                mejor["created_at"] = now.isoformat()
                mejor["updated_at"] = now.isoformat()
                mejor["state"] = init
                mejor["symbol"] = sym_key
                mejor["log"] = [{"ts":now.strftime("%H:%M UTC"),"state":init,
                    "msg":f"{mejor.get('estrategia','')} · Score {mejor['score']}/100"}]
                ast["signal"] = mejor
                ast["closed_at"] = None
                _set_ast(sym_key, ast)
                sig_act = mejor
                _tg_signal(sym_key, mejor)

        razones_nt = (
            _razones_no_trade(ctx_mtf, score_max, im5, ih1)
            if not sig_act or sig_act.get("state") in _CLOSED
            else []
        )

        meta = {
            "src": src, "precio": precio, "dec": dec,
            "atr_h1": ih1.get("atr",0) if ih1 else 0,
            "rsi_h1": ih1.get("rsi",50) if ih1 else 50,
            "e200_h1":ih1.get("e200",precio) if ih1 else precio,
            "score_max": score_max,
            "razones_nt": razones_nt,
            "label": label,
        }
        return ast, ctx_mtf, precio, meta

    except Exception as ex:
        return None, None, None, {"error": f"{ex}\n{traceback.format_exc()}"}

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
                if e.get("impact")=="High" and e.get("country")=="USD":
                    try:
                        dt = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
                        ev.append({"dt":dt,"titulo":e.get("title","")})
                    except Exception:
                        pass
        except Exception:
            pass
    return sorted(ev, key=lambda x: x["dt"])

def _news_risk(ev):
    now = datetime.now(timezone.utc)
    for e in ev:
        d = (e["dt"]-now).total_seconds()/60
        if -30 <= d <= 30:
            return "PELIGRO", f"🔴 PELIGRO — {_he(e['titulo'])} {'+' if d>0 else ''}{int(d)} min"
        if 30 < d <= 120:
            return "PRECAUCION", f"🟡 PRECAUCIÓN — {_he(e['titulo'])} en {int(d)} min"
    fut = [e for e in ev if (e["dt"]-now).total_seconds()>0]
    if fut:
        p=fut[0]; m=int((p["dt"]-now).total_seconds()/60)
        return "SEGURO", f"🟢 Sin peligro — próximo: {_he(p['titulo'])} en {m} min"
    return "SEGURO","🟢 Sin eventos de alto impacto ahora"

# ═══════════════════════════════════════════════════════════════════════
# UI — TARJETA DE SEÑAL
# ═══════════════════════════════════════════════════════════════════════
def _render_card(sig, precio, sym, dec):
    state = sig.get("state","IDEA_EN_FORMACION")
    ic, lbl, col, bg = _SC.get(state, _SC["IDEA_EN_FORMACION"])
    d      = sig.get("dir","buy")
    dc     = "#00e676" if d=="buy" else "#ff5252"
    arrow  = "▲" if d=="buy" else "▼"
    accion_word = "COMPRA" if d=="buy" else "VENTA"
    score  = sig.get("score",0)
    sc_lbl, sc_col = _score_label(score)

    def f(v): return _fmt(v, dec)

    accion = _ACCION.get(state,"")

    entry  = sig.get("entry",0);   sl   = sig.get("sl",0)
    tp1    = sig.get("tp1",0);     tp2  = sig.get("tp2",0)
    tp3    = sig.get("tp3",0);     tp4  = sig.get("tp4",0)
    sl_d   = sig.get("sl_d",0)
    rr1    = sig.get("rr1",1.5);   rr2  = sig.get("rr2",2.5)
    rr3    = sig.get("rr3",4.0);   rr4  = sig.get("rr4",6.0)
    estrategia = _he(sig.get("estrategia",""))
    ctx_txt    = _he(sig.get("ctx",""))

    et = _entry_type(d, precio, entry)
    et_label = f"{accion_word} {et}" if et != "MARKET" else f"{accion_word} AHORA (MARKET)"

    # Estrellas de confianza
    stars = "".join(
        f'<span style="color:{"#ffd600" if i < score//20 else "#1a1a28"};font-size:1em">★</span>'
        for i in range(5)
    )

    # Progreso hacia TP1
    prog   = _progreso(sig, precio)
    prog_p = max(0, min(100, prog*100))
    prog_txt = "zona de entrada ✅" if prog_p<=15 else ("espera retroceso ⏳" if prog_p<=60 else "ya avanzó mucho ⚠️")

    # Distancia en puntos desde entrada
    def pts(a, b): return abs(a - b)

    st.markdown(f"""
<div style="background:#07070d;border:2px solid {col};border-radius:16px;
  padding:1.3rem 1.4rem;margin-bottom:.5rem">

  <!-- ═══ CABECERA ═══ -->
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div>
      <div style="color:#d8d8f8;font-size:1.05em;font-weight:900">{_he(MDEF.get(sym,("","",dec,1,False))[1])}</div>
      <div style="color:#252540;font-size:.72em;margin-top:1px">{estrategia} &nbsp;·&nbsp; {ctx_txt}</div>
    </div>
    <div style="background:{dc}18;border:1.5px solid {dc};border-radius:10px;
      padding:5px 14px;text-align:center">
      <div style="color:{dc};font-size:.88em;font-weight:900">{arrow} {et_label}</div>
    </div>
  </div>

  <!-- ═══ ESTADO ═══ -->
  <div style="background:{bg};border-left:4px solid {col};border-radius:0 10px 10px 0;
    padding:10px 14px;margin-bottom:12px">
    <div style="color:{col};font-size:1.05em;font-weight:900">{ic}&nbsp; {lbl}</div>
    <div style="color:#555;font-size:.8em;margin-top:3px">{accion}</div>
  </div>

  <!-- ═══ ENTRADA Y STOP ═══ -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">

    <div style="background:#0b0b18;border:2px solid #42a5f5;border-radius:12px;padding:11px 14px">
      <div style="color:#1a1a38;font-size:.62em;font-weight:700;text-transform:uppercase;
        letter-spacing:.08em;margin-bottom:3px">📍 PRECIO DE ENTRADA</div>
      <div style="color:#ffffff;font-size:1.4em;font-weight:900;letter-spacing:.02em">{f(entry)}</div>
      <div style="color:#333;font-size:.7em;margin-top:2px">
        Precio actual: <b style="color:#888">{f(precio)}</b>
        &nbsp;·&nbsp; Dif: {f(pts(precio,entry))}
      </div>
    </div>

    <div style="background:#0f0507;border:2px solid #ff5252;border-radius:12px;padding:11px 14px">
      <div style="color:#2a1010;font-size:.62em;font-weight:700;text-transform:uppercase;
        letter-spacing:.08em;margin-bottom:3px">🛑 STOP LOSS</div>
      <div style="color:#ff5252;font-size:1.4em;font-weight:900;letter-spacing:.02em">{f(sl)}</div>
      <div style="color:#2a1010;font-size:.7em;margin-top:2px">
        Si el precio llega aquí → cierra la operación
        &nbsp;·&nbsp; <b style="color:#cc3333">-{f(sl_d)} pts</b>
      </div>
    </div>

  </div>

  <!-- ═══ SEPARADOR OBJETIVOS ═══ -->
  <div style="text-align:center;color:#1a1a30;font-size:.6em;font-weight:700;
    letter-spacing:.18em;padding:5px 0 6px 0;text-transform:uppercase">
    ── Objetivos de ganancia ──
  </div>

  <!-- ═══ TPs ═══ -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px">

    <div style="background:#060e08;border:1.5px solid #1e4a22;border-radius:10px;padding:9px 12px">
      <div style="color:#0e2210;font-size:.6em;font-weight:700;text-transform:uppercase;margin-bottom:2px">🎯 TP1 — 1er objetivo</div>
      <div style="color:#69f0ae;font-size:1.15em;font-weight:900">{f(tp1)}</div>
      <div style="color:#0e2210;font-size:.68em;margin-top:2px">
        +{f(pts(tp1,entry))} pts &nbsp;·&nbsp; RR 1:{rr1:.1f}
      </div>
    </div>

    <div style="background:#060e08;border:1.5px solid #1e5a28;border-radius:10px;padding:9px 12px">
      <div style="color:#0e2210;font-size:.6em;font-weight:700;text-transform:uppercase;margin-bottom:2px">🎯 TP2 — 2do objetivo</div>
      <div style="color:#00e676;font-size:1.15em;font-weight:900">{f(tp2)}</div>
      <div style="color:#0e2210;font-size:.68em;margin-top:2px">
        +{f(pts(tp2,entry))} pts &nbsp;·&nbsp; RR 1:{rr2:.1f}
      </div>
    </div>

    <div style="background:#070e06;border:1.5px solid #2a5a18;border-radius:10px;padding:9px 12px">
      <div style="color:#0e220a;font-size:.6em;font-weight:700;text-transform:uppercase;margin-bottom:2px">🎯 TP3 — 3er objetivo</div>
      <div style="color:#b8e65a;font-size:1.15em;font-weight:900">{f(tp3)}</div>
      <div style="color:#0e220a;font-size:.68em;margin-top:2px">
        +{f(pts(tp3,entry))} pts &nbsp;·&nbsp; RR 1:{rr3:.1f}
      </div>
    </div>

    <div style="background:#0e0e06;border:1.5px solid #4a4a00;border-radius:10px;padding:9px 12px">
      <div style="color:#1e1e08;font-size:.6em;font-weight:700;text-transform:uppercase;margin-bottom:2px">🏆 TP4 — objetivo máximo</div>
      <div style="color:#ffd600;font-size:1.15em;font-weight:900">{f(tp4) if tp4 else "—"}</div>
      <div style="color:#1e1e08;font-size:.68em;margin-top:2px">
        {("+"+f(pts(tp4,entry))+" pts · RR 1:"+str(rr4)) if tp4 else "deja correr"}
      </div>
    </div>

  </div>

  <!-- ═══ PROGRESO ═══ -->
  <div style="background:#08080f;border-radius:8px;padding:8px 12px;margin-bottom:8px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
      <span style="color:#1e1e30;font-size:.65em;font-weight:700;text-transform:uppercase">
        Avance del precio hacia TP1
      </span>
      <span style="color:{dc};font-size:.7em;font-weight:700">{prog_p:.0f}% — {prog_txt}</span>
    </div>
    <div style="background:#0e0e18;border-radius:4px;height:6px;overflow:hidden">
      <div style="background:{dc};height:6px;width:{min(prog_p,100):.0f}%;border-radius:4px;
        transition:width .3s"></div>
    </div>
    <div style="display:flex;justify-content:space-between;margin-top:3px;
      color:#141428;font-size:.6em">
      <span>Entrada {f(entry)}</span>
      <span>TP1 {f(tp1)}</span>
    </div>
  </div>

  <!-- ═══ CONFIANZA ═══ -->
  <div style="display:flex;justify-content:space-between;align-items:center;
    background:#060610;border:1px solid #0e0e1e;border-radius:8px;padding:7px 12px">
    <div>
      <div style="color:#1a1a30;font-size:.62em;text-transform:uppercase;font-weight:700;
        margin-bottom:3px">Confianza de la señal</div>
      <div>{stars}</div>
    </div>
    <div style="text-align:right">
      <div style="color:{sc_col};font-size:1.7em;font-weight:900;line-height:1">{score}</div>
      <div style="color:#1a1a30;font-size:.62em">/100 &nbsp; {sc_lbl}</div>
    </div>
  </div>

</div>""", unsafe_allow_html=True)


def _render_mtf(ctx_mtf):
    cells = ""
    for tf in ["H4","H1","M15","M5"]:
        t=ctx_mtf.get(tf,{}); color=t.get("color","#252535"); lbl=t.get("label","Sin datos")
        rsi=t.get("rsi"); rt=f'<br><span style="color:#1e1e30;font-size:.6em">RSI {rsi:.0f}</span>' if rsi else ""
        cells += (f'<div style="background:#0a0a14;border:1px solid #14142a;border-radius:8px;'
                  f'padding:7px 5px;text-align:center">'
                  f'<div style="color:#1a1a30;font-size:.62em;font-weight:700;margin-bottom:1px">{tf}</div>'
                  f'<div style="color:{color};font-size:.72em;font-weight:700">{lbl}{rt}</div></div>')
    st.markdown(f"""
<div style="margin-bottom:.6rem">
  <div style="color:#1a1a30;font-size:.63em;font-weight:700;text-transform:uppercase;
    letter-spacing:.1em;margin-bottom:5px">Análisis Multi-Temporal</div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:5px">{cells}</div>
</div>""", unsafe_allow_html=True)


def _render_no_trade(sym, razones, ctx_mtf, score_max):
    bar_c = "#00e676" if score_max>=80 else ("#ffd600" if score_max>=60 else "#ff5252")
    emoji = "🔥" if score_max>=80 else ("👀" if score_max>=60 else "🔍")
    razon_principal = _he(razones[0]) if razones else "Buscando setup perfecto..."

    # Nivel de fuerza visual
    nivel = "CASI LISTO" if score_max>=75 else ("OBSERVANDO" if score_max>=55 else "ESPERANDO")
    nivel_c = "#ffd600" if score_max>=75 else ("#42a5f5" if score_max>=55 else "#333")

    st.markdown(f"""
<div style="background:#07070d;border:1px solid #12122a;border-radius:14px;
  padding:1.1rem 1.3rem;margin-bottom:.5rem">

  <!-- CABECERA -->
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div>
      <div style="color:#888;font-size:.95em;font-weight:700">{emoji} SIN SEÑAL AHORA</div>
      <div style="color:#1e1e30;font-size:.75em;margin-top:2px">
        El scanner está buscando el momento perfecto
      </div>
    </div>
    <div style="text-align:center;background:#08080f;border:1px solid #12122a;
      border-radius:10px;padding:6px 14px">
      <div style="color:{bar_c};font-size:1.5em;font-weight:900;line-height:1">{score_max}</div>
      <div style="color:#1a1a30;font-size:.6em">/100</div>
      <div style="color:{nivel_c};font-size:.6em;font-weight:700">{nivel}</div>
    </div>
  </div>

  <!-- BARRA DE PROGRESO -->
  <div style="background:#0a0a14;border-radius:4px;height:5px;margin-bottom:10px;overflow:hidden">
    <div style="background:{bar_c};height:5px;width:{min(score_max,100)}%;border-radius:4px"></div>
  </div>

  <!-- RAZÓN PRINCIPAL (simple) -->
  <div style="background:#0a0a14;border-left:3px solid #1e1e38;border-radius:0 8px 8px 0;
    padding:8px 12px;margin-bottom:8px">
    <div style="color:#1e1e38;font-size:.62em;font-weight:700;text-transform:uppercase;margin-bottom:2px">
      ¿Por qué no hay señal?
    </div>
    <div style="color:#444;font-size:.82em">{razon_principal}</div>
  </div>

  <!-- RAZONES ADICIONALES (colapsadas) -->
  {"".join(f'<div style="color:#252535;font-size:.72em;padding:2px 0">▸ {_he(r)}</div>' for r in razones[1:3])}

  <div style="color:#1a1a28;font-size:.65em;margin-top:6px;text-align:right">
    Necesitas {MIN_SCORE_ENTRY}/100 para entrada &nbsp;·&nbsp; Ahora: {score_max}/100
  </div>
</div>""", unsafe_allow_html=True)


def _render_closed(sig, dec):
    state=sig.get("state",""); ic,lbl,col,_=_SC.get(state,_SC["INVALIDADA"])
    logs=sig.get("log",[]); last=logs[-1].get("msg","") if logs else ""
    def f(v): return _fmt(v, dec)
    st.markdown(f"""
<div style="background:#07070d;border:1px solid #111120;border-radius:10px;
  padding:.8rem 1.1rem;margin-bottom:.4rem;opacity:.65">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="color:{col};font-size:.95em;font-weight:700">{ic} {lbl}</div>
      <div style="color:#252535;font-size:.75em;margin-top:2px">
        {_he(sig.get('estrategia',''))} · {'▲ BUY' if sig.get('dir')=='buy' else '▼ SELL'}
        · Entrada {f(sig.get('entry',0))} · SL {f(sig.get('sl',0))}
      </div>
      <div style="color:#1a1a2e;font-size:.72em;margin-top:2px">{_he(last)}</div>
    </div>
    <div style="color:#1e1e30;font-size:.7em">Score {sig.get('score',0)}/100</div>
  </div>
</div>""", unsafe_allow_html=True)


def _render_log(sig):
    logs = sig.get("log",[])
    if not logs: return
    with st.expander(f"📋 Historial · {len(logs)} eventos", expanded=False):
        for e in reversed(logs):
            ic,_,c,_ = _SC.get(e.get("state",""), ("·","","#333",""))
            st.markdown(
                f'<div style="display:flex;gap:8px;padding:3px 0;border-bottom:1px solid #0c0c18;'
                f'font-size:.76em"><span style="color:#1a1a28;min-width:66px">{e.get("ts","")}</span>'
                f'<span style="color:{c};min-width:16px">{ic}</span>'
                f'<span style="color:#303050">{_he(e.get("msg",""))}</span></div>',
                unsafe_allow_html=True
            )

# ═══════════════════════════════════════════════════════════════════════
# RENDER DE UN ACTIVO
# ═══════════════════════════════════════════════════════════════════════
_SRC_BADGE = {
    "MT5":   '<span style="background:#0a1430;color:#42a5f5;padding:2px 8px;border-radius:10px;font-size:.68em;font-weight:700">📊 MT5</span>',
    "Yahoo": '<span style="background:#140e00;color:#ffd600;padding:2px 8px;border-radius:10px;font-size:.68em;font-weight:700">🌐 Yahoo</span>',
}

def _render_asset(sym_key, n_nivel, n_txt, pen):
    abierto, hora_txt = mercado_abierto(sym_key)
    yft, label, dec, pp, is_gold = MDEF.get(sym_key, ("","",2,1,False))

    if not abierto:
        st.markdown(f"""
<div style="background:#080810;border:1px solid #14142a;border-radius:10px;
  padding:.8rem 1.2rem;margin-bottom:.5rem;opacity:.5">
  <span style="color:#333;font-size:.9em">{_he(label)}</span>
  <span style="color:#ff5252;font-size:.78em;margin-left:10px">{_he(hora_txt)}</span>
</div>""", unsafe_allow_html=True)
        return

    with st.spinner(f"Analizando {sym_key}…"):
        ast, ctx_mtf, precio, meta = _analyze_asset(sym_key, pen)

    if ast is None:
        st.markdown(f"""
<div style="background:#08080e;border:1px solid #181828;border-radius:10px;
  padding:.8rem 1.2rem;margin-bottom:.5rem">
  <div style="color:#ff9800;font-size:.88em;font-weight:700">⚠️ {_he(sym_key)} — Sin datos ahora</div>
  <div style="color:#2a2a3a;font-size:.75em;margin-top:3px">
    No se pudo obtener información. El scanner reintenta en {REFRESH}s.
  </div>
</div>""", unsafe_allow_html=True)
        return

    sig = ast.get("signal")
    src = meta.get("src","Yahoo")
    score_max = meta.get("score_max",0)

    # Alert de cambio de estado
    sk = f"_last_state_{sym_key}"
    prev_st = st.session_state.get(sk)
    curr_st = sig.get("state") if sig and sig.get("state") not in _CLOSED else "BUSCANDO_SETUP"
    if prev_st and prev_st != curr_st:
        ic,lbl,_,_ = _SC.get(curr_st, _SC["BUSCANDO_SETUP"])
        st.toast(f"{sym_key}: {ic} {lbl}", icon="📡")
    st.session_state[sk] = curr_st

    # Header métricas
    tend    = "▲ ALCISTA" if precio > meta.get("e200_h1",0) else "▼ BAJISTA"
    tend_c  = "#00e676" if "ALCISTA" in tend else "#ff5252"
    badge   = _SRC_BADGE.get(src, _SRC_BADGE["Yahoo"])
    hora_c  = "#00e676" if abierto else "#333"

    col1,col2,col3,col4 = st.columns([1.4,1,1,1.5])
    col1.metric(label, f"{_fmt(precio,dec)}")
    col2.metric("ATR H1",  f"{meta.get('atr_h1',0):.{dec}f}")
    col3.metric("RSI H1",  f"{meta.get('rsi_h1',50):.0f}")
    with col4:
        st.markdown(
            f'<div style="padding:6px 0">{badge} '
            f'<span style="color:{hora_c};font-size:.7em;margin-left:6px">{_he(hora_txt)}</span></div>',
            unsafe_allow_html=True
        )

    # Noticias
    nc = {"PELIGRO":"#c62828","PRECAUCION":"#ff9800","SEGURO":"#00c853"}.get(n_nivel,"#00c853")
    st.markdown(f"""
<div style="background:#07070e;border:1px solid #101020;border-radius:7px;
  padding:.45rem .9rem;margin:.3rem 0 .6rem 0;font-size:.8em">
  <span style="color:#1a1a30">📰 Noticias USD: </span>
  <span style="color:{nc};font-weight:700">{n_txt}</span>
  {('<span style="color:#c62828;font-weight:900;margin-left:10px">⛔ NO OPERAR</span>' if n_nivel=="PELIGRO" else "")}
</div>""", unsafe_allow_html=True)

    # MTF
    _render_mtf(ctx_mtf)
    st.markdown("<hr style='border:none;border-top:1px solid #0e0e1a;margin:.2rem 0 .5rem 0'>",
                unsafe_allow_html=True)

    # Señal activa o cerrada + no-trade
    tiene_activa = sig and sig.get("state") not in _CLOSED

    if tiene_activa:
        _render_card(sig, precio, sym_key, dec)
        _render_log(sig)
        if st.button(f"🗑 Descartar señal", key=f"del_{sym_key}"):
            sig = _log_change(sig, "INVALIDADA", "Cerrado manualmente")
            ast["signal"] = sig
            ast["closed_at"] = datetime.now(timezone.utc).isoformat()
            ast["cooldown_until"] = (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()
            _set_ast(sym_key, ast)
            st.rerun()
    else:
        if sig and sig.get("state") in _CLOSED:
            _render_closed(sig, dec)
            cd = ast.get("cooldown_until")
            if cd:
                try:
                    rem = (datetime.fromisoformat(cd)-datetime.now(timezone.utc)).total_seconds()
                    if rem > 0:
                        st.markdown(
                            f'<div style="color:#1a1a30;font-size:.72em;margin-bottom:.5rem">'
                            f'⏱ Buscando nuevo setup en {int(rem/60)}m {int(rem%60)}s…</div>',
                            unsafe_allow_html=True
                        )
                except Exception:
                    pass
        _render_no_trade(sym_key, meta.get("razones_nt",[]), ctx_mtf, score_max)

# ═══════════════════════════════════════════════════════════════════════
# WELTRADE — Tab especial solo MT5
# ═══════════════════════════════════════════════════════════════════════
WELTRADE_GRUPOS = {
    "FX Volatility": ["FX Vol 20","FX Vol 40","FX Vol 60","FX Vol 80","FX Vol 99"],
    "GainX":         ["GainX 400","GainX 600","GainX 800","GainX 999"],
    "PainX":         ["PainX 400","PainX 600","PainX 800","PainX 999"],
    "BreakX":        ["BreakX 600","BreakX 1200","BreakX 1800"],
    "TrendX":        ["TrendX 600","TrendX 1200","TrendX 1800"],
    "SwitchX":       ["SwitchX 600","SwitchX 1200"],
}
WELTRADE_COLORS = {
    "FX Volatility":"#42a5f5","GainX":"#00e676","PainX":"#ff5252",
    "BreakX":"#ff9800","TrendX":"#ab47bc","SwitchX":"#ffd600",
}

def _render_weltrade_tab(n_nivel, n_txt, pen):
    if not _mt5_init():
        st.markdown("""
<div style="background:#0a0814;border:1px solid #1a1230;border-radius:10px;
  padding:.8rem 1.2rem;margin-bottom:.8rem">
  <div style="color:#ffd600;font-size:.85em;font-weight:700;margin-bottom:3px">
    ⚡ MT5 no conectado — mostrando instrumentos estándar Weltrade
  </div>
  <div style="color:#252535;font-size:.73em">
    Los índices sintéticos (GainX, PainX, etc.) requieren MT5.
    Abre MetaTrader5 con tu cuenta Weltrade y recarga el scanner para activarlos.
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown('<div style="color:#1a1a30;font-size:.65em;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px">Instrumentos estándar disponibles en Weltrade</div>', unsafe_allow_html=True)
        wt_syms = ["XAUUSD","EURUSD","GBPUSD","USDJPY","US30","US100"]
        c1, c2 = st.columns(2)
        for i, sym in enumerate(wt_syms):
            with (c1 if i % 2 == 0 else c2):
                try:
                    lbl = MDEF[sym][1]
                    st.markdown(f"#### {lbl}")
                    _render_asset(sym, n_nivel, n_txt, pen)
                except Exception as ex:
                    st.warning(f"{sym}: sin datos")
        return

    # Radar de activos Weltrade
    st.markdown('<div style="color:#1a1a30;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">Radar Weltrade — señales activas por grupo</div>', unsafe_allow_html=True)

    for grupo, syms in WELTRADE_GRUPOS.items():
        color = WELTRADE_COLORS.get(grupo,"#555")
        st.markdown(f'<div style="color:{color};font-size:.78em;font-weight:700;margin:.6rem 0 .3rem 0">{grupo}</div>', unsafe_allow_html=True)
        cols = st.columns(min(len(syms), 5))
        for i, sym in enumerate(syms):
            with cols[i % 5]:
                try:
                    p = _mt5_price(sym)
                    if p:
                        df_m15 = None
                        if _MT5:
                            try:
                                _mt5lib.symbol_select(sym, True)
                                r = _mt5lib.copy_rates_from_pos(sym, _mt5lib.TIMEFRAME_M15, 0, 100)
                                if r is not None and len(r)>=20:
                                    df_m15 = pd.DataFrame(r)
                                    df_m15.columns = [c.lower() if c.lower() in ["open","high","low","close","time","tick_volume"] else c.lower() for c in df_m15.columns]
                                    df_m15 = df_m15.rename(columns={"tick_volume":"volume"})
                            except Exception:
                                pass
                        im15 = _ind(df_m15) if df_m15 is not None else None
                        rsi_v = f"RSI {im15['rsi']:.0f}" if im15 else "—"
                        st.markdown(f"""
<div style="background:#090910;border:1px solid #141428;border-radius:8px;
  padding:7px 9px;margin:2px 0;text-align:center">
  <div style="color:{color};font-size:.7em;font-weight:700">{_he(sym)}</div>
  <div style="color:#888;font-size:.75em;font-weight:700">{p:.2f}</div>
  <div style="color:#252535;font-size:.62em">{rsi_v}</div>
</div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
<div style="background:#08080e;border:1px solid #111120;border-radius:8px;
  padding:7px 9px;margin:2px 0;text-align:center;opacity:.4">
  <div style="color:#333;font-size:.7em">{_he(sym)}</div>
  <div style="color:#1e1e30;font-size:.62em">sin datos</div>
</div>""", unsafe_allow_html=True)
                except Exception:
                    pass

    st.markdown("""
<div style="color:#1a1a30;font-size:.72em;margin-top:1rem;padding-top:.5rem;border-top:1px solid #0a0a14">
  Los índices sintéticos Weltrade operan 24/7.
  Señales automáticas con estado completo próximamente.
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR — Config Telegram
# ═══════════════════════════════════════════════════════════════════════
def _sidebar():
    with st.sidebar:
        st.markdown('<div style="color:#ffd600;font-size:1.1em;font-weight:900;margin-bottom:12px">🥇 RAVEN PRO</div>', unsafe_allow_html=True)

        # Telegram
        st.markdown('<div style="color:#42a5f5;font-size:.8em;font-weight:700;margin-bottom:6px">📱 TELEGRAM ALERTAS</div>', unsafe_allow_html=True)
        cfg = _load_cfg()
        tok = st.text_input("Bot Token", value=cfg.get("tg_token",""), type="password", key="tg_tok_input")
        cid = st.text_input("Chat ID",   value=cfg.get("tg_chatid",""), key="tg_cid_input")
        if st.button("💾 Guardar Telegram", key="tg_save"):
            cfg["tg_token"] = tok.strip()
            cfg["tg_chatid"] = cid.strip()
            _save_cfg(cfg)
            st.success("✅ Guardado")
        if st.button("🧪 Probar", key="tg_test"):
            cfg["tg_token"] = tok.strip()
            cfg["tg_chatid"] = cid.strip()
            _save_cfg(cfg)
            _tg_send("🥇 <b>RAVEN PRO</b> — Test de conexión OK ✅")
            st.success("Mensaje enviado")

        st.markdown("---")
        st.markdown('<div style="color:#555;font-size:.72em">Score mínimo señal: <b style="color:#ffd600">'+str(MIN_SCORE_SHOW)+'</b></div>', unsafe_allow_html=True)
        st.markdown('<div style="color:#555;font-size:.72em">Score mínimo entrada: <b style="color:#00e676">'+str(MIN_SCORE_ENTRY)+'</b></div>', unsafe_allow_html=True)
        st.markdown('<div style="color:#555;font-size:.72em">Actualización: cada <b>'+str(REFRESH)+'s</b></div>', unsafe_allow_html=True)

        if st.button("🗑 Borrar todos los estados", key="clr_state"):
            _save_state({})
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════
# SESIÓN
# ═══════════════════════════════════════════════════════════════════════
def _sesion():
    h=datetime.now(timezone.utc).hour
    if   h<7:  return "🌏 ASIÁTICA","#42a5f5"
    elif h<12: return "🇬🇧 LONDRES","#00e676"
    elif h<17: return "🇺🇸 NUEVA YORK","#ff9800"
    else:      return "🌙 FUERA HORARIO","#444"

# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════
def main():
    _sidebar()

    sesion, ses_col = _sesion()
    ev              = _fetch_news()
    n_nivel, n_txt  = _news_risk(ev)
    pen             = {"PELIGRO":35,"PRECAUCION":12,"SEGURO":0}.get(n_nivel,0)
    nb_c = {"PELIGRO":"#c62828","PRECAUCION":"#ff9800","SEGURO":"#00c853"}.get(n_nivel,"#00c853")

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#07070e,#12090a);border:1px solid #1e1400;
  border-radius:12px;padding:.9rem 1.5rem;margin-bottom:.7rem;
  display:flex;align-items:center;justify-content:space-between">
  <div>
    <div style="color:#ffd600;font-size:1.35em;font-weight:900">🥇 RAVEN TRADE IDEAS PRO</div>
    <div style="color:#252525;font-size:.8em;margin-top:1px">
      ORO · ÍNDICES · FOREX · MATERIAS · CRYPTO · WELTRADE · Una señal por activo
    </div>
  </div>
  <div style="text-align:right">
    <div style="color:{ses_col};font-size:.88em;font-weight:700">{sesion}</div>
    <span style="background:{nb_c};color:{'#000' if n_nivel!='PELIGRO' else '#fff'};
      padding:2px 9px;border-radius:12px;font-size:.72em;font-weight:700">{n_nivel}</span>
  </div>
</div>""", unsafe_allow_html=True)

    tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs([
        "🥇 ORO","📈 ÍNDICES","💱 FOREX","🛢️ MATERIAS","₿ CRYPTO","⚡ WELTRADE"
    ])

    with tab1:
        try:
            _render_asset("XAUUSD", n_nivel, n_txt, pen)
        except Exception as ex:
            st.error(f"Error ORO: {ex}")
            st.code(traceback.format_exc())

    with tab2:
        try:
            for sym in ["US30","US100","SPX500","GER40","UK100"]:
                st.markdown(f"#### {MDEF[sym][1]}")
                _render_asset(sym, n_nivel, n_txt, pen)
                st.markdown("---")
        except Exception as ex:
            st.error(f"Error ÍNDICES: {ex}")
            st.code(traceback.format_exc())

    with tab3:
        try:
            c1,c2 = st.columns(2)
            pairs = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDMXN"]
            for i,sym in enumerate(pairs):
                with (c1 if i%2==0 else c2):
                    st.markdown(f"#### {MDEF[sym][1]}")
                    _render_asset(sym, n_nivel, n_txt, pen)
        except Exception as ex:
            st.error(f"Error FOREX: {ex}")
            st.code(traceback.format_exc())

    with tab4:
        try:
            for sym in ["XAGUSD","WTIUSD"]:
                st.markdown(f"#### {MDEF[sym][1]}")
                _render_asset(sym, n_nivel, n_txt, pen)
                st.markdown("---")
        except Exception as ex:
            st.error(f"Error MATERIAS: {ex}")
            st.code(traceback.format_exc())

    with tab5:
        try:
            c1,c2 = st.columns(2)
            cryptos = ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD"]
            for i,sym in enumerate(cryptos):
                with (c1 if i%2==0 else c2):
                    st.markdown(f"#### {MDEF[sym][1]}")
                    _render_asset(sym, n_nivel, n_txt, pen)
        except Exception as ex:
            st.error(f"Error CRYPTO: {ex}")
            st.code(traceback.format_exc())

    with tab6:
        try:
            _render_weltrade_tab(n_nivel, n_txt, pen)
        except Exception as ex:
            st.error(f"Error WELTRADE: {ex}")
            st.code(traceback.format_exc())

    st.markdown("""
<div style="color:#0a0a14;font-size:.68em;text-align:center;margin-top:1.2rem;
  padding-top:.6rem;border-top:1px solid #0a0a12">
  RAVEN TRADE IDEAS PRO · Solo educativo · Gestiona siempre tu riesgo
</div>""", unsafe_allow_html=True)

    # Auto-refresh sin bloquear UI
    _stc.html(
        f'<script>setTimeout(function(){{window.parent.location.reload();}},{REFRESH*1000});</script>',
        height=0
    )

if __name__ == "__main__":
    main()
