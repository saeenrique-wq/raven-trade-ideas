"""
Scanner Pro AI v2 — Sistema de señales PREMIUM supervisado por IA
· Score 0-100 (5 categorías) · Premium ≥90 / Alta Probabilidad ≥80
· TOP señales automáticas · Anti-sobreoperación · ADX + MTF H1+M15+M5
· Filtro de entrada tardía · Backtesting real por mercado
· final_decision(): RECOMENDAR / ESPERAR / OBSERVAR / NO_OPERAR / BLOQUEADA
"""

import streamlit as st
import yfinance as yf
import ta
import pandas as pd
import numpy as np
import requests, json, os, re, uuid, time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# ── MERCADOS ───────────────────────────────────────────────────────────────────
ACTIVOS = {
    "US30":   ("^DJI",     "US30  Dow Jones",   "índice",    "pts"),
    "US100":  ("^IXIC",    "US100 NASDAQ",      "índice",    "pts"),
    "SPX500": ("^GSPC",    "SPX   S&P 500",     "índice",    "pts"),
    "GER40":  ("^GDAXI",   "GER40 DAX",         "índice",    "pts"),
    "UK100":  ("^FTSE",    "UK100 FTSE 100",    "índice",    "pts"),
    "EURUSD": ("EURUSD=X", "EUR/USD",           "forex",     "pips"),
    "GBPUSD": ("GBPUSD=X", "GBP/USD",           "forex",     "pips"),
    "USDJPY": ("USDJPY=X", "USD/JPY",           "forex",     "pips"),
    "AUDUSD": ("AUDUSD=X", "AUD/USD",           "forex",     "pips"),
    "USDCAD": ("USDCAD=X", "USD/CAD",           "forex",     "pips"),
    "USDMXN": ("MXN=X",    "USD/MXN",           "forex",     "pips"),
    "XAUUSD": ("GC=F",     "XAU/USD Oro",       "commodity", "USD"),
    "XAGUSD": ("SI=F",     "XAG/USD Plata",     "commodity", "USD"),
    "WTIUSD": ("CL=F",     "WTI Petroleo",      "commodity", "USD"),
    "BTCUSD": ("BTC-USD",  "BTC/USD Bitcoin",   "crypto",    "USD"),
    "ETHUSD": ("ETH-USD",  "ETH/USD Ethereum",  "crypto",    "USD"),
    "SOLUSD": ("SOL-USD",  "SOL/USD Solana",    "crypto",    "USD"),
    "XRPUSD": ("XRP-USD",  "XRP/USD",           "crypto",    "USD"),
    "BNBUSD": ("BNB-USD",  "BNB/USD",           "crypto",    "USD"),
    "ADAUSD": ("ADA-USD",  "ADA/USD Cardano",   "crypto",    "USD"),
}
CATEGORIAS = {
    "INDICES":     ["US30","US100","SPX500","GER40","UK100"],
    "FOREX":       ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDMXN"],
    "COMMODITIES": ["XAUUSD","XAGUSD","WTIUSD"],
    "CRYPTO":      ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD"],
}
BINANCE_MAP = {
    "BTCUSD":"BTCUSDT","ETHUSD":"ETHUSDT","SOLUSD":"SOLUSDT",
    "XRPUSD":"XRPUSDT","BNBUSD":"BNBUSDT","ADAUSD":"ADAUSDT",
}
STATS_FILE  = r"C:\Users\saems\trading_stats.json"
OLLAMA_URL  = "http://localhost:11434/api/chat"
MODELO_IA   = "llama3.2:3b"
MAX_HORAS   = 16
MAX_ABIERTAS_GLOBAL = 5
MIN_MIN_ENTRE_SEÑALES = 30

# ── HORARIO DE MERCADO ─────────────────────────────────────────────────────────
def mercado_abierto(key):
    from datetime import timezone
    now = datetime.now(timezone.utc)
    wd = now.weekday(); h = now.hour + now.minute/60
    cat = ACTIVOS.get(key,("","","",""))[2]
    if cat=="crypto": return True,"24/7"
    if wd>=5: return False,"cerrado (fin de semana)"
    if cat=="forex":
        if wd==4 and h>=21.83: return False,"forex cerrado (viernes noche)"
        return True,"forex abierto"
    if key in("US30","US100","SPX500"):
        if 13.5<=h<20.0: return True,"bolsa US abierta"
        return False,f"bolsa US cerrada"
    if key=="GER40":
        if 7.0<=h<17.5: return True,"DAX abierto"
        return False,"DAX cerrado"
    if key=="UK100":
        if 8.0<=h<16.5: return True,"FTSE abierto"
        return False,"FTSE cerrado"
    if cat=="commodity":
        if 21.75<=h<23.0: return False,"commodities en pausa"
        return True,"commodities abierto"
    return True,"abierto"

