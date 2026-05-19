# raven_trade_ideas.py · v7
# RAVEN TRADE IDEAS — Asistente profesional
# Una señal por activo. Seguimiento completo. Sin ruido.

import streamlit as st
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import requests
import json
import os as _os
from datetime import datetime, timezone, timedelta
import time

try:
    import yfinance as yf
    _YF_OK = True
except ImportError:
    _YF_OK = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
MIN_SCORE_SHOW  = 70    # mínimo para mostrar idea
MIN_SCORE_ENTRY = 80    # mínimo para ENTRADA_VALIDA
LATE_PULLBACK   = 0.35  # % avance hacia TP1 → esperar pullback
LATE_CANCEL     = 0.62  # % avance → cancelar
COOLDOWN_MIN    = 15    # minutos entre ideas
STATE_FILE      = r"C:\Users\saems\raven_state.json"
REFRESH         = 45    # segundos entre actualizaciones automáticas

# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA + CSS
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="RAVEN TRADE IDEAS", page_icon="🥇",
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#06060e}
[data-testid="stHeader"]{background:transparent}
.block-container{padding:.8rem 1.6rem;max-width:1180px}
div[data-testid="stButton"]>button{background:#12121e;color:#ccc;border:1px solid #252535;
  border-radius:6px;font-size:.82em;padding:4px 14px}