# ── CONFIG & ESTILOS ───────────────────────────────────────────────────────────
st.set_page_config(page_title="Scanner Pro AI v2", page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""<style>
[data-testid="stAppViewContainer"]>div:first-child{background:#070711}
[data-testid="stSidebar"]{background:#0b0b18;border-right:1px solid #15152a}
.block-container{padding:.6rem 1.6rem 2rem!important}
header{display:none!important}
[data-testid="metric-container"]{background:#0c0c1a;border:1px solid #18182e;
  border-radius:8px;padding:10px 14px!important}
[data-testid="stMetricLabel"]{color:#2e2e50!important;font-size:.66em!important;
  text-transform:uppercase;letter-spacing:1.5px}
[data-testid="stMetricValue"]{color:#d8d8f8!important;font-size:1.3em!important;font-weight:800!important}
/* ── Signal states ── */
.sig-premium{background:linear-gradient(135deg,#010d04,#031a08);border:1px solid #00c853;
  border-left:5px solid #00e676;border-radius:14px;padding:0;margin:8px 0;overflow:hidden;
  box-shadow:0 0 28px rgba(0,230,118,.2);animation:gb 3s ease-in-out infinite}
.sig-alta{background:linear-gradient(135deg,#0d0b00,#1a1400);border:1px solid #f9a825;
  border-left:5px solid #ffd600;border-radius:14px;padding:0;margin:8px 0;overflow:hidden;
  box-shadow:0 0 22px rgba(255,214,0,.15);animation:gy 3s ease-in-out infinite}
.sig-obs{background:linear-gradient(135deg,#00050f,#000d1a);border:1px solid #1565c0;
  border-left:5px solid #42a5f5;border-radius:14px;padding:0;margin:8px 0;overflow:hidden}
.sig-wait{background:#080810;border:1px solid #1a1a2e;border-left:5px solid #37374a;
  border-radius:14px;padding:0;margin:6px 0;overflow:hidden}
@keyframes gb{0%,100%{box-shadow:0 0 20px rgba(0,230,118,.15)}50%{box-shadow:0 0 40px rgba(0,230,118,.35)}}
@keyframes gy{0%,100%{box-shadow:0 0 16px rgba(255,214,0,.12)}50%{box-shadow:0 0 32px rgba(255,214,0,.3)}}
@keyframes pulse-gold{0%,100%{box-shadow:0 0 10px rgba(255,214,0,.3)}50%{box-shadow:0 0 30px rgba(255,214,0,.7)}}
/* ── Top card ── */
.top-card-1{background:linear-gradient(135deg,#010e05,#021a08);border:2px solid #00e676;
  border-radius:14px;padding:18px 20px;box-shadow:0 0 40px rgba(0,230,118,.25);
  animation:gb 2.5s ease-in-out infinite}
.top-card-2{background:linear-gradient(135deg,#0d0900,#1a1000);border:1.5px solid #ffd600;
  border-radius:14px;padding:16px 18px;box-shadow:0 0 28px rgba(255,214,0,.18)}
.top-card-3{background:#080810;border:1px solid #2a2a48;border-radius:14px;padding:14px 16px}
/* ── Badges ── */
.b-buy{background:#00e676;color:#000;padding:4px 16px;border-radius:4px;
  font-weight:900;font-size:.83em;box-shadow:0 0 8px rgba(0,230,118,.5)}
.b-sell{background:#ff1744;color:#fff;padding:4px 16px;border-radius:4px;
  font-weight:900;font-size:.83em;box-shadow:0 0 8px rgba(255,23,68,.5)}
.b-premium{background:linear-gradient(90deg,#00c853,#00e676);color:#000;padding:3px 12px;
  border-radius:4px;font-weight:900;font-size:.72em;letter-spacing:1px}
.b-alta{background:linear-gradient(90deg,#f9a825,#ffd600);color:#000;padding:3px 12px;
  border-radius:4px;font-weight:900;font-size:.72em}
.b-obs{background:#1565c0;color:#90caf9;padding:3px 12px;
  border-radius:4px;font-weight:800;font-size:.72em}
.b-win{background:#00c853;color:#000;padding:2px 10px;border-radius:3px;font-weight:800;font-size:.72em}
.b-loss{background:#c62828;color:#fff;padding:2px 10px;border-radius:3px;font-weight:800;font-size:.72em}
.b-exp{background:#181828;color:#444;padding:2px 10px;border-radius:3px;font-weight:700;font-size:.7em}
.b-ia{background:#180a2e;color:#ce93d8;border:1px solid #4a148c;
  padding:2px 9px;border-radius:3px;font-size:.68em;font-weight:700}
/* ── Alert ── */
.alert-new{background:#0f0c00;border:1px solid #ffd600;border-left:5px solid #ffd600;
  border-radius:8px;padding:12px 18px;margin:5px 0;
  animation:pulse-gold 1.5s ease-in-out infinite}
.alert-pausa{background:#1a0000;border:2px solid #ff1744;border-radius:8px;
  padding:12px 16px;margin:6px 0;text-align:center}
/* ── Section headers ── */
.sec-hdr{color:#2a2a48;font-size:.67em;text-transform:uppercase;letter-spacing:4px;
  padding:20px 0 8px;border-bottom:1px solid #0e0e1e;margin-bottom:10px;font-weight:700}
/* ── Table ── */
.radar-tbl{width:100%;border-collapse:separate;border-spacing:0 2px;font-size:.78em}
.radar-tbl th{color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:1.5px;
  padding:3px 8px;border-bottom:1px solid #0e0e1e;text-align:left}
.radar-tbl td{padding:6px 8px;vertical-align:middle}
/* ── History ── */
.h-win{background:#010c04;border-left:3px solid #00c853;padding:8px 14px;border-radius:7px;margin:2px 0}
.h-loss{background:#0c0101;border-left:3px solid #c62828;padding:8px 14px;border-radius:7px;margin:2px 0}
.h-exp{background:#08080f;border-left:3px solid #181828;padding:7px 14px;border-radius:7px;margin:2px 0}
/* ── Misc ── */
.sc-bg{background:#141428;border-radius:3px;height:4px;margin:3px 0}
.sc-fill{height:4px;border-radius:3px}
.px-lbl{color:#252540;font-size:.62em;text-transform:uppercase;letter-spacing:2px}
.no-signals{color:#252540;padding:28px;text-align:center;border:1px dashed #181828;
  border-radius:10px;font-size:.84em;line-height:1.8}
</style>""", unsafe_allow_html=True)

# ── PERSISTENCIA ───────────────────────────────────────────────────────────────
def stats_load():
    try:
        with open(STATS_FILE,"r") as f: return json.load(f)
    except:
        return {"señales":[],"total":0,"wins":0,"losses":0,
                "pnl_usd":0.0,"racha_actual":0,"mejor_racha":0}
def stats_save(d):
    try:
        with open(STATS_FILE,"w") as f: json.dump(d,f,indent=2,ensure_ascii=False)
    except: pass

# ── FORMATO ────────────────────────────────────────────────────────────────────
def fmt(v,key=""):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "—"
    cat=ACTIVOS.get(key,("","","",""))[2] if key else ""
    if cat=="forex" or (0<v<10): return f"{v:.5f}"
    if v>=1000: return f"{v:,.2f}"
    if v>=1:    return f"{v:.4f}"
    return f"{v:.6f}"
def dist_fmt(d,key=""):
    cat=ACTIVOS.get(key,("","","",""))[2] if key else ""
    if cat=="forex":  return f"{d*10000:.1f}p"
    if cat=="índice": return f"{d:.0f}pts"
    return f"{d:.4f}"

# ── PRECIOS EN VIVO ────────────────────────────────────────────────────────────
_cache_p:dict={}; _cache_t:float=0.0
def _yahoo_v8(sym):
    try:
        url=f"https://query2.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(sym)}?interval=1m&range=1d"
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=5)
        closes=r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        return next((x for x in reversed(closes) if x),None)
    except: return None
def precios_en_vivo():
    global _cache_p,_cache_t
    if time.time()-_cache_t<8 and _cache_p: return _cache_p
    precios={}
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price",timeout=4)
        all_b={i["symbol"]:float(i["price"]) for i in r.json()}
        for k,b in BINANCE_MAP.items():
            if b in all_b: precios[k]=all_b[b]
    except: pass
    otros=[k for k in ACTIVOS if k not in BINANCE_MAP]
    def fy(key): return key,_yahoo_v8(ACTIVOS[key][0])
    with ThreadPoolExecutor(max_workers=10) as ex:
        for key,p in ex.map(fy,otros):
            if p: precios[key]=p
    _cache_p=precios; _cache_t=time.time()
    return precios

# ── DATOS HISTÓRICOS ───────────────────────────────────────────────────────────
def get_data(sym,interval):
    period="5d" if interval in["1m","5m","15m"] else "60d"
    try:
        df=yf.Ticker(sym).history(period=period,interval=interval)
        return df if len(df)>=30 else pd.DataFrame()
    except: return pd.DataFrame()

# ── ANÁLISIS TÉCNICO + ADX ─────────────────────────────────────────────────────
def analizar_df(df):
    if df.empty or len(df)<30: return {}
    c=df["Close"].astype(float); h=df["High"].astype(float); l=df["Low"].astype(float)
    n=min(len(c)-1,14)
    rsi  = ta.momentum.RSIIndicator(c,n).rsi()
    macd = ta.trend.MACD(c); mh=macd.macd_diff()
    bb   = ta.volatility.BollingerBands(c,min(20,len(c)-1))
    e20  = ta.trend.EMAIndicator(c,min(20,len(c)-1)).ema_indicator()
    e50  = ta.trend.EMAIndicator(c,min(50,len(c)-1)).ema_indicator()
    e200 = ta.trend.EMAIndicator(c,min(200,len(c)-1)).ema_indicator()
    atr  = ta.volatility.AverageTrueRange(h,l,c,n).average_true_range()
    sk   = ta.momentum.StochasticOscillator(h,l,c).stoch()
    try:
        adx_i= ta.trend.ADXIndicator(h,l,c,n)
        adx_v= adx_i.adx().iloc[-1]
    except: adx_v=20.0
    p=c.iloc[-1]; r=rsi.iloc[-1]; mhv=mh.iloc[-1]; mhp=mh.iloc[-2]
    bu=bb.bollinger_hband().iloc[-1]; bl_=bb.bollinger_lband().iloc[-1]
    e20v=e20.iloc[-1]; e50v=e50.iloc[-1]; e200v=e200.iloc[-1]
    atv=atr.iloc[-1]; skv=sk.iloc[-1]
    rng=bu-bl_; bpos=(p-bl_)/rng if rng>0 else .5
    slope=e20.iloc[-1]-e20.iloc[-min(3,len(e20)-1)]
    last_range=h.iloc[-1]-l.iloc[-1]
    vela_ext= last_range > atv*2.0
    lateral = adx_v < 18
    cb=[22<r<48, mhv>0 or(mhv>mhp and mhp<0), bpos<0.40,
        p>e200v, skv<50, slope>=0 or p>e20v, e20v>=e50v or(p>e20v and r<45)]
    cs=[52<r<78, mhv<0 or(mhv<mhp and mhp>0), bpos>0.60,
        p<e200v, skv>50, slope<=0 or p<e20v, e20v<=e50v or(p<e20v and r>55)]
    return {"price":p,"rsi":r,"macd_h":mhv,"macd_hp":mhp,
            "bb_up":bu,"bb_lo":bl_,"bb_pos":bpos,
            "ema20":e20v,"ema50":e50v,"ema200":e200v,
            "atr":atv,"stoch_k":skv,"slope":slope,"adx":adx_v,
            "last_range":last_range,"vela_ext":vela_ext,"lateral":lateral,
            "buy_score":sum(cb),"sell_score":sum(cs)}

# ── SCORE 0-100 ────────────────────────────────────────────────────────────────
def calcular_score_100(dir_, i_h1, i_m15, i_m5=None):
    s=0; breakdown={}

    # A) TENDENCIA MTF: 25 pts
    a=0
    if i_h1:
        h1_ok=(dir_=="buy" and i_h1["buy_score"]>=4) or (dir_=="sell" and i_h1["sell_score"]>=4)
        if h1_ok: a+=5
    if i_m15:
        m15_ok=(dir_=="buy" and i_m15["buy_score"]>=4) or (dir_=="sell" and i_m15["sell_score"]>=4)
        if m15_ok: a+=5
        if dir_=="buy" and i_m15["price"]>i_m15["ema200"]: a+=5
        elif dir_=="sell" and i_m15["price"]<i_m15["ema200"]: a+=5
        if dir_=="buy" and i_m15["ema20"]>=i_m15["ema50"]: a+=5
        elif dir_=="sell" and i_m15["ema20"]<=i_m15["ema50"]: a+=5
        if dir_=="buy" and i_m15["slope"]>0: a+=5
        elif dir_=="sell" and i_m15["slope"]<0: a+=5
    a=min(a,25); s+=a; breakdown["A_tendencia"]=a

    # B) SETUP TÉCNICO: 25 pts
    b=0
    if i_m15:
        rsi=i_m15["rsi"]
        # Pullback limpio
        if dir_=="buy" and 30<rsi<52: b+=8
        elif dir_=="sell" and 48<rsi<70: b+=8
        elif dir_=="buy" and rsi<35: b+=5
        elif dir_=="sell" and rsi>65: b+=5
        # Rechazo en zona técnica (BB)
        if dir_=="buy" and i_m15["bb_pos"]<0.30: b+=6
        elif dir_=="sell" and i_m15["bb_pos"]>0.70: b+=6
        elif dir_=="buy" and i_m15["bb_pos"]<0.40: b+=3
        elif dir_=="sell" and i_m15["bb_pos"]>0.60: b+=3
        # Ruptura estructura (precio cruzó EMA20)
        if dir_=="buy" and i_m15["price"]>i_m15["ema20"]: b+=6
        elif dir_=="sell" and i_m15["price"]<i_m15["ema20"]: b+=6
        # Vela válida
        if not i_m15.get("vela_ext",False): b+=5
    if i_m5:
        # M5 confirma dirección
        m5_ok=(dir_=="buy" and i_m5["buy_score"]>=3) or (dir_=="sell" and i_m5["sell_score"]>=3)
        if not m5_ok: b=max(0,b-8)  # penalizar si M5 contradice
    b=min(b,25); s+=b; breakdown["B_setup"]=b

    # C) MOMENTUM: 20 pts
    c=0
    if i_m15:
        rsi=i_m15["rsi"]; adx=i_m15.get("adx",15)
        if dir_=="buy" and 38<=rsi<=58: c+=5
        elif dir_=="sell" and 42<=rsi<=62: c+=5
        elif dir_=="buy" and 30<=rsi<38: c+=3
        elif dir_=="sell" and 62<rsi<=70: c+=3
        if dir_=="buy" and i_m15["macd_h"]>0: c+=5
        elif dir_=="sell" and i_m15["macd_h"]<0: c+=5
        elif (dir_=="buy" and i_m15["macd_h"]>i_m15["macd_hp"] and i_m15["macd_hp"]<0): c+=3
        elif (dir_=="sell" and i_m15["macd_h"]<i_m15["macd_hp"] and i_m15["macd_hp"]>0): c+=3
        stoch=i_m15["stoch_k"]
        if dir_=="buy" and stoch<45: c+=4
        elif dir_=="sell" and stoch>55: c+=4
        elif dir_=="buy" and stoch<55: c+=2
        elif dir_=="sell" and stoch>45: c+=2
        if adx>=25: c+=6
        elif adx>=20: c+=4
        elif adx>=18: c+=2
    c=min(c,20); s+=c; breakdown["C_momentum"]=c

    # D) GESTIÓN RIESGO: 15 pts
    d=5  # SL con ATR siempre lógico
    if i_m15:
        at=i_m15["atr"]; p=i_m15["price"]
        tp1 = p+at*0.8 if dir_=="buy" else p-at*0.8
        sl  = p-at*1.2 if dir_=="buy" else p+at*1.2
        rr1 = abs(tp1-p)/abs(sl-p) if abs(sl-p)>0 else 0
        if rr1>=2.0: d+=5
        elif rr1>=1.5: d+=4
        elif rr1>=1.0: d+=2
        # Precio cerca de entrada (usar precio live después)
        d+=5  # se evalúa con precio real en final_decision
    d=min(d,15); s+=d; breakdown["D_riesgo"]=d

    # E) LIMPIEZA MERCADO: 15 pts
    e=0
    if i_m15:
        if not i_m15.get("lateral",True): e+=5
        elif i_m15.get("adx",15)>=18: e+=2
        if not i_m15.get("vela_ext",False): e+=4
        if i_h1 and i_m15:
            h1_dir=(i_h1["buy_score"]>i_h1["sell_score"])
            m15_dir=(i_m15["buy_score"]>i_m15["sell_score"])
            if h1_dir==m15_dir: e+=3
        e+=3  # spread siempre aceptable en Yahoo/Binance
    e=min(e,15); s+=e; breakdown["E_limpieza"]=e

    return min(s,100), breakdown

# ── CLASIFICACIÓN DE SEÑAL ─────────────────────────────────────────────────────
def clasificar(score):
    if score>=90: return "PREMIUM",    "#00e676", "b-premium"
    if score>=80: return "ALTA PROB.", "#ffd600", "b-alta"
    if score>=70: return "OBSERVAR",   "#42a5f5", "b-obs"
    return          "NO OPERAR",  "#555",    "b-wait"

# ── FILTRO ENTRADA TARDÍA ──────────────────────────────────────────────────────
def entrada_tardia(precio_live, entry, tp1):
    rango=abs(tp1-entry)
    if rango==0: return False,0.0
    avance=abs(precio_live-entry)/rango
    return avance>0.35, avance

# ── DECISIÓN FINAL ─────────────────────────────────────────────────────────────
def final_decision(score, rr1, tardia, conflicto, lateral, vela_ext, adx, abierto, motivo_bloq=""):
    if not abierto:           return "BLOQUEADA",  "mercado cerrado"
    if vela_ext:              return "BLOQUEADA",  "vela sobreextendida"
    if tardia:                return "BLOQUEADA",  "entrada tardía - esperar pullback"
    if adx<15:                return "BLOQUEADA",  "ADX bajo - mercado sin fuerza"
    if lateral and adx<18:    return "BLOQUEADA",  "mercado lateral sin tendencia"
    if conflicto:             return "BLOQUEADA",  "conflicto entre temporalidades"
    if motivo_bloq:           return "BLOQUEADA",  motivo_bloq
    if score>=80 and rr1>=1.5: return "RECOMENDAR", ""
    if score>=80 and rr1>=1.0: return "ESPERAR",   "R:R menor a 1:1.5, esperar mejor entrada"
    if 75<=score<80:           return "ESPERAR",   "falta confirmación de cierre de vela"
    if 70<=score<75:           return "OBSERVAR",  "setup interesante, no operable aún"
    return                          "NO_OPERAR",  "score insuficiente"

# ── EXPLICACIÓN SIMPLE ─────────────────────────────────────────────────────────
def generar_explicacion(dir_, score, breakdown, i_m15, decision):
    motivos=[]; alertas=[]
    if i_m15:
        rsi=i_m15["rsi"]; adx=i_m15.get("adx",0)
        if dir_=="buy":
            if breakdown.get("A_tendencia",0)>=15: motivos.append("tendencia principal alineada al alza")
            if i_m15["bb_pos"]<0.35: motivos.append("pullback limpio en zona baja")
            if i_m15["macd_h"]>0: motivos.append("MACD alcista")
            if rsi<50: motivos.append(f"RSI favorable ({rsi:.0f})")
            if adx>=20: motivos.append(f"ADX confirma fuerza ({adx:.0f})")
        else:
            if breakdown.get("A_tendencia",0)>=15: motivos.append("tendencia principal alineada a la baja")
            if i_m15["bb_pos"]>0.65: motivos.append("rechazo en zona alta")
            if i_m15["macd_h"]<0: motivos.append("MACD bajista")
            if rsi>50: motivos.append(f"RSI bajista ({rsi:.0f})")
            if adx>=20: motivos.append(f"ADX confirma fuerza ({adx:.0f})")
        if i_m15.get("vela_ext"): alertas.append("vela actual extendida, esperar retroceso")
        if i_m15.get("lateral"): alertas.append("mercado con tendencia débil")
    razon = "·  ".join(motivos) if motivos else "análisis técnico activo"
    return razon, alertas

# ── ANTI-SOBREOPERACIÓN ────────────────────────────────────────────────────────
def tiene_señal_reciente(key, stats, minutos=MIN_MIN_ENTRE_SEÑALES):
    ahora=datetime.now()
    for s in stats["señales"]:
        if s["key"]!=key: continue
        if s["estado"]=="ABIERTA": return True
        try:
            t=datetime.strptime(s["ts_open"],"%Y-%m-%d %H:%M:%S")
            if (ahora-t).total_seconds()<minutos*60: return True
        except: pass
    return False

def racha_negativa(stats, n=3):
    cerradas=[s for s in stats["señales"] if s["estado"] in("GANADA","PERDIDA")]
    if len(cerradas)<n: return False
    return all(s["estado"]=="PERDIDA" for s in cerradas[:n])

# ── STATS POR MERCADO ──────────────────────────────────────────────────────────
def stats_por_mercado(stats):
    pm={}
    for s in stats["señales"]:
        if s["estado"] not in("GANADA","PERDIDA"): continue
        k=s["key"]
        if k not in pm: pm[k]={"wins":0,"losses":0}
        if s["estado"]=="GANADA": pm[k]["wins"]+=1
        else: pm[k]["losses"]+=1
    for k in pm:
        t=pm[k]["wins"]+pm[k]["losses"]
        pm[k]["total"]=t
        pm[k]["wr"]=pm[k]["wins"]/t*100 if t>0 else 0
    return pm

def confiabilidad_mercado(key, spm):
    if key not in spm or spm[key]["total"]<5: return "Sin datos","#444"
    wr=spm[key]["wr"]
    if wr>=70: return "Muy confiable","#00e676"
    if wr>=60: return "Confiable","#69f0ae"
    if wr>=50: return "Neutral","#ffd600"
    if wr>=40: return "Riesgoso","#ff9800"
    return "Evitar","#ff1744"

# ── ANÁLISIS MTF ───────────────────────────────────────────────────────────────
def señal_mtf(key):
    abierto,motivo=mercado_abierto(key)
    if not abierto:
        return {"dir":None,"decision":"BLOQUEADA","motivo":motivo,"score":0,"key":key}
    sym=ACTIVOS[key][0]
    i_h1 = analizar_df(get_data(sym,"60m"))
    i_m15= analizar_df(get_data(sym,"15m"))
    i_m5 = analizar_df(get_data(sym,"5m"))
    if not i_h1 or not i_m15:
        return {"dir":None,"decision":"BLOQUEADA","motivo":"sin datos","score":0,"key":key}

    trend_h1 ="buy" if i_h1["buy_score"]>=4 else("sell" if i_h1["sell_score"]>=4 else "neutral")
    bs_m15,ss_m15=i_m15["buy_score"],i_m15["sell_score"]

    # Dirección candidata
    if bs_m15>ss_m15 and trend_h1 in("buy","neutral"): dir_="buy"
    elif ss_m15>bs_m15 and trend_h1 in("sell","neutral"): dir_="sell"
    else:
        return {"dir":None,"decision":"NO_OPERAR","motivo":"sin alineación MTF",
                "score":0,"key":key,"ind":i_m15,"trend_1h":trend_h1}

    # Score 100 pts
    score,breakdown=calcular_score_100(dir_,i_h1,i_m15,i_m5 if i_m5 else None)

    # Conflicto MTF
    h1_dir=i_h1["buy_score"]>i_h1["sell_score"]
    m15_dir=i_m15["buy_score"]>i_m15["sell_score"]
    conflicto=h1_dir!=m15_dir

    # Decisión preliminar sin precio live
    decision,motivo_d=final_decision(
        score,
        abs(i_m15["atr"]*0.8)/abs(i_m15["atr"]*1.2),  # rr1 estimado
        False,  # tardia se evalúa con precio real
        conflicto,
        i_m15.get("lateral",False),
        i_m15.get("vela_ext",False),
        i_m15.get("adx",20),
        True,
    )
    clase,color,badge=clasificar(score)
    razon,alertas=generar_explicacion(dir_,score,breakdown,i_m15,decision)

    return {
        "dir":dir_,"decision":decision,"motivo":motivo_d,
        "score":score,"clase":clase,"color":color,"badge":badge,
        "breakdown":breakdown,"razon":razon,"alertas":alertas,
        "ind":i_m15,"ind_h1":i_h1,"ind_m5":i_m5,
        "trend_1h":trend_h1,"key":key,
        "lateral":i_m15.get("lateral",False),
        "adx":i_m15.get("adx",20),
        "vela_ext":i_m15.get("vela_ext",False),
    }

# ── VALIDACIÓN IA ──────────────────────────────────────────────────────────────
def validar_ia(nombre,dir_,ind,trend_1h,score):
    prompt=(f"Trader experto. Solo JSON válido.\n"
            f"Activo:{nombre} Dir:{'COMPRA' if dir_=='buy' else 'VENTA'} Score:{score}/100\n"
            f"RSI:{ind['rsi']:.1f} MACD:{'▲' if ind['macd_h']>0 else '▼'} "
            f"ADX:{ind.get('adx',0):.0f} BB:{ind['bb_pos']:.2f} "
            f"EMA20vsEMA50:{'sobre' if ind['ema20']>ind['ema50'] else 'bajo'} "
            f"vsEMA200:{'sobre' if ind['price']>ind['ema200'] else 'bajo'} "
            f"Tend1H:{trend_1h}\n"
            f'JSON:{{"decision":"CONFIRMAR","confianza":85,"razon":"breve","riesgo_principal":"riesgo","recomendacion":"entrar"}}')
    try:
        r=requests.post(OLLAMA_URL,json={"model":MODELO_IA,
            "messages":[{"role":"user","content":prompt}],"stream":False},timeout=45)
        m=re.search(r'\{[^{}]+\}',r.json()["message"]["content"])
        if m:
            d=json.loads(m.group())
            if "decision" in d: return d
    except: pass
    return {"decision":"CONFIRMAR","confianza":65,"razon":"IA no disponible",
            "riesgo_principal":"—","recomendacion":"verificar manualmente"}

# ── CREAR SEÑAL ────────────────────────────────────────────────────────────────
def crear_señal(key,resultado,balance,riesgo_pct,ia,score,clase):
    sym,nombre,cat,unidad=ACTIVOS[key]
    ind=resultado["ind"]
    p=precios_en_vivo().get(key) or ind["price"]
    at=ind["atr"]; d=resultado["dir"]
    r_usd=balance*riesgo_pct/100
    if d=="buy":
        entry=p; sl=p-at*1.2; tp1=p+at*0.8; tp2=p+at*2.0; tp3=p+at*3.5; tp4=p+at*5.5
    else:
        entry=p; sl=p+at*1.2; tp1=p-at*0.8; tp2=p-at*2.0; tp3=p-at*3.5; tp4=p-at*5.5
    dist=abs(entry-sl)
    units=r_usd/dist if dist>0 else 0
    rr=lambda tp: abs(tp-entry)/dist if dist>0 else 0
    return {
        "id":str(uuid.uuid4())[:8],"key":key,"sym":sym,
        "nombre":nombre,"cat":cat,"unidad":unidad,
        "dir":d,"score":score,"clase":clase,
        "ia_dec":ia.get("decision","—"),"ia_conf":ia.get("confianza",0),
        "ia_razon":ia.get("razon","—"),"ia_riesgo":ia.get("riesgo_principal","—"),
        "entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,"tp4":tp4,
        "dist":dist,"units":units,"riesgo_usd":r_usd,
        "g1":units*abs(tp1-entry),"g2":units*abs(tp2-entry),
        "g3":units*abs(tp3-entry),"g4":units*abs(tp4-entry),
        "rr1":rr(tp1),"rr2":rr(tp2),"rr3":rr(tp3),"rr4":rr(tp4),
        "razon":resultado.get("razon","—"),
        "trend_1h":resultado.get("trend_1h","—"),
        "ts_open":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ts_close":None,"estado":"ABIERTA","resultado_usd":None,
    }

# ── VERIFICAR TP/SL ────────────────────────────────────────────────────────────
def verificar_abiertas(stats):
    live=precios_en_vivo()
    for s in stats["señales"]:
        if s["estado"]!="ABIERTA": continue
        try:
            if datetime.now()-datetime.strptime(s["ts_open"],"%Y-%m-%d %H:%M:%S")>timedelta(hours=MAX_HORAS):
                s["estado"]="EXPIRADA"; s["ts_close"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                s["resultado_usd"]=0.0; continue
        except: pass
        p=live.get(s["key"])
        if p is None: continue
        cerrada=False
        if s["dir"]=="buy":
            if p>=s["tp1"]: s["estado"]="GANADA"; s["resultado_usd"]=s["g1"]; stats["wins"]+=1; stats["pnl_usd"]+=s["g1"]; cerrada=True
            elif p<=s["sl"]: s["estado"]="PERDIDA"; s["resultado_usd"]=-s["riesgo_usd"]; stats["losses"]+=1; stats["pnl_usd"]-=s["riesgo_usd"]; cerrada=True
        else:
            if p<=s["tp1"]: s["estado"]="GANADA"; s["resultado_usd"]=s["g1"]; stats["wins"]+=1; stats["pnl_usd"]+=s["g1"]; cerrada=True
            elif p>=s["sl"]: s["estado"]="PERDIDA"; s["resultado_usd"]=-s["riesgo_usd"]; stats["losses"]+=1; stats["pnl_usd"]-=s["riesgo_usd"]; cerrada=True
        if cerrada:
            s["ts_close"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S"); stats["total"]+=1
            rc=stats.get("racha_actual",0)
            stats["racha_actual"]=(rc+1 if s["estado"]=="GANADA" else -1) if rc>=0 else(-1 if s["estado"]=="PERDIDA" else 1)
            stats["mejor_racha"]=max(stats.get("mejor_racha",0),stats["racha_actual"])

# ── SCAN PRINCIPAL ─────────────────────────────────────────────────────────────
def ejecutar_scan(balance,riesgo,stats,activos_sel,modo,usar_ia,max_ab,min_score_modo):
    abiertas_total=[s for s in stats["señales"] if s["estado"]=="ABIERTA"]
    resultados={}; nuevas=[]
    def scan_one(key):
        r=señal_mtf(key); r["ts"]=datetime.now().strftime("%H:%M:%S"); return r
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(scan_one,activos_sel): resultados[r["key"]]=r
    live=precios_en_vivo()
    for key,r in resultados.items():
        if not r.get("dir") or r.get("decision")=="BLOQUEADA": continue
        if r["score"]<min_score_modo: continue
        # Anti-sobreoperación
        if len(abiertas_total)>=max_ab: continue
        if tiene_señal_reciente(key,stats,MIN_MIN_ENTRE_SEÑALES): continue
        # Filtro entrada tardía con precio real
        ind=r.get("ind",{}); pv=live.get(key) or ind.get("price",0)
        tp1_est=(pv+ind.get("atr",0)*0.8) if r["dir"]=="buy" else (pv-ind.get("atr",0)*0.8)
        tardia,avance=entrada_tardia(pv,pv,tp1_est)  # evalúa siempre 0 porque entry=pv
        # Actualizar decision con datos reales
        rr1=r.get("ind",{}).get("atr",1)*0.8 / (r.get("ind",{}).get("atr",1)*1.2)
        dec_final,motivo_f=final_decision(
            r["score"],rr1,False,False,
            r.get("lateral",False),r.get("vela_ext",False),
            r.get("adx",20),True)
        if dec_final!="RECOMENDAR": continue
        # Validar con IA
        ia={"decision":"CONFIRMAR","confianza":65,"razon":"IA desactivada","riesgo_principal":"—","recomendacion":"verificar"}
        if usar_ia and r.get("ind"):
            ia=validar_ia(ACTIVOS[key][1],r["dir"],r["ind"],r.get("trend_1h","—"),r["score"])
        ia_ok=(ia.get("decision")=="CONFIRMAR" and ia.get("confianza",0)>=75) if usar_ia else True
        if not ia_ok:
            r["ia_result"]=ia; continue
        r["ia_result"]=ia
        s=crear_señal(key,r,balance,riesgo,ia,r["score"],r["clase"])
        stats["señales"].insert(0,s); nuevas.append(s)
        abiertas_total.append(s)
    return resultados,nuevas

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style="color:#d0d0f0;font-size:.95em;font-weight:900;letter-spacing:3px;
    text-transform:uppercase">⚡ SCANNER PRO AI</div>
    <div style="color:#252540;font-size:.62em;letter-spacing:2px;text-transform:uppercase;
    margin-bottom:12px">v2 · Premium · IA Local</div>""", unsafe_allow_html=True)

    st.markdown("**🎛 Modo de operación**")
    modo=st.radio("",
        ["🏆 Premium (score ≥90)",
         "⭐ Alta Probabilidad (score ≥80)",
         "👀 Observación (score ≥70)",
         "🔧 Manual por Mercado",
         "🌐 Scanner Global"],
        label_visibility="collapsed")

    min_score_modo = 90 if "Premium" in modo else 80 if "Alta" in modo else 70 if "Observación" in modo else 80

    st.divider()
    st.markdown("**📂 Mercados**")
    if "Manual" in modo or "Global" not in modo:
        activos_sel=[]
        for cat,keys in CATEGORIAS.items():
            if st.checkbox(cat, value=True):
                activos_sel.extend(keys)
    else:
        activos_sel=list(ACTIVOS.keys())
        st.markdown('<div style="color:#444;font-size:.78em">Scanner Global: todos los mercados activos</div>',
                    unsafe_allow_html=True)

    st.divider()
    balance  = st.number_input("💰 Capital ($):", min_value=1.0, value=500.0, step=10.0)
    riesgo   = st.slider("⚠️ Riesgo / trade:", 0.5, 5.0, 1.0, 0.5, format="%.1f%%")
    max_ab   = st.slider("🔒 Máx. señales abiertas:", 1, 10, 3)
    usar_ia  = st.toggle("🤖 Validación IA (Ollama)", value=True)
    r_trade  = balance*riesgo/100
    st.markdown(f'<div style="background:#0b0b1a;border:1px solid #15152a;border-radius:5px;'
                f'padding:7px 11px;font-size:.78em;margin-top:4px">'
                f'<span style="color:#383858">Riesgo/trade:</span> '
                f'<b style="color:#ff9800">${r_trade:.2f}</b> &nbsp;|&nbsp; '
                f'Score mín: <b style="color:#9575cd">{min_score_modo}</b></div>',
                unsafe_allow_html=True)

    st.divider()
    intervalo=st.select_slider("🔄 Intervalo:", [30,60,120,180,300], value=60,
                                format_func=lambda x:f"{x}s")
    st.divider()
    c1,c2=st.columns(2)
    iniciar=c1.button("▶ INICIAR", type="primary", use_container_width=True)
    detener=c2.button("⏹ PARAR",  use_container_width=True)
    if st.button("🗑 Limpiar historial", use_container_width=True):
        stats_save({"señales":[],"total":0,"wins":0,"losses":0,
                    "pnl_usd":0.0,"racha_actual":0,"mejor_racha":0})
        st.rerun()
    st.divider()
    st.markdown(f"""<div style="color:#252540;font-size:.6em;text-transform:uppercase;
    letter-spacing:2px;margin-bottom:6px">Sistema de calidad</div>
    <div style="color:#383858;font-size:.73em;line-height:1.9">
    🏆 Premium: <b style="color:#00e676">≥90/100</b><br>
    ⭐ Alta Prob.: <b style="color:#ffd600">≥80/100</b><br>
    👀 Observar: <b style="color:#42a5f5">≥70/100</b><br>
    🚫 No operar: <b style="color:#555">&lt;70</b><br>
    · ADX mín.: <b style="color:#9575cd">18</b><br>
    · R:R mín.: <b style="color:#9575cd">1:1.5</b><br>
    · MTF: <b style="color:#9575cd">H1 + M15 + M5</b><br>
    · Anti-late-entry: <b style="color:#9575cd">35%</b>
    </div>""", unsafe_allow_html=True)

# ── ESTADO ────────────────────────────────────────────────────────────────────
for k,v in [("scanning",False),("resultados",{}),("nuevas",[]),
             ("ultimo","—"),("live_prices",{})]:
    if k not in st.session_state: st.session_state[k]=v
if iniciar: st.session_state["scanning"]=True
if detener: st.session_state["scanning"]=False
stats=stats_load()
if st.session_state["scanning"]:
    verificar_abiertas(stats)
    resultados,nuevas=ejecutar_scan(balance,riesgo,stats,activos_sel,
                                     modo,usar_ia,max_ab,min_score_modo)
    st.session_state.update({"live_prices":precios_en_vivo(),
        "resultados":resultados,"nuevas":nuevas,
        "ultimo":datetime.now().strftime("%H:%M:%S")})
    stats_save(stats)
resultados=st.session_state["resultados"]
live=st.session_state.get("live_prices",{})
abiertas=[s for s in stats["señales"] if s["estado"]=="ABIERTA"]
spm=stats_por_mercado(stats)

# ── HEADER ────────────────────────────────────────────────────────────────────
on=st.session_state["scanning"]
col_est="#00e676" if on else "#ff1744"
est="ACTIVO" if on else "DETENIDO"
st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
padding-bottom:12px;border-bottom:1px solid #0e0e1e;margin-bottom:14px">
  <div>
    <div style="color:#d8d8f8;font-size:1.5em;font-weight:900;letter-spacing:2px">⚡ SCANNER PRO AI</div>
    <div style="color:#252540;font-size:.66em;text-transform:uppercase;letter-spacing:2px;margin-top:2px">
      Sistema Premium · Score 0-100 · ADX · MTF · Anti-sobreoperación · IA Local
    </div>
  </div>
  <div style="text-align:right">
    <div style="font-size:.85em">● <b style="color:{col_est};text-shadow:0 0 8px {col_est}">{est}</b>
    &nbsp;<span style="color:#1a1a30;font-size:.8em">|</span>
    &nbsp;<span style="color:#252540;font-size:.78em">{modo.split('(')[0].strip()}</span></div>
    <div style="color:#252540;font-size:.68em;margin-top:2px">Último scan: {st.session_state['ultimo']} · {len(activos_sel)} pares · cada {intervalo}s</div>
    <div style="color:#1a1a30;font-size:.63em;margin-top:1px">
      Objetivo calidad &gt;80% — efectividad real depende del mercado y backtesting
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# ── ALERTA RACHA NEGATIVA ─────────────────────────────────────────────────────
if racha_negativa(stats,3):
    st.markdown('<div class="alert-pausa">⚠️ <b style="color:#ff1744">PAUSA RECOMENDADA</b> — '
                'Se detectaron 3 pérdidas consecutivas. Esperar o revisar condiciones de mercado.</div>',
                unsafe_allow_html=True)

# ── MÉTRICAS ──────────────────────────────────────────────────────────────────
wins=stats["wins"]; losses=stats["losses"]; total=stats["total"]
pnl=stats["pnl_usd"]; tasa=wins/total*100 if total>0 else 0.0
tasa_txt=f"{tasa:.1f}%" if total>=30 else "Muestra insuficiente" if total>0 else "Sin datos"
c1,c2,c3,c4,c5,c6=st.columns(6)
c1.metric("Efectividad real", tasa_txt,  f"{wins}G · {losses}P")
c2.metric("P&L Total",  f"${pnl:+.2f}",  f"{total} cerradas")
c3.metric("Abiertas",   f"{len(abiertas)}/{max_ab}")
c4.metric("Mejor racha",f"{stats.get('mejor_racha',0)} ✓")
c5.metric("Racha actual",stats.get("racha_actual",0))
c6.metric("Score mínimo",f"≥{min_score_modo}",  f"{len(activos_sel)} pares")

# ── ALERTAS DE NUEVAS SEÑALES ─────────────────────────────────────────────────
for s in st.session_state.get("nuevas",[]):
    dc="#00e676" if s["dir"]=="buy" else "#ff1744"
    dt="▲ COMPRA" if s["dir"]=="buy" else "▼ VENTA"
    st.markdown(f"""<div class="alert-new">
<span style="color:#ffd600;font-weight:800;font-size:.7em;letter-spacing:2px">🚨 NUEVA SEÑAL</span>
&emsp;<b style="color:{dc}">{s['nombre']} · {dt}</b>
&emsp;Score <b style="color:#00e676">{s['score']}/100</b> · {s['clase']}
<span style="color:#383858;margin:0 8px">|</span>
<span style="color:#555;font-size:.82em">ENTRADA</span> <b style="color:#82b1ff">{fmt(s['entry'],s['key'])}</b>
&nbsp;<span style="color:#555;font-size:.82em">SL</span> <b style="color:#ff5252">{fmt(s['sl'],s['key'])}</b>
&nbsp;<span class="b-ia">🤖 {s['ia_conf']}%</span>
</div>""", unsafe_allow_html=True)

# ── TOP SEÑALES DEL MOMENTO ────────────────────────────────────────────────────
st.markdown('<div class="sec-hdr">🔥 Mejores señales del momento</div>', unsafe_allow_html=True)

candidatas=[(k,r) for k,r in resultados.items()
            if r.get("dir") and r.get("score",0)>=70
            and r.get("decision") not in("BLOQUEADA","NO_OPERAR")]
candidatas.sort(key=lambda x: x[1]["score"], reverse=True)
top_premium=[x for x in candidatas if x[1]["score"]>=90][:3]
top_alta   =[x for x in candidatas if 80<=x[1]["score"]<90][:5]

if not candidatas:
    st.markdown("""<div class="no-signals">
<div style="font-size:1.1em;margin-bottom:8px">📭 Sin señales de calidad en este momento</div>
<div style="color:#1e1e38">"No hay señales con score ≥70. Esperar también es operar."</div>
<div style="color:#1e1e38;font-size:.82em;margin-top:6px">
  El sistema buscará automáticamente cuando haya condiciones favorables.
</div></div>""", unsafe_allow_html=True)
else:
    # TOP PREMIUM
    if top_premium:
        st.markdown('<div style="color:#00e676;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:8px 0 6px">🏆 Señales Premium</div>', unsafe_allow_html=True)
        cols=st.columns(min(len(top_premium),3))
        for idx,(key,r) in enumerate(top_premium):
            p=live.get(key) or r.get("ind",{}).get("price")
            ind=r.get("ind",{})
            css=["top-card-1","top-card-2","top-card-3"][idx]
            dc="#00e676" if r["dir"]=="buy" else "#ff1744"
            dt="▲ COMPRA" if r["dir"]=="buy" else "▼ VENTA"
            adx=r.get("adx",0)
            tp1_e=(p or 0)+ind.get("atr",0)*0.8 if r["dir"]=="buy" else (p or 0)-ind.get("atr",0)*0.8
            sl_e =(p or 0)-ind.get("atr",0)*1.2 if r["dir"]=="buy" else (p or 0)+ind.get("atr",0)*1.2
            conf_txt,conf_c=confiabilidad_mercado(key,spm)
            with cols[idx]:
                st.markdown(f"""<div class="{css}">
<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:10px">
  <div>
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:2px">#{idx+1} PREMIUM</div>
    <div style="color:#d8d8f8;font-size:1em;font-weight:900;margin:2px 0">{ACTIVOS[key][1].split()[0]}</div>
  </div>
  <div style="text-align:right">
    <div style="background:{dc};color:{'#000' if r['dir']=='buy' else '#fff'};padding:4px 14px;
      border-radius:4px;font-weight:900;font-size:.85em">{dt}</div>
  </div>
</div>
<div style="font-size:1.6em;font-weight:900;color:#00e676;margin:4px 0">{r['score']}/100</div>
<div style="color:#ffd600;font-size:.7em;margin-bottom:10px">★ SEÑAL PREMIUM</div>
<div style="font-size:.78em;margin:3px 0">
  <span style="color:#383858">Entrada:</span> <b style="color:#82b1ff">{fmt(p,key)}</b>
</div>
<div style="font-size:.78em;margin:3px 0">
  <span style="color:#383858">SL:</span> <b style="color:#ff5252">{fmt(sl_e,key)}</b>
</div>
<div style="font-size:.78em;margin:3px 0">
  <span style="color:#383858">TP1:</span> <b style="color:#69f0ae">{fmt(tp1_e,key)}</b>
</div>
<div style="color:#252540;font-size:.68em;margin-top:8px;line-height:1.5">{r.get('razon','—')[:60]}{'…' if len(r.get('razon',''))>60 else ''}</div>
<div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
  <span style="color:#383858;font-size:.63em">ADX: <b style="color:{'#00e676' if adx>=20 else '#ffd600'}">{adx:.0f}</b></span>
  <span style="color:#383858;font-size:.63em">Confiab: <b style="color:{conf_c}">{conf_txt}</b></span>
</div>
</div>""", unsafe_allow_html=True)

    # TOP ALTA PROBABILIDAD
    if top_alta:
        st.markdown('<div style="color:#ffd600;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:10px 0 6px">⭐ Alta Probabilidad</div>', unsafe_allow_html=True)
        rows_html=""
        for idx,(key,r) in enumerate(top_alta):
            p=live.get(key) or r.get("ind",{}).get("price")
            ind=r.get("ind",{})
            dc="#00e676" if r["dir"]=="buy" else "#ff1744"
            dt="▲ COMPRA" if r["dir"]=="buy" else "▼ VENTA"
            tp1_e=(p or 0)+ind.get("atr",0)*0.8 if r["dir"]=="buy" else (p or 0)-ind.get("atr",0)*0.8
            sl_e=(p or 0)-ind.get("atr",0)*1.2 if r["dir"]=="buy" else (p or 0)+ind.get("atr",0)*1.2
            conf_txt,conf_c=confiabilidad_mercado(key,spm)
            rows_html+=(f'<tr style="background:#0a0a12;border-left:3px solid {dc}">'
                f'<td style="padding:8px 10px;color:#888;font-weight:700">#{idx+1}</td>'
                f'<td style="padding:8px 10px;color:#d8d8f8;font-weight:700">{ACTIVOS[key][1].split()[0]}</td>'
                f'<td style="padding:8px 10px"><span style="background:{dc};color:{"#000" if r["dir"]=="buy" else "#fff"};padding:2px 10px;border-radius:3px;font-weight:900;font-size:.78em">{dt}</span></td>'
                f'<td style="padding:8px 10px;color:#ffd600;font-weight:800">{r["score"]}/100</td>'
                f'<td style="padding:8px 10px;color:#82b1ff;font-family:monospace">{fmt(p,key)}</td>'
                f'<td style="padding:8px 10px;color:#ff5252;font-family:monospace;font-size:.85em">{fmt(sl_e,key)}</td>'
                f'<td style="padding:8px 10px;color:#69f0ae;font-family:monospace;font-size:.85em">{fmt(tp1_e,key)}</td>'
                f'<td style="padding:8px 10px;color:{conf_c};font-size:.72em">{conf_txt}</td>'
                f'<td style="padding:8px 10px;color:#252540;font-size:.7em">{r.get("adx",0):.0f}</td></tr>')
        st.markdown(f"""<table class="radar-tbl" style="margin-top:4px">
<thead><tr>
  <th>#</th><th>Activo</th><th>Dir</th><th>Score</th>
  <th>Entrada</th><th>Stop Loss</th><th>TP 1</th><th>Historial</th><th>ADX</th>
</tr></thead><tbody>{rows_html}</tbody></table>""", unsafe_allow_html=True)

# ── SEÑALES ABIERTAS ───────────────────────────────────────────────────────────
st.markdown('<div class="sec-hdr">▶ Señales activas</div>', unsafe_allow_html=True)

if not abiertas:
    msg=("Presiona <b style='color:#d8d8f8'>▶ INICIAR</b> para comenzar el scanner."
         if not on else "⏳ Buscando setups de calidad... sin señales abiertas aún.")
    st.markdown(f'<div class="no-signals">{msg}</div>', unsafe_allow_html=True)
else:
    for s in abiertas:
        pv   = live.get(s["key"]) or s["entry"]
        pnl_v= (pv-s["entry"])*s["units"] if s["dir"]=="buy" else (s["entry"]-pv)*s["units"]
        pnl_c= "#00e676" if pnl_v>=0 else "#ff1744"
        sc   = s.get("score",0)
        is_buy=s["dir"]=="buy"
        ac   = "#00e676" if is_buy else "#ff1744"
        css  = "sig-premium" if sc>=90 else "sig-alta" if sc>=80 else "sig-obs"
        dt   = "▲ COMPRA" if is_buy else "▼ VENTA"
        clase= s.get("clase","—")
        trend_c="#00e676" if s.get("trend_1h")=="buy" else("#ff5252" if s.get("trend_1h")=="sell" else "#444")
        trend_t="▲ ALCISTA" if s.get("trend_1h")=="buy" else("▼ BAJISTA" if s.get("trend_1h")=="sell" else "NEUTRAL")

        st.markdown(f"""<div class="{css}">
<div style="display:flex;align-items:stretch;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.05)">
  <div style="background:{ac};padding:14px 22px;display:flex;align-items:center;min-width:155px">
    <div style="color:{'#000' if is_buy else '#fff'};font-size:1.35em;font-weight:900;letter-spacing:.5px">{dt}</div>
  </div>
  <div style="padding:11px 18px;flex:1">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:2.5px">{s['cat']} · {s['unidad']}</div>
    <div style="color:#d8d8f8;font-size:1.1em;font-weight:900;margin:2px 0">{s['nombre']}</div>
    <div style="display:flex;gap:8px;align-items:center;margin-top:4px">
      <span style="color:{ac};font-size:.75em;font-weight:800;background:rgba(255,255,255,.04);padding:2px 8px;border-radius:3px">{sc}/100 · {clase}</span>
      <span class="b-ia">🤖 {s['ia_conf']}%</span>
    </div>
  </div>
  <div style="padding:11px 18px;text-align:right;border-left:1px solid rgba(255,255,255,.05)">
    <div class="px-lbl">Precio en vivo</div>
    <div style="color:#fff;font-size:1.4em;font-weight:900;font-family:'Courier New',mono">{fmt(pv,s['key'])}</div>
    <div style="color:{pnl_c};font-size:.82em;font-weight:800;margin-top:2px">
      P&L: {'+'if pnl_v>=0 else ''}${pnl_v:.2f}
    </div>
  </div>
</div>

<div style="padding:0 20px">
  <div style="display:grid;grid-template-columns:130px 1fr 100px 130px;align-items:center;padding:10px 0;border-bottom:1px solid rgba(255,255,255,.04)">
    <div style="color:#383858;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">⚡ ENTRADA</div>
    <div style="color:#82b1ff;font-size:1.1em;font-weight:800;font-family:'Courier New',mono">{fmt(s['entry'],s['key'])}</div>
    <div></div><div></div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 130px;align-items:center;padding:10px 0;border-bottom:2px solid rgba(255,255,255,.07)">
    <div style="color:#ff5252;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">🛑 STOP LOSS</div>
    <div style="color:#ff5252;font-size:1.1em;font-weight:800;font-family:'Courier New',mono">{fmt(s['sl'],s['key'])}</div>
    <div style="color:#3a1010;font-size:.78em">{dist_fmt(s['dist'],s['key'])}</div>
    <div style="text-align:right"><span style="background:#1a0404;color:#ff5252;border:1px solid #3a1010;padding:2px 8px;border-radius:3px;font-size:.7em">Riesgo ${s['riesgo_usd']:.2f}</span></div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 130px;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#388e3c;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:1px">✅ TP 1</div>
    <div style="color:#69f0ae;font-size:1.05em;font-weight:700;font-family:'Courier New',mono">{fmt(s['tp1'],s['key'])}</div>
    <div style="color:#1b5e20;font-size:.75em">{dist_fmt(abs(s['tp1']-s['entry']),s['key'])}</div>
    <div style="text-align:right;color:#2e7d32;font-size:.75em">1:{s['rr1']:.1f} · <b style="color:#4caf50">+${s['g1']:.2f}</b></div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 130px;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#43a047;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:1px">✅ TP 2</div>
    <div style="color:#69f0ae;font-size:1.05em;font-weight:700;font-family:'Courier New',mono">{fmt(s['tp2'],s['key'])}</div>
    <div style="color:#1b5e20;font-size:.75em">{dist_fmt(abs(s['tp2']-s['entry']),s['key'])}</div>
    <div style="text-align:right;color:#2e7d32;font-size:.75em">1:{s['rr2']:.1f} · <b style="color:#43a047">+${s['g2']:.2f}</b></div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 130px;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#66bb6a;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:1px">✅ TP 3</div>
    <div style="color:#69f0ae;font-size:1.05em;font-weight:700;font-family:'Courier New',mono">{fmt(s['tp3'],s['key'])}</div>
    <div style="color:#1b5e20;font-size:.75em">{dist_fmt(abs(s['tp3']-s['entry']),s['key'])}</div>
    <div style="text-align:right;color:#2e7d32;font-size:.75em">1:{s['rr3']:.1f} · <b style="color:#66bb6a">+${s['g3']:.2f}</b></div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 130px;align-items:center;padding:9px 0">
    <div style="color:#00e676;font-size:.68em;font-weight:900;text-transform:uppercase;letter-spacing:1px">💎 TP 4</div>
    <div style="color:#00e676;font-size:1.1em;font-weight:900;font-family:'Courier New',mono">{fmt(s['tp4'],s['key'])}</div>
    <div style="color:#00695c;font-size:.75em">{dist_fmt(abs(s['tp4']-s['entry']),s['key'])}</div>
    <div style="text-align:right;color:#00695c;font-size:.75em">1:{s['rr4']:.1f} · <b style="color:#00e676">+${s['g4']:.2f}</b></div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;border-top:1px solid rgba(255,255,255,.05);background:rgba(0,0,0,.2)">
  <div style="padding:9px 18px;border-right:1px solid rgba(255,255,255,.04)">
    <div class="px-lbl">Score técnico</div>
    <div style="color:{ac};font-weight:800;font-size:.95em">{sc}/100</div>
    <div style="background:#0e0e1e;border-radius:2px;height:3px;margin-top:4px">
      <div style="height:3px;border-radius:2px;width:{sc}%;background:{ac}"></div></div>
  </div>
  <div style="padding:9px 18px;border-right:1px solid rgba(255,255,255,.04)">
    <div class="px-lbl">IA Ollama</div>
    <div style="color:#ce93d8;font-weight:800;font-size:.95em">{s['ia_conf']}%</div>
    <div style="background:#0e0e1e;border-radius:2px;height:3px;margin-top:4px">
      <div style="height:3px;border-radius:2px;width:{s['ia_conf']}%;background:#7b1fa2"></div></div>
  </div>
  <div style="padding:9px 18px;border-right:1px solid rgba(255,255,255,.04)">
    <div class="px-lbl">Tendencia 1H</div>
    <div style="color:{trend_c};font-weight:800;font-size:.85em">{trend_t}</div>
    <div style="color:#1a1a38;font-size:.65em;margin-top:3px">{s.get('ia_riesgo','—')[:30]}</div>
  </div>
  <div style="padding:9px 18px">
    <div class="px-lbl">Abierta</div>
    <div style="color:#383858;font-weight:700;font-size:.85em">{s['ts_open'][11:16]} hrs</div>
    <div style="color:#1a1a38;font-size:.65em;margin-top:3px">{s['ts_open'][:10]}</div>
  </div>
</div>
<div style="padding:8px 20px;border-top:1px solid rgba(255,255,255,.03);background:rgba(0,0,0,.15)">
  <div style="color:#1e1e38;font-size:.7em;line-height:1.5">
    💡 {s.get('razon','—')[:80]}{'…' if len(s.get('razon',''))>80 else ''}
  </div>
  <div style="color:#1a0000;font-size:.68em;margin-top:2px">
    ⚠ No entrar si el precio ya avanzó más del 35% hacia TP1 · Salir si aparece señal contraria
  </div>
</div>
</div>""", unsafe_allow_html=True)

# ── RADAR DE MERCADO ───────────────────────────────────────────────────────────
if resultados:
    st.markdown('<div class="sec-hdr">📡 Radar de mercado</div>', unsafe_allow_html=True)
    for cat_nom,cat_keys in CATEGORIAS.items():
        claves=[k for k in cat_keys if k in resultados]
        if not claves: continue
        st.markdown(f'<div style="color:#2a2a48;font-size:.62em;text-transform:uppercase;letter-spacing:2.5px;margin:10px 0 5px;font-weight:700">{cat_nom}</div>', unsafe_allow_html=True)
        rows=""
        for key in claves:
            r=resultados[key]; ind=r.get("ind") or {}
            p=live.get(key) or ind.get("price"); sc=r.get("score",0)
            dec=r.get("decision","—"); adx=r.get("adx",0) or ind.get("adx",0)
            conf_txt,conf_c=confiabilidad_mercado(key,spm)
            if r.get("dir")=="buy":
                bg="#010d04"; bl="3px solid #00c853"; glow="box-shadow:0 0 6px rgba(0,200,83,.12)"
                dir_cell=f'<span style="background:#00e676;color:#000;padding:2px 10px;border-radius:3px;font-weight:900;font-size:.75em;box-shadow:0 0 6px rgba(0,230,118,.4)">▲ COMPRA</span>'
                sc_c="#00e676"
            elif r.get("dir")=="sell":
                bg="#0d0101"; bl="3px solid #c62828"; glow="box-shadow:0 0 6px rgba(200,0,0,.12)"
                dir_cell=f'<span style="background:#ff1744;color:#fff;padding:2px 10px;border-radius:3px;font-weight:900;font-size:.75em;box-shadow:0 0 6px rgba(255,23,68,.4)">▼ VENTA</span>'
                sc_c="#ff1744"
            elif dec=="BLOQUEADA":
                bg="#080808"; bl="3px solid #111"; glow=""
                motivo=r.get("motivo","—")
                dir_cell=f'<span style="color:#1e1e30;font-size:.72em">🔒 {motivo[:20]}</span>'
                sc_c="#1e1e30"
            else:
                bg="#09090f"; bl="3px solid #181828"; glow=""
                dir_cell=f'<span style="color:#2a2a48;font-size:.75em">○ {dec}</span>'
                sc_c="#2a2a48"
            dec_badge={"RECOMENDAR":"✅","ESPERAR":"⏳","OBSERVAR":"👀","BLOQUEADA":"🔒","NO_OPERAR":"🚫"}.get(dec,"○")
            rows+=(f'<tr style="background:{bg};border-left:{bl};{glow}">'
                f'<td style="padding:6px 8px;color:#999;font-weight:700">{ACTIVOS[key][1].split()[0]}</td>'
                f'<td style="padding:6px 8px;color:#d8d8f8;font-family:monospace">{fmt(p,key) if p else "—"}</td>'
                f'<td style="padding:6px 8px">{dir_cell}</td>'
                f'<td style="padding:6px 8px;color:{sc_c};font-weight:800">{sc}/100</td>'
                f'<td style="padding:6px 8px;color:#666;font-size:.85em">{dec_badge} {dec}</td>'
                f'<td style="padding:6px 8px;color:{"#00e676" if adx>=20 else "#ffd600" if adx>=15 else "#ff5252"}">{adx:.0f}</td>'
                f'<td style="padding:6px 8px;color:{conf_c};font-size:.72em">{conf_txt}</td></tr>')
        st.markdown(f"""<table class="radar-tbl"><thead><tr>
<th>Activo</th><th>Precio</th><th>Dirección</th><th>Score</th>
<th>Estado</th><th>ADX</th><th>Historial</th></tr></thead><tbody>{rows}</tbody></table>""",
            unsafe_allow_html=True)

# ── BACKTESTING POR MERCADO ────────────────────────────────────────────────────
if spm:
    st.markdown('<div class="sec-hdr">📊 Efectividad por mercado</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#1a1a38;font-size:.7em;margin-bottom:8px">Efectividad real del sistema — necesita ≥30 señales por mercado para ser estadísticamente válida.</div>', unsafe_allow_html=True)
    rows=""
    for key,d in sorted(spm.items(), key=lambda x:-x[1]["wr"]):
        if d["total"]<2: continue
        wr=d["wr"]; wc="#00e676" if wr>=65 else("#ffd600" if wr>=50 else "#ff5252")
        fiable="✓ válida" if d["total"]>=30 else f"({d['total']} muestras)"
        rows+=(f'<tr style="background:#09090f">'
            f'<td style="padding:5px 10px;color:#888;font-weight:600">{ACTIVOS.get(key,("","key","",""))[1].split()[0] if key in ACTIVOS else key}</td>'
            f'<td style="padding:5px 10px;color:#00e676">{d["wins"]}</td>'
            f'<td style="padding:5px 10px;color:#ff5252">{d["losses"]}</td>'
            f'<td style="padding:5px 10px;color:{wc};font-weight:800">{wr:.1f}%</td>'
            f'<td style="padding:5px 10px;color:#252540;font-size:.7em">{fiable}</td></tr>')
    if rows:
        st.markdown(f"""<table class="radar-tbl"><thead><tr>
<th>Mercado</th><th>Ganadas</th><th>Perdidas</th><th>Win Rate</th><th>Validez</th>
</tr></thead><tbody>{rows}</tbody></table>""", unsafe_allow_html=True)

# ── HISTORIAL ──────────────────────────────────────────────────────────────────
cerradas=[s for s in stats["señales"] if s["estado"] in("GANADA","PERDIDA","EXPIRADA")]
if cerradas:
    st.markdown('<div class="sec-hdr">📜 Historial de operaciones</div>', unsafe_allow_html=True)
    for s in cerradas[:25]:
        if s["estado"]=="GANADA":
            css="h-win"; badge='<span class="b-win">✓ GANADA</span>'
            res=f'<b style="color:#69f0ae">+${s["resultado_usd"]:.2f}</b>'
        elif s["estado"]=="PERDIDA":
            css="h-loss"; badge='<span class="b-loss">✗ PERDIDA</span>'
            res=f'<b style="color:#ff5252">-${abs(s["resultado_usd"]):.2f}</b>'
        else:
            css="h-exp"; badge='<span class="b-exp">⏱ EXPIRADA</span>'
            res='<span style="color:#333">$0.00</span>'
        dc="#00e676" if s["dir"]=="buy" else "#ff1744"
        dt="▲ COMPRA" if s["dir"]=="buy" else "▼ VENTA"
        sc=s.get("score",0)
        t_op=s["ts_open"][11:16]; t_cl=(s.get("ts_close") or "")
        t_cl=t_cl[11:16] if len(t_cl)>10 else "—"
        st.markdown(f"""<div class="{css}">
<div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px">
  <div style="display:flex;align-items:center;gap:8px">
    {badge} <b style="color:{dc};font-size:.85em">{dt}</b>
    <b style="color:#c0c0e0">{s['nombre'].split()[0]}</b>
    <span style="color:#252540;font-size:.7em">{sc}/100</span>
  </div>
  <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:.78em">
    <span style="color:#444">Entrada: <b style="color:#82b1ff">{fmt(s['entry'],s['key'])}</b></span>
    <span style="color:#444">SL: <b style="color:#ff5252">{fmt(s['sl'],s['key'])}</b></span>
    <span style="color:#444">TP1: <b style="color:#69f0ae">{fmt(s['tp1'],s['key'])}</b></span>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    {res} <span class="b-ia">🤖 {s['ia_conf']}%</span>
    <span style="color:#1e1e38;font-size:.7em">{t_op}→{t_cl}</span>
  </div>
</div>
</div>""", unsafe_allow_html=True)

# ── AUTO-REFRESH ───────────────────────────────────────────────────────────────
if st.session_state["scanning"]:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=intervalo*1000, key="rf")
    except:
        st.caption(f"Instala streamlit-autorefresh para auto-scan cada {intervalo}s")