div[data-testid="stButton"]>button:hover{background:#1e1e32}
div[data-testid="metric-container"]{background:#0a0a12;border:1px solid #16162a;
  border-radius:8px;padding:8px 12px}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# ESTADOS — colores, íconos, acciones
# ═══════════════════════════════════════════════════════════════════════════════
_SC = {
    "BUSCANDO_SETUP":     dict(icon="🔴", label="NO OPERAR",          color="#ff5252", bg="#100008"),
    "IDEA_EN_FORMACION":  dict(icon="🟡", label="IDEA EN FORMACIÓN",  color="#ffd600", bg="#100e00"),
    "ESPERANDO_PULLBACK": dict(icon="⏳", label="ESPERAR PULLBACK",   color="#ff9800", bg="#100800"),
    "ENTRADA_VALIDA":     dict(icon="🟢", label="ENTRADA VÁLIDA",     color="#00e676", bg="#001410"),
    "EN_OPERACION":       dict(icon="🔵", label="EN OPERACIÓN",       color="#42a5f5", bg="#001020"),
    "TP1_ALCANZADO":      dict(icon="✅", label="TP1 ALCANZADO",      color="#69f0ae", bg="#001a0c"),
    "TP2_ALCANZADO":      dict(icon="✅", label="TP2 ALCANZADO",      color="#00e676", bg="#002014"),
    "TP3_ALCANZADO":      dict(icon="🏆", label="TP3 ALCANZADO",      color="#ffd600", bg="#141000"),
    "STOP_LOSS":          dict(icon="❌", label="STOP LOSS",          color="#ff5252", bg="#180000"),
    "INVALIDADA":         dict(icon="⛔", label="SEÑAL INVALIDADA",   color="#ff5252", bg="#120000"),
    "CANCELAR_IDEA":      dict(icon="🚫", label="CANCELAR IDEA",      color="#ff9800", bg="#100800"),
}
_ACCION = {
    "BUSCANDO_SETUP":     "Sin setup válido. Monitorear mercado.",
    "IDEA_EN_FORMACION":  "Setup posible — esperar más confirmación antes de entrar.",
    "ESPERANDO_PULLBACK": "Setup válido pero entrada tardía. Esperar retroceso al nivel de entrada.",
    "ENTRADA_VALIDA":     "Precio en zona de entrada. Se puede ejecutar la operación.",
    "EN_OPERACION":       "Trade activo. Gestionar con SL y TPs definidos.",
    "TP1_ALCANZADO":      "TP1 cumplido. Mover SL a breakeven. Considerar cerrar 30-50%.",
    "TP2_ALCANZADO":      "TP2 cumplido. Mover SL a TP1. Dejar el resto correr hacia TP3.",
    "TP3_ALCANZADO":      "Objetivo completo. Cerrar toda la posición.",
    "STOP_LOSS":          "Idea fallida. No recuperable. Esperar nuevo setup.",
    "INVALIDADA":         "Estructura cambió. No operar esta idea.",
    "CANCELAR_IDEA":      "El movimiento ya corrió. Esperar nueva oportunidad.",
}
_CLOSED = {"STOP_LOSS", "TP3_ALCANZADO", "INVALIDADA", "CANCELAR_IDEA"}

# ═══════════════════════════════════════════════════════════════════════════════
# YAHOO FINANCE — MAPEO
# ═══════════════════════════════════════════════════════════════════════════════
YAHOO_MAP = {
    "xauusd":"GC=F","xauusdm":"GC=F","xauusdc":"GC=F","xauusd+":"GC=F",
    "xauusd.":"GC=F","gold":"GC=F","xau/usd":"GC=F","xauusdz":"GC=F","xauusdi":"GC=F",
    "us30":"^DJI","dj30":"^DJI","djia":"^DJI","us30cash":"^DJI","dj30cash":"^DJI",
    "wallst30":"^DJI","wallstreet30":"^DJI","us30m":"^DJI","dji":"^DJI","dow30":"^DJI",
}

def _yt(symbol):
    k = symbol.lower().replace(" ","").replace("/","")
    if k in YAHOO_MAP: return YAHOO_MAP[k]
    if "xau" in k or "gold" in k: return "GC=F"
    if "us30" in k or "dj30" in k or "djia" in k or "dow" in k: return "^DJI"
    return None

def _is_gold(symbol):
    return _yt(symbol) == "GC=F" or "xau" in symbol.lower()

# ═══════════════════════════════════════════════════════════════════════════════
# DATOS — MT5 + Yahoo Finance
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def _mt5_ok():
    try: return mt5.initialize()
    except: return False

@st.cache_data(ttl=25, show_spinner=False)
def _yf_price(yticker):
    if not _YF_OK: return None
    try:
        p = yf.Ticker(yticker).fast_info.last_price
        if p and float(p) > 0: return float(p)
    except: pass
    try:
        df = yf.Ticker(yticker).history(period="1d", interval="1m")
        if not df.empty: return float(df["Close"].iloc[-1])
    except: pass
    return None

@st.cache_data(ttl=120, show_spinner=False)
def _yf_bars(yticker, interval, n):
    if not _YF_OK: return None
    pm = {"2m":"1d","5m":"5d","15m":"5d","1h":"60d","1d":"2y"}
    try:
        df = yf.Ticker(yticker).history(period=pm.get(interval,"60d"), interval=interval)
        if df.empty: return None
        df.columns = [c.lower() for c in df.columns]
        for c in ["open","high","low","close"]:
            if c not in df.columns: return None
        if "volume" not in df.columns: df["volume"] = 0
        df.index = pd.to_datetime(df.index, utc=True)
        return df[["open","high","low","close","volume"]].tail(n)
    except: return None

def _yf_h4(yticker, n=200):
    df = _yf_bars(yticker, "1h", 800)
    if df is None: return None
    return df.resample("4h").agg(open="first",high="max",low="min",close="last",volume="sum").dropna().tail(n)

_TF_YF = {
    mt5.TIMEFRAME_M1:"2m", mt5.TIMEFRAME_M5:"5m",
    mt5.TIMEFRAME_M15:"15m", mt5.TIMEFRAME_H1:"1h", mt5.TIMEFRAME_D1:"1d",
}

def _price(symbol):
    if _mt5_ok():
        mt5.symbol_select(symbol, True); time.sleep(0.15)
        for _ in range(3):
            t = mt5.symbol_info_tick(symbol)
            if t and t.bid > 0: return (t.bid+t.ask)/2, "MT5"
            time.sleep(0.3)
    yt = _yt(symbol)
    if yt:
        p = _yf_price(yt)
        if p: return p, "Yahoo"
    return None, None

def _bars(symbol, tf, n=400):
    if _mt5_ok():
        mt5.symbol_select(symbol, True)
        r = mt5.copy_rates_from_pos(symbol, tf, 0, n)
        if r is not None and len(r) > 10:
            df = pd.DataFrame(r)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            return df.set_index("time")
    yt = _yt(symbol)
    if not yt: return None
    if tf == mt5.TIMEFRAME_H4: return _yf_h4(yt, n)
    return _yf_bars(yt, _TF_YF.get(tf,"1h"), n)

XAUUSD_NAMES = ["XAUUSD","XAUUSDm","XAUUSDc","XAUUSD+","XAUUSD.","Gold","GOLD","XAU/USD","XAUUSDz","XAUUSDi"]
DJ30_NAMES   = ["US30","DJ30","DJIA","US30Cash","DJ30Cash","WallSt30","WallStreet30","US30m","DJI","Dow30"]

def _find_mt5(names):
    for n in names:
        if mt5.symbol_info(n) is None: continue
        mt5.symbol_select(n, True); time.sleep(0.2)
        t = mt5.symbol_info_tick(n)
        if t and t.bid > 0: return n
    kw = {n.lower().replace("/","").replace(" ","") for n in names}
    all_s = mt5.symbols_get()
    if all_s:
        for s in all_s:
            sn = s.name.lower().replace("/","").replace(" ","")
            if any(k in sn or sn in k for k in kw):
                mt5.symbol_select(s.name, True); time.sleep(0.2)
                t = mt5.symbol_info_tick(s.name)
                if t and t.bid > 0: return s.name
    return None

@st.cache_data(ttl=120, show_spinner=False)
def _find_xauusd():
    if _mt5_ok():
        s = _find_mt5(XAUUSD_NAMES)
        if s: return s, "MT5"
    if _YF_OK and _yf_price("GC=F"): return "XAUUSD","Yahoo"
    return None, None

@st.cache_data(ttl=120, show_spinner=False)
def _find_dj30():
    if _mt5_ok():
        s = _find_mt5(DJ30_NAMES)
        if s: return s, "MT5"
    if _YF_OK and _yf_price("^DJI"): return "US30","Yahoo"
    return None, None

def _pipval(symbol, provider="Yahoo"):
    if provider == "MT5" and _mt5_ok():
        info = mt5.symbol_info(symbol)
        if info and info.trade_tick_size > 0:
            return info.trade_tick_value / info.trade_tick_size
    yt = _yt(symbol)
    return 10 if yt == "GC=F" else 1

# ═══════════════════════════════════════════════════════════════════════════════
# NOTICIAS
# ═══════════════════════════════════════════════════════════════════════════════
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
                    except: pass
        except: pass
    return sorted(ev, key=lambda x: x["dt"])

def _news_risk(ev):
    now = datetime.now(timezone.utc)
    for e in ev:
        d = (e["dt"]-now).total_seconds()/60
        if -30 <= d <= 30:
            return "PELIGRO", f"🔴 PELIGRO — {e['titulo']} {'+' if d>0 else ''}{int(d)} min"
        if 30 < d <= 120:
            return "PRECAUCION", f"🟡 PRECAUCIÓN — {e['titulo']} en {int(d)} min"
    fut = [e for e in ev if (e["dt"]-now).total_seconds()>0]
    if fut:
        p=fut[0]; m=int((p["dt"]-now).total_seconds()/60)
        return "SEGURO", f"🟢 Sin peligro — próximo: {p['titulo']} en {m} min"
    return "SEGURO","🟢 Sin eventos de alto impacto"

# ═══════════════════════════════════════════════════════════════════════════════
# INDICADORES
# ═══════════════════════════════════════════════════════════════════════════════
def _ema(s,n): return s.ewm(span=n,adjust=False).mean()
def _sma(s,n): return s.rolling(n).mean()
def _rsi(s,n=14):
    d=s.diff(); g=d.where(d>0,0).rolling(n).mean()
    lo=(-d.where(d<0,0)).rolling(n).mean()
    return 100-100/(1+g/lo.replace(0,np.nan))
def _atr(df,n=14):
    h,l,c=df.high,df.low,df.close
    tr=pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()
def _bb(s,n=20,k=2):
    ma=_sma(s,n); std=s.rolling(n).std()
    return ma+k*std, ma, ma-k*std
def _kc(df,n=20,m=1.5):
    mid=_ema(df.close,n); a=_atr(df,n)
    return mid+m*a, mid, mid-m*a
def _swing_lows(df,n=3):
    return [i for i in range(n,len(df)-n) if df.low.iloc[i]==df.low.iloc[i-n:i+n+1].min()]
def _swing_highs(df,n=3):
    return [i for i in range(n,len(df)-n) if df.high.iloc[i]==df.high.iloc[i-n:i+n+1].max()]

# ═══════════════════════════════════════════════════════════════════════════════
# RIESGO — TP1·1.5 | TP2·2.5 | TP3·4.0
# ═══════════════════════════════════════════════════════════════════════════════
def _risk(entry, sl, direction, pp=10):
    d = abs(entry-sl)
    if d < 0.01: return None
    s = 1 if direction=="buy" else -1
    return dict(sl_d=d,
                tp1=entry+s*d*1.5, rr1=1.5, g1=d*1.5*pp,
                tp2=entry+s*d*2.5, rr2=2.5, g2=d*2.5*pp,
                tp3=entry+s*d*4.0, rr3=4.0, g3=d*4.0*pp,
                riesgo=d*pp)

def _fmt(v, dec=2): return f"{v:,.{dec}f}"

# ═══════════════════════════════════════════════════════════════════════════════
# ESTRATEGIAS — detectores de señal (sin cambios de lógica)
# ═══════════════════════════════════════════════════════════════════════════════
def strat_london_breakout(df_h1, precio):
    ahora = datetime.now(timezone.utc); h=ahora.hour
    if not (7<=h<10): return None
    hoy=ahora.replace(hour=0,minute=0,second=0,microsecond=0)
    asian=df_h1[(df_h1.index>=hoy)&(df_h1.index<hoy.replace(hour=7))]
    if len(asian)<3: return None
    a_hi=asian.high.max(); a_lo=asian.low.min(); a_rng=a_hi-a_lo
    if a_rng<5: return None
    at=_atr(df_h1).iloc[-1]; thr=a_rng*0.12
    for direction,cond,sl_ref in [
        ("buy", precio>a_hi+thr, a_lo-at*0.5),
        ("sell",precio<a_lo-thr, a_hi+at*0.5),
    ]:
        if not cond: continue
        r=_risk(precio,sl_ref,direction)
        if r is None: continue
        sc=58
        body_sum=(asian.close-asian.open).abs().sum(); rng_sum=(asian.high-asian.low).sum()
        if rng_sum>0 and body_sum/rng_sum>0.55: sc+=8
        ld=df_h1[df_h1.index>=hoy.replace(hour=7)]
        breaks=(ld.high>a_hi).sum() if direction=="buy" else (ld.low<a_lo).sum()
        if breaks<=1: sc+=10
        at_avg=_atr(df_h1).rolling(20).mean().iloc[-1]
        if at>at_avg*1.15: sc+=6
        return dict(estrategia="LONDON BREAKOUT",icon="🇬🇧",dir=direction,tipo="INTRADAY",
                    dur="~1-4h",entry=precio,sl=sl_ref,score_base=min(sc,88),
                    ctx=f"Rango asiático {a_lo:.2f}–{a_hi:.2f} ({a_rng:.1f} pts)",**r)
    return None

def strat_trend_pullback(df_d1,df_h4,df_h1,df_m15,precio):
    for df,n in [(df_d1,30),(df_h4,50),(df_h1,60),(df_m15,30)]:
        if df is None or len(df)<n: return None
    e20d=_ema(df_d1.close,20).iloc[-1]; e50d=_ema(df_d1.close,50).iloc[-1]
    e20h4=_ema(df_h4.close,20).iloc[-1]; e50h4=_ema(df_h4.close,50).iloc[-1]
    e20h=_ema(df_h1.close,20).iloc[-1];  e50h=_ema(df_h1.close,50).iloc[-1]; e200h=_ema(df_h1.close,200).iloc[-1]
    d1b=df_d1.close.iloc[-1]>e20d>e50d; h4b=e20h4>e50h4; h1b=e20h>e50h>e200h
    d1s=df_d1.close.iloc[-1]<e20d<e50d; h4s=e20h4<e50h4; h1s=e20h<e50h<e200h
    bull=sum([d1b,h4b,h1b]); bear=sum([d1s,h4s,h1s])
    if bull<2 and bear<2: return None
    at=_atr(df_h1).iloc[-1]; rs=_rsi(df_m15.close).iloc[-1]
    direction="buy" if bull>=bear else "sell"
    if direction=="buy":
        dist=precio-e20h
        if not (-at*0.9<=dist<=at*0.4): return None
        if not (35<=rs<=55): return None
        sl=e50h-at*0.3; sc=62+bull*9+(5 if 40<=rs<=50 else 0)
    else:
        dist=e20h-precio
        if not (-at*0.9<=dist<=at*0.4): return None
        if not (45<=rs<=65): return None
        sl=e50h+at*0.3; sc=62+bear*9+(5 if 50<=rs<=60 else 0)
    r=_risk(precio,sl,direction)
    if r is None: return None
    td=f"D1:{'▲' if d1b else '▼'}  H4:{'▲' if h4b else '▼'}  H1:{'▲' if h1b else '▼'}"
    return dict(estrategia="PULLBACK TENDENCIA MTF",icon="📐",dir=direction,tipo="SWING",
                dur="~4-24h",entry=precio,sl=sl,score_base=min(sc,93),
                ctx=f"{td} · RSI M15:{rs:.0f} · EMA20 H1:{e20h:.2f}",**r)

def strat_ema_momentum(df_h1,df_m15,precio):
    if df_h1 is None or len(df_h1)<30 or df_m15 is None or len(df_m15)<20: return None
    e9=_ema(df_h1.close,9); e21=_ema(df_h1.close,21); e50=_ema(df_h1.close,50)
    at=_atr(df_h1).iloc[-1]; at_avg=_atr(df_h1).rolling(20).mean().iloc[-1]
    if at<at_avg*0.65: return None
    rh=_rsi(df_h1.close).iloc[-1]; rm=_rsi(df_m15.close).iloc[-1]
    cb=e9.iloc[-2]<e21.iloc[-2] and e9.iloc[-1]>e21.iloc[-1]
    cs=e9.iloc[-2]>e21.iloc[-2] and e9.iloc[-1]<e21.iloc[-1]
    if not cb and not cs:
        cb=e9.iloc[-3]<e21.iloc[-3] and e9.iloc[-2]>e21.iloc[-2] and precio>e9.iloc[-1]
        cs=e9.iloc[-3]>e21.iloc[-3] and e9.iloc[-2]<e21.iloc[-2] and precio<e9.iloc[-1]
    if not cb and not cs: return None
    if cb and 48<=rh<=72 and precio>e21.iloc[-1]*0.998:
        sl=e21.iloc[-1]-at*0.5; sc=63+(8 if precio>e50.iloc[-1] else 0)+(5 if 52<rh<65 else 0)+(4 if 52<rm<65 else 0)
        r=_risk(precio,sl,"buy")
        if r is None: return None
        return dict(estrategia="CRUCE EMA MOMENTUM",icon="⚡",dir="buy",tipo="INTRADAY",dur="~1-4h",
                    entry=precio,sl=sl,score_base=min(sc,85),ctx=f"Cruce EMA9/21 H1 ↑ · RSI H1:{rh:.0f} M15:{rm:.0f}",**r)
    if cs and 28<=rh<=52 and precio<e21.iloc[-1]*1.002:
        sl=e21.iloc[-1]+at*0.5; sc=63+(8 if precio<e50.iloc[-1] else 0)+(5 if 35<rh<48 else 0)+(4 if 35<rm<48 else 0)
        r=_risk(precio,sl,"sell")
        if r is None: return None
        return dict(estrategia="CRUCE EMA MOMENTUM",icon="⚡",dir="sell",tipo="INTRADAY",dur="~1-4h",
                    entry=precio,sl=sl,score_base=min(sc,85),ctx=f"Cruce EMA9/21 H1 ↓ · RSI H1:{rh:.0f} M15:{rm:.0f}",**r)
    return None

def strat_supply_demand(df_h4,df_h1,precio):
    if df_h4 is None or len(df_h4)<50 or df_h1 is None or len(df_h1)<20: return None
    at4=_atr(df_h4).iloc[-1]; rh=_rsi(df_h1.close).iloc[-1]
    for idx in _swing_lows(df_h4,n=4)[-10:]:
        z=df_h4.low.iloc[idx]; zt,zb=z+at4,z-at4*0.3
        if zb<=precio<=zt and rh<42:
            sl=z-at4*0.45; r=_risk(precio,sl,"buy")
            if r is None: continue
            tests=sum(1 for i in range(len(df_h4)) if zb<=df_h4.low.iloc[i]<=zt)
            sc=66+(10 if tests<=2 else 0)+(10 if rh<35 else 0)
            return dict(estrategia="ZONA DEMANDA S&D",icon="🏛️",dir="buy",tipo="SWING",dur="~4-24h",
                        entry=precio,sl=sl,score_base=min(sc,92),ctx=f"Zona {z:.2f} · RSI:{rh:.0f} · {tests}x testeada",**r)
    for idx in _swing_highs(df_h4,n=4)[-10:]:
        z=df_h4.high.iloc[idx]; zb,zt=z-at4,z+at4*0.3
        if zb<=precio<=zt and rh>58:
            sl=z+at4*0.45; r=_risk(precio,sl,"sell")
            if r is None: continue
            tests=sum(1 for i in range(len(df_h4)) if zb<=df_h4.high.iloc[i]<=zt)
            sc=66+(10 if tests<=2 else 0)+(10 if rh>65 else 0)
            return dict(estrategia="ZONA OFERTA S&D",icon="🏛️",dir="sell",tipo="SWING",dur="~4-24h",
                        entry=precio,sl=sl,score_base=min(sc,92),ctx=f"Zona {z:.2f} · RSI:{rh:.0f} · {tests}x testeada",**r)
    return None

def strat_bb_squeeze(df_h1,precio):
    if df_h1 is None or len(df_h1)<30: return None
    bbu,bbm,bbd=_bb(df_h1.close,20,2); kcu,kcm,kcd=_kc(df_h1,20,1.5)
    at=_atr(df_h1).iloc[-1]; rh=_rsi(df_h1.close).iloc[-1]
    sq=bbu.iloc[-2]<kcu.iloc[-2] and bbd.iloc[-2]>kcd.iloc[-2]
    if not sq: sq=bbu.iloc[-3]<kcu.iloc[-3] and bbd.iloc[-3]>kcd.iloc[-3]
    if not sq: return None
    rel=bbu.iloc[-1]>kcu.iloc[-1] or bbd.iloc[-1]<kcd.iloc[-1]
    if not rel: return None
    roc=(df_h1.close.iloc[-1]/df_h1.close.iloc[-6]-1)*100
    if roc>0.1 and precio>bbm.iloc[-1] and rh>50:
        sl=bbm.iloc[-1]-at*0.5; r=_risk(precio,sl,"buy")
        if r is None: return None
        sc=68+(7 if roc>0.3 else 0)+(5 if rh>55 else 0)
        return dict(estrategia="BB SQUEEZE BREAKOUT",icon="💥",dir="buy",tipo="INTRADAY",dur="~1-3h",
                    entry=precio,sl=sl,score_base=min(sc,88),ctx=f"Squeeze ↑ · ROC:{roc:.2f}% · RSI:{rh:.0f}",**r)
    if roc<-0.1 and precio<bbm.iloc[-1] and rh<50:
        sl=bbm.iloc[-1]+at*0.5; r=_risk(precio,sl,"sell")
        if r is None: return None
        sc=68+(7 if roc<-0.3 else 0)+(5 if rh<45 else 0)
        return dict(estrategia="BB SQUEEZE BREAKOUT",icon="💥",dir="sell",tipo="INTRADAY",dur="~1-3h",
                    entry=precio,sl=sl,score_base=min(sc,88),ctx=f"Squeeze ↓ · ROC:{roc:.2f}% · RSI:{rh:.0f}",**r)
    return None

def strat_precio_accion(df_h1,precio,df_d1=None,df_h4=None):
    if df_h1 is None or len(df_h1)<5: return None
    at=_atr(df_h1).iloc[-1]; rh=_rsi(df_h1.close).iloc[-1]
    o2,h2,l2,c2=df_h1[["open","high","low","close"]].iloc[-2].values
    o1,h1_,l1,c1=df_h1[["open","high","low","close"]].iloc[-1].values
    b2=abs(c2-o2); b1=abs(c1-o1); rng1=h1_-l1
    if rng1<at*0.3: return None
    hammer=(b1>0)and(c1-l1)>b1*2.5 and(c1>o1)and(h1_-c1)<b1*0.4
    shooting=(b1>0)and(h1_-c1)>b1*2.5 and(c1<o1)and(c1-l1)<b1*0.4
    eng_bull=(c2<o2)and(c1>o1)and(c1>o2)and(o1<c2)and b1>b2*1.1
    eng_bear=(c2>o2)and(c1<o1)and(c1<o2)and(o1>c2)and b1>b2*1.1
    buy_pat=hammer or eng_bull; sell_pat=shooting or eng_bear
    if not buy_pat and not sell_pat: return None
    mtf_b=0; mtf_s=0
    if df_d1 is not None and len(df_d1)>=50:
        e20d=_ema(df_d1.close,20).iloc[-1]
        if df_d1.close.iloc[-1]<e20d: mtf_s+=1
        else: mtf_b+=1
    if df_h4 is not None and len(df_h4)>=30:
        e20h4=_ema(df_h4.close,20).iloc[-1]; e50h4=_ema(df_h4.close,50).iloc[-1]
        if e20h4<e50h4: mtf_s+=1
        else: mtf_b+=1
    if len(df_h1)>=50:
        e50h1=_ema(df_h1.close,50).iloc[-1]
        if df_h1.close.iloc[-1]<e50h1: mtf_s+=1
        else: mtf_b+=1
    if buy_pat and mtf_s>=2 and rh>28: return None
    if sell_pat and mtf_b>=2 and rh<72: return None
    if buy_pat and precio<c1*0.9995: return None
    if sell_pat and precio>c1*1.0005: return None
    near=False
    for step in [50,100]:
        if abs(precio-round(precio/step)*step)<=at*1.5: near=True; break
    if df_d1 is not None and len(df_d1)>=2:
        if abs(precio-df_d1.high.iloc[-2])<=at*1.5 or abs(precio-df_d1.low.iloc[-2])<=at*1.5: near=True
    if not near and (mtf_s>=1 or mtf_b>=1): return None
    if buy_pat and rh<65:
        sl=(l1 if hammer else min(l1,l2))-at*0.3; r=_risk(c1,sl,"buy")
        if r is None: return None
        patron="Engulfing Alcista" if eng_bull else "Martillo"
        sc=63+(8 if eng_bull else 0)+(12 if near else 0)+(8 if rh<35 else 0)+(5 if mtf_b>=1 else 0)
        return dict(estrategia=f"PRECIO ACCIÓN — {patron}",icon="🕯️",dir="buy",tipo="INTRADAY",dur="~1-4h",
                    entry=c1,sl=sl,score_base=min(sc,91),ctx=f"{patron} · RSI:{rh:.0f} · MTF:{'▼'*mtf_s}{'▲'*mtf_b}",**r)
    if sell_pat and rh>35:
        sl=(h1_ if shooting else max(h1_,h2))+at*0.3; r=_risk(c1,sl,"sell")
        if r is None: return None
        patron="Engulfing Bajista" if eng_bear else "Estrella Fugaz"
        sc=63+(8 if eng_bear else 0)+(12 if near else 0)+(8 if rh>65 else 0)+(5 if mtf_s>=1 else 0)
        return dict(estrategia=f"PRECIO ACCIÓN — {patron}",icon="🕯️",dir="sell",tipo="INTRADAY",dur="~1-4h",
                    entry=c1,sl=sl,score_base=min(sc,91),ctx=f"{patron} · RSI:{rh:.0f} · MTF:{'▼'*mtf_s}{'▲'*mtf_b}",**r)
    return None

def strat_scalp_ema(df_m5,df_m15,df_h1,precio):
    if any(df is None or len(df)<30 for df in [df_m5,df_m15,df_h1]): return None
    e9=_ema(df_m5.close,9); e21=_ema(df_m5.close,21)
    at5=_atr(df_m5).iloc[-1]; at5avg=_atr(df_m5).rolling(20).mean().iloc[-1]
    if at5<at5avg*0.6: return None
    rh1=_rsi(df_h1.close).iloc[-1]; rm=_rsi(df_m15.close).iloc[-1]
    e20h1=_ema(df_h1.close,20).iloc[-1]; e50h1=_ema(df_h1.close,50).iloc[-1]
    cb=e9.iloc[-2]<e21.iloc[-2] and e9.iloc[-1]>e21.iloc[-1]
    cs=e9.iloc[-2]>e21.iloc[-2] and e9.iloc[-1]<e21.iloc[-1]
    if not cb and not cs:
        cb=(e9.iloc[-3]<e21.iloc[-3] and e9.iloc[-2]>e21.iloc[-2] and precio>e9.iloc[-1])
        cs=(e9.iloc[-3]>e21.iloc[-3] and e9.iloc[-2]<e21.iloc[-2] and precio<e9.iloc[-1])
    if not cb and not cs: return None
    if cb and e20h1>e50h1 and 48<=rm<=72:
        sl=e21.iloc[-1]-at5*1.2
        if abs(precio-sl)<2: return None
        r=_risk(precio,sl,"buy")
        if r is None: return None
        sc=66+(7 if rm>55 else 0)+(5 if rh1>50 else 0)
        return dict(estrategia="EMA SCALP M5",icon="🏹",dir="buy",tipo="SCALP",dur="~5-20 min",
                    entry=precio,sl=sl,score_base=min(sc,86),ctx=f"Cruce EMA9/21 M5 ↑ · RSI M15:{rm:.0f}",**r)
    if cs and e20h1<e50h1 and 28<=rm<=52:
        sl=e21.iloc[-1]+at5*1.2
        if abs(precio-sl)<2: return None
        r=_risk(precio,sl,"sell")
        if r is None: return None
        sc=66+(7 if rm<45 else 0)+(5 if rh1<50 else 0)
        return dict(estrategia="EMA SCALP M5",icon="🏹",dir="sell",tipo="SCALP",dur="~5-20 min",
                    entry=precio,sl=sl,score_base=min(sc,86),ctx=f"Cruce EMA9/21 M5 ↓ · RSI M15:{rm:.0f}",**r)
    return None

def strat_scalp_momentum(df_m15,df_h1,precio):
    if df_m15 is None or len(df_m15)<10 or df_h1 is None or len(df_h1)<20: return None
    at15=_atr(df_m15).iloc[-1]; rm=_rsi(df_m15.close).iloc[-1]
    e20h1=_ema(df_h1.close,20).iloc[-1]; e50h1=_ema(df_h1.close,50).iloc[-1]
    o,h,l,c=df_m15[["open","high","low","close"]].iloc[-2].values
    body=abs(c-o); rng=h-l
    if rng<at15*1.3 or body<rng*0.65: return None
    if c>o and e20h1>e50h1 and 50<rm<80 and precio<=c+body*0.3:
        sl=l-at15*0.3
        if abs(precio-sl)<3: return None
        r=_risk(precio,sl,"buy")
        if r is None: return None
        sc=68+(7 if rm>60 else 0)+(5 if body>rng*0.8 else 0)
        return dict(estrategia="MOMENTUM M15",icon="🚀",dir="buy",tipo="SCALP",dur="~15-45 min",
                    entry=precio,sl=sl,score_base=min(sc,88),ctx=f"Vela alcista M15 {body:.1f}pts · RSI:{rm:.0f}",**r)
    if c<o and e20h1<e50h1 and 20<rm<50 and precio>=c-body*0.3:
        sl=h+at15*0.3
        if abs(precio-sl)<3: return None
        r=_risk(precio,sl,"sell")
        if r is None: return None
        sc=68+(7 if rm<40 else 0)+(5 if body>rng*0.8 else 0)
        return dict(estrategia="MOMENTUM M15",icon="🚀",dir="sell",tipo="SCALP",dur="~15-45 min",
                    entry=precio,sl=sl,score_base=min(sc,88),ctx=f"Vela bajista M15 {body:.1f}pts · RSI:{rm:.0f}",**r)
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# SCORE PROFESIONAL — 7 componentes, 100 pts
# ═══════════════════════════════════════════════════════════════════════════════
def _score_pro(sig, df_m1, df_m5, df_m15, df_h1, df_h4, precio):
    d = sig["dir"]
    pts = {}

    # 1. Contexto H1/H4 — 20 pts
    h4p = 0
    if df_h4 is not None and len(df_h4) >= 50:
        e20 = _ema(df_h4.close,20).iloc[-1]; e50 = _ema(df_h4.close,50).iloc[-1]
        h4p = 10 if (e20>e50 if d=="buy" else e20<e50) else 0
    h1p = 0
    if df_h1 is not None and len(df_h1) >= 50:
        e20=_ema(df_h1.close,20).iloc[-1]; e50=_ema(df_h1.close,50).iloc[-1]; c=df_h1.close.iloc[-1]
        if d=="buy":  h1p = 10 if c>e20>e50 else (5 if c>e50 else 0)
        else:         h1p = 10 if c<e20<e50 else (5 if c<e50 else 0)
    pts["ctx_h1_h4"] = h4p + h1p  # max 20

    # 2. Confirmación M15 — 15 pts
    m15p = 0
    if df_m15 is not None and len(df_m15) >= 20:
        e9=_ema(df_m15.close,9).iloc[-1]; e21=_ema(df_m15.close,21).iloc[-1]
        rsi15=_rsi(df_m15.close).iloc[-1]; c=df_m15.close.iloc[-1]
        if d=="buy":  m15p = 15 if c>e9>e21 and rsi15>50 else (8 if c>e21 else 0)
        else:         m15p = 15 if c<e9<e21 and rsi15<50 else (8 if c<e21 else 0)
    pts["conf_m15"] = m15p  # max 15

    # 3. Setup M5 — 25 pts (derivado del score_base de la estrategia)
    raw = sig.get("score_base", 65)
    pts["setup_m5"] = max(0, min(25, int((raw-55)/38*25)))  # max 25

    # 4. Confirmación M1 — 10 pts
    m1p = 0
    if df_m1 is not None and len(df_m1) >= 13:
        e9=_ema(df_m1.close,9).iloc[-1]
        e21=_ema(df_m1.close,21).iloc[-1] if len(df_m1)>=21 else e9
        c=df_m1.close.iloc[-1]
        if d=="buy":  m1p = 10 if c>e9>e21 else (5 if c>e21 else 0)
        else:         m1p = 10 if c<e9<e21 else (5 if c<e21 else 0)
    pts["conf_m1"] = m1p  # max 10

    # 5. Momentum — 10 pts
    momp = 0
    if df_m5 is not None and len(df_m5) >= 14:
        rsi5 = _rsi(df_m5.close).iloc[-1]
        if d=="buy":  momp = 10 if 50<=rsi5<=70 else (5 if 40<=rsi5<50 else 0)
        else:         momp = 10 if 30<=rsi5<=50 else (5 if 50<rsi5<=60 else 0)
    pts["momentum"] = momp  # max 10

    # 6. Volatilidad/ATR — 10 pts
    volp = 0
    if df_h1 is not None and len(df_h1) >= 20:
        atr=_atr(df_h1).iloc[-1]; avg=_atr(df_h1).rolling(20).mean().iloc[-1]
        if avg > 0:
            r = atr/avg
            volp = 10 if 0.75<=r<=1.6 else (5 if r>1.6 else 3)
    pts["vol_atr"] = volp  # max 10

    # 7. Entrada limpia — 10 pts
    entry=sig["entry"]; tp1=sig["tp1"]; dist=abs(tp1-entry)
    if dist > 0:
        prog = (precio-entry)/dist if d=="buy" else (entry-precio)/dist
        if   prog <= 0.05: cleanp = 10
        elif prog <= 0.15: cleanp = 8
        elif prog <= 0.30: cleanp = 5
        elif prog <= 0.50: cleanp = 2
        else:              cleanp = 0
    else:
        cleanp = 0
    pts["entrada_limpia"] = cleanp  # max 10

    return min(sum(pts.values()), 100), pts


def _score_label(score):
    if score >= 90: return "PREMIUM",         "#ffd600"
    if score >= 80: return "ALTA PROBABILIDAD","#00e676"
    if score >= 70: return "OBSERVAR",         "#42a5f5"
    return                  "NO OPERAR",       "#ff5252"

# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXTO MTF
# ═══════════════════════════════════════════════════════════════════════════════
def _contexto_mtf(df_m1, df_m5, df_m15, df_h1, df_h4):
    def _tf(df, fast, slow):
        if df is None or len(df) < slow:
            return {"label":"Sin datos","color":"#333","bull":0,"bear":0,"rsi":50}
        ef=_ema(df.close,fast).iloc[-1]; es=_ema(df.close,slow).iloc[-1]; c=df.close.iloc[-1]
        rsi=_rsi(df.close).iloc[-1] if len(df)>=14 else 50
        if c>ef>es:   return {"label":"▲ ALCISTA", "color":"#00e676","bull":1,"bear":0,"rsi":rsi}
        if c<ef<es:   return {"label":"▼ BAJISTA", "color":"#ff5252","bull":0,"bear":1,"rsi":rsi}
        if ef>es:     return {"label":"↗ LATERAL+","color":"#ffd600","bull":0.5,"bear":0,"rsi":rsi}
        return              {"label":"↘ LATERAL−","color":"#ff9800","bull":0,"bear":0.5,"rsi":rsi}
    return {
        "H4":  _tf(df_h4,  20, 50),
        "H1":  _tf(df_h1,  20, 50),
        "M15": _tf(df_m15,  9, 21),
        "M5":  _tf(df_m5,   9, 21),
        "M1":  _tf(df_m1,   5, 13),
    }

def _razon_tipo(tipo, ctx):
    h1  = ctx.get("H1",{}).get("label","?")
    m15 = ctx.get("M15",{}).get("label","?")
    m5  = ctx.get("M5",{}).get("label","?")
    if tipo == "SCALP":
        return f"Scalp: M5 {m5.lower()} con H1 {h1.lower()}. Duración estimada: minutos. Entrada precisa."
    if tipo == "SWING":
        return f"Swing: Contexto H4/H1 con tendencia clara ({h1.lower()}). Duración: horas a días."
    return f"Intraday: H1 {h1.lower()} · M15 {m15.lower()} · setup ejecutado en M5 {m5.lower()}. Duración: 30 min – pocas horas."

def _razones_no_trade(ctx, score_max, df_m5, df_h1):
    r = []
    h1=ctx.get("H1",{}); m15=ctx.get("M15",{})
    if score_max < MIN_SCORE_SHOW:
        r.append(f"Score máximo detectado: {score_max}/100 — mínimo requerido: {MIN_SCORE_SHOW}/100")
    if h1.get("bull",0)>0.3 and m15.get("bear",0)>0.3:
        r.append("Conflicto: H1 alcista pero M15 bajista — esperar alineación")
    elif h1.get("bear",0)>0.3 and m15.get("bull",0)>0.3:
        r.append("Conflicto: H1 bajista pero M15 alcista — esperar alineación")
    rsi_h1=h1.get("rsi",50)
    if 44<=rsi_h1<=56:
        r.append(f"RSI H1 en zona neutral ({rsi_h1:.0f}) — sin momentum claro")
    if df_m5 is not None and len(df_m5)>=20:
        a=_atr(df_m5).iloc[-1]; avg=_atr(df_m5).rolling(20).mean().iloc[-1]
        if avg>0 and a<avg*0.65:
            r.append("Volatilidad M5 muy baja — mercado sin movimiento")
    h1lbl=h1.get("label","")
    if "LATERAL" in h1lbl:
        r.append(f"H1 en zona lateral ({h1lbl}) — sin tendencia definida")
    if not r:
        r.append("No hay setup limpio con suficiente confirmación en este momento")
        r.append("Esperar: ruptura de rango, pullback a zona clave, o alineación MTF")
    return r

# ═══════════════════════════════════════════════════════════════════════════════
# MÁQUINA DE ESTADOS
# ═══════════════════════════════════════════════════════════════════════════════
def _progreso(sig, precio):
    e=sig["entry"]; tp1=sig["tp1"]; dist=abs(tp1-e)
    if dist<=0: return 0
    return ((precio-e)/dist) if sig["dir"]=="buy" else ((e-precio)/dist)

def _transition(sig, precio, df_h1, df_m15):
    state=sig.get("state","IDEA_EN_FORMACION")
    d=sig["dir"]; e=sig["entry"]; sl=sig["sl"]
    tp1=sig["tp1"]; tp2=sig["tp2"]; tp3=sig["tp3"]

    # TP3
    if (d=="buy" and precio>=tp3) or (d=="sell" and precio<=tp3):
        return "TP3_ALCANZADO", f"Precio tocó TP3 ({tp3:.2f})"
    # TP2
    if state not in ("TP3_ALCANZADO","TP2_ALCANZADO"):
        if (d=="buy" and precio>=tp2) or (d=="sell" and precio<=tp2):
            return "TP2_ALCANZADO", f"Precio tocó TP2 ({tp2:.2f})"
    # TP1
    if state not in ("TP3_ALCANZADO","TP2_ALCANZADO","TP1_ALCANZADO"):
        if (d=="buy" and precio>=tp1) or (d=="sell" and precio<=tp1):
            return "TP1_ALCANZADO", f"Precio tocó TP1 ({tp1:.2f})"
    # SL
    if (d=="buy" and precio<=sl) or (d=="sell" and precio>=sl):
        return "STOP_LOSS", f"Precio tocó Stop Loss ({sl:.2f})"

    # Pre-entrada: invalidación / tardío / retorno
    if state in ("IDEA_EN_FORMACION","ESPERANDO_PULLBACK","ENTRADA_VALIDA"):
        prog = _progreso(sig, precio)
        if prog > LATE_CANCEL:
            return "CANCELAR_IDEA", f"Precio recorrió {prog*100:.0f}% hacia TP1 sin entrada — demasiado tarde"
        if prog > LATE_PULLBACK and state != "ESPERANDO_PULLBACK":
            return "ESPERANDO_PULLBACK", f"Precio avanzó {prog*100:.0f}% hacia TP1 — esperar retroceso a {e:.2f}"
        if prog <= 0.12 and state == "ESPERANDO_PULLBACK":
            return "ENTRADA_VALIDA", f"Precio regresó a zona de entrada tras pullback"
        # Invalidación por cambio de tendencia
        if df_h1 is not None and len(df_h1)>=50:
            e50h1=_ema(df_h1.close,50).iloc[-1]
            if d=="buy" and precio < e50h1*0.9995:
                return "INVALIDADA", "H1 rompió EMA50 bajista — setup de compra invalidado"
            if d=="sell" and precio > e50h1*1.0005:
                return "INVALIDADA", "H1 rompió EMA50 alcista — setup de venta invalidado"
        # Activar entrada
        if state=="ENTRADA_VALIDA":
            if (d=="buy" and precio>=e) or (d=="sell" and precio<=e):
                return "EN_OPERACION", f"Precio cruzó nivel de entrada ({e:.2f})"
    return None, None

# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENCIA
# ═══════════════════════════════════════════════════════════════════════════════
def _load_st():
    try:
        if _os.path.exists(STATE_FILE):
            with open(STATE_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except: pass
    return {}

def _save_st(data):
    try:
        with open(STATE_FILE,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
    except: pass

def _get_ast(symbol):
    return _load_st().get(symbol, {"signal":None,"closed_at":None,"cooldown_until":None})

def _set_ast(symbol, data):
    st_data=_load_st(); st_data[symbol]=data; _save_st(st_data)

def _log_change(sig, new_state, msg):
    ts=datetime.now(timezone.utc).strftime("%H:%M UTC")
    sig.setdefault("log",[]).append({"ts":ts,"state":new_state,"msg":msg})
    sig["state"]=new_state
    sig["updated_at"]=datetime.now(timezone.utc).isoformat()
    return sig

# ═══════════════════════════════════════════════════════════════════════════════
# SELECCIÓN DE MEJOR SEÑAL
# ═══════════════════════════════════════════════════════════════════════════════
def _select_best(candidatos, df_m1, df_m5, df_m15, df_h1, df_h4, precio, pen):
    scored = []
    for s in candidatos:
        if s is None: continue
        score, detail = _score_pro(s, df_m1, df_m5, df_m15, df_h1, df_h4, precio)
        score = max(score - pen, 0)
        if score < MIN_SCORE_SHOW: continue
        prog = _progreso(s, precio)
        if prog > LATE_CANCEL: continue
        s["score"] = score
        s["score_detail"] = detail
        scored.append(s)
    if not scored: return None, 0
    # Mayor score, desempate por entrada más limpia
    scored.sort(key=lambda x: (x["score"], x["score_detail"].get("entrada_limpia",0)), reverse=True)
    # Score máximo visto (para el panel no-trade)
    return scored[0], scored[0]["score"]

def _best_score_any(candidatos, df_m1, df_m5, df_m15, df_h1, df_h4, precio, pen):
    """Devuelve el mejor score posible aunque sea < MIN. Para panel no-trade."""
    best = 0
    for s in candidatos:
        if s is None: continue
        score, _ = _score_pro(s, df_m1, df_m5, df_m15, df_h1, df_h4, precio)
        score = max(score - pen, 0)
        if score > best: best = score
    return best

# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE ANÁLISIS — una llamada por activo
# ═══════════════════════════════════════════════════════════════════════════════
def _analizar(symbol, provider, pen):
    precio, src = _price(symbol)
    if precio is None: return None, None, None, None

    pp = _pipval(symbol, src or provider)

    df_m1  = _bars(symbol, mt5.TIMEFRAME_M1,  200)
    df_m5  = _bars(symbol, mt5.TIMEFRAME_M5,  400)
    df_m15 = _bars(symbol, mt5.TIMEFRAME_M15, 400)
    df_h1  = _bars(symbol, mt5.TIMEFRAME_H1,  400)
    df_h4  = _bars(symbol, mt5.TIMEFRAME_H4,  300)
    df_d1  = _bars(symbol, mt5.TIMEFRAME_D1,  200)

    ctx = _contexto_mtf(df_m1, df_m5, df_m15, df_h1, df_h4)
    ast = _get_ast(symbol)
    sig = ast.get("signal")

    # ── Actualizar señal activa ────────────────────────────────────────────────
    if sig and sig.get("state") not in _CLOSED:
        new_st, motivo = _transition(sig, precio, df_h1, df_m15)
        if new_st and new_st != sig.get("state"):
            sig = _log_change(sig, new_st, motivo)
            ast["signal"] = sig
            if new_st in _CLOSED:
                ast["closed_at"] = datetime.now(timezone.utc).isoformat()
                ast["cooldown_until"] = (datetime.now(timezone.utc)+timedelta(minutes=COOLDOWN_MIN)).isoformat()
            _set_ast(symbol, ast)

    # ── Buscar nueva señal si no hay activa ────────────────────────────────────
    sig_act = ast.get("signal")
    en_cd = False
    cd = ast.get("cooldown_until")
    if cd:
        try: en_cd = datetime.fromisoformat(cd) > datetime.now(timezone.utc)
        except: pass

    necesita_nueva = (sig_act is None or sig_act.get("state") in _CLOSED) and not en_cd

    # Construir candidatos
    gold = _is_gold(symbol)
    candidatos = [
        strat_london_breakout(df_h1, precio) if gold else None,
        strat_trend_pullback(df_d1, df_h4, df_h1, df_m15, precio),
        strat_ema_momentum(df_h1, df_m15, precio),
        strat_supply_demand(df_h4, df_h1, precio),
        strat_bb_squeeze(df_h1, precio),
        strat_precio_accion(df_h1, precio, df_d1, df_h4),
        strat_scalp_ema(df_m5, df_m15, df_h1, precio),
        strat_scalp_momentum(df_m15, df_h1, precio),
    ]

    score_max = _best_score_any(candidatos, df_m1, df_m5, df_m15, df_h1, df_h4, precio, pen)

    if necesita_nueva:
        mejor, _ = _select_best(candidatos, df_m1, df_m5, df_m15, df_h1, df_h4, precio, pen)
        if mejor:
            d = mejor["sl_d"]
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
                tipo_raw = mejor.get("tipo","INTRADAY")
                mejor["tipo_razon"] = _razon_tipo(tipo_raw, ctx)
                now = datetime.now(timezone.utc)
                mejor["id"] = f"{symbol}_{mejor['dir']}_{now.strftime('%H%M')}"
                mejor["created_at"] = now.isoformat()
                mejor["updated_at"] = now.isoformat()
                mejor["state"] = init
                mejor["symbol"] = symbol
                mejor["log"] = [{"ts":now.strftime("%H:%M UTC"),"state":init,
                    "msg":f"{mejor['estrategia']} detectado · Score {mejor['score']}/100"}]
                ast["signal"] = mejor
                ast["closed_at"] = None
                _set_ast(symbol, ast)
                sig_act = mejor

    razones_nt = _razones_no_trade(ctx, score_max, df_m5, df_h1) if not sig_act or sig_act.get("state") in _CLOSED else []

    ind = {
        "src":      src or provider,
        "precio":   precio,
        "atr_h1":   _atr(df_h1).iloc[-1] if df_h1 is not None else 0,
        "rsi_h1":   _rsi(df_h1.close).iloc[-1] if df_h1 is not None else 50,
        "e200_h1":  _ema(df_h1.close,200).iloc[-1] if df_h1 is not None else precio,
        "score_max":score_max,
        "razones_nt":razones_nt,
        "df_m5":    df_m5,
        "df_h1":    df_h1,
    }
    return ast, ctx, precio, ind

# ═══════════════════════════════════════════════════════════════════════════════
# UI — TARJETA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
def _render_card(sig, precio, decimals):
    state = sig.get("state","IDEA_EN_FORMACION")
    cfg   = _SC.get(state, _SC["IDEA_EN_FORMACION"])
    d     = sig["dir"]
    dc    = "#00e676" if d=="buy" else "#ff5252"
    dt    = "▲ COMPRAR" if d=="buy" else "▼ VENDER"
    tipo  = sig.get("tipo","INTRADAY")
    score = sig.get("score",0)
    sc_lbl, sc_col = _score_label(score)

    def f(v): return _fmt(v, decimals)

    accion = _ACCION.get(state,"")
    prog   = _progreso(sig, precio)
    prog_p = max(0, min(100, prog*100))
    bar_c  = "#00e676" if d=="buy" else "#ff5252"

    # Distancias
    d_e  = abs(precio - sig["entry"])
    d_sl = abs(precio - sig["sl"])
    d_t1 = abs(precio - sig["tp1"])

    tipo_razon = sig.get("tipo_razon","")

    # Score breakdown pills
    sd = sig.get("score_detail",{})
    comp_names = {
        "ctx_h1_h4":"H1/H4","conf_m15":"M15","setup_m5":"Setup M5",
        "conf_m1":"M1","momentum":"Momentum","vol_atr":"Volatilidad","entrada_limpia":"Entrada"
    }
    comp_max  = {"ctx_h1_h4":20,"conf_m15":15,"setup_m5":25,"conf_m1":10,"momentum":10,"vol_atr":10,"entrada_limpia":10}
    pills_html = ""
    for k,n in comp_names.items():
        v=sd.get(k,0); mx=comp_max[k]; pct=v/mx*100 if mx>0 else 0
        pc="#00e676" if pct>=70 else ("#ffd600" if pct>=40 else "#ff5252")
        pills_html += (f'<span style="background:#0a0a14;border:1px solid #1a1a28;border-radius:6px;'
                       f'padding:3px 8px;font-size:.68em;margin:2px">'
                       f'<span style="color:#444">{n}: </span>'
                       f'<span style="color:{pc};font-weight:700">{v}/{mx}</span></span>')

    st.markdown(f"""
<div style="background:linear-gradient(145deg,{cfg['bg']},#08080f);
  border:2px solid {cfg['color']};border-radius:14px;padding:1.5rem 1.8rem;margin-bottom:.6rem">

  <!-- HEADER: estado + activo + score -->
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
    <div>
      <div style="color:{cfg['color']};font-size:1.45em;font-weight:900;letter-spacing:.02em">
        {cfg['icon']} {cfg['label']}
      </div>
      <div style="color:#777;font-size:.9em;margin-top:4px">
        {sig.get('symbol','')} &nbsp;·&nbsp; {tipo} &nbsp;·&nbsp;
        <span style="color:{dc};font-weight:700">{dt}</span> &nbsp;·&nbsp;
        <span style="color:#555">{sig.get('icon','')} {sig.get('estrategia','')}</span>
      </div>
    </div>
    <div style="text-align:right">
      <div style="color:{sc_col};font-size:2.2em;font-weight:900;line-height:1">{score}</div>
      <div style="color:#333;font-size:.7em">/100 &nbsp; {sc_lbl}</div>
    </div>
  </div>

  <hr style="border:none;border-top:1px solid #141422;margin:.5rem 0 .8rem 0">

  <!-- PRECIOS -->
  <div style="display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:8px;margin-bottom:12px">
    <div style="background:#0c0c18;border:1px solid #1c1c2e;border-radius:8px;padding:10px 14px">
      <div style="color:#333;font-size:.65em;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px">Entrada ideal</div>
      <div style="color:#fff;font-size:1.1em;font-weight:700">{f(sig['entry'])}</div>
      <div style="color:#444;font-size:.72em;margin-top:2px">Ahora: <span style="color:#aaa">{f(precio)}</span></div>
    </div>
    <div style="background:#120008;border:1px solid #2e0010;border-radius:8px;padding:10px 14px">
      <div style="color:#333;font-size:.65em;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px">Stop Loss</div>
      <div style="color:#ff5252;font-size:1.1em;font-weight:700">{f(sig['sl'])}</div>
      <div style="color:#444;font-size:.72em;margin-top:2px">Riesgo: {f(sig['sl_d'])} pts</div>
    </div>
    <div style="background:#081408;border:1px solid #182a18;border-radius:8px;padding:10px 14px">
      <div style="color:#333;font-size:.65em;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px">Objetivos (RR)</div>
      <div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">
        <span style="color:#69f0ae;font-size:.85em;font-weight:700">TP1&nbsp;{f(sig['tp1'])}<span style="color:#333;font-size:.75em"> ·1:{sig['rr1']:.1f}</span></span>
        <span style="color:#00e676;font-size:.85em;font-weight:700">TP2&nbsp;{f(sig['tp2'])}<span style="color:#333;font-size:.75em"> ·1:{sig['rr2']:.1f}</span></span>
        <span style="color:#ffd600;font-size:.85em;font-weight:700">TP3&nbsp;{f(sig['tp3'])}<span style="color:#333;font-size:.75em"> ·1:{sig['rr3']:.1f}</span></span>
      </div>
    </div>
  </div>

  <!-- ACCIÓN -->
  <div style="background:#0a0a14;border-left:3px solid {cfg['color']};border-radius:0 8px 8px 0;
    padding:10px 14px;margin-bottom:10px">
    <div style="color:{cfg['color']};font-size:.75em;font-weight:700;text-transform:uppercase;
      letter-spacing:.06em;margin-bottom:3px">Acción recomendada</div>
    <div style="color:#ccc;font-size:.9em">{accion}</div>
  </div>

  <!-- PROGRESO HACIA TP1 -->
  <div style="margin-bottom:10px">
    <div style="display:flex;justify-content:space-between;margin-bottom:4px">
      <span style="color:#333;font-size:.7em">Avance hacia TP1</span>
      <span style="color:{bar_c};font-size:.76em;font-weight:700">{prog_p:.0f}%
        {"— en zona" if prog_p<=15 else ("— PULLBACK" if prog_p<=60 else "— TARDE")}</span>
    </div>
    <div style="background:#0e0e1a;border-radius:4px;height:5px;overflow:hidden">
      <div style="background:{bar_c};height:5px;width:{min(prog_p,100):.0f}%;
        border-radius:4px;transition:width .3s"></div>
    </div>
    <div style="display:flex;justify-content:space-between;margin-top:3px;color:#222;font-size:.65em">
      <span>Entrada {f(sig['entry'])}</span><span>TP1 {f(sig['tp1'])}</span>
    </div>
  </div>

  <!-- TIPO + MOTIVO -->
  <div style="background:#080812;border:1px solid #12122a;border-radius:8px;padding:8px 12px;margin-bottom:8px">
    <div style="color:#333;font-size:.68em;font-weight:700;text-transform:uppercase;
      letter-spacing:.06em;margin-bottom:3px">Por qué {tipo}</div>
    <div style="color:#555;font-size:.8em">{tipo_razon}</div>
  </div>

  <!-- SCORE BREAKDOWN -->
  <div style="margin-top:6px">{pills_html}</div>

</div>""", unsafe_allow_html=True)


def _render_tracking(sig, precio, decimals):
    """Panel de seguimiento numérico debajo de la tarjeta."""
    d=sig["dir"]; state=sig.get("state","")
    def f(v): return _fmt(v, decimals)
    prog_p = max(0, min(100, _progreso(sig, precio)*100))
    bar_c  = "#00e676" if d=="buy" else "#ff5252"
    ts     = sig.get("updated_at","")[:16].replace("T"," ")+" UTC" if sig.get("updated_at") else "—"

    d_entry = abs(precio - sig["entry"])
    d_sl    = abs(precio - sig["sl"])
    d_tp1   = abs(precio - sig["tp1"])
    d_tp2   = abs(precio - sig["tp2"])

    st.markdown(f"""
<div style="background:#080810;border:1px solid #141426;border-radius:10px;
  padding:1rem 1.4rem;margin-bottom:.6rem">
  <div style="color:#252540;font-size:.68em;font-weight:700;text-transform:uppercase;
    letter-spacing:.1em;margin-bottom:10px">Seguimiento en vivo</div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px">
    <div style="background:#0c0c18;border:1px solid #14142a;border-radius:7px;padding:8px 10px">
      <div style="color:#2a2a44;font-size:.65em">PRECIO ACTUAL</div>
      <div style="color:#fff;font-weight:700;font-size:.95em">{f(precio)}</div>
    </div>
    <div style="background:#0c0c18;border:1px solid #14142a;border-radius:7px;padding:8px 10px">
      <div style="color:#2a2a44;font-size:.65em">A ENTRADA</div>
      <div style="color:#ffd600;font-weight:700;font-size:.95em">{f(d_entry)} pts</div>
    </div>
    <div style="background:#0c0c18;border:1px solid #14142a;border-radius:7px;padding:8px 10px">
      <div style="color:#2a2a44;font-size:.65em">A STOP LOSS</div>
      <div style="color:#ff5252;font-weight:700;font-size:.95em">{f(d_sl)} pts</div>
    </div>
    <div style="background:#0c0c18;border:1px solid #14142a;border-radius:7px;padding:8px 10px">
      <div style="color:#2a2a44;font-size:.65em">A TP1</div>
      <div style="color:#69f0ae;font-weight:700;font-size:.95em">{f(d_tp1)} pts</div>
    </div>
  </div>
  <div style="background:#0e0e1a;border-radius:4px;height:4px;overflow:hidden;margin-bottom:4px">
    <div style="background:{bar_c};height:4px;width:{min(prog_p,100):.0f}%;border-radius:4px"></div>
  </div>
  <div style="color:#1e1e36;font-size:.68em">Última actualización: {ts}</div>
</div>""", unsafe_allow_html=True)


def _render_mtf(ctx):
    cells = ""
    for tf in ["H4","H1","M15","M5","M1"]:
        t   = ctx.get(tf,{}); color=t.get("color","#333"); lbl=t.get("label","?")
        rsi = t.get("rsi"); rsi_txt=f"<br><span style='color:#252540;font-size:.62em'>RSI {rsi:.0f}</span>" if rsi else ""
        cells += (f'<div style="background:#0a0a14;border:1px solid #14142a;border-radius:8px;'
                  f'padding:8px 6px;text-align:center">'
                  f'<div style="color:#1e1e36;font-size:.65em;font-weight:700;margin-bottom:2px">{tf}</div>'
                  f'<div style="color:{color};font-size:.75em;font-weight:700">{lbl}{rsi_txt}</div></div>')
    st.markdown(f"""
<div style="margin-bottom:.7rem">
  <div style="color:#1e1e36;font-size:.65em;font-weight:700;text-transform:uppercase;
    letter-spacing:.1em;margin-bottom:6px">Análisis Multi-Temporal</div>
  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px">{cells}</div>
</div>""", unsafe_allow_html=True)


def _render_no_trade(razones, ctx, score_max, symbol):
    h1lbl  = ctx.get("H1",{}).get("label","?")
    m15lbl = ctx.get("M15",{}).get("label","?")
    m5lbl  = ctx.get("M5",{}).get("label","?")
    bar_w  = min(score_max,100)
    bar_c  = "#ff5252" if score_max<70 else "#ffd600"
    reasons_html = "".join(
        f'<div style="color:#444;font-size:.82em;padding:4px 0;border-bottom:1px solid #0e0e18">'
        f'<span style="color:#2a2a44">▸ </span>{r}</div>'
        for r in razones
    )
    next_action = "Esperar ruptura de zona clave o retroceso a EMA con confirmación M15."
    st.markdown(f"""
<div style="background:#09090f;border:1px solid #161622;border-radius:12px;
  padding:1.4rem 1.8rem;margin-bottom:.6rem">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
    <div>
      <div style="color:#ff5252;font-size:1.3em;font-weight:900">🔴 NO OPERAR · {symbol}</div>
      <div style="color:#2a2a40;font-size:.82em;margin-top:4px">Sin setup válido en este momento</div>
    </div>
    <div style="text-align:right">
      <div style="color:{bar_c};font-size:1.8em;font-weight:900;line-height:1">{score_max}</div>
      <div style="color:#222;font-size:.68em">/100 · score actual</div>
    </div>
  </div>

  <!-- Score bar -->
  <div style="background:#0e0e18;border-radius:4px;height:4px;margin-bottom:4px;overflow:hidden">
    <div style="background:{bar_c};height:4px;width:{bar_w}%;border-radius:4px"></div>
  </div>
  <div style="color:#1e1e30;font-size:.68em;margin-bottom:12px">
    Mínimo para señal: {MIN_SCORE_SHOW}/100 &nbsp;·&nbsp; Para entrada válida: {MIN_SCORE_ENTRY}/100
  </div>

  <!-- Razones -->
  <div style="margin-bottom:12px">
    <div style="color:#252540;font-size:.7em;font-weight:700;text-transform:uppercase;
      letter-spacing:.08em;margin-bottom:6px">Por qué no hay trade:</div>
    {reasons_html}
  </div>

  <!-- Qué esperar -->
  <div style="background:#0c0c18;border-left:2px solid #252540;padding:8px 12px;border-radius:0 6px 6px 0">
    <div style="color:#2a2a44;font-size:.7em;font-weight:700;margin-bottom:2px">ACCIÓN</div>
    <div style="color:#444;font-size:.82em">{next_action}</div>
  </div>

  <!-- Contexto actual -->
  <div style="margin-top:10px;color:#1e1e2e;font-size:.72em">
    H1: {h1lbl} &nbsp;·&nbsp; M15: {m15lbl} &nbsp;·&nbsp; M5: {m5lbl}
  </div>
</div>""", unsafe_allow_html=True)


def _render_cerrada(sig, decimals):
    state=sig.get("state",""); cfg=_SC.get(state,_SC["INVALIDADA"])
    logs=sig.get("log",[]); last_msg=logs[-1].get("msg","") if logs else ""
    def f(v): return _fmt(v, decimals)
    st.markdown(f"""
<div style="background:#08080e;border:1px solid #141420;border-radius:10px;
  padding:.9rem 1.2rem;margin-bottom:.6rem;opacity:.75">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="color:{cfg['color']};font-size:1em;font-weight:700">{cfg['icon']} {cfg['label']}</div>
      <div style="color:#333;font-size:.78em;margin-top:2px">
        {sig.get('estrategia','')} · {('▲ BUY' if sig.get('dir')=='buy' else '▼ SELL')} ·
        Entrada {f(sig.get('entry',0))} · SL {f(sig.get('sl',0))}
      </div>
      <div style="color:#252535;font-size:.74em;margin-top:3px">{last_msg}</div>
    </div>
    <div style="color:#222;font-size:.7em">Score {sig.get('score',0)}/100</div>
  </div>
</div>""", unsafe_allow_html=True)


def _render_log(sig):
    logs = sig.get("log",[])
    if not logs: return
    with st.expander(f"📋 Historial de cambios · {len(logs)} eventos", expanded=False):
        for e in reversed(logs):
            cfg=_SC.get(e.get("state",""),{"color":"#333","icon":"·"})
            st.markdown(
                f'<div style="display:flex;gap:10px;padding:4px 0;border-bottom:1px solid #0c0c18;'
                f'font-size:.78em;align-items:baseline">'
                f'<span style="color:#1e1e30;min-width:68px">{e.get("ts","")}</span>'
                f'<span style="color:{cfg["color"]};min-width:18px">{cfg["icon"]}</span>'
                f'<span style="color:#3a3a55">{e.get("msg","")}</span>'
                f'</div>',
                unsafe_allow_html=True
            )


def _alert_state_change(symbol, prev_state, curr_state):
    if not prev_state or prev_state == curr_state: return
    cfg = _SC.get(curr_state,{})
    st.toast(f"{symbol}: {cfg.get('icon','')} {cfg.get('label','')}", icon="📡")

# ═══════════════════════════════════════════════════════════════════════════════
# RENDER POR ACTIVO
# ═══════════════════════════════════════════════════════════════════════════════
_SRC_BADGE = {
    "MT5":   '<span style="background:#0a1430;color:#42a5f5;padding:2px 9px;border-radius:10px;font-size:.7em;font-weight:700">📊 MT5 en vivo</span>',
    "Yahoo": '<span style="background:#140e00;color:#ffd600;padding:2px 9px;border-radius:10px;font-size:.7em;font-weight:700">🌐 Yahoo Finance</span>',
}

def _sesion():
    h=datetime.now(timezone.utc).hour
    if   h< 7: return "🌏 ASIÁTICA","#42a5f5"
    elif h<12: return "🇬🇧 LONDRES","#00e676"
    elif h<17: return "🇺🇸 NUEVA YORK","#ff9800"
    else:       return "🌙 FUERA HORARIO","#555"

def _render_activo(symbol, provider, n_nivel, n_txt, pen, decimals, tab_prefix):
    with st.spinner(f"Analizando {symbol}…"):
        ast, ctx, precio, ind = _analizar(symbol, provider, pen)

    if ast is None:
        st.error(f"❌ Sin conexión a datos para {symbol}. Verifica internet o MT5.")
        return

    sig     = ast.get("signal")
    src     = ind["src"]
    score_max = ind["score_max"]

    # ── Alertas de cambio de estado ────────────────────────────────────────────
    state_key = f"last_state_{tab_prefix}"
    prev_st = st.session_state.get(state_key)
    curr_st = sig.get("state") if sig and sig.get("state") not in _CLOSED else "BUSCANDO_SETUP"
    _alert_state_change(symbol, prev_st, curr_st)
    st.session_state[state_key] = curr_st

    # ── Header compacto ────────────────────────────────────────────────────────
    tend   = "▲ ALCISTA" if precio > ind["e200_h1"] else "▼ BAJISTA"
    tend_c = "#00e676"   if "ALCISTA" in tend       else "#ff5252"
    badge  = _SRC_BADGE.get(src, _SRC_BADGE["Yahoo"])

    col1, col2, col3, col4, col5 = st.columns([1.2,1,1,1,1.5])
    col1.metric(f"💰 {symbol}", f"{_fmt(precio, decimals)}")
    col2.metric("ATR H1",    f"{ind['atr_h1']:.{decimals}f}")
    col3.metric("RSI H1",    f"{ind['rsi_h1']:.0f}")
    col4.metric("Tendencia", tend)
    with col5:
        st.markdown(f'<div style="padding:8px 0">{badge}</div>', unsafe_allow_html=True)

    # ── Noticias ───────────────────────────────────────────────────────────────
    news_colors = {"PELIGRO":"#c62828","PRECAUCION":"#ff9800","SEGURO":"#00c853"}
    nc = news_colors.get(n_nivel,"#00c853")
    st.markdown(f"""
<div style="background:#080810;border:1px solid #141420;border-radius:8px;
  padding:.5rem 1rem;margin:.4rem 0 .8rem 0;font-size:.82em">
  <span style="color:#252540">📰 Noticias USD: </span>
  <span style="color:{nc};font-weight:700">{n_txt}</span>
  {('<span style="color:#c62828;font-weight:900;margin-left:12px">⛔ NO OPERAR durante noticias</span>' if n_nivel=="PELIGRO" else "")}
</div>""", unsafe_allow_html=True)

    # ── Contexto MTF ───────────────────────────────────────────────────────────
    _render_mtf(ctx)

    st.markdown("<hr style='border:none;border-top:1px solid #0e0e1a;margin:.3rem 0 .7rem 0'>", unsafe_allow_html=True)

    # ── Señal activa o señal cerrada reciente ──────────────────────────────────
    tiene_activa = sig and sig.get("state") not in _CLOSED

    if tiene_activa:
        # Señal viva — tarjeta principal + tracking
        _render_card(sig, precio, decimals)
        _render_tracking(sig, precio, decimals)
        _render_log(sig)

        # Botón para cerrar manualmente
        if st.button(f"🗑️ Descartar señal manualmente", key=f"del_{tab_prefix}"):
            sig = _log_change(sig, "INVALIDADA", "Cerrado manualmente por el usuario")
            ast["signal"] = sig
            ast["closed_at"] = datetime.now(timezone.utc).isoformat()
            ast["cooldown_until"] = (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()
            _set_ast(symbol, ast)
            st.rerun()

    else:
        # Sin señal activa
        # Si hay una señal reciente cerrada, mostrarla (dim)
        if sig and sig.get("state") in _CLOSED:
            _render_cerrada(sig, decimals)
            # Cooldown countdown
            cd = ast.get("cooldown_until")
            if cd:
                try:
                    rem = (datetime.fromisoformat(cd)-datetime.now(timezone.utc)).total_seconds()
                    if rem > 0:
                        st.markdown(f'<div style="color:#1e1e30;font-size:.74em;margin-bottom:.6rem">'
                                    f'⏱ Buscando nuevo setup en {int(rem/60)}m {int(rem%60)}s…</div>',
                                    unsafe_allow_html=True)
                except: pass

        # Panel de no-trade
        _render_no_trade(ind["razones_nt"], ctx, score_max, symbol)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    sesion, ses_col = _sesion()
    ev               = _fetch_news()
    n_nivel, n_txt   = _news_risk(ev)
    pen              = {"PELIGRO":35,"PRECAUCION":12,"SEGURO":0}.get(n_nivel,0)

    # ── Header ────────────────────────────────────────────────────────────────
    nb_colors = {"PELIGRO":"#c62828","PRECAUCION":"#ff9800","SEGURO":"#00c853"}
    nb_c = nb_colors.get(n_nivel,"#00c853")
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#07070e,#12090a);border:1px solid #2a1800;
  border-radius:12px;padding:1rem 1.6rem;margin-bottom:.8rem;
  display:flex;align-items:center;justify-content:space-between">
  <div>
    <div style="color:#ffd600;font-size:1.4em;font-weight:900">🥇 RAVEN TRADE IDEAS</div>
    <div style="color:#2a2220;font-size:.82em;margin-top:2px">
      XAUUSD &amp; DJ30 · Asistente profesional de señales · Una idea por activo
    </div>
  </div>
  <div style="text-align:right">
    <div style="color:{ses_col};font-size:.9em;font-weight:700">{sesion}</div>
    <div style="margin-top:3px">
      <span style="background:{nb_c};color:{'#000' if n_nivel!='PELIGRO' else '#fff'};
        padding:2px 10px;border-radius:12px;font-size:.74em;font-weight:700">{n_nivel}</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    _mt5_ok()  # intentar MT5 silenciosamente

    with st.spinner("Detectando fuente de datos…"):
        xau_sym, xau_prov = _find_xauusd()
        dj30_sym, dj30_prov = _find_dj30()

    oro_lbl  = f"🥇 ORO · {xau_sym}"  if xau_sym  else "🥇 ORO (sin datos)"
    dj30_lbl = f"📈 DJ30 · {dj30_sym}" if dj30_sym else "📈 DJ30 (sin datos)"
    tab1, tab2 = st.tabs([oro_lbl, dj30_lbl])

    with tab1:
        if xau_sym:
            _render_activo(xau_sym, xau_prov, n_nivel, n_txt, pen, decimals=2, tab_prefix="oro")
        else:
            st.markdown("""<div style="color:#333;text-align:center;padding:3rem">
              ⚠️ Sin datos para Oro. Abre MT5 o verifica tu conexión.</div>""",
              unsafe_allow_html=True)

    with tab2:
        if dj30_sym:
            _render_activo(dj30_sym, dj30_prov, n_nivel, n_txt, pen, decimals=0, tab_prefix="dj30")
        else:
            st.markdown("""<div style="color:#333;text-align:center;padding:3rem">
              ⚠️ Sin datos para DJ30. Abre MT5 o verifica tu conexión.</div>""",
              unsafe_allow_html=True)

    st.markdown("""
<div style="color:#0e0e1a;font-size:.7em;text-align:center;margin-top:1.5rem;
  padding-top:.8rem;border-top:1px solid #0a0a14">
  RAVEN TRADE IDEAS · Solo educativo · Gestiona siempre tu riesgo
</div>""", unsafe_allow_html=True)

    time.sleep(REFRESH)
    st.rerun()

if __name__ == "__main__":
    main()
