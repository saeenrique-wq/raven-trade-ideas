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
import requests, json, os, re, uuid, time, threading, math
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
KEYS_FILE   = r"C:\Users\saems\scanner_keys.json"
OLLAMA_URL  = "http://localhost:11434/api/chat"
MODELO_IA   = "llama3.2:3b"
MAX_HORAS   = 16
MAX_ABIERTAS_GLOBAL = 5
MIN_MIN_ENTRE_SEÑALES = 30

def keys_load():
    try:
        with open(KEYS_FILE,"r") as f: return json.load(f)
    except: return {}
def keys_save(d):
    try:
        with open(KEYS_FILE,"w") as f: json.dump(d,f,indent=2)
    except: pass
_KEYS = keys_load()

# ── ÍNDICES SINTÉTICOS WELTRADE (MT5) ────────────────────────────────────────
# (nombre_mt5, tipo): tipo = volatility|gain|pain|flip|trend|switch|break|special
WELTRADE_SINTETICOS = {
    "WFV20":     ("FX Vol 20",    "volatility"),
    "WFV40":     ("FX Vol 40",    "volatility"),
    "WFV60":     ("FX Vol 60",    "volatility"),
    "WFV80":     ("FX Vol 80",    "volatility"),
    "WFV99":     ("FX Vol 99",    "volatility"),
    "WSFV20":    ("SFX Vol 20",   "volatility"),
    "WSFV40":    ("SFX Vol 40",   "volatility"),
    "WSFV60":    ("SFX Vol 60",   "volatility"),
    "WSFV80":    ("SFX Vol 80",   "volatility"),
    "WSFV99":    ("SFX Vol 99",   "volatility"),
    "WFLIP1":    ("FlipX 1",      "flip"),
    "WFLIP2":    ("FlipX 2",      "flip"),
    "WFLIP3":    ("FlipX 3",      "flip"),
    "WFLIP4":    ("FlipX 4",      "flip"),
    "WFLIP5":    ("FlipX 5",      "flip"),
    "WGAIN400":  ("GainX 400",    "gain"),
    "WGAIN600":  ("GainX 600",    "gain"),
    "WGAIN800":  ("GainX 800",    "gain"),
    "WGAIN999":  ("GainX 999",    "gain"),
    "WGAIN1200": ("GainX 1200",   "gain"),
    "WPAIN400":  ("PainX 400",    "pain"),
    "WPAIN600":  ("PainX 600",    "pain"),
    "WPAIN800":  ("PainX 800",    "pain"),
    "WPAIN999":  ("PainX 999",    "pain"),
    "WPAIN1200": ("PainX 1200",   "pain"),
    "WSWITCH600": ("SwitchX 600",  "switch"),
    "WSWITCH1200":("SwitchX 1200", "switch"),
    "WSWITCH1800":("SwitchX 1800", "switch"),
    "WBREAK600":  ("BreakX 600",   "break"),
    "WBREAK1200": ("BreakX 1200",  "break"),
    "WBREAK1800": ("BreakX 1800",  "break"),
    "WTREND600":  ("TrendX 600",   "trend"),
    "WTREND1200": ("TrendX 1200",  "trend"),
    "WTREND1800": ("TrendX 1800",  "trend"),
    "WPLUSX1":   ("PlusX 1",      "special"),
    "WFIBOX":    ("FiboX",        "special"),
    "WQUADX":    ("QuadX",        "special"),
}
# Mapa inverso: nombre_mt5 → key interno
_WT_MT5_TO_KEY = {v[0]: k for k, v in WELTRADE_SINTETICOS.items()}

# ── ÍNDICES SINTÉTICOS (MT5/Deriv o API Deriv como respaldo) ──────────────────
SINTETICOS = {
    "V10":     "Volatility 10 Index",
    "V25":     "Volatility 25 Index",
    "V50":     "Volatility 50 Index",
    "V60":     "Volatility 60 Index",
    "V75":     "Volatility 75 Index",
    "V100":    "Volatility 100 Index",
    "V10s":    "Volatility 10 (1s) Index",
    "V25s":    "Volatility 25 (1s) Index",
    "V50s":    "Volatility 50 (1s) Index",
    "V75s":    "Volatility 75 (1s) Index",
    "V100s":   "Volatility 100 (1s) Index",
    "BOOM300": "Boom 300 Index",
    "BOOM500": "Boom 500 Index",
    "BOOM1000":"Boom 1000 Index",
    "CRASH300":"Crash 300 Index",
    "CRASH500":"Crash 500 Index",
    "CRASH1000":"Crash 1000 Index",
    "STEP":    "Step Index",
    "JUMP10":  "Jump 10 Index",
    "JUMP25":  "Jump 25 Index",
    "JUMP50":  "Jump 50 Index",
    "JUMP75":  "Jump 75 Index",
    "JUMP100": "Jump 100 Index",
}

# Símbolos en la API pública de Deriv (sin cuenta, sin autenticación)
DERIV_SYMBOLS = {
    "V10":     "R_10",
    "V25":     "R_25",
    "V50":     "R_50",
    # "V60": "R_60"  — símbolo inválido en Deriv API pública (no existe R_60)
    "V75":     "R_75",
    "V100":    "R_100",
    "V10s":    "1HZ10V",
    "V25s":    "1HZ25V",
    "V50s":    "1HZ50V",
    "V75s":    "1HZ75V",
    "V100s":   "1HZ100V",
    "BOOM300": "BOOM300N",
    "BOOM500": "BOOM500",
    "BOOM1000":"BOOM1000",
    "CRASH300":"CRASH300N",
    "CRASH500":"CRASH500",
    "CRASH1000":"CRASH1000",
    "STEP":    "stpRNG",
    "JUMP10":  "JD10",
    "JUMP25":  "JD25",
    "JUMP50":  "JD50",
    "JUMP75":  "JD75",
    "JUMP100": "JD100",
}

# ── HINTS DE SÍMBOLOS WELTRADE (candidatos por orden de prioridad) ─────────────
WELTRADE_SYMBOL_HINTS = {
    "EURUSD":  ["EURUSD","EURUSD.","EURUSDm","EURUSD_i","EUR/USD"],
    "GBPUSD":  ["GBPUSD","GBPUSD.","GBPUSDm","GBPUSD_i","GBP/USD"],
    "USDJPY":  ["USDJPY","USDJPY.","USDJPYm","USDJPY_i","USD/JPY"],
    "AUDUSD":  ["AUDUSD","AUDUSD.","AUDUSDm","AUDUSD_i","AUD/USD"],
    "USDCAD":  ["USDCAD","USDCAD.","USDCADm","USDCAD_i","USD/CAD"],
    "USDMXN":  ["USDMXN","USDMXN.","USDMXNm","USDMXN_i","USD/MXN"],
    "USDCHF":  ["USDCHF","USDCHF.","USDCHFm","USD/CHF"],
    "XAUUSD":  ["XAUUSD","XAUUSD.","XAUUSDm","XAUUSDc","XAUUSDpro","XAUUSD_i",
                "GOLD","Gold","gold","XAUUSD.r","XAUUSD-ECN","XAUUSDf","XAUUSD+","XAUUSDs"],
    "XAGUSD":  ["XAGUSD","XAGUSD.","XAGUSDm","SILVER","Silver"],
    "WTIUSD":  ["WTI","WTI.","USOIL","USOIL.","XTIUSD","WTI.cash","Crude"],
    "US30":    ["US30","US30.","US30m","US30.cash","US30Cash","DJ30","DJI","Wall Street"],
    "US100":   ["US100","US100.","US100m","US100.cash","NAS100","USTEC","NASDAQ","US Tech 100"],
    "SPX500":  ["SPX500","SPX500.","SPX500m","SPX500.cash","US500","SP500","S&P500"],
    "GER40":   ["GER40","GER40.","GER40m","GER40.cash","DE40","DAX","DAX40"],
    "UK100":   ["UK100","UK100.","UK100m","UK100.cash","FTSE100","FTSE"],
    # Crypto — primero sin T (BTCUSD) luego con T (BTCUSDT)
    "BTCUSD":  ["BTCUSD","BTCUSD.","BTCUSDm","BTCUSDT","BTC/USD","Bitcoin"],
    "ETHUSD":  ["ETHUSD","ETHUSD.","ETHUSDm","ETHUSDT","ETH/USD","Ethereum"],
    "SOLUSD":  ["SOLUSD","SOLUSD.","SOLUSDm","SOLUSDT","SOL/USD"],
    "XRPUSD":  ["XRPUSD","XRPUSD.","XRPUSDm","XRPUSDT","XRP/USD"],
    "BNBUSD":  ["BNBUSD","BNBUSD.","BNBUSDm","BNBUSDT","BNB/USD"],
    "ADAUSD":  ["ADAUSD","ADAUSD.","ADAUSDm","ADAUSDT","ADA/USD"],
    # Sintéticos Deriv
    "V10":     ["Volatility 10 Index","R_10","Vol10Index","VOLX10"],
    "V25":     ["Volatility 25 Index","R_25","Vol25Index","VOLX25"],
    "V50":     ["Volatility 50 Index","R_50","Vol50Index","VOLX50"],
    "V60":     ["Volatility 60 Index","VOLX60"],
    "V75":     ["Volatility 75 Index","R_75","Vol75Index","VOLX75"],
    "V100":    ["Volatility 100 Index","R_100","Vol100Index","VOLX100"],
    "V10s":    ["Volatility 10 (1s) Index","1HZ10V","Vol10_1s"],
    "V25s":    ["Volatility 25 (1s) Index","1HZ25V","Vol25_1s"],
    "V50s":    ["Volatility 50 (1s) Index","1HZ50V","Vol50_1s"],
    "V75s":    ["Volatility 75 (1s) Index","1HZ75V","Vol75_1s"],
    "V100s":   ["Volatility 100 (1s) Index","1HZ100V","Vol100_1s"],
    "BOOM300": ["Boom 300 Index","BOOM300","BOOM300N"],
    "BOOM500": ["Boom 500 Index","BOOM500","BOOM500N"],
    "BOOM1000":["Boom 1000 Index","BOOM1000","BOOM1000N"],
    "CRASH300":["Crash 300 Index","CRASH300","CRASH300N"],
    "CRASH500":["Crash 500 Index","CRASH500","CRASH500N"],
    "CRASH1000":["Crash 1000 Index","CRASH1000","CRASH1000N"],
    "STEP":    ["Step Index","STEP","STPIDX"],
    "JUMP10":  ["Jump 10 Index","JUMP10","JD10"],
    "JUMP25":  ["Jump 25 Index","JUMP25","JD25"],
    "JUMP50":  ["Jump 50 Index","JUMP50","JD50"],
    "JUMP75":  ["Jump 75 Index","JUMP75","JD75"],
    "JUMP100": ["Jump 100 Index","JUMP100","JD100"],
}
# Mantener alias para compatibilidad con código existente
MT5_SYMBOLS = WELTRADE_SYMBOL_HINTS

# ── CONEXIÓN MT5 ───────────────────────────────────────────────────────────────
_mt5_status = {"connected":False,"broker":"—","server":"—","account":"—","error":"No iniciado"}

def _mt5_save_state():
    """Persiste _mt5_status en session_state para que sobreviva rerenders."""
    try:
        st.session_state["mt5_status"] = dict(_mt5_status)
    except Exception:
        pass

def ensure_mt5_connection(force=False):
    """Conecta MT5. Persiste estado en session_state para no perderlo en cada render."""
    global _mt5_status
    if not force and _mt5_status.get("connected"):
        return True
    try:
        import MetaTrader5 as mt5
    except ImportError:
        _mt5_status = {"connected":False,"broker":"—","server":"—","account":"—",
                       "error":"MetaTrader5 no instalado. pip install MetaTrader5"}
        _mt5_save_state(); return False
    try:
        initialized = mt5.initialize()
        if not initialized:
            err = mt5.last_error()
            _mt5_status = {"connected":False,"broker":"—","server":"—","account":"—",
                           "error":f"initialize() falló: {err}"}
            _mt5_save_state(); return False
        info = mt5.account_info()
        if info:
            _mt5_status = {
                "connected": True,
                "broker":  getattr(info,"company","Desconocido"),
                "server":  getattr(info,"server","—"),
                "account": str(getattr(info,"login","—")),
                "error":   "",
                "last_error": str(mt5.last_error()),
            }
        else:
            _mt5_status = {"connected":True,"broker":"—","server":"—",
                           "account":"—","error":"Sin cuenta activa","last_error":str(mt5.last_error())}
        _mt5_save_state(); return True
    except Exception as e:
        _mt5_status = {"connected":False,"broker":"—","server":"—","account":"—",
                       "error":str(e)[:80],"last_error":str(e)}
        _mt5_save_state(); return False

# Alias para compatibilidad
def init_mt5():
    return ensure_mt5_connection(force=True)

def get_available_mt5_symbols(force=False):
    """Lee todos los símbolos disponibles en MT5. Cachea en session_state 60s."""
    if not _mt5_status.get("connected"):
        return []
    now = time.time()
    cached = st.session_state.get("mt5_symbols")
    last_t = st.session_state.get("mt5_symbols_ts", 0)
    if cached is not None and not force and (now - last_t) < 60:
        return cached
    try:
        import MetaTrader5 as mt5
        syms = mt5.symbols_get()
        if syms is None:
            return cached or []
        names = [s.name for s in syms]
        st.session_state["mt5_symbols"] = names
        st.session_state["mt5_symbols_ts"] = now
        return names
    except:
        return cached or []

def find_mt5_symbol(asset_key):
    """
    Busca el símbolo real en MT5 para un asset_key dado.
    Retorna dict con found, symbol, reason.
    """
    available = get_available_mt5_symbols()
    # Si MT5 no está disponible, devolver no encontrado
    if not available:
        return {"found":False,"requested":asset_key,"symbol":None,
                "reason":"MT5 sin símbolos (desconectado o lista vacía)"}

    available_lower = {s.lower(): s for s in available}
    candidates = WELTRADE_SYMBOL_HINTS.get(asset_key, [asset_key])

    # 1. Coincidencia exacta con candidatos conocidos
    for c in candidates:
        if c in available:
            return {"found":True,"requested":asset_key,"symbol":c,"reason":"match exacto"}

    # 2. Coincidencia sin distinción de mayúsculas
    for c in candidates:
        if c.lower() in available_lower:
            real = available_lower[c.lower()]
            return {"found":True,"requested":asset_key,"symbol":real,"reason":"match case-insensitive"}

    # 3. El asset_key mismo (sin hints)
    base = asset_key.replace("/","")
    if base in available:
        return {"found":True,"requested":asset_key,"symbol":base,"reason":"match directo"}
    if base.lower() in available_lower:
        return {"found":True,"requested":asset_key,"symbol":available_lower[base.lower()],"reason":"match directo ci"}

    # 4. startswith — candidatos que empiezan con el base
    for sym in available:
        if sym.startswith(base):
            return {"found":True,"requested":asset_key,"symbol":sym,"reason":f"startswith '{base}'"}

    # 5. Búsqueda flexible: algún candidato es prefijo de un símbolo disponible
    for c in candidates:
        cbase = c.replace("/","")
        for sym in available:
            if sym.startswith(cbase):
                return {"found":True,"requested":asset_key,"symbol":sym,"reason":f"startswith candidato '{cbase}'"}

    # 6. El símbolo disponible contiene el base (para nombres largos como sintéticos)
    for c in candidates:
        for sym in available:
            if c.lower() in sym.lower() or sym.lower() in c.lower():
                return {"found":True,"requested":asset_key,"symbol":sym,"reason":f"contiene '{c}'"}

    return {"found":False,"requested":asset_key,"symbol":None,
            "reason":f"no encontrado en {len(available)} símbolos Weltrade"}

def _rates_to_df(rates):
    """Convierte array de rates MT5 a DataFrame OHLCV."""
    df = pd.DataFrame(rates)
    df.index = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"open":"Open","high":"High","low":"Low",
                       "close":"Close","tick_volume":"Volume"}, inplace=True)
    return df

def get_mt5_bars(symbol_key, timeframe_str, n=200):
    """Obtiene velas OHLCV de MT5 con búsqueda automática de símbolo real."""
    if not _mt5_status.get("connected"):
        return pd.DataFrame()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return pd.DataFrame()

    TF = {"1m":mt5.TIMEFRAME_M1,"5m":mt5.TIMEFRAME_M5,
          "15m":mt5.TIMEFRAME_M15,"60m":mt5.TIMEFRAME_H1}
    tf = TF.get(timeframe_str, mt5.TIMEFRAME_M15)

    result = find_mt5_symbol(symbol_key)
    if not result["found"]:
        # Guardar diagnóstico en session_state para debug
        st.session_state[f"mt5_debug_{symbol_key}"] = {
            "status":"SIN SÍMBOLO","symbol":None,"bars":0,"reason":result["reason"]}
        return pd.DataFrame()

    sym = result["symbol"]
    try:
        # Activar símbolo en Market Watch
        mt5.symbol_select(sym, True)
        info = mt5.symbol_info(sym)
        if info is None:
            st.session_state[f"mt5_debug_{symbol_key}"] = {
                "status":"SÍMBOLO SIN INFO","symbol":sym,"bars":0,"reason":"symbol_info() None"}
            return pd.DataFrame()

        # Intento 1: copy_rates_from_pos
        rates = mt5.copy_rates_from_pos(sym, tf, 0, n)
        if rates is not None and len(rates) >= 30:
            st.session_state[f"mt5_debug_{symbol_key}"] = {
                "status":"OK","symbol":sym,"bars":len(rates),"reason":result["reason"]}
            return _rates_to_df(rates)

        # Intento 2: esperar y reintentar (MT5 necesita suscribirse al símbolo)
        time.sleep(0.5)
        rates = mt5.copy_rates_from_pos(sym, tf, 0, n)
        if rates is not None and len(rates) >= 30:
            st.session_state[f"mt5_debug_{symbol_key}"] = {
                "status":"OK (retry)","symbol":sym,"bars":len(rates),"reason":result["reason"]}
            return _rates_to_df(rates)

        # Intento 3: copy_rates_range con rango de fechas
        utc_to = datetime.utcnow()
        utc_from = utc_to - timedelta(days=10)
        rates = mt5.copy_rates_range(sym, tf, utc_from, utc_to)
        if rates is not None and len(rates) >= 30:
            st.session_state[f"mt5_debug_{symbol_key}"] = {
                "status":"OK (range)","symbol":sym,"bars":len(rates),"reason":result["reason"]}
            return _rates_to_df(rates)

        # Sin datos
        bars_got = len(rates) if rates is not None else 0
        st.session_state[f"mt5_debug_{symbol_key}"] = {
            "status":"SIN HISTÓRICO","symbol":sym,"bars":bars_got,
            "reason":"Abre el gráfico en MT5 para descargar histórico"}
        return pd.DataFrame()

    except Exception as e:
        st.session_state[f"mt5_debug_{symbol_key}"] = {
            "status":"ERROR","symbol":sym,"bars":0,"reason":str(e)[:60]}
        return pd.DataFrame()

def get_mt5_price(symbol_key):
    """Precio bid actual desde MT5 usando búsqueda automática de símbolo."""
    if not _mt5_status.get("connected"):
        return None
    try:
        import MetaTrader5 as mt5
        result = find_mt5_symbol(symbol_key)
        if not result["found"]:
            return None
        sym = result["symbol"]
        mt5.symbol_select(sym, True)
        tick = mt5.symbol_info_tick(sym)
        if tick and tick.bid > 0:
            return tick.bid
    except:
        pass
    return None

# ══════════════════════════════════════════════════════════════════════════════
# ORO / XAUUSD M5 — MÓDULO ESPECIALIZADO
# ══════════════════════════════════════════════════════════════════════════════

XAUUSD_VARIANTS = [
    "XAUUSD", "XAUUSD.", "XAUUSDm", "XAUUSDc", "XAUUSDpro",
    "GOLD", "Gold", "gold", "XAUUSD.r", "XAUUSD_i", "XAUUSD-ECN",
    "XAUUSDf", "XAUUSD+", "XAUUSDs", "XAUUSD.pro", "XAU/USD",
]

def find_gold_mt5_symbol():
    """Busca el símbolo real de XAUUSD entre todos los disponibles en MT5."""
    if not _mt5_status.get("connected"):
        return None, "MT5 desconectado"
    available = get_available_mt5_symbols()
    if not available:
        return None, "Lista de símbolos MT5 vacía"
    available_set  = set(available)
    available_lower = {s.lower(): s for s in available}
    candidates = list(dict.fromkeys(XAUUSD_VARIANTS + WELTRADE_SYMBOL_HINTS.get("XAUUSD", [])))
    for c in candidates:
        if c in available_set:
            return c, f"match exacto '{c}'"
        if c.lower() in available_lower:
            return available_lower[c.lower()], f"match ci '{c}'"
    for s in available:
        if s.upper().startswith("XAUUSD") or s.upper() == "GOLD":
            return s, f"startswith: '{s}'"
    return None, f"no encontrado entre {len(available)} símbolos"

def is_new_m5_candle():
    """True si estamos en los primeros 30 s de una vela M5 nueva."""
    now = datetime.utcnow()
    secs = (now.minute % 5) * 60 + now.second
    return secs < 30

def get_gold_live_data():
    """Obtiene precio en vivo y velas M1/M5/M15 de XAUUSD desde MT5."""
    out = {
        "ok": False, "symbol": "XAUUSD", "mt5_symbol": None,
        "price": None, "bid": None, "ask": None, "spread": None,
        "m1": pd.DataFrame(), "m5": pd.DataFrame(), "m15": pd.DataFrame(),
        "source": "MT5 / Weltrade", "error": None,
    }
    if not _mt5_status.get("connected"):
        out["error"] = "MT5 desconectado — presiona Conectar MT5"
        return out
    try:
        import MetaTrader5 as mt5
    except ImportError:
        out["error"] = "MetaTrader5 no instalado (pip install MetaTrader5)"
        return out
    sym, reason = find_gold_mt5_symbol()
    if not sym:
        out["error"] = f"Símbolo XAUUSD no encontrado: {reason}"
        return out
    out["mt5_symbol"] = sym
    try:
        mt5.symbol_select(sym, True)
        tick = mt5.symbol_info_tick(sym)
        if tick and tick.bid > 0:
            out["bid"]    = float(tick.bid)
            out["ask"]    = float(tick.ask)
            out["price"]  = float(tick.bid)
            out["spread"] = round(tick.ask - tick.bid, 4)
        def _get_bars(tf, n=350):
            r = mt5.copy_rates_from_pos(sym, tf, 0, n)
            if r is None or len(r) < 30:
                time.sleep(0.35)
                r = mt5.copy_rates_from_pos(sym, tf, 0, n)
            if r is not None and len(r) >= 30:
                return _rates_to_df(r)
            utc_to = datetime.utcnow()
            r = mt5.copy_rates_range(sym, tf, utc_to - timedelta(days=10), utc_to)
            return _rates_to_df(r) if r is not None and len(r) >= 30 else pd.DataFrame()
        out["m1"]  = _get_bars(mt5.TIMEFRAME_M1,  350)
        out["m5"]  = _get_bars(mt5.TIMEFRAME_M5,  350)
        out["m15"] = _get_bars(mt5.TIMEFRAME_M15, 350)
        if out["m5"].empty:
            out["error"] = "Sin velas M5 — abre el gráfico XAUUSD en MT5"
            return out
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)[:80]
    return out

def calc_gold_ind(df):
    """Indicadores técnicos para Gold: incluye EMA9, EMA21 además de analizar_df."""
    if df is None or df.empty or len(df) < 30:
        return {}
    base = analizar_df(df)
    if not base:
        return {}
    c = df["Close"].astype(float)
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    o = df["Open"].astype(float)
    n = min(len(c) - 1, 14)
    ema9  = ta.trend.EMAIndicator(c, min(9,  len(c)-1)).ema_indicator()
    ema21 = ta.trend.EMAIndicator(c, min(21, len(c)-1)).ema_indicator()
    base["ema9"]       = float(ema9.iloc[-1])
    base["ema21"]      = float(ema21.iloc[-1])
    base["ema9_prev"]  = float(ema9.iloc[-2])  if len(ema9)  > 1 else base["ema9"]
    base["ema21_prev"] = float(ema21.iloc[-2]) if len(ema21) > 1 else base["ema21"]
    last_o = float(o.iloc[-1]); last_c2 = float(c.iloc[-1])
    last_h = float(h.iloc[-1]); last_l  = float(l.iloc[-1])
    cuerpo = abs(last_c2 - last_o)
    rango  = last_h - last_l
    base["cuerpo"]        = cuerpo
    base["rango_vela"]    = rango
    base["mecha_sup"]     = last_h - max(last_o, last_c2)
    base["mecha_inf"]     = min(last_o, last_c2) - last_l
    base["cierre_alcista"] = last_c2 > last_o
    base["max_10"] = float(h.iloc[-11:-1].max()) if len(h) > 11 else float(h.max())
    base["min_10"] = float(l.iloc[-11:-1].min()) if len(l) > 11 else float(l.min())
    base["max_20"] = float(h.iloc[-21:-1].max()) if len(h) > 21 else float(h.max())
    base["min_20"] = float(l.iloc[-21:-1].min()) if len(l) > 21 else float(l.min())
    atr_s = ta.volatility.AverageTrueRange(h, l, c, n).average_true_range()
    base["atr_avg"] = float(atr_s.iloc[-10:].mean()) if len(atr_s) >= 10 else base["atr"]
    base["vol_tick"] = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else 0
    return base

def score_gold(i_m15, i_m5, i_m1, spread, spread_max=3.0):
    """Score 0-100 específico XAUUSD con 7 componentes."""
    s = 0; bd = {}

    # A) Tendencia M15 alineada: 20 pts
    a = 0
    if i_m15:
        p15 = i_m15.get("price", 0)
        if p15 > i_m15.get("ema200", 0): a += 7
        elif p15 < i_m15.get("ema200", 0): a += 7
        if i_m15.get("ema20", 0) > i_m15.get("ema50", 0): a += 7
        elif i_m15.get("ema20", 0) < i_m15.get("ema50", 0): a += 7
        adx15 = i_m15.get("adx", 0)
        if adx15 >= 20: a += 6
        elif adx15 >= 15: a += 3
    a = min(a, 20); s += a; bd["A_tend_m15"] = a

    # B) Setup M5 válido: 25 pts
    b = 0
    if i_m5:
        rsi5 = i_m5.get("rsi", 50); adx5 = i_m5.get("adx", 15)
        if 35 <= rsi5 <= 65: b += 8
        elif 30 <= rsi5 <= 70: b += 4
        if adx5 >= 20: b += 8
        elif adx5 >= 15: b += 4
        if not i_m5.get("lateral", True): b += 5
        if not i_m5.get("vela_ext", False): b += 4
    b = min(b, 25); s += b; bd["B_setup_m5"] = b

    # C) Confirmación M1: 15 pts
    c = 0
    if i_m1:
        if i_m1.get("buy_score", 0) >= 3 or i_m1.get("sell_score", 0) >= 3: c += 8
        rsi1 = i_m1.get("rsi", 50)
        if 30 <= rsi1 <= 70: c += 4
        if i_m1.get("ema20", 0) > 0 and i_m1.get("ema50", 0) > 0: c += 3
    c = min(c, 15); s += c; bd["C_conf_m1"] = c

    # D) Momentum / ADX / MACD: 15 pts
    d = 0
    if i_m5:
        adx5 = i_m5.get("adx", 0)
        if adx5 >= 25: d += 6
        elif adx5 >= 20: d += 4
        if abs(i_m5.get("macd_h", 0)) > 0: d += 5
        sk = i_m5.get("stoch_k", 50)
        if sk < 45 or sk > 55: d += 4
    d = min(d, 15); s += d; bd["D_momentum"] = d

    # E) ATR y volatilidad: 10 pts
    e = 0
    if i_m5:
        atr = i_m5.get("atr", 0); avg = i_m5.get("atr_avg", atr)
        if atr > 0 and avg > 0:
            ratio = atr / avg
            if 0.7 <= ratio <= 2.5: e += 6
            elif 0.5 <= ratio < 0.7: e += 3
        if not i_m5.get("vela_ext", False): e += 4
    e = min(e, 10); s += e; bd["E_atr"] = e

    # F) Entrada no tardía: 10 pts (se resta en senal_gold_m5 si hay tardía)
    f = 10; bd["F_entrada"] = f; s += f

    # G) Spread aceptable: 5 pts
    g = 0
    if spread is not None:
        if spread <= spread_max: g = 5
        elif spread <= spread_max * 1.5: g = 2
    g = min(g, 5); s += g; bd["G_spread"] = g

    return min(s, 100), bd

def senal_gold_m5(stats=None, horarios_bloqueados=None, spread_max=3.0, min_score=70):
    """Motor de señales XAUUSD M5. Analiza 4 patrones con contexto M15 y M1."""
    res = {
        "ok": False, "dir": None, "decision": "BLOQUEADA",
        "motivo": "iniciando", "score": 0, "score_bd": {},
        "patron": "—", "entry": 0.0, "sl": 0.0,
        "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "tp4": 0.0,
        "tendencia_m15": "neutral", "setup_m5": "—", "conf_m1": "—",
        "nuevo_ciclo": is_new_m5_candle(), "mt5_symbol": None,
        "price": None, "bid": None, "ask": None, "spread": None,
        "m1_bars": 0, "m5_bars": 0, "m15_bars": 0,
        "ind_m5": {}, "ind_m15": {}, "ind_m1": {},
        "ia_nota": "", "clase": "NO OPERAR", "color": "#555", "badge": "b-wait",
        "ultima_act": datetime.now().strftime("%H:%M:%S"),
    }

    # Filtro noticias manual
    if horarios_bloqueados:
        now_u = datetime.utcnow()
        now_hm = now_u.hour * 60 + now_u.minute
        for blq in horarios_bloqueados:
            try:
                h1, m1_ = map(int, blq[0].split(":")); h2, m2 = map(int, blq[1].split(":"))
                if (h1 * 60 + m1_) <= now_hm <= (h2 * 60 + m2):
                    res["decision"] = "BLOQUEADA"
                    res["motivo"]   = f"Noticia bloqueada {blq[0]}-{blq[1]}"
                    return res
            except:
                pass

    data = get_gold_live_data()
    st.session_state["gold_live_data"] = data

    if not data["ok"]:
        res["motivo"]   = data.get("error", "sin datos MT5")
        res["decision"] = "BLOQUEADA"
        # propagate partial data for debug
        res["mt5_symbol"] = data.get("mt5_symbol")
        return res

    res.update({
        "ok": True, "mt5_symbol": data["mt5_symbol"],
        "price": data["price"], "bid": data["bid"],
        "ask": data["ask"],     "spread": data["spread"],
        "m1_bars": len(data["m1"]), "m5_bars": len(data["m5"]),
        "m15_bars": len(data["m15"]),
    })

    i_m5  = calc_gold_ind(data["m5"])
    i_m15 = calc_gold_ind(data["m15"])
    i_m1  = calc_gold_ind(data["m1"]) if not data["m1"].empty else {}
    res["ind_m5"] = i_m5; res["ind_m15"] = i_m15; res["ind_m1"] = i_m1

    if not i_m5:
        res["motivo"] = "Sin indicadores M5 — histórico insuficiente"
        return res

    price = data["price"] or i_m5["price"]
    atr   = i_m5.get("atr", 5.0) or 5.0

    abierto, motivo_merc = mercado_abierto("XAUUSD")
    if not abierto:
        res["decision"] = "BLOQUEADA"; res["motivo"] = motivo_merc
        return res

    spread_val = data["spread"]
    if spread_val and spread_val > spread_max * 2:
        res["decision"] = "BLOQUEADA"
        res["motivo"]   = f"Spread muy alto: {spread_val:.2f} (máx {spread_max:.1f})"
        return res

    # ── Tendencia M15 ─────────────────────────────────────────────────────────
    tend_m15 = "neutral"
    if i_m15:
        if (i_m15.get("price", 0) > i_m15.get("ema50", 0) and
                i_m15.get("ema20", 0) > i_m15.get("ema50", 0)):
            tend_m15 = "buy"
        elif (i_m15.get("price", 0) < i_m15.get("ema50", 0) and
              i_m15.get("ema20", 0) < i_m15.get("ema50", 0)):
            tend_m15 = "sell"
    res["tendencia_m15"] = tend_m15

    # ── Variables M5 ──────────────────────────────────────────────────────────
    rsi5     = i_m5.get("rsi", 50)
    adx5     = i_m5.get("adx", 15)
    macd5    = i_m5.get("macd_h", 0)
    ema9_5   = i_m5.get("ema9", price)
    ema21_5  = i_m5.get("ema21", price)
    ema50_5  = i_m5.get("ema50", price)
    ema200_5 = i_m5.get("ema200", price)
    atr_avg  = i_m5.get("atr_avg", atr)
    mecha_inf  = i_m5.get("mecha_inf", 0)
    mecha_sup  = i_m5.get("mecha_sup", 0)
    cuerpo5    = i_m5.get("cuerpo", atr * 0.3)
    cierre_alc = i_m5.get("cierre_alcista", False)
    max_10  = i_m5.get("max_10", price)
    min_10  = i_m5.get("min_10", price)

    # Confirmación M1
    conf_m1 = "—"
    if i_m1:
        if i_m1.get("buy_score", 0) >= 3:    conf_m1 = "alcista"
        elif i_m1.get("sell_score", 0) >= 3: conf_m1 = "bajista"

    # ── Patrones ──────────────────────────────────────────────────────────────
    dir_   = None; patron = "—"; setup_m5 = "—"

    # 1. Pullback a EMA 21
    pb_buy  = (tend_m15 in ("buy", "neutral") and
               price > ema50_5 * 0.9985 and
               abs(price - ema21_5) < atr * 0.8 and
               40 <= rsi5 <= 58 and
               (mecha_inf > cuerpo5 * 1.5 or cierre_alc))
    pb_sell = (tend_m15 in ("sell", "neutral") and
               price < ema50_5 * 1.0015 and
               abs(price - ema21_5) < atr * 0.8 and
               42 <= rsi5 <= 60 and
               (mecha_sup > cuerpo5 * 1.5 or not cierre_alc))

    # 2. Ruptura de rango
    rb_buy  = (price > max_10 * 1.0001 and atr > atr_avg * 0.9 and
               adx5 >= 20 and cierre_alc and tend_m15 in ("buy", "neutral"))
    rb_sell = (price < min_10 * 0.9999 and atr > atr_avg * 0.9 and
               adx5 >= 20 and not cierre_alc and tend_m15 in ("sell", "neutral"))

    # 3. Fakeout / barrida de liquidez
    fk_buy  = (price > min_10 and mecha_inf > cuerpo5 * 2.5 and
               rsi5 >= 40 and cierre_alc)
    fk_sell = (price < max_10 and mecha_sup > cuerpo5 * 2.5 and
               rsi5 <= 60 and not cierre_alc)

    # 4. Continuación momentum
    mo_buy  = (ema9_5 > ema21_5 > ema50_5 and macd5 > 0 and
               adx5 >= 25 and cierre_alc and price < ema21_5 + atr * 2)
    mo_sell = (ema9_5 < ema21_5 < ema50_5 and macd5 < 0 and
               adx5 >= 25 and not cierre_alc and price > ema21_5 - atr * 2)

    if pb_buy:   dir_ = "buy";  patron = "Pullback EMA21"; setup_m5 = "Rechazo alcista en EMA21"
    elif pb_sell: dir_ = "sell"; patron = "Pullback EMA21"; setup_m5 = "Rechazo bajista en EMA21"
    elif mo_buy:  dir_ = "buy";  patron = "Momentum Alcista"; setup_m5 = "EMA9>21>50 · MACD+ · ADX fuerte"
    elif mo_sell: dir_ = "sell"; patron = "Momentum Bajista"; setup_m5 = "EMA9<21<50 · MACD- · ADX fuerte"
    elif rb_buy:  dir_ = "buy";  patron = "Ruptura Rango";   setup_m5 = f"Cierre sobre máx {max_10:.2f}"
    elif rb_sell: dir_ = "sell"; patron = "Ruptura Rango";   setup_m5 = f"Cierre bajo mín {min_10:.2f}"
    elif fk_buy:  dir_ = "buy";  patron = "Fakeout Bajista"; setup_m5 = "Barrida liquidez · mecha inferior"
    elif fk_sell: dir_ = "sell"; patron = "Fakeout Alcista"; setup_m5 = "Barrida liquidez · mecha superior"

    res["patron"] = patron; res["setup_m5"] = setup_m5; res["conf_m1"] = conf_m1

    if dir_ is None:
        res["decision"] = "NO_OPERAR"; res["motivo"] = "Sin patrón válido en M5"
        return res

    res["dir"] = dir_

    # ── Score ─────────────────────────────────────────────────────────────────
    score, score_bd = score_gold(i_m15, i_m5, i_m1 if i_m1 else None, spread_val, spread_max)
    res["score"] = score; res["score_bd"] = score_bd

    # ── Niveles ATR ───────────────────────────────────────────────────────────
    m = 1 if dir_ == "buy" else -1
    entry = price
    sl   = entry - m * atr * 1.2
    tp1  = entry + m * atr * 0.8
    tp2  = entry + m * atr * 2.0
    tp3  = entry + m * atr * 3.5
    tp4  = entry + m * atr * 5.5
    res.update({"entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3, "tp4": tp4})

    # Filtro entrada tardía
    tardia, avance = entrada_tardia(price, entry, tp1)
    if tardia:
        score = max(0, score - 10)
        res["score"] = score; score_bd["F_entrada"] = 0
        res["decision"] = "ESPERAR"; res["motivo"] = "Entrada tardía — esperar pullback"
        res["clase"] = "ESPERAR"; res["color"] = "#ffd600"; res["badge"] = "b-alta"
        return res

    # Deduplicación
    if stats and is_duplicate_gold_signal(stats):
        res["decision"] = "BLOQUEADA"
        res["motivo"]   = "Señal XAUUSD duplicada / cooldown 15 min"
        return res

    clase_g, color_g, badge_g = clasificar(score)
    res["clase"] = clase_g; res["color"] = color_g; res["badge"] = badge_g

    if score >= 80:
        res["decision"] = "RECOMENDAR"
        res["motivo"]   = clase_g
    elif score >= min_score:
        res["decision"] = "OBSERVAR"
        res["motivo"]   = "Setup en formación"
    else:
        res["decision"] = "NO_OPERAR"
        res["motivo"]   = f"Score insuficiente ({score}/100)"

    # Nota IA compacta (sin bloquear señal)
    res["ia_nota"] = (
        f"XAUUSD {patron} en M5 con M15 {'alcista' if tend_m15=='buy' else 'bajista' if tend_m15=='sell' else 'neutral'} "
        f"y RSI {rsi5:.0f}. {'LONG' if dir_=='buy' else 'SHORT'} válido si respeta zona."
    )
    return res

def is_duplicate_gold_signal(stats):
    """Cooldown 15 min entre señales XAUUSD."""
    now = datetime.now()
    for s in stats.get("señales", []):
        if s.get("key") != "XAUUSD": continue
        if s.get("estado") == "ABIERTA": return True
        try:
            t = datetime.strptime(s["ts_open"], "%Y-%m-%d %H:%M:%S")
            if (now - t).total_seconds() < 15 * 60: return True
        except:
            pass
    return False

def stats_gold_summary(stats):
    """Resumen estadístico de señales XAUUSD."""
    sg = [s for s in stats.get("señales", []) if s.get("key") == "XAUUSD"]
    cerradas = [s for s in sg if s.get("estado") in ("GANADA", "PERDIDA")]
    wins  = sum(1 for s in cerradas if s["estado"] == "GANADA")
    losses= sum(1 for s in cerradas if s["estado"] == "PERDIDA")
    total = len(cerradas)
    patrones = {}
    for s in cerradas:
        p = s.get("patron", "—")
        if p not in patrones: patrones[p] = {"wins": 0, "losses": 0}
        if s["estado"] == "GANADA": patrones[p]["wins"] += 1
        else:                       patrones[p]["losses"] += 1
    sw = [s.get("score", 0) for s in cerradas if s["estado"] == "GANADA"]
    sl_ = [s.get("score", 0) for s in cerradas if s["estado"] == "PERDIDA"]
    return {
        "total": total, "wins": wins, "losses": losses,
        "winrate": wins / total * 100 if total > 0 else 0,
        "patrones": patrones,
        "score_avg_win":  sum(sw)  / len(sw)  if sw  else 0,
        "score_avg_loss": sum(sl_) / len(sl_) if sl_ else 0,
        "abiertas": sum(1 for s in sg if s.get("estado") == "ABIERTA"),
    }

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

# ── RESTAURAR ESTADO MT5 DESDE SESSION_STATE ──────────────────────────────────
# _mt5_status es variable de módulo y se resetea en cada rerender de Streamlit.
# Lo restauramos desde session_state antes de que cualquier función lo use.
if "mt5_status" not in st.session_state:
    st.session_state["mt5_status"] = dict(_mt5_status)
else:
    _mt5_status.update(st.session_state["mt5_status"])
# Auto-intentar conexión silenciosa al iniciar
if not _mt5_status.get("connected"):
    ensure_mt5_connection(force=False)

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
    base={"señales":[],"total":0,"wins":0,"losses":0,"pnl_usd":0.0,"racha_actual":0,"mejor_racha":0}
    try:
        with open(STATS_FILE,"r",encoding="utf-8") as f: d=json.load(f)
        base.update(d)
        if not isinstance(base.get("señales"),list): base["señales"]=[]
        return base
    except: return base
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
_cache_fuentes:dict={}  # key -> "MT5"/"Binance"/"Yahoo"/"CoinGecko"

def _coingecko_prices():
    """Precios crypto desde CoinGecko como fuente adicional."""
    CG_IDS = {
        "BTCUSD":"bitcoin","ETHUSD":"ethereum","SOLUSD":"solana",
        "XRPUSD":"ripple","BNBUSD":"binancecoin","ADAUSD":"cardano",
    }
    try:
        ids = ",".join(CG_IDS.values())
        r = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd",
            timeout=6)
        data = r.json()
        return {k: data[v]["usd"] for k,v in CG_IDS.items() if v in data and "usd" in data[v]}
    except:
        return {}

def _yahoo_spot(key):
    """Precio spot desde Yahoo Finance."""
    sym = ACTIVOS.get(key,("",))[0]
    if not sym: return None
    return _yahoo_v8(sym)

def precios_en_vivo():
    global _cache_p, _cache_t, _cache_fuentes
    if time.time()-_cache_t<8 and _cache_p: return _cache_p
    precios={}
    fuentes={}

    # ── Fuente 1: MT5 Weltrade (más preciso, spread real)
    if _mt5_status["connected"]:
        for key in ACTIVOS:
            p = get_mt5_price(key)
            if p:
                precios[key]=p; fuentes[key]="MT5"

    # ── Fuente 2: Binance (crypto en tiempo real, sin spread)
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price",timeout=4)
        all_b={i["symbol"]:float(i["price"]) for i in r.json()}
        for k,b in BINANCE_MAP.items():
            if k not in precios and b in all_b:
                precios[k]=all_b[b]; fuentes[k]="Binance"
    except: pass

    # ── Fuente 3: CoinGecko (respaldo crypto)
    pendientes_crypto=[k for k in BINANCE_MAP if k not in precios]
    if pendientes_crypto:
        for k,p in _coingecko_prices().items():
            if k not in precios:
                precios[k]=p; fuentes[k]="CoinGecko"

    # ── Fuente 4: Yahoo Finance (forex, índices, commodities)
    pendientes=[k for k in ACTIVOS if k not in precios]
    def fy(key): return key,_yahoo_spot(key)
    if pendientes:
        with ThreadPoolExecutor(max_workers=10) as ex:
            for key,p in ex.map(fy,pendientes):
                if p:
                    precios[key]=p; fuentes[key]="Yahoo"

    _cache_p=precios; _cache_t=time.time(); _cache_fuentes=fuentes
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

# ── PATRONES DE VELAS JAPONESAS ───────────────────────────────────────────────
def detectar_patron_vela(df):
    """Detecta patrones de velas japonesas en las últimas 3 velas. Devuelve (nombre, score_bonus)."""
    if df is None or df.empty or len(df) < 3:
        return "—", 0
    try:
        o = df["Open"].values; h = df["High"].values
        l = df["Low"].values;  c = df["Close"].values
        o1,h1,l1,c1 = o[-3],h[-3],l[-3],c[-3]
        o2,h2,l2,c2 = o[-2],h[-2],l[-2],c[-2]
        o3,h3,l3,c3 = o[-1],h[-1],l[-1],c[-1]
        cuerpo3 = abs(c3-o3); rango3 = h3-l3
        if rango3 < 1e-10: return "—", 0
        somb_sup = h3 - max(o3,c3); somb_inf = min(o3,c3) - l3
        cuerpo2  = abs(c2-o2); cuerpo1 = abs(c1-o1)
        # Engulfing alcista
        if c3>o3 and c2<o2 and c3>=o2 and o3<=c2:
            return "Engulfing Bull", 10
        # Engulfing bajista
        if c3<o3 and c2>o2 and c3<=o2 and o3>=c2:
            return "Engulfing Bear", 10
        # Morning Star
        if c1<o1 and cuerpo2<=cuerpo1*0.35 and c3>o3 and c3>(o1+c1)/2:
            return "Morning Star", 10
        # Evening Star
        if c1>o1 and cuerpo2<=cuerpo1*0.35 and c3<o3 and c3<(o1+c1)/2:
            return "Evening Star", 10
        # Pin Bar alcista
        if somb_inf>=cuerpo3*2.5 and somb_sup<=rango3*0.15:
            return "Pin Bar Bull", 9
        # Pin Bar bajista
        if somb_sup>=cuerpo3*2.5 and somb_inf<=rango3*0.15:
            return "Pin Bar Bear", 9
        # Hammer (después de bajada)
        if somb_inf>=cuerpo3*2 and somb_sup<=cuerpo3*0.5 and cuerpo3/rango3<0.4 and c2<o2:
            return "Hammer", 8
        # Shooting Star (después de subida)
        if somb_sup>=cuerpo3*2 and somb_inf<=cuerpo3*0.5 and cuerpo3/rango3<0.4 and c2>o2:
            return "Shooting Star", 8
        # Marubozu alcista
        if c3>o3 and somb_sup<=cuerpo3*0.05 and somb_inf<=cuerpo3*0.05:
            return "Marubozu Bull", 7
        # Marubozu bajista
        if c3<o3 and somb_sup<=cuerpo3*0.05 and somb_inf<=cuerpo3*0.05:
            return "Marubozu Bear", 7
        # Doji
        if cuerpo3<=rango3*0.08:
            return "Doji", 5
        # Vela fuerte alcista
        if c3>o3 and cuerpo3/rango3>0.65:
            return "Vela Alcista", 3
        # Vela fuerte bajista
        if c3<o3 and cuerpo3/rango3>0.65:
            return "Vela Bajista", 3
    except Exception:
        pass
    return "—", 0

# ── CLASIFICACIÓN DE ESTRATEGIA ───────────────────────────────────────────────
def clasificar_estrategia(dir_, ind, score, breakdown):
    """Devuelve (tipo: Scalping/Intradía/Swing, estilo: Pullback/Breakout/Reversal/Trend/Momentum/Range)."""
    if not ind:
        return "Intradía", "Setup"
    rsi   = ind.get("rsi",50); adx = ind.get("adx",15)
    bb    = ind.get("bb_pos",0.5); mh = ind.get("macd_h",0); mhp = ind.get("macd_hp",0)
    lat   = ind.get("lateral",False); trend_a = breakdown.get("A_tendencia",0)
    # Estilo
    if adx>=25 and ((dir_=="buy" and bb>0.80) or (dir_=="sell" and bb<0.20)):
        estilo = "Breakout"
    elif ((dir_=="buy" and rsi<35 and mh>mhp) or (dir_=="sell" and rsi>65 and mh<mhp)):
        estilo = "Reversal"
    elif ((dir_=="buy" and 35<=rsi<=52 and bb<0.45) or (dir_=="sell" and 48<=rsi<=65 and bb>0.55)):
        estilo = "Pullback"
    elif lat or adx<18:
        estilo = "Range"
    elif adx>=20 and abs(mh)>abs(mhp)*1.15:
        estilo = "Momentum"
    elif trend_a>=20:
        estilo = "Trend"
    else:
        estilo = "Setup"
    # Tipo (velocidad)
    if adx>=30 and not lat and estilo in("Breakout","Momentum"):
        tipo = "Scalping"
    elif trend_a>=20 and adx>=20:
        tipo = "Swing"
    else:
        tipo = "Intradía"
    return tipo, estilo

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
    # rr1 ya no bloquea: el score engloba R:R en su categoría D.
    # vela muy extendida = mercado sobreextendido, mejor esperar retroceso
    if not abierto:         return "BLOQUEADA", "mercado cerrado"
    if vela_ext:            return "ESPERAR",   "vela extendida - esperar retroceso"
    if adx < 13:            return "BLOQUEADA", "ADX muy bajo - sin fuerza direccional"
    if motivo_bloq:         return "BLOQUEADA", motivo_bloq
    # Tardía y conflicto ya no bloquean duramente: solo "esperar"
    if tardia:              return "ESPERAR",   "entrada tardía - aguardar pullback"
    if conflicto:           return "ESPERAR",   "conflicto entre temporalidades"
    if lateral and adx<16:  return "ESPERAR",   "mercado lateral, aguardar tendencia"
    # Decisión por score (la R:R está implícita en la categoría D del score)
    if score >= 80:         return "RECOMENDAR", ""
    if score >= 70:         return "ESPERAR",    "esperando más confirmación técnica"
    if score >= 60:         return "OBSERVAR",   "setup en formación"
    return                         "NO_OPERAR",  "score insuficiente"

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
    _uso = st.session_state.get("uso_mt5_val","Solo sintéticos")
    def _bars(tf):
        # Si MT5 está en "Fuente principal" y conectado, intentar primero
        if _uso == "Fuente principal para todo" and _mt5_status.get("connected"):
            df = get_mt5_bars(key, tf)
            if not df.empty:
                return df
        # En cualquier otro caso (Solo sintéticos / Desactivado / vacío MT5) → Yahoo
        return get_data(sym, tf)
    i_h1  = analizar_df(_bars("60m"))
    _df_m15 = _bars("15m")
    i_m15 = analizar_df(_df_m15)
    i_m5  = analizar_df(_bars("5m"))
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
    _patron,_pscore = detectar_patron_vela(_df_m15)
    _tipo_est,_estilo_est = clasificar_estrategia(dir_,i_m15,score,breakdown)

    return {
        "dir":dir_,"decision":decision,"motivo":motivo_d,
        "score":score,"clase":clase,"color":color,"badge":badge,
        "breakdown":breakdown,"razon":razon,"alertas":alertas,
        "ind":i_m15,"ind_h1":i_h1,"ind_m5":i_m5,
        "trend_1h":trend_h1,"key":key,
        "lateral":i_m15.get("lateral",False),
        "adx":i_m15.get("adx",20),
        "vela_ext":i_m15.get("vela_ext",False),
        "patron":_patron,"patron_score":_pscore,
        "tipo_est":_tipo_est,"estilo_est":_estilo_est,
    }

# ── ESTADO DE ENTRADA ──────────────────────────────────────────────────────────
def calcular_entry_status(precio_live, entry, tp1):
    rango=abs(tp1-entry)
    if rango==0: return "NO ENTRAR","#ff5252"
    avance=abs(precio_live-entry)/rango
    if avance<0.35: return "CERCA DE ENTRADA","#00e676"
    if avance<0.50: return "ESPERAR PULLBACK","#ffd600"
    return "ENTRADA TARDÍA","#ff9800"

# ── DERIV API (datos de sintéticos con autenticación por token) ───────────────
_deriv_cache: dict = {}

def _deriv_ws_call(payload, timeout=14):
    """
    Llama a la API WebSocket de Deriv de forma síncrona.
    Intenta ws.derivws.com primero, luego ws.binaryws.com como fallback.
    App ID configurable vía scanner_keys.json campo 'deriv_app_id'.
    """
    try:
        import websocket as _ws_lib
    except ImportError:
        return None
    _app_id = _KEYS.get("deriv_app_id","1089") or "1089"
    _token  = _KEYS.get("deriv", "")
    # Intentar derivws.com primero, luego binaryws.com como fallback
    for _host in ["ws.derivws.com", "ws.binaryws.com"]:
        _ws_url = f"wss://{_host}/websockets/v3?app_id={_app_id}"
        result = {}
        done   = threading.Event()

        def on_msg(ws, msg):
            try: d = json.loads(msg)
            except: done.set(); ws.close(); return
            if d.get("msg_type") == "authorize":
                if d.get("error"):
                    result["error"] = d["error"].get("message","auth error")
                    done.set(); ws.close()
                else:
                    ws.send(json.dumps(payload))
                return
            result["data"] = d; done.set(); ws.close()

        def on_err(ws, err):
            result["error"] = str(err); done.set()

        def on_open(ws):
            if _token:
                ws.send(json.dumps({"authorize": _token}))
            else:
                ws.send(json.dumps(payload))

        try:
            ws = _ws_lib.WebSocketApp(_ws_url, on_message=on_msg,
                                       on_open=on_open, on_error=on_err)
            t = threading.Thread(target=ws.run_forever, daemon=True)
            t.start()
            done.wait(timeout=timeout)
        except Exception as e:
            result["error"] = str(e)

        if result.get("data"):
            return result["data"]
        # Si hubo error de auth, no reintentar con el otro host
        if "auth error" in str(result.get("error","")):
            return None
    return None

def get_deriv_bars(key, timeframe_str, n=200):
    """Velas OHLCV desde la API pública de Deriv para índices sintéticos."""
    sym = DERIV_SYMBOLS.get(key)
    if not sym:
        return pd.DataFrame()
    TF = {"1m": 60, "5m": 300, "15m": 900, "60m": 3600}
    gran = TF.get(timeframe_str, 900)
    try:
        data = _deriv_ws_call({
            "ticks_history": sym, "count": n,
            "style": "candles", "granularity": gran, "subscribe": 0
        })
        if not data or data.get("error") or "candles" not in data:
            return pd.DataFrame()
        rows = [{"Open": float(c["open"]), "High": float(c["high"]),
                 "Low":  float(c["low"]),  "Close": float(c["close"]),
                 "Volume": 100, "time": int(c["epoch"])} for c in data["candles"]]
        if len(rows) < 30:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime(df["time"], unit="s")
        return df.drop("time", axis=1)
    except Exception:
        return pd.DataFrame()

def get_deriv_price(key):
    """Precio spot actual desde Deriv API."""
    sym = DERIV_SYMBOLS.get(key)
    if not sym:
        return None
    try:
        data = _deriv_ws_call({"ticks": sym, "subscribe": 0}, timeout=6)
        if data and "tick" in data:
            return float(data["tick"].get("quote", 0)) or None
    except Exception:
        pass
    return None

def _sint_get_bars(key, tf, n=200):
    """Obtiene velas para sintético: MT5 primero, luego Deriv API."""
    df = pd.DataFrame()
    if _mt5_status.get("connected"):
        df = get_mt5_bars(key, tf, n)
    if df.empty:
        df = get_deriv_bars(key, tf, n)
    return df

def _save_deriv_debug(symbol_key, info):
    try:
        if "deriv_debug" not in st.session_state:
            st.session_state["deriv_debug"] = {}
        st.session_state["deriv_debug"][symbol_key] = info
    except: pass

def _sint_get_price(key):
    """Precio live para sintético: Deriv ticks primero, luego Deriv candles, luego MT5."""
    p = deriv_get_live_price(key)
    if p: return p
    if _mt5_status.get("connected"):
        p = get_mt5_price(key)
    return p

# ── DERIV: PIPELINE DE TICKS ──────────────────────────────────────────────────

def get_deriv_config():
    """App ID y token desde _KEYS o session_state."""
    app_id = (st.session_state.get("deriv_app_id_inp") or
              _KEYS.get("deriv_app_id") or "1089") or "1089"
    return {"app_id": str(app_id), "token": _KEYS.get("deriv","")}

def deriv_get_ticks(symbol_key, count=2000):
    """Descarga ticks históricos desde Deriv WS. Devuelve DataFrame con epoch/price."""
    deriv_sym = DERIV_SYMBOLS.get(symbol_key)
    if not deriv_sym:
        return pd.DataFrame()
    _dbg = {"deriv_symbol": deriv_sym, "ticks": 0, "last_price": None,
            "last_update": datetime.now().isoformat(), "error": None}
    try:
        data = _deriv_ws_call({
            "ticks_history": deriv_sym,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "start": 1,
            "style": "ticks"
        }, timeout=16)
        if not data:
            _dbg["error"] = "sin respuesta WebSocket"
            _save_deriv_debug(symbol_key, _dbg)
            return pd.DataFrame()
        if data.get("error"):
            _dbg["error"] = str(data["error"].get("message", data["error"]))[:80]
            _save_deriv_debug(symbol_key, _dbg)
            return pd.DataFrame()
        hist   = data.get("history", {})
        epochs = hist.get("times", [])
        prices = hist.get("prices", [])
        if not epochs or len(epochs) < 10:
            _dbg["error"] = f"pocos ticks: {len(epochs)}"
            _save_deriv_debug(symbol_key, _dbg)
            return pd.DataFrame()
        df = pd.DataFrame({"epoch": [int(e) for e in epochs],
                           "price": [float(p) for p in prices]})
        df["timestamp"] = pd.to_datetime(df["epoch"], unit="s")
        _dbg["ticks"]      = len(df)
        _dbg["last_price"] = float(prices[-1])
        _save_deriv_debug(symbol_key, _dbg)
        return df
    except Exception as e:
        _dbg["error"] = str(e)[:80]
        _save_deriv_debug(symbol_key, _dbg)
        return pd.DataFrame()

def deriv_get_live_price(symbol_key):
    """Último precio disponible usando ticks Deriv."""
    deriv_sym = DERIV_SYMBOLS.get(symbol_key)
    if not deriv_sym:
        return None
    try:
        data = _deriv_ws_call({
            "ticks_history": deriv_sym,
            "adjust_start_time": 1,
            "count": 5,
            "end": "latest",
            "start": 1,
            "style": "ticks"
        }, timeout=9)
        if data and "history" in data:
            prices = data["history"].get("prices", [])
            if prices:
                return float(prices[-1])
    except: pass
    return get_deriv_price(symbol_key)

def deriv_ticks_to_candles(df_ticks, timeframe_seconds=60):
    """Convierte DataFrame de ticks a OHLCV. Añade tick_count, range, body, velocidad."""
    if df_ticks is None or df_ticks.empty or len(df_ticks) < 10:
        return pd.DataFrame()
    try:
        df = df_ticks.copy().sort_values("epoch")
        df["ts"] = pd.to_datetime(df["epoch"], unit="s")
        df = df.set_index("ts")
        rule = f"{timeframe_seconds}s"
        agg = df["price"].resample(rule).ohlc().dropna()
        if len(agg) < 8:
            return pd.DataFrame()
        agg.columns = ["Open","High","Low","Close"]
        cnt = df["price"].resample(rule).count().reindex(agg.index).fillna(1)
        agg["Volume"]        = cnt
        agg["tick_count"]    = cnt
        agg["range"]         = agg["High"] - agg["Low"]
        agg["body"]          = (agg["Close"] - agg["Open"]).abs()
        agg["wick_top"]      = agg["High"] - agg[["Open","Close"]].max(axis=1)
        agg["wick_bottom"]   = agg[["Open","Close"]].min(axis=1) - agg["Low"]
        agg["tick_velocity"] = agg["tick_count"] / max(timeframe_seconds, 1)
        return agg
    except Exception:
        return pd.DataFrame()

def get_synthetic_data(symbol_key):
    """Pipeline completo: ticks → velas en 5 temporalidades. Devuelve dict estructurado."""
    out = {
        "ok": False, "symbol_key": symbol_key,
        "deriv_symbol": DERIV_SYMBOLS.get(symbol_key,""),
        "price": None, "ticks": pd.DataFrame(),
        "candles_2s": pd.DataFrame(), "candles_5s": pd.DataFrame(),
        "candles_15s": pd.DataFrame(), "candles_1m": pd.DataFrame(),
        "candles_2m": pd.DataFrame(), "source": "Deriv WS", "error": None,
    }
    try:
        # STEP y JUMP son índices lentos — necesitan más ticks para tener velas suficientes
        _count = 5000 if (symbol_key == "STEP" or symbol_key.startswith("JUMP")) else 2000
        df_ticks = deriv_get_ticks(symbol_key, count=_count)
        if df_ticks.empty:
            out["error"] = "Sin ticks de Deriv"
            return out
        out["ticks"] = df_ticks
        out["price"] = float(df_ticks["price"].iloc[-1])
        out["candles_2s"]  = deriv_ticks_to_candles(df_ticks, 2)
        out["candles_5s"]  = deriv_ticks_to_candles(df_ticks, 5)
        out["candles_15s"] = deriv_ticks_to_candles(df_ticks, 15)
        out["candles_1m"]  = deriv_ticks_to_candles(df_ticks, 60)
        out["candles_2m"]  = deriv_ticks_to_candles(df_ticks, 120)
        # Actualizar debug con conteo de velas
        _dbg = st.session_state.get("deriv_debug",{}).get(symbol_key,{})
        _dbg.update({
            "candles_2s":  len(out["candles_2s"]),
            "candles_5s":  len(out["candles_5s"]),
            "candles_15s": len(out["candles_15s"]),
            "candles_1m":  len(out["candles_1m"]),
            "candles_2m":  len(out["candles_2m"]),
        })
        _save_deriv_debug(symbol_key, _dbg)
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)[:80]
    return out

# ── INDICADORES PARA SINTÉTICOS ───────────────────────────────────────────────

def calc_synthetic_indicators(candles):
    """Indicadores técnicos sobre velas de sintéticos (sin librería ta)."""
    if candles is None or candles.empty or len(candles) < 12:
        return {}
    try:
        c  = candles["Close"].astype(float)
        h  = candles["High"].astype(float)
        lo = candles["Low"].astype(float)
        n  = min(len(c)-1, 14)
        # EMA
        ema9  = c.ewm(span=9,  adjust=False).mean()
        ema21 = c.ewm(span=21, adjust=False).mean()
        # RSI
        delta = c.diff()
        gain  = delta.clip(lower=0).rolling(n).mean()
        loss  = (-delta.clip(upper=0)).rolling(n).mean()
        rs    = gain / loss.replace(0, 1e-10)
        rsi   = 100 - 100/(1+rs)
        # ATR
        tr = pd.concat([h - lo,
                        (h - c.shift()).abs(),
                        (lo - c.shift()).abs()], axis=1).max(axis=1)
        atr_s = tr.rolling(min(5,  n)).mean()
        atr_m = tr.rolling(min(14, n)).mean()
        # Bollinger
        bm = c.rolling(min(20, len(c)-1)).mean()
        bs = c.rolling(min(20, len(c)-1)).std().fillna(0)
        bu = bm + bs*2; bl_ = bm - bs*2
        bw = (bu - bl_) / bm.replace(0, 1e-10)
        # Aceleración
        pdiff = c.diff()
        accel = pdiff.diff()
        # Tick velocity
        tv    = candles.get("tick_velocity", pd.Series([0]*len(c), index=c.index))
        tv_avg = tv.rolling(min(10, len(tv)-1)).mean()
        px     = float(c.iloc[-1])
        bpos   = float(np.clip((px - float(bl_.iloc[-1])) /
                               (float(bu.iloc[-1]) - float(bl_.iloc[-1]) + 1e-10), 0, 1))
        def _v(s): return float(s.iloc[-1]) if not pd.isna(s.iloc[-1]) else 0.0
        return {
            "price": px, "ema9": _v(ema9), "ema21": _v(ema21),
            "rsi14": _v(rsi) or 50.0,
            "atr_short": _v(atr_s), "atr_mid": _v(atr_m),
            "bb_upper": _v(bu), "bb_mid": _v(bm), "bb_lower": _v(bl_),
            "bb_width": _v(bw), "bb_pos": bpos,
            "acceleration": _v(accel),
            "accel_prev":   float(accel.iloc[-2]) if len(accel)>1 and not pd.isna(accel.iloc[-2]) else 0.0,
            "tick_velocity": _v(tv), "tick_velocity_avg": _v(tv_avg),
            "ema_cross": "bull" if _v(ema9) > _v(ema21) else "bear",
            "last_range": float(h.iloc[-1] - lo.iloc[-1]),
            "price_diff": _v(pdiff),
        }
    except Exception:
        return {}

# ── MOTORES DE SEÑAL POR TIPO DE SINTÉTICO ────────────────────────────────────

def score_synthetic(setup):
    """Score 0-100 en 5 categorías de 20 pts."""
    s  = 20 if setup.get("ema_aligned") else (10 if setup.get("ema_near") else 0)
    s += min(int(setup.get("accel_score",  0)), 20)
    s += min(int(setup.get("atr_score",    0)), 20)
    s += min(int(setup.get("patron_score", 0)), 20)
    s += min(int(setup.get("entry_score",  0)), 20)
    return min(s, 100)

def _calc_levels_sint(entry, direction, atr, fallback=0.001):
    if not atr or atr <= 0: atr = fallback
    m = 1 if direction=="buy" else -1
    return {"sl": entry - m*atr*1.2, "tp1": entry + m*atr*0.8,
            "tp2": entry + m*atr*2.0, "tp3": entry + m*atr*3.5,
            "tp4": entry + m*atr*5.5}

def _is_late_sint(price, entry, tp1):
    rng = abs(tp1 - entry)
    if rng == 0: return False
    return abs(price - entry) / rng > 0.35

def motor_volatility(key, data):
    """V10/V25/V50/V75/V100: EMA cross + confirmación momentum."""
    ind = calc_synthetic_indicators(data.get("candles_1m"))
    if not ind: return None
    price = data["price"]; ema9=ind["ema9"]; ema21=ind["ema21"]
    rsi=ind["rsi14"]; atr_s=ind["atr_short"]; atr_m=ind["atr_mid"] or atr_s
    bpos=ind["bb_pos"]; accel=ind["acceleration"]; ema_c=ind["ema_cross"]
    tv=ind.get("tick_velocity",0); tavg=ind.get("tick_velocity_avg",0)
    pdiff=ind.get("price_diff",0)

    if ema_c=="bull" and rsi<72: dir_="buy"
    elif ema_c=="bear" and rsi>28: dir_="sell"
    else: return None

    near_ema21 = abs(price - ema21) < atr_m*0.8 if atr_m>0 else True
    bb_ok      = (bpos<0.45 and dir_=="buy") or (bpos>0.55 and dir_=="sell")
    accel_dir  = (dir_=="buy" and pdiff>0) or (dir_=="sell" and pdiff<0)
    accel_ok   = accel_dir and ((dir_=="buy" and accel>=0) or (dir_=="sell" and accel<=0))
    atr_exp    = atr_s > atr_m*0.6 if atr_m>0 else True
    # late: precio demasiado lejos de EMA21 (ya se movió mucho)
    late       = abs(price - ema21) > atr_m*2.5 if atr_m>0 else False
    vela_ext   = ind.get("last_range",0) > atr_m*2.5 if atr_m>0 else False
    levels     = _calc_levels_sint(price, dir_, atr_m)

    patron = "Pullback EMA21" if near_ema21 else ("Rechazo BB" if bb_ok else
             ("Ruptura EMA9" if ((rsi<55 and dir_=="buy") or (rsi>45 and dir_=="sell")) else "Trend EMA"))
    setup = {
        "ema_aligned": True,
        "accel_score":  20 if accel_ok else (12 if accel_dir else 6),
        "atr_score":    20 if atr_exp else 12,
        "patron_score": 20 if (near_ema21 or bb_ok) else 12,
        "entry_score":  20 if (not late and not vela_ext) else (10 if not vela_ext else 2),
    }
    return {"dir":dir_, "score":score_synthetic(setup), "patron":patron, "atr":atr_m,
            "levels":levels, "late":late, "ind":ind,
            "tipo_est": "Scalping" if atr_s>atr_m else "Intradía",
            "estilo_est": "Pullback" if near_ema21 else ("Breakout" if atr_exp else "Trend"),
            "ticks_s": round(tv,2)}

def motor_boom(key, data):
    """BOOM: siempre LONG — detecta momento alcista en índice boom."""
    ind = calc_synthetic_indicators(data.get("candles_5s"))
    if not ind: return None
    price=data["price"]; accel=ind["acceleration"]; accel_p=ind["accel_prev"]
    atr_s=ind["atr_short"]; atr_m=ind["atr_mid"] or atr_s
    tv=ind.get("tick_velocity",0); tavg=ind.get("tick_velocity_avg",0)
    rsi=ind["rsi14"]; ema_c=ind["ema_cross"]
    dir_="buy"
    accel_up  = accel > 0
    accel_inc = accel_up and (accel_p <= 0 or accel > accel_p*0.8)
    vel_surge = tv > tavg*1.02 if tavg>0 else True
    atr_exp   = atr_s > atr_m*0.6 if atr_m>0 else True
    # late: RSI sobrecomprado (ya subió mucho)
    late      = rsi > 80
    ema_near  = abs(ind["ema9"] - ind["ema21"]) < atr_s*0.5 if atr_s>0 else True
    levels    = _calc_levels_sint(price, "buy", atr_m)
    patron    = "Boom Surge" if (vel_surge and accel_inc) else ("Boom Setup" if accel_up else "Boom Base")
    setup = {
        "ema_aligned": ema_c=="bull",
        "ema_near":    ema_near,
        "accel_score":  20 if accel_inc else (14 if accel_up else 8),
        "atr_score":    20 if atr_exp else 12,
        "patron_score": 20 if (vel_surge and accel_up) else 14,
        "entry_score":  20 if (not late and rsi<78) else (8 if rsi<78 else 2),
    }
    return {"dir":dir_, "score":score_synthetic(setup), "patron":patron, "atr":atr_m,
            "levels":levels, "late":late, "ind":ind,
            "tipo_est":"Scalping", "estilo_est":"Momentum", "ticks_s":round(tv,2)}

def motor_crash(key, data):
    """CRASH: siempre SELL — detecta momento bajista en índice crash."""
    ind = calc_synthetic_indicators(data.get("candles_5s"))
    if not ind: return None
    price=data["price"]; accel=ind["acceleration"]; accel_p=ind["accel_prev"]
    atr_s=ind["atr_short"]; atr_m=ind["atr_mid"] or atr_s
    tv=ind.get("tick_velocity",0); tavg=ind.get("tick_velocity_avg",0)
    rsi=ind["rsi14"]; ema_c=ind["ema_cross"]
    dir_="sell"
    accel_dn  = accel < 0
    accel_inc = accel_dn and (accel_p >= 0 or accel < accel_p*0.8)
    vel_surge = tv > tavg*1.02 if tavg>0 else True
    atr_exp   = atr_s > atr_m*0.6 if atr_m>0 else True
    # late: RSI sobrevendido (ya bajó mucho)
    late      = rsi < 20
    ema_near  = abs(ind["ema9"] - ind["ema21"]) < atr_s*0.5 if atr_s>0 else True
    levels    = _calc_levels_sint(price, "sell", atr_m)
    patron    = "Crash Drop" if (vel_surge and accel_inc) else ("Crash Setup" if accel_dn else "Crash Base")
    setup = {
        "ema_aligned": ema_c=="bear",
        "ema_near":    ema_near,
        "accel_score":  20 if accel_inc else (14 if accel_dn else 8),
        "atr_score":    20 if atr_exp else 12,
        "patron_score": 20 if (vel_surge and accel_dn) else 14,
        "entry_score":  20 if (not late and rsi>22) else (8 if rsi>22 else 2),
    }
    return {"dir":dir_, "score":score_synthetic(setup), "patron":patron, "atr":atr_m,
            "levels":levels, "late":late, "ind":ind,
            "tipo_est":"Scalping", "estilo_est":"Momentum", "ticks_s":round(tv,2)}

def motor_step(key, data):
    """Step Index: sigue la dirección EMA + posición Bollinger."""
    ind = calc_synthetic_indicators(data.get("candles_1m"))
    if not ind: ind = calc_synthetic_indicators(data.get("candles_15s"))
    if not ind: return None
    price=data["price"]; atr_m=ind["atr_mid"] or ind["atr_short"]; atr_s=ind["atr_short"]
    rsi=ind["rsi14"]; bpos=ind["bb_pos"]; accel=ind["acceleration"]
    ema_c=ind["ema_cross"]
    dir_="buy" if ema_c=="bull" else "sell"
    ruptura = (dir_=="buy" and bpos>0.65) or (dir_=="sell" and bpos<0.35)
    rsi_ok  = (dir_=="buy" and 30<rsi<75) or (dir_=="sell" and 25<rsi<70)
    # late: precio en extremo de BB (ya rompió demasiado)
    late    = (dir_=="buy" and bpos>0.92) or (dir_=="sell" and bpos<0.08)
    levels  = _calc_levels_sint(price, dir_, atr_m)
    patron  = "Step Ruptura" if ruptura else "Step Trend"
    setup = {
        "ema_aligned": True,
        "accel_score":  18 if abs(accel)>0 else 10,
        "atr_score":    18 if atr_m>0 else 5,
        "patron_score": 20 if ruptura else 12,
        "entry_score":  20 if (not late and rsi_ok) else (10 if rsi_ok else 4),
    }
    sc = score_synthetic(setup)
    return {"dir":dir_, "score":sc, "patron":patron, "atr":atr_m,
            "levels":levels, "late":late, "ind":ind,
            "tipo_est":"Intradía", "estilo_est":"Breakout" if ruptura else "Trend",
            "ticks_s":round(ind.get("tick_velocity",0),2)}

def motor_jump(key, data):
    """Jump 10/25/50/75/100: detecta jump reciente en cualquier dirección."""
    ind = calc_synthetic_indicators(data.get("candles_5s"))
    if not ind: ind = calc_synthetic_indicators(data.get("candles_15s"))
    if not ind: return None
    price=data["price"]; accel=ind["acceleration"]
    atr_s=ind["atr_short"]; atr_m=ind["atr_mid"] or atr_s
    tv=ind.get("tick_velocity",0); tavg=ind.get("tick_velocity_avg",0)
    dir_="buy" if accel>=0 else "sell"
    jump_det = abs(accel) > atr_s*0.25 if atr_s>0 else False
    vel_ok   = tv>tavg*0.85 if tavg>0 else True
    ticks_df = data.get("ticks", pd.DataFrame())
    jump_rec = False
    if not ticks_df.empty and len(ticks_df)>=10:
        last5 = ticks_df.tail(5)["price"]
        jump_rec = (last5.max()-last5.min()) > atr_s*0.4 if atr_s>0 else False
    levels = _calc_levels_sint(price, dir_, atr_m)
    late   = not jump_rec
    patron = "Jump Activo" if jump_rec else "Jump Tardío"
    ema_near = abs(ind["ema9"] - ind["ema21"]) < atr_s*0.5 if atr_s>0 else True
    setup = {
        "ema_aligned": ind["ema_cross"]==("bull" if dir_=="buy" else "bear"),
        "ema_near":    ema_near,
        "accel_score":  20 if jump_det else 10,
        "atr_score":    18 if atr_s>0 else 5,
        "patron_score": 20 if (jump_det and vel_ok) else 12,
        "entry_score":  20 if jump_rec else 6,
    }
    sc = score_synthetic(setup)
    if not jump_rec: sc = min(sc, 62)
    return {"dir":dir_, "score":sc, "patron":patron, "atr":atr_m,
            "levels":levels, "late":late, "ind":ind,
            "tipo_est":"Scalping", "estilo_est":"Momentum",
            "ticks_s":round(tv,2),
            "razon":"Jump reciente detectado" if jump_rec else "Jump tardío - esperar próximo"}

# ── SEÑAL WELTRADE (MT5) ──────────────────────────────────────────────────────
def señal_weltrade(key):
    """Señal para índices sintéticos de Weltrade usando MT5 como fuente."""
    nombre, tipo = WELTRADE_SINTETICOS.get(key, (key, "volatility"))
    _base = {
        "key": key, "sym": key, "nombre": nombre, "cat": "WELTRADE",
        "is_synthetic": True, "is_weltrade": True, "fuente": "MT5 Weltrade",
        "adx": 0, "ind": {}, "ind_m5": None, "trend_1h": "neutral",
        "alertas": [], "breakdown": {}, "ia_result": {},
        "lateral": False, "vela_ext": False,
    }
    if not _mt5_status.get("connected"):
        _base.update({"dir":None,"decision":"BLOQUEADA","motivo":"MT5 desconectado",
            "score":0,"clase":"NO OPERAR","color":"#555","badge":"b-wait",
            "price":None,"entry":0,"sl":0,"tp1":0,"tp2":0,"tp3":0,"tp4":0,
            "atr":0,"ticks_s":0,"estado_data":"SIN MT5","razon":"MT5 desconectado",
            "patron":"—","tipo_est":"—","estilo_est":"—"})
        return _base
    try:
        import MetaTrader5 as mt5
        mt5.symbol_select(nombre, True)
        # Obtener velas M5 (análisis principal) y M15 (tendencia)
        r5  = mt5.copy_rates_from_pos(nombre, mt5.TIMEFRAME_M5,  0, 200)
        r15 = mt5.copy_rates_from_pos(nombre, mt5.TIMEFRAME_M15, 0, 200)
        if r5 is None or len(r5) < 30:
            _base.update({"dir":None,"decision":"BLOQUEADA","motivo":"Sin histórico M5",
                "score":0,"clase":"NO OPERAR","color":"#555","badge":"b-wait",
                "price":None,"entry":0,"sl":0,"tp1":0,"tp2":0,"tp3":0,"tp4":0,
                "atr":0,"ticks_s":0,"estado_data":"SIN DATOS","razon":"Sin datos MT5",
                "patron":"—","tipo_est":"—","estilo_est":"—"})
            return _base
        df5  = _rates_to_df(r5)
        df15 = _rates_to_df(r15) if r15 is not None and len(r15)>=30 else df5
        i5  = analizar_df(df5)
        i15 = analizar_df(df15)
        if not i5:
            _base.update({"dir":None,"decision":"BLOQUEADA","motivo":"Sin indicadores",
                "score":0,"clase":"NO OPERAR","color":"#555","badge":"b-wait",
                "price":None,"entry":0,"sl":0,"tp1":0,"tp2":0,"tp3":0,"tp4":0,
                "atr":0,"ticks_s":0,"estado_data":"SIN DATOS","razon":"Sin indicadores",
                "patron":"—","tipo_est":"—","estilo_est":"—"})
            return _base
        price = i5["price"]; atr = i5["atr"]; adx = i5.get("adx",20)

        # Dirección según tipo de índice
        if tipo == "gain":
            dir_ = "buy"   # GainX siempre alcista (como Boom)
        elif tipo == "pain":
            dir_ = "sell"  # PainX siempre bajista (como Crash)
        else:
            bs = i5["buy_score"]; ss = i5["sell_score"]
            if bs > ss: dir_ = "buy"
            elif ss > bs: dir_ = "sell"
            else: dir_ = "buy" if i15.get("buy_score",0) >= i15.get("sell_score",0) else "sell"

        sc, breakdown = calcular_score_100(dir_, i15, i5)
        # Bonificación por tipo: gain/pain siempre tienen bias claro → +10 pts
        if tipo in ("gain","pain"): sc = min(sc + 10, 100)

        patron, bonus = detectar_patron_vela(df5)
        sc = min(sc + bonus, 100)
        rr1 = 1.5 if atr > 0 else 0
        tardia = False; conflicto = False
        lateral = i5.get("lateral", False); vela_ext = i5.get("vela_ext", False)
        decision, motivo = final_decision(sc, rr1, tardia, conflicto, lateral, vela_ext, adx, False)
        clase, color, badge = clasificar(sc)
        m = 1 if dir_=="buy" else -1
        levels = {"sl": price - m*atr*1.2, "tp1": price + m*atr*0.8,
                  "tp2": price + m*atr*2.0, "tp3": price + m*atr*3.5, "tp4": price + m*atr*5.5}
        tipo_est = "Scalping" if atr/price < 0.002 else "Intradía"
        estilo_m = {"gain":"Momentum","pain":"Momentum","trend":"Trend","break":"Breakout",
                    "flip":"Reversal","switch":"Swing","volatility":"Pullback"}.get(tipo,"Trend")
        _base.update({
            "dir":dir_, "decision":decision, "motivo":motivo,
            "score":sc, "clase":clase, "color":color, "badge":badge,
            "razon":f"{patron} · {sc}/100", "patron":patron,
            "tipo_est":tipo_est, "estilo_est":estilo_m,
            "price":price, "entry":price,
            "sl":levels["sl"], "tp1":levels["tp1"], "tp2":levels["tp2"],
            "tp3":levels["tp3"], "tp4":levels["tp4"],
            "atr":atr, "ticks_s":0, "ind":i5, "adx":adx,
            "estado_data":"OK", "breakdown":breakdown, "trend_1h":
                "bull" if i15.get("buy_score",0)>i15.get("sell_score",0) else "bear",
        })
    except Exception as e:
        _base.update({"dir":None,"decision":"BLOQUEADA","motivo":str(e)[:60],
            "score":0,"clase":"NO OPERAR","color":"#555","badge":"b-wait",
            "price":None,"entry":0,"sl":0,"tp1":0,"tp2":0,"tp3":0,"tp4":0,
            "atr":0,"ticks_s":0,"estado_data":"ERROR","razon":str(e)[:60],
            "patron":"—","tipo_est":"—","estilo_est":"—"})
    return _base

# ── ANÁLISIS SINTÉTICOS — motor propio basado en ticks Deriv ─────────────────
def señal_sintetico(key):
    """Señal para índices sintéticos usando Deriv WS como fuente principal."""
    nombre = SINTETICOS.get(key, key)
    fuente = "Deriv WS"
    _base  = {
        "key": key, "sym": key, "nombre": nombre,
        "cat": "SINTETICOS", "is_synthetic": True, "fuente": fuente,
        "adx": 0, "ind": {}, "ind_m5": None, "trend_1h": "neutral",
        "alertas": [], "breakdown": {}, "ia_result": {},
        "lateral": False, "vela_ext": False,
    }

    # ── Paso 1: datos desde Deriv (ticks → velas) ────────────────────────────
    data = get_synthetic_data(key)

    if not data["ok"]:
        err = data.get("error","sin datos Deriv")
        _base.update({
            "dir":None, "decision":"BLOQUEADA", "motivo":err,
            "score":0, "clase":"NO OPERAR", "color":"#555", "badge":"b-wait",
            "razon":f"Sin datos Deriv WS: {err}",
            "patron":"—", "tipo_est":"—", "estilo_est":"—",
            "price":None, "entry":0, "sl":0, "tp1":0, "tp2":0, "tp3":0, "tp4":0,
            "atr":0, "ticks_s":0, "estado_data":"SIN DATOS",
        })
        return _base

    price = data["price"]

    # ── Paso 2: elegir motor según tipo ──────────────────────────────────────
    motor_result = None
    try:
        if   key.startswith("BOOM"):  motor_result = motor_boom(key, data)
        elif key.startswith("CRASH"): motor_result = motor_crash(key, data)
        elif key == "STEP":           motor_result = motor_step(key, data)
        elif key.startswith("JUMP"):  motor_result = motor_jump(key, data)
        else:                         motor_result = motor_volatility(key, data)
    except Exception as _me:
        motor_result = None

    # ── Fallback: analizar_df sobre velas 1m si motor falla ──────────────────
    if motor_result is None:
        _df_fb = data.get("candles_1m", pd.DataFrame())
        _ind   = analizar_df(_df_fb) if not _df_fb.empty else {}
        if _ind:
            bs, ss = _ind.get("buy_score",0), _ind.get("sell_score",0)
            dir_fb = "buy" if bs>ss else ("sell" if ss>bs else None)
            sc_fb  = 0
            if dir_fb:
                sc_fb, _bd = calcular_score_100(dir_fb, None, _ind, None)
            _base.update({
                "dir":dir_fb, "decision":"NO_OPERAR" if dir_fb else "BLOQUEADA",
                "motivo":"motor sin señal clara", "score":sc_fb,
                "clase":"NO OPERAR","color":"#555","badge":"b-wait",
                "razon":"Analizando estructura","patron":"—",
                "tipo_est":"—","estilo_est":"—",
                "price":price,"entry":price,"sl":0,"tp1":0,"tp2":0,"tp3":0,"tp4":0,
                "atr":_ind.get("atr",0),"ticks_s":0,"ind":_ind,"estado_data":"OK",
            })
        else:
            _base.update({
                "dir":None,"decision":"BLOQUEADA","motivo":"sin indicadores",
                "score":0,"clase":"NO OPERAR","color":"#555","badge":"b-wait",
                "razon":"Sin velas suficientes","patron":"—",
                "tipo_est":"—","estilo_est":"—",
                "price":price,"entry":price,"sl":0,"tp1":0,"tp2":0,"tp3":0,"tp4":0,
                "atr":0,"ticks_s":0,"estado_data":"SIN DATOS",
            })
        return _base

    # ── Paso 3: construir resultado completo ─────────────────────────────────
    dir_       = motor_result["dir"]
    score      = motor_result["score"]
    levels     = motor_result["levels"]
    atr        = motor_result.get("atr", 0)
    patron     = motor_result.get("patron","—")
    late       = motor_result.get("late", False)
    ind        = motor_result.get("ind", {})
    tipo_est   = motor_result.get("tipo_est","Intradía")
    estilo_est = motor_result.get("estilo_est","Setup")
    ticks_s    = motor_result.get("ticks_s", 0)
    razon_m    = motor_result.get("razon","")

    # Decisión — sintéticos tienen umbrales propios (mercados 24/7, alta volatilidad)
    if score>=65 and not late:
        decision="RECOMENDAR"; motivo=razon_m or ""
    elif score>=52 or late:
        decision="ESPERAR"
        motivo="Entrada tardía - aguardar pullback" if late else "Esperando confirmación"
    elif score>=40:
        decision="OBSERVAR"; motivo="Setup en formación"
    else:
        decision="NO_OPERAR"; motivo="Score insuficiente"

    clase,color,badge = clasificar(score)
    razon = razon_m or f"{patron} · {score}/100"
    # ADX aproximado desde ATR relativo
    adx_est = int(min(atr/price*100*25, 99)) if price and atr else 0

    _base.update({
        "dir":dir_, "decision":decision, "motivo":motivo,
        "score":score, "clase":clase, "color":color, "badge":badge,
        "razon":razon, "patron":patron, "tipo_est":tipo_est, "estilo_est":estilo_est,
        "price":price, "entry":price,
        "sl":   levels.get("sl",0),  "tp1":levels.get("tp1",0),
        "tp2":  levels.get("tp2",0), "tp3":levels.get("tp3",0),
        "tp4":  levels.get("tp4",0),
        "atr":atr, "ticks_s":ticks_s, "ind":ind, "adx":adx_est,
        "estado_data":"OK",
    })
    return _base

# ── VALIDACIÓN MULTI-IA ────────────────────────────────────────────────────────
def _ia_prompt(nombre,dir_,ind,trend_1h,score):
    return (f"Trader experto. Solo JSON válido sin texto extra.\n"
            f"Activo:{nombre} Dir:{'COMPRA' if dir_=='buy' else 'VENTA'} Score:{score}/100\n"
            f"RSI:{ind['rsi']:.1f} MACD:{'▲' if ind['macd_h']>0 else '▼'} "
            f"ADX:{ind.get('adx',0):.0f} BB:{ind['bb_pos']:.2f} "
            f"EMA20:{'+' if ind['ema20']>ind['ema50'] else '-'}EMA50 "
            f"Precio:{'+' if ind['price']>ind['ema200'] else '-'}EMA200 "
            f"Tend1H:{trend_1h}\n"
            f'Responde SOLO con este JSON: {{"decision":"CONFIRMAR o RECHAZAR",'
            f'"confianza":0-100,"razon":"max 12 palabras","riesgo":"riesgo principal"}}')

def _ia_parse(text):
    try:
        m=re.search(r'\{[^{}]+\}',str(text))
        if m:
            d=json.loads(m.group())
            if "decision" in d: return d
    except: pass
    return None

def _call_ollama_ia(prompt):
    try:
        r=requests.post(OLLAMA_URL,
            json={"model":MODELO_IA,"messages":[{"role":"user","content":prompt}],"stream":False},
            timeout=45)
        return _ia_parse(r.json()["message"]["content"])
    except: return None

def _call_claude_ia(prompt,api_key):
    try:
        r=requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":api_key,"anthropic-version":"2023-06-01",
                     "content-type":"application/json"},
            json={"model":"claude-haiku-4-5-20251001","max_tokens":200,
                  "messages":[{"role":"user","content":prompt}]},
            timeout=20)
        return _ia_parse(r.json()["content"][0]["text"])
    except: return None

def _call_openai_ia(prompt,api_key):
    try:
        r=requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
            json={"model":"gpt-4o-mini","max_tokens":200,
                  "messages":[{"role":"user","content":prompt}]},
            timeout=20)
        return _ia_parse(r.json()["choices"][0]["message"]["content"])
    except: return None

def _call_groq_ia(prompt,api_key):
    try:
        r=requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
            json={"model":"llama-3.3-70b-versatile","max_tokens":300,"temperature":0.1,
                  "messages":[{"role":"user","content":prompt}]},
            timeout=20)
        return _ia_parse(r.json()["choices"][0]["message"]["content"])
    except: return None

def _call_mistral_ia(prompt,api_key):
    try:
        r=requests.post("https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
            json={"model":"mistral-small-latest","max_tokens":300,"temperature":0.1,
                  "messages":[{"role":"user","content":prompt}]},
            timeout=20)
        return _ia_parse(r.json()["choices"][0]["message"]["content"])
    except: return None

def _call_gemini_ia(prompt,api_key):
    try:
        r=requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
            json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"maxOutputTokens":300,"temperature":0.1}},
            timeout=20)
        return _ia_parse(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    except: return None

def validar_multi_ia(nombre,dir_,ind,trend_1h,score,apis):
    """Lanza todas las IAs activas en paralelo y devuelve consenso por mayoría."""
    prompt=_ia_prompt(nombre,dir_,ind,trend_1h,score)
    tareas={}
    if apis.get("ollama"):  tareas["Ollama"] =(lambda p=prompt: _call_ollama_ia(p))
    if apis.get("claude"):  tareas["Claude"] =(lambda p=prompt,k=apis["claude"]: _call_claude_ia(p,k))
    if apis.get("openai"):  tareas["OpenAI"] =(lambda p=prompt,k=apis["openai"]: _call_openai_ia(p,k))
    if apis.get("groq"):    tareas["Groq"]   =(lambda p=prompt,k=apis["groq"]: _call_groq_ia(p,k))
    if apis.get("gemini"):  tareas["Gemini"] =(lambda p=prompt,k=apis["gemini"]: _call_gemini_ia(p,k))
    if apis.get("mistral"): tareas["Mistral"]=(lambda p=prompt,k=apis["mistral"]: _call_mistral_ia(p,k))
    if not tareas:
        return {"decision":"CONFIRMAR","confianza":65,"razon":"Sin IAs activas","riesgo_principal":"—",
                "votos_confirmar":0,"votos_rechazar":0,"total_ias":0,"detalles":{}}
    detalles={}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures={name:ex.submit(fn) for name,fn in tareas.items()}
        for name,fut in futures.items():
            try: detalles[name]=fut.result(timeout=55)
            except: detalles[name]=None
    validas=[v for v in detalles.values() if v]
    confirman=[v for v in validas if v.get("decision")=="CONFIRMAR"]
    total=len(validas); n_conf=len(confirman)
    # Si TODAS las IAs fallaron (timeout/sin conexión), no penalizar: la decisión técnica ya aprobó
    if total == 0:
        return {"decision":"CONFIRMAR","confianza":65,"razon":"IAs no disponibles - análisis técnico",
                "riesgo_principal":"—","votos_confirmar":0,"votos_rechazar":0,"total_ias":0,"detalles":detalles}
    avg_conf=int(sum(v.get("confianza",50) for v in confirman)/n_conf) if n_conf else 0
    mejor=max(confirman,key=lambda x:x.get("confianza",0)) if confirman else (validas[0] if validas else {})
    return {
        "decision":"CONFIRMAR" if n_conf>0 and n_conf/total>=0.5 else "RECHAZAR",
        "confianza":avg_conf,
        "razon":mejor.get("razon","—") if mejor else "—",
        "riesgo_principal":mejor.get("riesgo","—") if mejor else "—",
        "votos_confirmar":n_conf,"votos_rechazar":total-n_conf,"total_ias":total,
        "detalles":detalles,
    }

def validar_ia(nombre,dir_,ind,trend_1h,score):
    """Compatibilidad: llama solo Ollama."""
    return validar_multi_ia(nombre,dir_,ind,trend_1h,score,{"ollama":True})

# ── TELEGRAM ──────────────────────────────────────────────────────────────────
def enviar_telegram(señal, bot_token, chat_id):
    """Envía alerta de señal a Telegram vía Bot API. Devuelve (ok, mensaje)."""
    if not bot_token or not chat_id:
        return False, "Token o chat_id vacío"
    d   = "▲ COMPRA" if señal["dir"]=="buy" else "▼ VENTA"
    pat = señal.get("patron","—"); est = señal.get("estilo_est","—"); tipo = señal.get("tipo_est","")
    strat_txt = f"{tipo} · {est}" if tipo and tipo != "—" else est
    texto = (
        f"⚡ *RAVEN AI · SEÑAL ACTIVA*\n"
        f"*{señal['nombre']}* · {d}\n"
        f"Clase: *{señal.get('clase','—')} · {señal['score']}/100*\n"
        f"Estrategia: {strat_txt} · {pat}\n\n"
        f"📍 Entrada: `{fmt(señal['entry'],señal['key'])}`\n"
        f"🛑 SL: `{fmt(señal['sl'],señal['key'])}`\n"
        f"🎯 TP1: `{fmt(señal['tp1'],señal['key'])}` +${señal['g1']:.2f} (1:{señal['rr1']:.1f})\n"
        f"🎯 TP2: `{fmt(señal['tp2'],señal['key'])}` +${señal['g2']:.2f} (1:{señal['rr2']:.1f})\n"
        f"💎 TP4: `{fmt(señal['tp4'],señal['key'])}` +${señal['g4']:.2f}\n\n"
        f"🤖 IA: {señal.get('ia_votos',0)}/{señal.get('ia_total',1)} · {señal['ia_conf']}% confianza\n"
        f"⏰ {señal['ts_open'][11:16]} UTC"
    )
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id":chat_id,"text":texto,"parse_mode":"Markdown"},
            timeout=8)
        if r.status_code==200:
            return True, "Enviado ✅"
        return False, r.json().get("description","Error HTTP")
    except Exception as e:
        return False, str(e)[:60]

def enviar_telegram_gold(señal, bot_token, chat_id):
    """Alerta Telegram específica para señales ORO / XAUUSD M5."""
    if not bot_token or not chat_id:
        return False, "Token o chat_id vacío"
    d      = señal.get("dir", "buy")
    emoji  = "🟢" if d == "buy" else "🔴"
    tipo   = "LONG" if d == "buy" else "SHORT"
    score  = señal.get("score", 0)
    texto  = (
        f"⚡ *RAVEN AI · ORO M5*\n"
        f"{emoji} *{tipo} XAUUSD* @ `{señal.get('entry',0):.2f}`\n\n"
        f"🛑 SL: `{señal.get('sl',0):.2f}`\n"
        f"🎯 TP1: `{señal.get('tp1',0):.2f}`\n"
        f"🎯 TP2: `{señal.get('tp2',0):.2f}`\n"
        f"🎯 TP3: `{señal.get('tp3',0):.2f}`\n\n"
        f"Score: *{score}/100*\n"
        f"Patrón: {señal.get('patron','—')}\n"
        f"M15: {señal.get('tendencia_m15','—')}\n"
        f"M5: {señal.get('setup_m5','—')}\n"
        f"M1: {señal.get('conf_m1','—')}\n"
        f"Fuente: MT5 / Weltrade\n"
        f"Estado: Entrada válida\n"
        f"⏰ {datetime.now().strftime('%H:%M')} UTC"
    )
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"},
            timeout=8)
        return (True, "Enviado ✅") if r.status_code == 200 else (False, r.json().get("description","Error HTTP"))
    except Exception as e:
        return False, str(e)[:60]

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
        "ia_votos":ia.get("votos_confirmar",0),"ia_total":ia.get("total_ias",0),
        "ia_detalles":ia.get("detalles",{}),
        "entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,"tp4":tp4,
        "dist":dist,"units":units,"riesgo_usd":r_usd,
        "g1":units*abs(tp1-entry),"g2":units*abs(tp2-entry),
        "g3":units*abs(tp3-entry),"g4":units*abs(tp4-entry),
        "rr1":rr(tp1),"rr2":rr(tp2),"rr3":rr(tp3),"rr4":rr(tp4),
        "razon":resultado.get("razon","—"),
        "trend_1h":resultado.get("trend_1h","—"),
        "patron":resultado.get("patron","—"),
        "tipo_est":resultado.get("tipo_est","—"),
        "estilo_est":resultado.get("estilo_est","—"),
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
def ejecutar_scan(balance,riesgo,stats,activos_sel,modo,usar_ia,max_ab,min_score_modo,apis_ia=None):
    # Solo contar señales forex/regulares contra max_ab (no sintéticos ni Weltrade)
    abiertas_total=[s for s in stats["señales"] if s["estado"]=="ABIERTA" and not s.get("is_synthetic")]
    resultados={}; nuevas=[]
    apis=apis_ia or {}
    def scan_one(key):
        r=señal_mtf(key); r["ts"]=datetime.now().strftime("%H:%M:%S"); return r
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(scan_one,activos_sel): resultados[r["key"]]=r
    live=precios_en_vivo()
    for key,r in resultados.items():
        # Solo procesar señales con dirección y score suficiente
        if not r.get("dir"): continue
        if r.get("decision") == "BLOQUEADA": continue
        if r["score"] < min_score_modo: continue
        # Solo crear señal si la decisión técnica es RECOMENDAR
        if r.get("decision") != "RECOMENDAR": continue
        if len(abiertas_total) >= max_ab: continue
        if tiene_señal_reciente(key, stats, MIN_MIN_ENTRE_SEÑALES): continue
        # Validación multi-IA en paralelo
        ia = {"decision":"CONFIRMAR","confianza":65,"razon":"IA desactivada",
              "riesgo_principal":"—","votos_confirmar":0,"votos_rechazar":0,"total_ias":0,"detalles":{}}
        if usar_ia and r.get("ind"):
            ia = validar_multi_ia(ACTIVOS[key][1],r["dir"],r["ind"],r.get("trend_1h","—"),r["score"],apis)
        # Si todas las IAs fallaron (sin conexión), aceptar igualmente (técnico ya aprobó)
        ia_ok = True
        if usar_ia and ia.get("total_ias", 0) > 0:
            ia_ok = (ia.get("decision") == "CONFIRMAR" and ia.get("confianza", 0) >= 55)
        if not ia_ok:
            r["ia_result"] = ia; continue
        r["ia_result"] = ia
        s = crear_señal(key, r, balance, riesgo, ia, r["score"], r["clase"])
        stats["señales"].insert(0, s); nuevas.append(s)
        abiertas_total.append(s)
    return resultados, nuevas

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style="color:#d0d0f0;font-size:.95em;font-weight:900;letter-spacing:3px;
    text-transform:uppercase">⚡ RAVEN AI</div>
    <div style="color:#252540;font-size:.62em;letter-spacing:2px;text-transform:uppercase;
    margin-bottom:10px">Centro de Señales · v2</div>""", unsafe_allow_html=True)

    # ── Modo de vista ─────────────────────────────────────────────────────────
    modo_vista = st.radio("Vista", ["SIMPLE","AVANZADO"], horizontal=True,
                          label_visibility="collapsed")
    es_avanzado = (modo_vista == "AVANZADO")

    st.divider()
    # ── Controles básicos (siempre visibles) ──────────────────────────────────
    balance  = st.number_input("💰 Capital ($):", min_value=1.0, value=500.0, step=10.0)
    riesgo   = st.slider("⚠️ Riesgo / trade:", 0.5, 5.0, 1.0, 0.5, format="%.1f%%")
    usar_ia  = st.toggle("🤖 Validación Multi-IA", value=True)

    st.divider()
    # ── Calidad de señal ──────────────────────────────────────────────────────
    modo=st.radio("Calidad mínima",
        ["🏆 Premium (score ≥90)",
         "⭐ Alta Probabilidad (score ≥80)",
         "👀 Observación (score ≥70)"],
        label_visibility="collapsed")
    min_score_modo = 90 if "Premium" in modo else 80 if "Alta" in modo else 70

    st.divider()
    # ── MT5 / Deriv ───────────────────────────────────────────────────────────
    uso_mt5 = st.radio("📡 Uso de MT5/Deriv",
        ["Solo sintéticos", "Fuente principal para todo", "Desactivado"],
        label_visibility="collapsed")
    st.session_state["uso_mt5_val"] = uso_mt5   # para que señal_mtf lo lea
    usar_sinteticos = st.checkbox("🔷 Analizar Sintéticos Deriv/MT5", value=True)

    # Filtro de sintéticos Deriv
    sinteticos_sel = list(SINTETICOS.keys())
    if usar_sinteticos:
        _sint_opciones = list(SINTETICOS.keys())
        sinteticos_sel = st.multiselect(
            "Sintéticos Deriv:",
            options=_sint_opciones,
            default=["V75","BOOM500","BOOM1000","CRASH500","CRASH1000","STEP","JUMP100"],
            format_func=lambda k: f"{k} · {SINTETICOS[k]}",
            key="sint_sel",
        )
        if not sinteticos_sel:
            sinteticos_sel = _sint_opciones

    # Weltrade MT5 sintéticos
    usar_weltrade = st.checkbox("🟠 Analizar Índices Weltrade (MT5)", value=True)
    weltrade_sel = []
    if usar_weltrade:
        _wt_opts = list(WELTRADE_SINTETICOS.keys())
        weltrade_sel = st.multiselect(
            "Índices Weltrade:",
            options=_wt_opts,
            default=["WGAIN400","WGAIN600","WGAIN800","WPAIN400","WPAIN600","WPAIN800",
                     "WFV40","WFV60","WFV80","WFLIP1","WFLIP2","WTREND600","WTREND1200"],
            format_func=lambda k: f"{WELTRADE_SINTETICOS[k][0]}",
            key="wt_sel",
        )
        if not weltrade_sel:
            weltrade_sel = _wt_opts

    # ── ORO / XAUUSD M5 ──────────────────────────────────────────────────────
    st.divider()
    usar_gold = st.checkbox("🟡 Señales ORO / XAUUSD M5 (MT5)", value=True, key="usar_gold_chk")
    st.session_state["usar_gold_val"] = usar_gold
    if usar_gold:
        gold_min_score = st.slider("Score mín. ORO:", 60, 90, 70, 5, key="gold_min_score")
        gold_spread_max = st.number_input("Spread máx. ORO (USD):", min_value=0.5, max_value=10.0,
                                          value=3.0, step=0.5, key="gold_spread_max")
        gold_news_filter = st.toggle("🗞 Filtro noticias manual", value=False, key="gold_news_filter")
        gold_news_times  = ""
        if gold_news_filter:
            gold_news_times = st.text_area("Horarios bloqueados (UTC, uno por línea):",
                value="08:25-08:35\n12:55-13:05\n14:25-14:35",
                height=80, key="gold_news_times",
                help="Formato HH:MM-HH:MM. Usa UTC.")
        st.session_state["gold_min_score_val"]  = gold_min_score
        st.session_state["gold_spread_max_val"] = gold_spread_max
        st.session_state["gold_news_times_val"] = gold_news_times
    else:
        st.session_state.setdefault("gold_min_score_val", 70)
        st.session_state.setdefault("gold_spread_max_val", 3.0)
        st.session_state.setdefault("gold_news_times_val", "")

    _c1sb, _c2sb = st.columns(2)
    if _c1sb.button("🔌 Conectar MT5", use_container_width=True):
        ensure_mt5_connection(force=True)
        get_available_mt5_symbols(force=True)
    if _c2sb.button("🔄 Símbolos", use_container_width=True):
        get_available_mt5_symbols(force=True)

    ms = _mt5_status
    _nsyms = len(st.session_state.get("mt5_symbols", []))
    if ms["connected"]:
        st.markdown(f'<div style="background:#010d04;border:1px solid #00c853;border-radius:6px;'
            f'padding:6px 10px;font-size:.7em;margin-top:4px">'
            f'<span style="color:#00e676">✅ MT5 conectado</span> &nbsp;'
            f'<span style="color:#444">{ms["broker"][:15]}</span><br>'
            f'<span style="color:#1a3a1a">Cta: {ms["account"]} · {_nsyms} símbolos</span>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="background:#0d0101;border:1px solid #c62828;border-radius:6px;'
            f'padding:6px 10px;font-size:.7em;margin-top:4px">'
            f'<span style="color:#ff5252">⚠ MT5 desconectado</span><br>'
            f'<span style="color:#333">{ms["error"][:45]}</span>'
            f'</div>', unsafe_allow_html=True)

    st.divider()
    # ── Iniciar / Parar ───────────────────────────────────────────────────────
    _sb1, _sb2 = st.columns(2)
    iniciar = _sb1.button("▶ INICIAR", type="primary", use_container_width=True)
    detener = _sb2.button("⏹ PARAR", use_container_width=True)
    intervalo = st.select_slider("🔄 Intervalo:", [30,60,120,180,300], value=60,
                                  format_func=lambda x: f"{x}s")
    max_ab = st.slider("🔒 Máx. señales:", 1, 10, 3)
    if st.button("🗑 Limpiar historial", use_container_width=True):
        stats_save({"señales":[],"total":0,"wins":0,"losses":0,
                    "pnl_usd":0.0,"racha_actual":0,"mejor_racha":0})
        st.rerun()

    # ── Modo AVANZADO: opciones extra ─────────────────────────────────────────
    if es_avanzado:
        st.divider()
        st.markdown('<div style="color:#252540;font-size:.62em;text-transform:uppercase;letter-spacing:2px">Mercados avanzado</div>', unsafe_allow_html=True)
        activos_sel = []
        for cat, keys in CATEGORIAS.items():
            if st.checkbox(cat, value=True, key=f"cat_{cat}"):
                activos_sel.extend(keys)

        with st.expander("⚙️ Configurar IAs", expanded=False):
            use_ollama_chk = st.checkbox("🟢 Ollama local", value=True, key="chk_ollama")
            use_claude_chk = st.checkbox("🟣 Claude", key="chk_claude")
            claude_key     = st.text_input("Claude Key:", type="password", key="key_claude",
                                           placeholder="sk-ant-...") if use_claude_chk else ""
            use_openai_chk = st.checkbox("🟡 OpenAI", key="chk_openai")
            openai_key     = st.text_input("OpenAI Key:", type="password", key="key_openai",
                                           placeholder="sk-...") if use_openai_chk else ""
            use_groq_chk   = st.checkbox("🔵 Groq (gratis)", key="chk_groq")
            groq_key       = st.text_input("Groq Key:", type="password", key="key_groq",
                                           placeholder="gsk_...") if use_groq_chk else ""
            use_gemini_chk = st.checkbox("🔴 Gemini", key="chk_gemini")
            gemini_key     = st.text_input("Gemini Key:", type="password", key="key_gemini",
                                           placeholder="AIza...") if use_gemini_chk else ""
            use_mistral_chk = st.checkbox("🟠 Mistral (gratis)", key="chk_mistral")
            mistral_key     = st.text_input("Mistral Key:", type="password", key="key_mistral",
                                            placeholder="...") if use_mistral_chk else ""
            if st.button("💾 Guardar keys", use_container_width=True):
                keys_save({"gemini":gemini_key,"claude":claude_key,"openai":openai_key,
                           "groq":groq_key,"mistral":mistral_key})
                st.success("Keys guardadas")

        with st.expander("🧪 Debug MT5", expanded=False):
            _ms2 = _mt5_status
            _nsyms_d = len(st.session_state.get("mt5_symbols", []))
            _mc = "#00e676" if _ms2.get("connected") else "#ff5252"
            st.markdown(f'<div style="font-size:.7em;line-height:1.8;color:#666">'
                f'<b style="color:{_mc}">MT5: {"CONECTADO" if _ms2.get("connected") else "DESCONECTADO"}</b><br>'
                f'Broker: {_ms2.get("broker","—")}<br>Server: {_ms2.get("server","—")}<br>'
                f'Cuenta: {_ms2.get("account","—")}<br>Símbolos: {_nsyms_d}<br>'
                f'Error: <span style="color:#ff9800">{_ms2.get("last_error",_ms2.get("error","—"))[:55]}</span>'
                f'</div>', unsafe_allow_html=True)
            for _dk in sorted([k for k in st.session_state if k.startswith("mt5_debug_")])[:8]:
                _dv = st.session_state[_dk]
                _dc = "#00e676" if str(_dv.get("status","")).startswith("OK") else "#ff9800"
                st.markdown(f'<div style="font-size:.63em;color:{_dc}">'
                    f'{_dk.replace("mt5_debug_","")} → {_dv.get("symbol","?")} '
                    f'| {_dv.get("status","?")} | {_dv.get("bars",0)} velas</div>',
                    unsafe_allow_html=True)

        with st.expander("🌐 Debug Deriv WS", expanded=False):
            _cfg_d = get_deriv_config() if "get_deriv_config" in dir() else {}
            _app_id_d = _KEYS.get("deriv_app_id","1089") or "1089"
            _tok_d    = "✅ Sí" if _KEYS.get("deriv","") else "❌ No"
            _last_err = st.session_state.get("deriv_last_error","—")
            st.markdown(f'<div style="font-size:.7em;line-height:1.9;color:#555">'
                f'App ID: <b style="color:#26c6da">{_app_id_d}</b><br>'
                f'Token cargado: <b style="color:#26c6da">{_tok_d}</b><br>'
                f'Último error global: <span style="color:#ff9800">{str(_last_err)[:60]}</span>'
                f'</div>', unsafe_allow_html=True)
            _dd = st.session_state.get("deriv_debug", {})
            if _dd:
                for _sk, _di in list(_dd.items())[:10]:
                    _ok = not _di.get("error") and _di.get("ticks",0)>0
                    _clr = "#00e676" if _ok else "#ff5252"
                    _err_txt = str(_di.get("error",""))[:50] if _di.get("error") else "—"
                    st.markdown(
                        f'<div style="background:#08080f;border:1px solid #141428;'
                        f'border-left:3px solid {_clr};border-radius:4px;'
                        f'padding:5px 10px;margin:3px 0;font-size:.67em;line-height:1.7">'
                        f'<b style="color:{_clr}">{_sk}</b> · {_di.get("deriv_symbol","?")}<br>'
                        f'<span style="color:#444">Precio: <b style="color:#82b1ff">'
                        f'{_di.get("last_price","—")}</b> · '
                        f'Ticks: <b>{_di.get("ticks",0)}</b> · '
                        f'V2s: {_di.get("candles_2s",0)} · '
                        f'V5s: {_di.get("candles_5s",0)} · '
                        f'V15s: {_di.get("candles_15s",0)} · '
                        f'V1m: {_di.get("candles_1m",0)} · '
                        f'V2m: {_di.get("candles_2m",0)}</span><br>'
                        f'<span style="color:#ff9800">{_err_txt}</span>'
                        f'</div>', unsafe_allow_html=True)
            else:
                st.caption("Sin datos aún — inicia el scanner con sintéticos activos")
    else:
        # Modo simple: todos los mercados activos, APIs desde archivo guardado
        activos_sel = list(ACTIVOS.keys())
        use_ollama_chk = True
        use_claude_chk  = bool(_KEYS.get("claude"))
        claude_key      = _KEYS.get("claude", "")
        use_openai_chk  = bool(_KEYS.get("openai"))
        openai_key      = _KEYS.get("openai", "")
        use_groq_chk    = bool(_KEYS.get("groq"))
        groq_key        = _KEYS.get("groq", "")
        use_gemini_chk  = bool(_KEYS.get("gemini"))
        gemini_key      = _KEYS.get("gemini", "")
        use_mistral_chk = bool(_KEYS.get("mistral"))
        mistral_key     = _KEYS.get("mistral", "")

    apis_ia = {
        "ollama":  use_ollama_chk,
        "claude":  claude_key  if (use_claude_chk  and claude_key)  else None,
        "openai":  openai_key  if (use_openai_chk  and openai_key)  else None,
        "groq":    groq_key    if (use_groq_chk    and groq_key)    else None,
        "gemini":  gemini_key  if (use_gemini_chk  and gemini_key)  else None,
        "mistral": mistral_key if (use_mistral_chk and mistral_key) else None,
    }
    r_trade = balance * riesgo / 100
    st.markdown(f'<div style="background:#0b0b1a;border:1px solid #15152a;border-radius:5px;'
                f'padding:6px 10px;font-size:.75em;margin-top:6px">'
                f'<span style="color:#383858">Riesgo/trade:</span> '
                f'<b style="color:#ff9800">${r_trade:.2f}</b> &nbsp;·&nbsp; '
                f'Score mín: <b style="color:#9575cd">{min_score_modo}</b></div>',
                unsafe_allow_html=True)

    st.divider()
    # ── Estado de IAs ─────────────────────────────────────────────────────────
    st.markdown('<div style="color:#252540;font-size:.62em;text-transform:uppercase;'
                'letter-spacing:2px;margin-bottom:6px">🤖 Estado de IAs</div>',
                unsafe_allow_html=True)
    _ollama_ok = False
    try:
        _oll_r = requests.get("http://localhost:11434/api/tags", timeout=2)
        _ollama_ok = (_oll_r.status_code == 200)
    except Exception:
        pass
    _deriv_key = _KEYS.get("deriv","")
    _ia_status_list = [
        ("Ollama local",  _ollama_ok,          "conectado" if _ollama_ok else "no disponible"),
        ("Claude API",    bool(claude_key),     "key cargada" if claude_key else "sin key"),
        ("OpenAI API",    bool(openai_key),     "key cargada" if openai_key else "sin key"),
        ("Groq API",      bool(groq_key),       "key cargada" if groq_key else "sin key"),
        ("Gemini API",    bool(gemini_key),     "key cargada" if gemini_key else "sin key"),
        ("Mistral API",   bool(mistral_key),    "key cargada" if mistral_key else "sin key"),
        ("Deriv API",     bool(_deriv_key),     "token activo ✅" if _deriv_key else "sin token"),
    ]
    _ia_html_sb = ""
    for _ia_name, _ia_ok, _ia_desc in _ia_status_list:
        _c = "#00e676" if _ia_ok else "#2a2a48"
        _ico = "✅" if _ia_ok else "❌"
        _ia_html_sb += (f'<div style="display:flex;justify-content:space-between;'
            f'padding:3px 0;border-bottom:1px solid #0e0e1e">'
            f'<span style="color:#444;font-size:.7em">{_ia_name}</span>'
            f'<span style="color:{_c};font-size:.7em;font-weight:700">{_ico} {_ia_desc}</span>'
            f'</div>')
    st.markdown(f'<div style="background:#08080f;border:1px solid #12121e;'
                f'border-radius:6px;padding:8px 10px">{_ia_html_sb}</div>',
                unsafe_allow_html=True)
    if st.button("🔍 Probar conexión IAs", use_container_width=True):
        _test_ok = []
        _test_fail = []
        try:
            _r2 = requests.get("http://localhost:11434/api/tags", timeout=3)
            if _r2.status_code == 200: _test_ok.append("Ollama")
            else: _test_fail.append("Ollama (error HTTP)")
        except Exception:
            _test_fail.append("Ollama (sin conexión)")
        for _kn, _kv in [("Claude",claude_key),("OpenAI",openai_key),
                          ("Groq",groq_key),("Gemini",gemini_key),("Mistral",mistral_key)]:
            if _kv: _test_ok.append(f"{_kn} (key presente)")
            else:   _test_fail.append(f"{_kn} (sin key)")
        if _test_ok:
            st.success("✅ " + " · ".join(_test_ok))
        if _test_fail:
            st.warning("❌ " + " · ".join(_test_fail))

    st.divider()
    # ── Telegram Alerts ───────────────────────────────────────────────────────
    with st.expander("📨 Alertas Telegram", expanded=False):
        _tg_on_saved  = bool(_KEYS.get("telegram_on", False))
        _tg_tok_saved = _KEYS.get("telegram_token","")
        _tg_cht_saved = _KEYS.get("telegram_chat","")
        tg_on    = st.toggle("Activar alertas Telegram", value=_tg_on_saved, key="tg_on")
        tg_token = st.text_input("Bot Token:", value=_tg_tok_saved, type="password",
                                  placeholder="123456:ABC...", key="tg_token")
        tg_chat  = st.text_input("Chat ID:", value=_tg_cht_saved,
                                  placeholder="-100123456", key="tg_chat")
        _tc1, _tc2 = st.columns(2)
        if _tc1.button("💾 Guardar TG", use_container_width=True):
            _kd2 = keys_load()
            _kd2.update({"telegram_on":tg_on,"telegram_token":tg_token,"telegram_chat":tg_chat})
            keys_save(_kd2); _KEYS.update(_kd2)
            st.success("Telegram guardado")
        if _tc2.button("🧪 Probar TG", use_container_width=True):
            if tg_token and tg_chat:
                _tok, _msg = enviar_telegram({
                    "nombre":"RAVEN AI Test","dir":"buy","score":99,
                    "clase":"PREMIUM","key":"EURUSD","entry":1.1000,"sl":1.0950,
                    "tp1":1.1040,"tp2":1.1080,"tp4":1.1180,"g1":5.0,"g2":10.0,"g4":18.0,
                    "rr1":0.8,"rr2":1.6,"rr4":3.2,"ia_votos":3,"ia_total":3,
                    "ia_conf":91,"patron":"—","tipo_est":"—","estilo_est":"—",
                    "ts_open":datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                    tg_token, tg_chat)
                st.success(_msg) if _tok else st.error(_msg)
            else:
                st.warning("Ingresa token y chat ID primero")

    # ── Deriv App ID configurable ─────────────────────────────────────────────
    with st.expander("⚙️ Deriv API Config", expanded=False):
        _app_id_saved  = _KEYS.get("deriv_app_id","1089")
        _deriv_t_saved = _KEYS.get("deriv","")
        new_app_id  = st.text_input("App ID:", value=_app_id_saved, placeholder="1089", key="deriv_app_id_inp")
        new_deriv_t = st.text_input("Token:", value=_deriv_t_saved, type="password", key="deriv_token_inp")
        if st.button("💾 Guardar Deriv config", use_container_width=True):
            _kd3 = keys_load()
            _kd3.update({"deriv_app_id":new_app_id,"deriv":new_deriv_t})
            keys_save(_kd3); _KEYS.update(_kd3)
            st.success(f"App ID {new_app_id} guardado")
        _deriv_stat = "✅ Token activo" if _KEYS.get("deriv") else "❌ Sin token"
        st.caption(f"Estado: {_deriv_stat} · App ID: {_KEYS.get('deriv_app_id','1089')}")

# ── ESTADO ────────────────────────────────────────────────────────────────────
for k,v in [("scanning",False),("resultados",{}),("nuevas",[]),
             ("ultimo","—"),("live_prices",{}),("resultados_sint",{})]:
    if k not in st.session_state: st.session_state[k]=v
for _kname in ["gemini","claude","openai","groq","mistral"]:
    if f"key_{_kname}" not in st.session_state:
        st.session_state[f"key_{_kname}"] = _KEYS.get(_kname,"")
    if f"chk_{_kname}" not in st.session_state:
        st.session_state[f"chk_{_kname}"] = bool(_KEYS.get(_kname,""))
if iniciar: st.session_state["scanning"]=True
if detener: st.session_state["scanning"]=False
stats=stats_load()
# Telegram vars (se leen del expander o del JSON guardado)
_tg_on    = st.session_state.get("tg_on", bool(_KEYS.get("telegram_on",False)))
_tg_token = st.session_state.get("tg_token", _KEYS.get("telegram_token",""))
_tg_chat  = st.session_state.get("tg_chat",  _KEYS.get("telegram_chat",""))

if st.session_state["scanning"]:
    verificar_abiertas(stats)
    # Filtrar mercados: si uso_mt5=="Solo sintéticos", pasar uso_mt5 para que
    # get_mt5_bars solo se llame internamente en sintéticos, no en el scan general
    resultados,nuevas=ejecutar_scan(balance,riesgo,stats,activos_sel,
                                     modo,usar_ia,max_ab,min_score_modo,apis_ia)
    rsint={}
    nuevas_sint=[]
    if usar_sinteticos and sinteticos_sel:
        def _scan_sint(k): r=señal_sintetico(k); r["ts"]=datetime.now().strftime("%H:%M:%S"); return r
        with ThreadPoolExecutor(max_workers=4) as ex:
            for r in ex.map(_scan_sint, sinteticos_sel): rsint[r["key"]]=r
        # Crear señales activas para sintéticos que recomiendan
        _abiertas_sint=[s for s in stats["señales"] if s["estado"]=="ABIERTA" and s.get("is_synthetic")]
        _abiertas_tot=[s for s in stats["señales"] if s["estado"]=="ABIERTA"]
        _min_sint = 62
        _max_sint = 10   # sintéticos tienen su propio límite
        _cool_sint = 5   # cooldown 5 min entre señales del mismo sintético
        for _sk, _sr in rsint.items():
            if _sr.get("decision")!="RECOMENDAR": continue
            if _sr.get("score",0)<_min_sint: continue
            if len(_abiertas_sint)>=_max_sint: continue
            if tiene_señal_reciente(_sk, stats, _cool_sint): continue
            if not _sr.get("dir") or not _sr.get("atr",0): continue
            # Señal sintética sin IA (la técnica manda, IA solo complementa)
            _ia_sint = {"decision":"CONFIRMAR","confianza":72,
                        "razon":"Sintético Deriv WS","riesgo_principal":"volatilidad",
                        "votos_confirmar":0,"votos_rechazar":0,"total_ias":0,"detalles":{}}
            if usar_ia and _sr.get("ind"):
                try:
                    _ia_sint = validar_multi_ia(
                        SINTETICOS.get(_sk,_sk), _sr["dir"], _sr["ind"],
                        _sr.get("trend_1h","neutral"), _sr["score"], apis_ia)
                except: pass
            _snueva = {
                "id":str(uuid.uuid4())[:8], "key":_sk, "sym":_sk,
                "nombre":SINTETICOS.get(_sk,_sk), "cat":"SINTETICOS", "unidad":"pts",
                "dir":_sr["dir"], "score":_sr["score"], "clase":_sr.get("clase","—"),
                "ia_dec":_ia_sint.get("decision","—"), "ia_conf":_ia_sint.get("confianza",0),
                "ia_razon":_ia_sint.get("razon","—"), "ia_riesgo":_ia_sint.get("riesgo_principal","—"),
                "ia_votos":_ia_sint.get("votos_confirmar",0), "ia_total":_ia_sint.get("total_ias",0),
                "ia_detalles":_ia_sint.get("detalles",{}),
                "entry":_sr["entry"], "sl":_sr["sl"],
                "tp1":_sr["tp1"], "tp2":_sr["tp2"], "tp3":_sr["tp3"], "tp4":_sr["tp4"],
                "dist":abs(_sr["entry"]-_sr["sl"]),
                "units": (balance*riesgo/100)/abs(_sr["entry"]-_sr["sl"]) if abs(_sr["entry"]-_sr.get("sl",0))>0 else 0,
                "riesgo_usd":balance*riesgo/100,
                "g1":0,"g2":0,"g3":0,"g4":0,"rr1":0,"rr2":0,"rr3":0,"rr4":0,
                "razon":_sr.get("razon","—"),
                "trend_1h":_sr.get("trend_1h","neutral"),
                "patron":_sr.get("patron","—"),
                "tipo_est":_sr.get("tipo_est","—"), "estilo_est":_sr.get("estilo_est","—"),
                "ts_open":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ts_close":None, "estado":"ABIERTA", "resultado_usd":None,
                "is_synthetic":True,
            }
            _dist = _snueva["dist"]
            if _dist>0:
                _u = _snueva["units"]
                for _n,_lvl in [("g1","tp1"),("g2","tp2"),("g3","tp3"),("g4","tp4")]:
                    _snueva[_n] = _u * abs(_snueva[_lvl]-_snueva["entry"])
                for _n,_lvl in [("rr1","tp1"),("rr2","tp2"),("rr3","tp3"),("rr4","tp4")]:
                    _snueva[_n] = abs(_snueva[_lvl]-_snueva["entry"]) / _dist
            stats["señales"].insert(0, _snueva)
            nuevas_sint.append(_snueva)
            _abiertas_tot.append(_snueva)

    # ── SCAN WELTRADE MT5 ─────────────────────────────────────────────────────
    rwelt = {}
    try:
        if usar_weltrade and weltrade_sel and _mt5_status.get("connected"):
            def _scan_welt(k): r=señal_weltrade(k); r["ts"]=datetime.now().strftime("%H:%M:%S"); return r
            with ThreadPoolExecutor(max_workers=4) as ex:
                for r in ex.map(_scan_welt, weltrade_sel): rwelt[r["key"]]=r
            _abiertas_welt=[s for s in stats["señales"] if s["estado"]=="ABIERTA" and s.get("is_weltrade")]
            _max_welt=10; _cool_welt=5; _min_welt=62
            for _wk, _wr in rwelt.items():
                if _wr.get("decision")!="RECOMENDAR": continue
                if _wr.get("score",0)<_min_welt: continue
                if len(_abiertas_welt)>=_max_welt: continue
                if tiene_señal_reciente(_wk, stats, _cool_welt): continue
                if not _wr.get("dir") or not _wr.get("atr",0): continue
                _wsnueva={
                    "id":str(uuid.uuid4())[:8],"key":_wk,"sym":_wk,
                    "nombre":WELTRADE_SINTETICOS.get(_wk,(_wk,"—"))[0],
                    "cat":"WELTRADE","unidad":"pts",
                    "dir":_wr["dir"],"score":_wr["score"],"clase":_wr.get("clase","—"),
                    "ia_dec":"CONFIRMAR","ia_conf":72,"ia_razon":"MT5 Weltrade","ia_riesgo":"volatilidad",
                    "ia_votos":0,"ia_total":0,"ia_detalles":{},
                    "entry":_wr["entry"],"sl":_wr["sl"],
                    "tp1":_wr["tp1"],"tp2":_wr["tp2"],"tp3":_wr["tp3"],"tp4":_wr["tp4"],
                    "dist":abs(_wr["entry"]-_wr["sl"]),
                    "units":(balance*riesgo/100)/abs(_wr["entry"]-_wr.get("sl",0)) if abs(_wr["entry"]-_wr.get("sl",0))>0 else 0,
                    "riesgo_usd":balance*riesgo/100,
                    "g1":0,"g2":0,"g3":0,"g4":0,"rr1":0,"rr2":0,"rr3":0,"rr4":0,
                    "razon":_wr.get("razon","—"),"trend_1h":_wr.get("trend_1h","neutral"),
                    "patron":_wr.get("patron","—"),"tipo_est":_wr.get("tipo_est","—"),
                    "estilo_est":_wr.get("estilo_est","—"),
                    "ts_open":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ts_close":None,"estado":"ABIERTA","resultado_usd":None,
                    "is_synthetic":True,"is_weltrade":True,
                }
                _wd=_wsnueva["dist"]
                if _wd>0:
                    _u=_wsnueva["units"]
                    for _n,_lv in [("g1","tp1"),("g2","tp2"),("g3","tp3"),("g4","tp4")]:
                        _wsnueva[_n]=_u*abs(_wsnueva[_lv]-_wsnueva["entry"])
                    for _n,_lv in [("rr1","tp1"),("rr2","tp2"),("rr3","tp3"),("rr4","tp4")]:
                        _wsnueva[_n]=abs(_wsnueva[_lv]-_wsnueva["entry"])/_wd
                stats["señales"].insert(0,_wsnueva)
                nuevas_sint.append(_wsnueva)
                _abiertas_welt.append(_wsnueva)
    except Exception as _ewelt:
        st.session_state["welt_last_error"] = str(_ewelt)[:120]

    # ── SCAN ORO / XAUUSD M5 ─────────────────────────────────────────────────
    _rgold = st.session_state.get("gold_result", {})
    _nueva_gold = None
    try:
        _usar_gold = st.session_state.get("usar_gold_val", False)
        if _usar_gold:
            _g_min   = float(st.session_state.get("gold_min_score_val", 70))
            _g_sp    = float(st.session_state.get("gold_spread_max_val", 3.0))
            _g_news  = st.session_state.get("gold_news_times_val", "")
            _g_hblq  = []
            if _g_news:
                for _line in _g_news.strip().splitlines():
                    _pts = _line.strip().split("-")
                    if len(_pts) == 2:
                        _g_hblq.append((_pts[0].strip(), _pts[1].strip()))
            _rgold = senal_gold_m5(stats, _g_hblq, _g_sp, _g_min)
            _rgold["ts"] = datetime.now().strftime("%H:%M:%S")
            # Crear señal activa si RECOMENDAR
            if _rgold.get("decision") == "RECOMENDAR" and _rgold.get("dir"):
                _at_g  = _rgold["ind_m5"].get("atr", 5.0) or 5.0
                _entry_g = _rgold["entry"]; _sl_g = _rgold["sl"]
                _dist_g  = abs(_entry_g - _sl_g)
                _r_usd_g = balance * riesgo / 100
                _units_g = _r_usd_g / _dist_g if _dist_g > 0 else 0
                def _rr_g(tp): return abs(tp - _entry_g) / _dist_g if _dist_g > 0 else 0
                _nueva_gold = {
                    "id": str(uuid.uuid4())[:8], "key": "XAUUSD",
                    "sym": "GC=F", "nombre": "XAU/USD Oro M5",
                    "cat": "commodity", "unidad": "USD",
                    "dir": _rgold["dir"], "score": _rgold["score"],
                    "clase": _rgold["clase"],
                    "ia_dec": "CONFIRMAR", "ia_conf": 72,
                    "ia_razon": _rgold.get("ia_nota", "—"), "ia_riesgo": "—",
                    "ia_votos": 0, "ia_total": 0, "ia_detalles": {},
                    "entry": _entry_g, "sl": _sl_g,
                    "tp1": _rgold["tp1"], "tp2": _rgold["tp2"],
                    "tp3": _rgold["tp3"], "tp4": _rgold["tp4"],
                    "dist": _dist_g, "units": _units_g, "riesgo_usd": _r_usd_g,
                    "g1": _units_g * abs(_rgold["tp1"] - _entry_g),
                    "g2": _units_g * abs(_rgold["tp2"] - _entry_g),
                    "g3": _units_g * abs(_rgold["tp3"] - _entry_g),
                    "g4": _units_g * abs(_rgold["tp4"] - _entry_g),
                    "rr1": _rr_g(_rgold["tp1"]), "rr2": _rr_g(_rgold["tp2"]),
                    "rr3": _rr_g(_rgold["tp3"]), "rr4": _rr_g(_rgold["tp4"]),
                    "razon": _rgold.get("setup_m5", "—"),
                    "trend_1h": _rgold.get("tendencia_m15", "neutral"),
                    "patron": _rgold.get("patron", "—"),
                    "tipo_est": "Scalping", "estilo_est": _rgold.get("patron", "—"),
                    "ts_open": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ts_close": None, "estado": "ABIERTA", "resultado_usd": None,
                    "is_gold": True, "telegram_enviado": False,
                }
                stats["señales"].insert(0, _nueva_gold)
                # Telegram gold
                if _tg_on and _tg_token and _tg_chat:
                    _tg_ok, _ = enviar_telegram_gold(_rgold, _tg_token, _tg_chat)
                    _nueva_gold["telegram_enviado"] = _tg_ok
            st.session_state["gold_result"] = _rgold
    except Exception as _egold:
        st.session_state["gold_last_error"] = str(_egold)[:120]

    st.session_state.update({"live_prices":precios_en_vivo(),
        "resultados":resultados,"nuevas":nuevas,
        "nuevas_sint":nuevas_sint,
        "ultimo":datetime.now().strftime("%H:%M:%S"),
        "resultados_sint":rsint,"resultados_welt":rwelt,
        "gold_result": _rgold})
    stats_save(stats)
    # Auto-enviar a Telegram: señales regulares
    if _tg_on and _tg_token and _tg_chat and nuevas:
        for _ns in nuevas:
            enviar_telegram(_ns, _tg_token, _tg_chat)
    # Auto-enviar a Telegram: señales sintéticas
    if _tg_on and _tg_token and _tg_chat and nuevas_sint:
        for _ns in nuevas_sint:
            _txt_sint = (
                f"⚡ *RAVEN AI · SINTÉTICO*\n"
                f"{'🟢 LONG' if _ns['dir']=='buy' else '🔴 SHORT'} *{_ns['nombre']}* @ `{_ns['entry']:.4f}`\n"
                f"🛑 SL: `{_ns['sl']:.4f}`\n"
                f"🎯 TP1: `{_ns['tp1']:.4f}`  TP2: `{_ns['tp2']:.4f}`  TP3: `{_ns['tp3']:.4f}`\n"
                f"Score: *{_ns['score']}/100*  Patrón: {_ns.get('patron','—')}\n"
                f"Fuente: Deriv WS  Estado: Entrada válida\n"
                f"⏰ {_ns['ts_open'][11:16]} UTC"
            )
            try:
                requests.post(
                    f"https://api.telegram.org/bot{_tg_token}/sendMessage",
                    json={"chat_id":_tg_chat,"text":_txt_sint,"parse_mode":"Markdown"},
                    timeout=8)
            except: pass

resultados       = st.session_state["resultados"]
resultados_sint  = st.session_state.get("resultados_sint",{})
live             = st.session_state.get("live_prices",{})
abiertas         = [s for s in stats["señales"] if s["estado"]=="ABIERTA"]
spm              = stats_por_mercado(stats)
on               = st.session_state["scanning"]

# ══════════════════════════════════════════════════════════════════════════════
# HEADER COMPACTO
# ══════════════════════════════════════════════════════════════════════════════
col_est="#00e676" if on else "#ff5252"
est_txt="ACTIVO" if on else "DETENIDO"
_ia_txt = "ON" if usar_ia else "OFF"
_ia_c   = "#9575cd" if usar_ia else "#333"
st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
padding-bottom:10px;border-bottom:1px solid #0e0e1e;margin-bottom:12px">
  <div>
    <span style="color:#d8d8f8;font-size:1.3em;font-weight:900;letter-spacing:2px">⚡ RAVEN AI</span>
    &nbsp;<span style="color:#252540;font-size:.68em;text-transform:uppercase;letter-spacing:2px">Centro de Señales</span>
  </div>
  <div style="display:flex;gap:14px;align-items:center">
    <span style="font-size:.82em">● <b style="color:{col_est}">{est_txt}</b></span>
    <span style="color:#1a1a38;font-size:.75em">🤖 IA: <b style="color:{_ia_c}">{_ia_txt}</b></span>
    <span style="color:#252540;font-size:.72em">⏱ {st.session_state['ultimo']} · {len(activos_sel)} pares</span>
  </div>
</div>""", unsafe_allow_html=True)

if racha_negativa(stats,3):
    st.markdown('<div class="alert-pausa">⚠️ <b style="color:#ff1744">PAUSA RECOMENDADA</b> — '
                '3 pérdidas consecutivas. Revisar condiciones de mercado.</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# 1. ESTADO DE FUENTES
# ══════════════════════════════════════════════════════════════════════════════
ms = _mt5_status
_nsyms_main = len(st.session_state.get("mt5_symbols",[]))
_fuentes_activas = []
if ms["connected"]: _fuentes_activas.append(f'<span style="color:#00e676">⚡ MT5 {ms["broker"][:10]}</span>')
_fuentes_activas.append('<span style="color:#f9a825">◆ Binance</span>')
_fuentes_activas.append('<span style="color:#42a5f5">◆ Yahoo</span>')
_fuentes_activas.append('<span style="color:#7e57c2">◆ CoinGecko</span>')
_fuentes_activas.append('<span style="color:#26c6da">◆ Deriv API</span>')
_mt5_estado = f'✅ Conectado · {ms["broker"][:18]} · {_nsyms_main} símbolos' if ms["connected"] else f'❌ Desconectado · {ms["error"][:40]}'
_mt5_color  = "#00e676" if ms["connected"] else "#ff5252"
st.markdown(f"""<div style="background:#08080f;border:1px solid #12121e;border-radius:8px;
padding:8px 16px;margin-bottom:12px;display:flex;gap:18px;align-items:center;flex-wrap:wrap">
  <span style="color:#252540;font-size:.65em;text-transform:uppercase;letter-spacing:2px">📡 FUENTES</span>
  {"&nbsp;·&nbsp;".join(_fuentes_activas)}
  <span style="margin-left:auto;font-size:.7em;color:{_mt5_color}">MT5: {_mt5_estado}</span>
</div>""", unsafe_allow_html=True)

# Alertas de nuevas señales
for s in st.session_state.get("nuevas",[]):
    dc="#00e676" if s["dir"]=="buy" else "#ff1744"
    dt="▲ COMPRA" if s["dir"]=="buy" else "▼ VENTA"
    st.markdown(f'<div class="alert-new">🚨 <b style="color:{dc}">{s["nombre"]} · {dt}</b>'
        f'&emsp;Score <b style="color:#00e676">{s["score"]}/100</b>'
        f'&emsp;Entrada: <b style="color:#82b1ff">{fmt(s["entry"],s["key"])}</b>'
        f'&emsp;SL: <b style="color:#ff5252">{fmt(s["sl"],s["key"])}</b></div>',
        unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABS POR MERCADO
# ══════════════════════════════════════════════════════════════════════════════
_KEYS_METALS  = ["XAUUSD","XAGUSD","WTIUSD"]
_KEYS_FOREX   = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDMXN"]
_KEYS_INDICES = ["US30","US100","SPX500","GER40","UK100"]
_KEYS_CRYPTO  = ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD"]

_gd = st.session_state.get("gold_result", {})
_usar_gold_ui = st.session_state.get("usar_gold_val", False)

def _badge(n):
    if n <= 0: return ""
    return f' <span style="background:#00e676;color:#000;border-radius:10px;padding:1px 7px;font-size:.65em;font-weight:900">{n}</span>'

def _n_act(keys):
    return sum(1 for s in abiertas if s.get("key") in keys)

_n_metals = _n_act(_KEYS_METALS) + (1 if _usar_gold_ui and _gd.get("decision")=="RECOMENDAR" else 0)
_n_forex   = _n_act(_KEYS_FOREX)
_n_idx     = _n_act(_KEYS_INDICES)
_n_crypto  = _n_act(_KEYS_CRYPTO)
_n_sint    = sum(1 for r in resultados_sint.values() if r.get("decision")=="RECOMENDAR")
_n_welt    = sum(1 for r in st.session_state.get("resultados_welt",{}).values() if r.get("decision")=="RECOMENDAR")

tab_metals, tab_forex, tab_idx, tab_crypto, tab_sint, tab_welt, tab_hist = st.tabs([
    f"🥇 METALES{_badge(_n_metals)}",
    f"💱 FOREX{_badge(_n_forex)}",
    f"📊 ÍNDICES{_badge(_n_idx)}",
    f"🟣 CRYPTO{_badge(_n_crypto)}",
    f"🔷 SINTÉTICOS{_badge(_n_sint)}",
    f"⚡ WELTRADE{_badge(_n_welt)}",
    "📜 HISTORIAL",
])

# ── helpers de renderizado ────────────────────────────────────────────────────
def _render_signal_card(s):
    pv     = live.get(s["key"]) or s["entry"]
    pnl_v  = (pv-s["entry"])*s["units"] if s["dir"]=="buy" else (s["entry"]-pv)*s["units"]
    pnl_c  = "#00e676" if pnl_v>=0 else "#ff1744"
    sc     = s.get("score",0)
    is_buy = s["dir"]=="buy"
    ac     = "#00e676" if is_buy else "#ff1744"
    css    = "sig-premium" if sc>=90 else "sig-alta" if sc>=80 else "sig-obs"
    dt     = "▲ BUY / COMPRAR" if is_buy else "▼ SELL / VENDER"
    es_txt, es_c = calcular_entry_status(pv, s["entry"], s["tp1"])
    avance = abs(pv-s["entry"])/abs(s["tp1"]-s["entry"])*100 if abs(s["tp1"]-s["entry"])>0 else 0
    trend_c = "#00e676" if s.get("trend_1h")=="buy" else ("#ff5252" if s.get("trend_1h")=="sell" else "#444")
    trend_t = "▲ ALCISTA" if s.get("trend_1h")=="buy" else ("▼ BAJISTA" if s.get("trend_1h")=="sell" else "NEUTRAL")
    fuente_datos = _cache_fuentes.get(s["key"], "—")
    _pat    = s.get("patron","—"); _tipo = s.get("tipo_est","—"); _estilo = s.get("estilo_est","—")
    _ind_s  = resultados.get(s["key"],{}).get("ind") or {}
    _atr_s  = _ind_s.get("atr", s.get("dist",0)/1.2)
    _entry_lo = s["entry"]-_atr_s*0.12 if is_buy else s["entry"]+_atr_s*0.12
    _entry_hi = s["entry"]+_atr_s*0.12 if is_buy else s["entry"]-_atr_s*0.12
    _range_str = f"{fmt(_entry_lo,s['key'])} — {fmt(_entry_hi,s['key'])}"
    st.markdown(f"""<div class="{css}">
<div style="display:flex;align-items:stretch;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.06)">
  <div style="background:{ac};padding:16px 24px;display:flex;align-items:center;min-width:180px">
    <div>
      <div style="color:{'#000' if is_buy else '#fff'};font-size:.6em;text-transform:uppercase;letter-spacing:2px;font-weight:700">✅ SEÑAL ACTIVA PARA ENTRAR</div>
      <div style="color:{'#000' if is_buy else '#fff'};font-size:1.25em;font-weight:900;margin-top:2px">{dt}</div>
      <div style="color:{'#00000088' if is_buy else '#ffffff66'};font-size:.62em;margin-top:3px">{_tipo} · {_estilo}</div>
    </div>
  </div>
  <div style="padding:12px 20px;flex:1">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:2px">📈 Activo · {s['cat']}</div>
    <div style="color:#d8d8f8;font-size:1.15em;font-weight:900;margin:2px 0">{s['nombre']}</div>
    <div style="display:flex;gap:8px;align-items:center;margin-top:4px;flex-wrap:wrap">
      <span style="color:{ac};font-size:.75em;font-weight:800;background:rgba(255,255,255,.04);padding:2px 9px;border-radius:3px">⭐ {s.get('clase','—')} · {sc}/100</span>
      <span style="background:#0a0a14;border:1px solid {es_c};color:{es_c};padding:2px 9px;border-radius:3px;font-size:.72em;font-weight:800">{es_txt}</span>
      <span style="background:#12082a;border:1px solid #3d1278;color:#ce93d8;padding:2px 8px;border-radius:3px;font-size:.7em">{_tipo} · {_estilo}</span>
      {f'<span style="background:#0a0e14;border:1px solid #1a2a40;color:#82b1ff;padding:2px 8px;border-radius:3px;font-size:.7em">🕯 {_pat}</span>' if _pat != "—" else ""}
      <span style="color:#444;font-size:.68em">📡 {fuente_datos}</span>
    </div>
  </div>
  <div style="padding:12px 20px;text-align:right;border-left:1px solid rgba(255,255,255,.05)">
    <div class="px-lbl">📍 PRECIO ACTUAL</div>
    <div style="color:#fff;font-size:1.45em;font-weight:900;font-family:'Courier New',mono">{fmt(pv,s['key'])}</div>
    <div style="color:{pnl_c};font-size:.82em;font-weight:800;margin-top:3px">P&L: {'+'if pnl_v>=0 else ''}${pnl_v:.2f}</div>
    <div style="color:#252540;font-size:.65em;margin-top:2px">Avance a TP1: {avance:.1f}%</div>
  </div>
</div>
<div style="padding:4px 20px 10px">
  <div style="display:grid;grid-template-columns:130px 1fr 100px 140px;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04)">
    <div style="color:#383858;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">🎯 ENTRADA IDEAL</div>
    <div style="color:#82b1ff;font-size:1.1em;font-weight:800;font-family:'Courier New',mono">{fmt(s['entry'],s['key'])}</div>
    <div style="color:#252562;font-size:.68em">Rango válido</div>
    <div style="text-align:right;color:#42a5f5;font-size:.7em;font-family:monospace">{_range_str}</div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 140px;align-items:center;padding:8px 0;border-bottom:2px solid rgba(255,255,255,.07)">
    <div style="color:#ff5252;font-size:.68em;font-weight:700;text-transform:uppercase;letter-spacing:1.5px">🛑 STOP LOSS</div>
    <div style="color:#ff5252;font-size:1.1em;font-weight:800;font-family:'Courier New',mono">{fmt(s['sl'],s['key'])}</div>
    <div style="color:#3a1010;font-size:.75em">{dist_fmt(s['dist'],s['key'])}</div>
    <div style="text-align:right"><span style="background:#1a0404;color:#ff5252;border:1px solid #3a1010;padding:2px 8px;border-radius:3px;font-size:.7em">Riesgo ${s['riesgo_usd']:.2f}</span></div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 140px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#388e3c;font-size:.68em;font-weight:700;text-transform:uppercase">🎯 TP 1</div>
    <div style="color:#69f0ae;font-size:1.05em;font-weight:700;font-family:'Courier New',mono">{fmt(s['tp1'],s['key'])}</div>
    <div style="color:#1b5e20;font-size:.75em">{dist_fmt(abs(s['tp1']-s['entry']),s['key'])}</div>
    <div style="text-align:right;color:#2e7d32;font-size:.75em">1:{s['rr1']:.1f} · <b style="color:#4caf50">💰 +${s['g1']:.2f}</b></div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 140px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#43a047;font-size:.68em;font-weight:700;text-transform:uppercase">🎯 TP 2</div>
    <div style="color:#69f0ae;font-size:1.05em;font-weight:700;font-family:'Courier New',mono">{fmt(s['tp2'],s['key'])}</div>
    <div style="color:#1b5e20;font-size:.75em">{dist_fmt(abs(s['tp2']-s['entry']),s['key'])}</div>
    <div style="text-align:right;color:#2e7d32;font-size:.75em">1:{s['rr2']:.1f} · <b style="color:#43a047">💰 +${s['g2']:.2f}</b></div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 140px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#66bb6a;font-size:.68em;font-weight:700;text-transform:uppercase">🎯 TP 3</div>
    <div style="color:#69f0ae;font-size:1.05em;font-weight:700;font-family:'Courier New',mono">{fmt(s['tp3'],s['key'])}</div>
    <div style="color:#1b5e20;font-size:.75em">{dist_fmt(abs(s['tp3']-s['entry']),s['key'])}</div>
    <div style="text-align:right;color:#2e7d32;font-size:.75em">1:{s['rr3']:.1f} · <b style="color:#66bb6a">💰 +${s['g3']:.2f}</b></div>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr 100px 140px;align-items:center;padding:8px 0">
    <div style="color:#00e676;font-size:.68em;font-weight:900;text-transform:uppercase">💎 TP 4</div>
    <div style="color:#00e676;font-size:1.1em;font-weight:900;font-family:'Courier New',mono">{fmt(s['tp4'],s['key'])}</div>
    <div style="color:#00695c;font-size:.75em">{dist_fmt(abs(s['tp4']-s['entry']),s['key'])}</div>
    <div style="text-align:right;color:#00695c;font-size:.75em">1:{s['rr4']:.1f} · <b style="color:#00e676">💰 +${s['g4']:.2f}</b></div>
  </div>
  <div style="background:#050510;border:1px solid {es_c}33;border-radius:6px;padding:9px 14px;margin-top:8px">
    <div style="color:{es_c};font-weight:900;font-size:.85em">⚡ ACCIÓN: {"ENTRAR — precio cerca de la entrada ideal" if es_txt=="CERCA DE ENTRADA" else ("ESPERAR — aguardar pullback hacia la entrada" if es_txt=="ESPERAR PULLBACK" else "NO ENTRAR — la entrada ya pasó")}</div>
    <div style="color:#252540;font-size:.72em;margin-top:4px">
      🚫 NO ENTRAR SI: el precio avanzó más del 35% a TP1 · está cerca del SL · la señal cambió · se extendió la vela.
    </div>
  </div>
  <div style="display:flex;gap:14px;margin-top:8px;font-size:.72em;flex-wrap:wrap">
    <span style="color:#383858">Score: <b style="color:{ac}">{sc}/100</b></span>
    <span style="color:#383858">IA: <b style="color:#ce93d8">{s.get('ia_votos',0)}/{s.get('ia_total',1)} · {s['ia_conf']}%</b></span>
    <span style="color:#383858">Tendencia 1H: <b style="color:{trend_c}">{trend_t}</b></span>
    {f'<span style="color:#383858">Patrón: <b style="color:#82b1ff">{_pat}</b></span>' if _pat != "—" else ""}
    <span style="color:#383858">Abierta: <b style="color:#555">{s["ts_open"][11:16]}</b></span>
  </div>
</div>
</div>""", unsafe_allow_html=True)

def _render_waiting_row(key, r):
    p   = live.get(key) or r.get("ind",{}).get("price")
    ind = r.get("ind",{})
    dc  = "#69f0ae" if r["dir"]=="buy" else "#ff8a80"
    dt  = "⏳ POSIBLE BUY" if r["dir"]=="buy" else "⏳ POSIBLE SELL"
    motivo = r.get("motivo","esperar confirmación")
    tp1_e = (p or 0)+ind.get("atr",0)*0.8 if r["dir"]=="buy" else (p or 0)-ind.get("atr",0)*0.8
    fuente = _cache_fuentes.get(key,"—")
    return (f'<tr style="background:#090910;border-left:3px solid #1a1a30">'
        f'<td style="padding:7px 10px;color:#ccc;font-weight:700">{ACTIVOS[key][1].split()[0]}</td>'
        f'<td style="padding:7px 10px"><span style="color:{dc};font-weight:700;font-size:.78em">{dt}</span></td>'
        f'<td style="padding:7px 10px;color:#9575cd;font-weight:800">{r["score"]}/100</td>'
        f'<td style="padding:7px 10px;color:#82b1ff;font-family:monospace;font-size:.83em">{fmt(p,key)}</td>'
        f'<td style="padding:7px 10px;color:#69f0ae;font-family:monospace;font-size:.78em">{fmt(tp1_e,key)}</td>'
        f'<td style="padding:7px 10px;color:#333;font-size:.7em">{motivo[:30]}</td>'
        f'<td style="padding:7px 10px;color:#252540;font-size:.68em">{fuente}</td></tr>')

def _render_radar_rows(cat_keys):
    rows = ""
    for key in cat_keys:
        if key not in resultados: continue
        r   = resultados[key]; ind = r.get("ind") or {}
        p   = live.get(key) or ind.get("price")
        sc  = r.get("score",0); dec = r.get("decision","—")
        adx = r.get("adx",0) or ind.get("adx",0)
        dir_ = r.get("dir"); fuente = _cache_fuentes.get(key,"—")
        if dec=="RECOMENDAR" and dir_=="buy":
            bg="#010d04"; bl="3px solid #00c853"; sc_c="#00e676"
            dir_cell='<span style="background:#00e676;color:#000;padding:2px 9px;border-radius:3px;font-weight:900;font-size:.75em">▲ COMPRA</span>'
            e_cell='<span style="color:#00e676;font-weight:800">✅ SÍ</span>'
        elif dec=="RECOMENDAR" and dir_=="sell":
            bg="#0d0101"; bl="3px solid #c62828"; sc_c="#ff1744"
            dir_cell='<span style="background:#ff1744;color:#fff;padding:2px 9px;border-radius:3px;font-weight:900;font-size:.75em">▼ VENTA</span>'
            e_cell='<span style="color:#ff5252;font-weight:800">✅ SÍ</span>'
        elif dec=="ESPERAR" and dir_=="buy":
            bg="#080e07"; bl="3px solid #1a3a1a"; sc_c="#69f0ae"
            dir_cell='<span style="color:#69f0ae;font-size:.75em;font-weight:700">⏳ POSIBLE BUY</span>'
            e_cell='<span style="color:#ffd600">⏳ ESPERAR</span>'
        elif dec=="ESPERAR" and dir_=="sell":
            bg="#0e0707"; bl="3px solid #3a1a1a"; sc_c="#ff8a80"
            dir_cell='<span style="color:#ff8a80;font-size:.75em;font-weight:700">⏳ POSIBLE SELL</span>'
            e_cell='<span style="color:#ffd600">⏳ ESPERAR</span>'
        elif dec=="BLOQUEADA":
            bg="#080808"; bl="3px solid #111"; sc_c="#1e1e30"
            dir_cell='<span style="color:#1e1e30;font-size:.72em">🔒 BLOQUEADA</span>'
            e_cell='<span style="color:#333">🔒 NO</span>'
        elif dec=="OBSERVAR":
            bg="#06060f"; bl="3px solid #1a1a3a"; sc_c="#42a5f5"
            dir_cell='<span style="color:#42a5f5;font-size:.75em">👀 OBSERVAR</span>'
            e_cell='<span style="color:#42a5f5">👀 SOLO OBSERVAR</span>'
        else:
            bg="#09090f"; bl="3px solid #181828"; sc_c="#2a2a48"
            dir_cell='<span style="color:#2a2a48;font-size:.75em">🚫 NO OPERAR</span>'
            e_cell='<span style="color:#2a2a48">🚫 NO</span>'
        abierto, _ = mercado_abierto(key)
        if not abierto:
            e_cell = '<span style="color:#333">🕒 CERRADO</span>'
        rows += (f'<tr style="background:{bg};border-left:{bl}">'
            f'<td style="padding:6px 8px;color:#999;font-weight:700">{ACTIVOS[key][1].split()[0]}</td>'
            f'<td style="padding:6px 8px;color:#d8d8f8;font-family:monospace">{fmt(p,key) if p else "—"}</td>'
            f'<td style="padding:6px 8px">{dir_cell}</td>'
            f'<td style="padding:6px 8px;color:{sc_c};font-weight:800">{sc}/100</td>'
            f'<td style="padding:6px 8px;font-size:.8em">{e_cell}</td>'
            f'<td style="padding:6px 8px;color:{"#00e676" if adx>=20 else "#ffd600" if adx>=15 else "#ff5252"}">{adx:.0f}</td>'
            f'<td style="padding:6px 8px;color:#383858;font-size:.68em">{fuente}</td></tr>')
    return rows

def _render_tab_signals(cat_keys, tab_name):
    tab_abiertas = [s for s in abiertas if s.get("key") in cat_keys]
    tab_esperar_ab = []
    for s in tab_abiertas:
        pv = live.get(s["key"]) or s["entry"]
        es_txt, _ = calcular_entry_status(pv, s["entry"], s["tp1"])
        if es_txt == "ENTRADA TARDÍA":
            tab_esperar_ab.append(s)
    tab_entrar = [s for s in tab_abiertas if s not in tab_esperar_ab]

    if tab_entrar:
        st.markdown(f'<div class="sec-hdr">🟢 SEÑALES ACTIVAS — {tab_name}</div>', unsafe_allow_html=True)
        for s in tab_entrar:
            _render_signal_card(s)
    else:
        if on:
            st.markdown(
                f'<div class="no-signals" style="margin:8px 0">'
                f'<div style="font-size:.95em;color:#d8d8f8">🚫 Sin señales activas en {tab_name}</div>'
                f'<div style="color:#1e1e38;font-size:.78em;margin-top:4px">Scanner activo — esperando setup válido.</div>'
                f'</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="no-signals" style="margin:8px 0">'
                f'<div style="font-size:.95em;color:#d8d8f8">🚫 Sin señales en {tab_name}</div>'
                f'<div style="color:#1e1e38;font-size:.78em;margin-top:4px">Presiona <b style="color:#d8d8f8">▶ INICIAR</b> para activar el scanner.</div>'
                f'</div>', unsafe_allow_html=True)

    esp_radar = [(k,r) for k,r in resultados.items()
                 if k in cat_keys and r.get("dir") and r.get("decision")=="ESPERAR" and r.get("score",0)>=70]
    esp_radar.sort(key=lambda x: x[1]["score"], reverse=True)
    if esp_radar or tab_esperar_ab:
        _n_e = len(esp_radar)+len(tab_esperar_ab)
        st.markdown(f'<div class="sec-hdr" style="margin-top:8px">🟡 EN ESPERA · {tab_name} &nbsp;'
            f'<span style="color:#ffd600;font-size:.8em">({_n_e} posibles setups)</span></div>', unsafe_allow_html=True)
        for s in tab_esperar_ab:
            pv = live.get(s["key"]) or s["entry"]
            dc = "#69f0ae" if s["dir"]=="buy" else "#ff8a80"
            dt = "⏳ POSIBLE BUY" if s["dir"]=="buy" else "⏳ POSIBLE SELL"
            st.markdown(f'<div class="sig-wait" style="padding:12px 18px;border-left:3px solid #ffd600">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">'
                f'<div><span style="color:#ffd600;font-weight:900;font-size:.8em">{dt}</span>'
                f'&nbsp;<b style="color:#ccc;font-size:.9em">{s["nombre"]}</b>'
                f'&nbsp;<span style="color:#333;font-size:.72em">{s.get("score",0)}/100</span></div>'
                f'<div><span style="color:#444;font-size:.72em">Precio: </span>'
                f'<b style="color:#82b1ff">{fmt(pv,s["key"])}</b>'
                f'&nbsp;<span style="color:#555;font-size:.7em">Entrada: {fmt(s["entry"],s["key"])}</span></div>'
                f'<span style="background:#1a1000;border:1px solid #ffd60044;color:#ffd600;'
                f'padding:2px 10px;border-radius:3px;font-size:.72em;font-weight:800">⏳ ESPERAR - NO ENTRAR</span>'
                f'</div></div>', unsafe_allow_html=True)
        if esp_radar:
            rows_e = "".join(_render_waiting_row(k,r) for k,r in esp_radar[:6])
            st.markdown(f"""<table class="radar-tbl"><thead><tr>
<th>Activo</th><th>Posible señal</th><th>Score</th>
<th>Precio</th><th>TP1 est.</th><th>Motivo</th><th>Fuente</th>
</tr></thead><tbody>{rows_e}</tbody></table>
<div style="color:#1a1a38;font-size:.7em;margin-top:5px">
⚠ NO ENTRAR — esperar confirmación. No son señales activas todavía.
</div>""", unsafe_allow_html=True)

    rows_r = _render_radar_rows(cat_keys)
    if rows_r:
        with st.expander("📡 Radar técnico", expanded=False):
            st.markdown(f"""<table class="radar-tbl"><thead><tr>
<th>Activo</th><th>Precio</th><th>Señal</th><th>Score</th>
<th>¿Entrar?</th><th>ADX</th><th>Fuente</th></tr></thead><tbody>{rows_r}</tbody></table>""",
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: 🥇 METALES
# ══════════════════════════════════════════════════════════════════════════════
with tab_metals:
    if _usar_gold_ui:
        _gd_ok      = _gd.get("ok", False)
        _gd_dec     = _gd.get("decision", "—")
        _gd_price   = _gd.get("price")
        _gd_bid     = _gd.get("bid")
        _gd_ask     = _gd.get("ask")
        _gd_spread  = _gd.get("spread")
        _gd_sym     = _gd.get("mt5_symbol", "—")
        _gd_tend    = _gd.get("tendencia_m15", "neutral")
        _gd_setup   = _gd.get("setup_m5", "—")
        _gd_conf    = _gd.get("conf_m1", "—")
        _gd_score   = _gd.get("score", 0)
        _gd_dir     = _gd.get("dir")
        _gd_patron  = _gd.get("patron", "—")
        _gd_motivo  = _gd.get("motivo", "—")
        _gd_ia      = _gd.get("ia_nota", "")
        _gd_ts      = _gd.get("ts", "—")
        _gd_clase   = _gd.get("clase", "—")
        _gd_nciclo  = _gd.get("nuevo_ciclo", False)
        _gd_m1b     = _gd.get("m1_bars", 0)
        _gd_m5b     = _gd.get("m5_bars", 0)
        _gd_m15b    = _gd.get("m15_bars", 0)
        _gd_error   = _gd.get("error") or ("" if _gd_ok else _gd_motivo)

        if not _gd:
            _estado_gold = "SIN DATOS"; _estado_c = "#555"
        elif not _gd_ok:
            _estado_gold = "SIN DATOS / ERROR"; _estado_c = "#ff5252"
        elif _gd_dec == "BLOQUEADA":
            _estado_gold = "BLOQUEADA"; _estado_c = "#ff9800"
        elif _gd_dec == "ESPERAR":
            _estado_gold = "ESPERAR"; _estado_c = "#ffd600"
        elif _gd_dec == "RECOMENDAR":
            _estado_gold = "SEÑAL ACTIVA"; _estado_c = "#00e676"
        elif _gd_dec == "OBSERVAR":
            _estado_gold = "OBSERVAR"; _estado_c = "#42a5f5"
        else:
            _estado_gold = "NO OPERAR"; _estado_c = "#444"

        _tend_icon = "▲" if _gd_tend == "buy" else ("▼" if _gd_tend == "sell" else "◆")
        _tend_c    = "#00e676" if _gd_tend == "buy" else ("#ff5252" if _gd_tend == "sell" else "#555")
        _spread_ok = _gd_spread is not None and _gd_spread <= st.session_state.get("gold_spread_max_val", 3.0)
        _spread_c  = "#00e676" if _spread_ok else "#ff9800"
        _price_str = f"{_gd_price:,.2f}" if _gd_price else "—"
        _bid_str   = f"{_gd_bid:,.2f}"   if _gd_bid   else "—"
        _ask_str   = f"{_gd_ask:,.2f}"   if _gd_ask   else "—"
        _spread_str= f"{_gd_spread:.2f}" if _gd_spread is not None else "—"
        _ciclo_tag = '<span style="color:#ffd600;font-size:.65em">🕯 Nueva vela M5</span>' if _gd_nciclo else ""

        st.markdown('<div class="sec-hdr">🟡 ORO / XAUUSD M5 &nbsp;<span style="color:#ffd600;font-size:.75em">◆ MT5 / Weltrade</span></div>', unsafe_allow_html=True)
        st.markdown(f"""<div style="background:linear-gradient(135deg,#0a0800,#15120000);
border:1px solid #3a2d00;border-left:5px solid #ffd600;border-radius:12px;
padding:14px 20px;margin:6px 0;box-shadow:0 0 18px rgba(255,214,0,.12)">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px">
  <div>
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:2px">🟡 XAUUSD · ORO M5 &nbsp; {_ciclo_tag}</div>
    <div style="color:#ffd600;font-size:1.3em;font-weight:900;margin:3px 0">
      {f"{'▲ LONG' if _gd_dir=='buy' else '▼ SHORT'}" if _gd_dir else "◆ Sin señal"}
      &nbsp;<span style="font-size:.65em;color:#888">{_gd_clase} · {_gd_score}/100</span>
    </div>
    <div style="color:#555;font-size:.72em;margin-top:2px">
      Patrón: <b style="color:#ffd600">{_gd_patron}</b> &nbsp;·&nbsp;
      <span style="color:{_estado_c};font-weight:800">{_estado_gold}</span>
    </div>
  </div>
  <div style="text-align:right">
    <div style="color:#888;font-size:.65em">📡 {_gd_sym if _gd_sym and _gd_sym != '—' else 'buscando...'}</div>
    <div style="color:#fff;font-size:1.5em;font-weight:900;font-family:'Courier New',mono">{_price_str}</div>
    <div style="color:{_spread_c};font-size:.75em">Spread: {_spread_str}</div>
    <div style="color:#252540;font-size:.63em">Actualizado: {_gd_ts}</div>
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px;
padding-top:10px;border-top:1px solid #1a1600">
  <div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;padding:8px 12px">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:1.5px">M15 Tendencia</div>
    <div style="color:{_tend_c};font-weight:800;font-size:.9em">{_tend_icon} {_gd_tend.upper()}</div>
  </div>
  <div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;padding:8px 12px">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:1.5px">M5 Setup</div>
    <div style="color:#ffd600;font-size:.78em;font-weight:700">{_gd_setup[:30] if _gd_setup else '—'}</div>
  </div>
  <div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;padding:8px 12px">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:1.5px">M1 Confirmación</div>
    <div style="color:#82b1ff;font-size:.78em;font-weight:700">{_gd_conf}</div>
  </div>
</div>
<div style="display:flex;gap:14px;margin-top:8px;font-size:.7em;flex-wrap:wrap">
  <span style="color:#333">Bid: <b style="color:#aaa">{_bid_str}</b></span>
  <span style="color:#333">Ask: <b style="color:#aaa">{_ask_str}</b></span>
  <span style="color:#333">M1: <b style="color:#444">{_gd_m1b}v</b></span>
  <span style="color:#333">M5: <b style="color:#444">{_gd_m5b}v</b></span>
  <span style="color:#333">M15: <b style="color:#444">{_gd_m15b}v</b></span>
  {f'<span style="color:#ff9800">⚠ {_gd_error[:60]}</span>' if _gd_error and not _gd_ok else ""}
  {f'<span style="color:#444;font-style:italic">{_gd_motivo[:50]}</span>' if _gd_motivo and _gd_dec not in ("RECOMENDAR",) else ""}
</div>
</div>""", unsafe_allow_html=True)

        if _gd_dir and _gd_dec == "RECOMENDAR":
            _gc = "#00e676" if _gd_dir == "buy" else "#ff1744"
            _gbg = "sig-premium" if _gd_score >= 90 else "sig-alta" if _gd_score >= 80 else "sig-obs"
            _gentry = _gd.get("entry", 0); _gsl = _gd.get("sl", 0)
            _gtp1 = _gd.get("tp1", 0); _gtp2 = _gd.get("tp2", 0)
            _gtp3 = _gd.get("tp3", 0); _gtp4 = _gd.get("tp4", 0)
            _gatr = _gd.get("ind_m5", {}).get("atr", 0)
            st.markdown(f"""<div class="{_gbg}">
<div style="display:flex;align-items:stretch;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.06)">
  <div style="background:{_gc};padding:14px 22px;display:flex;align-items:center;min-width:170px">
    <div>
      <div style="color:{'#000' if _gd_dir=='buy' else '#fff'};font-size:.58em;text-transform:uppercase;letter-spacing:2px;font-weight:700">✅ ORO · XAUUSD M5</div>
      <div style="color:{'#000' if _gd_dir=='buy' else '#fff'};font-size:1.2em;font-weight:900;margin-top:2px">{'▲ LONG / BUY' if _gd_dir=='buy' else '▼ SHORT / SELL'}</div>
      <div style="color:{'#00000077' if _gd_dir=='buy' else '#ffffff55'};font-size:.6em">Scalping · {_gd_patron}</div>
    </div>
  </div>
  <div style="padding:12px 18px;flex:1">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:2px">📈 XAUUSD / ORO · M5</div>
    <div style="color:#ffd600;font-size:1.1em;font-weight:900;margin:2px 0">XAU/USD Oro</div>
    <div style="display:flex;gap:8px;align-items:center;margin-top:4px;flex-wrap:wrap">
      <span style="color:{_gc};font-size:.75em;font-weight:800;background:rgba(255,255,255,.04);padding:2px 8px;border-radius:3px">⭐ {_gd_clase} · {_gd_score}/100</span>
      <span style="background:#12082a;border:1px solid #3d1278;color:#ce93d8;padding:2px 8px;border-radius:3px;font-size:.7em">🕯 {_gd_patron}</span>
      <span style="color:#ffd600;font-size:.68em">🟡 MT5 / Weltrade</span>
    </div>
    {f'<div style="color:#888;font-size:.72em;margin-top:6px;font-style:italic">{_gd_ia[:90]}</div>' if _gd_ia else ""}
  </div>
  <div style="padding:12px 20px;text-align:right;border-left:1px solid rgba(255,255,255,.05)">
    <div class="px-lbl">📍 PRECIO ACTUAL</div>
    <div style="color:#ffd600;font-size:1.4em;font-weight:900;font-family:'Courier New',mono">{_price_str}</div>
    <div style="color:{_spread_c};font-size:.72em">Spread: {_spread_str}</div>
  </div>
</div>
<div style="padding:4px 20px 10px">
  <div style="display:grid;grid-template-columns:120px 1fr;align-items:center;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04)">
    <div style="color:#383858;font-size:.68em;font-weight:700;text-transform:uppercase">🎯 ENTRADA</div>
    <div style="color:#ffd600;font-size:1.1em;font-weight:800;font-family:'Courier New',mono">{_gentry:,.2f}</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr;align-items:center;padding:7px 0;border-bottom:2px solid rgba(255,255,255,.07)">
    <div style="color:#ff5252;font-size:.68em;font-weight:700;text-transform:uppercase">🛑 STOP LOSS</div>
    <div style="color:#ff5252;font-size:1.1em;font-weight:800;font-family:'Courier New',mono">{_gsl:,.2f}</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr 1fr;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#388e3c;font-size:.67em;font-weight:700;text-transform:uppercase">🎯 TP 1</div>
    <div style="color:#69f0ae;font-size:1em;font-weight:700;font-family:'Courier New',mono">{_gtp1:,.2f}</div>
    <div style="color:#2e7d32;font-size:.72em">ATR×0.8 ({abs(_gtp1-_gentry):.2f})</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr 1fr;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#43a047;font-size:.67em;font-weight:700;text-transform:uppercase">🎯 TP 2</div>
    <div style="color:#69f0ae;font-size:1em;font-weight:700;font-family:'Courier New',mono">{_gtp2:,.2f}</div>
    <div style="color:#2e7d32;font-size:.72em">ATR×2.0 ({abs(_gtp2-_gentry):.2f})</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr 1fr;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#66bb6a;font-size:.67em;font-weight:700;text-transform:uppercase">🎯 TP 3</div>
    <div style="color:#69f0ae;font-size:1em;font-weight:700;font-family:'Courier New',mono">{_gtp3:,.2f}</div>
    <div style="color:#2e7d32;font-size:.72em">ATR×3.5 ({abs(_gtp3-_gentry):.2f})</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr 1fr;align-items:center;padding:7px 0">
    <div style="color:#ffd600;font-size:.67em;font-weight:900;text-transform:uppercase">💎 TP 4</div>
    <div style="color:#ffd600;font-size:1.1em;font-weight:900;font-family:'Courier New',mono">{_gtp4:,.2f}</div>
    <div style="color:#a37900;font-size:.72em">ATR×5.5 ({abs(_gtp4-_gentry):.2f})</div>
  </div>
  <div style="display:flex;gap:12px;margin-top:6px;font-size:.7em;flex-wrap:wrap">
    <span style="color:#383858">Score: <b style="color:#ffd600">{_gd_score}/100</b></span>
    <span style="color:#383858">M15: <b style="color:{_tend_c}">{_tend_icon} {_gd_tend}</b></span>
    <span style="color:#383858">M5: <b style="color:#ffd600">{_gd_setup[:28] if _gd_setup else '—'}</b></span>
    <span style="color:#383858">M1: <b style="color:#82b1ff">{_gd_conf}</b></span>
    <span style="color:#383858">ATR: <b style="color:#555">{_gatr:.2f}</b></span>
    <span style="color:#383858">Fuente: <b style="color:#ffd600">MT5 / Weltrade</b></span>
  </div>
</div>
</div>""", unsafe_allow_html=True)

        _g_stats = stats_gold_summary(stats)
        if _g_stats["total"] > 0:
            _wr_g = _g_stats["winrate"]
            _wrc  = "#00e676" if _wr_g >= 60 else ("#ffd600" if _wr_g >= 50 else "#ff5252")
            st.markdown(f'<div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;'
                f'padding:8px 14px;margin-top:4px;display:flex;gap:16px;flex-wrap:wrap;font-size:.72em">'
                f'<span style="color:#444">XAUUSD: <b style="color:#aaa">{_g_stats["total"]}</b></span>'
                f'<span style="color:#444">✅ <b style="color:#00e676">{_g_stats["wins"]}</b></span>'
                f'<span style="color:#444">❌ <b style="color:#ff5252">{_g_stats["losses"]}</b></span>'
                f'<span style="color:#444">WR: <b style="color:{_wrc}">{_wr_g:.1f}%</b></span>'
                f'<span style="color:#444">Score ganador: <b style="color:#555">{_g_stats["score_avg_win"]:.0f}</b></span>'
                f'</div>', unsafe_allow_html=True)

        if es_avanzado:
            with st.expander("🪙 Debug XAUUSD", expanded=False):
                _ms_g = _mt5_status
                _gld  = st.session_state.get("gold_live_data", {})
                _clr_mt5 = "#00e676" if _ms_g.get("connected") else "#ff5252"
                st.markdown(f'<div style="font-size:.72em;line-height:1.9;color:#555">'
                    f'<b style="color:{_clr_mt5}">MT5: {"CONECTADO" if _ms_g.get("connected") else "DESCONECTADO"}</b><br>'
                    f'Broker: {_ms_g.get("broker","—")}<br>Cuenta: {_ms_g.get("account","—")}<br>'
                    f'Símbolo: <b style="color:#ffd600">{_gld.get("mt5_symbol","no encontrado")}</b><br>'
                    f'Bid: {_gld.get("bid","—")} · Ask: {_gld.get("ask","—")} · Spread: {_gld.get("spread","—")}<br>'
                    f'M1: <b>{_gd.get("m1_bars",0)}</b> · M5: <b>{_gd.get("m5_bars",0)}</b> · M15: <b>{_gd.get("m15_bars",0)}</b><br>'
                    f'Score: <b style="color:#ffd600">{_gd.get("score",0)}/100</b> · Decisión: <b>{_gd.get("decision","—")}</b><br>'
                    f'Patrón: {_gd.get("patron","—")} · M15: {_gd.get("tendencia_m15","—")} · M5: {_gd.get("setup_m5","—")}<br>'
                    f'Error: <span style="color:#ff9800">{_gld.get("error","—")}</span> · Act: {_gd.get("ts","—")}'
                    f'</div>', unsafe_allow_html=True)
                _sbd = _gd.get("score_bd", {})
                if _sbd:
                    _sbd_html = "".join([
                        f'<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid #0e0e1e">'
                        f'<span style="color:#444;font-size:.7em">{k}</span>'
                        f'<span style="color:#ffd600;font-size:.7em">{v} pts</span></div>'
                        for k, v in _sbd.items()])
                    st.markdown(f'<div style="background:#08080f;border:1px solid #12121e;border-radius:6px;'
                        f'padding:8px 10px;margin-top:6px">{_sbd_html}</div>', unsafe_allow_html=True)

    _render_tab_signals(_KEYS_METALS, "METALES")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: 💱 FOREX
# ══════════════════════════════════════════════════════════════════════════════
with tab_forex:
    from datetime import timezone as _tz_fx
    _now_fx = datetime.now(_tz_fx.utc)
    _h_fx = _now_fx.hour
    if 22 <= _h_fx or _h_fx < 8:
        _ses = "🌏 ASIA"; _ses_c = "#42a5f5"
    elif 7 <= _h_fx < 10:
        _ses = "🌍+🌏 OVERLAP Asia/Europa"; _ses_c = "#ffd600"
    elif 13 <= _h_fx < 16:
        _ses = "🌍+🌎 OVERLAP Europa/NY"; _ses_c = "#ffd600"
    elif 8 <= _h_fx < 16:
        _ses = "🌍 EUROPA"; _ses_c = "#69f0ae"
    elif 13 <= _h_fx < 22:
        _ses = "🌎 NUEVA YORK"; _ses_c = "#ff9800"
    else:
        _ses = "🌙 Pre-sesión"; _ses_c = "#555"
    st.markdown(f'<div style="background:#09090f;border:1px solid #1a1a3a;border-radius:8px;'
        f'padding:8px 16px;margin-bottom:10px;font-size:.8em">'
        f'Sesión activa: <b style="color:{_ses_c}">{_ses}</b> &nbsp;·&nbsp; '
        f'<span style="color:#333">UTC {_now_fx.strftime("%H:%M")}</span></div>',
        unsafe_allow_html=True)
    _render_tab_signals(_KEYS_FOREX, "FOREX")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: 📊 ÍNDICES
# ══════════════════════════════════════════════════════════════════════════════
with tab_idx:
    _render_tab_signals(_KEYS_INDICES, "ÍNDICES")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: 🟣 CRYPTO
# ══════════════════════════════════════════════════════════════════════════════
with tab_crypto:
    st.markdown('<div style="background:#09090f;border:1px solid #1a1a3a;border-radius:8px;'
        'padding:8px 16px;margin-bottom:10px;font-size:.8em">'
        '<span style="color:#9575cd">🟣 Crypto — disponible 24/7 incluidos fines de semana</span>'
        '</div>', unsafe_allow_html=True)
    _render_tab_signals(_KEYS_CRYPTO, "CRYPTO")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: 🔷 SINTÉTICOS
# ══════════════════════════════════════════════════════════════════════════════
with tab_sint:
    if usar_sinteticos:
        st.markdown('<div class="sec-hdr">⚡ Sintéticos Deriv / MT5 &nbsp;'
            '<span style="color:#26c6da;font-size:.7em">◆ Fuente: Deriv WS</span></div>',
            unsafe_allow_html=True)
        if not resultados_sint:
            st.markdown('<div class="no-signals">⏳ Presiona ▶ INICIAR para analizar sintéticos.</div>',
                unsafe_allow_html=True)
        else:
            sint_activas = [(k,r) for k,r in resultados_sint.items() if r.get("decision")=="RECOMENDAR"]
            sint_espera  = [(k,r) for k,r in resultados_sint.items() if r.get("decision")=="ESPERAR"]
            sint_resto   = [(k,r) for k,r in resultados_sint.items() if r.get("decision") not in ("RECOMENDAR","ESPERAR")]
            rows_s = ""
            for key,r in sorted(sint_activas+sint_espera+sint_resto, key=lambda x: x[1].get("score",0), reverse=True):
                ind   = r.get("ind") or {}; dec = r.get("decision","—"); sc = r.get("score",0)
                dir_  = r.get("dir"); nombre = SINTETICOS.get(key,key)
                p     = r.get("price") or _sint_get_price(key)
                atr   = r.get("atr", 0) or ind.get("atr",0) or ind.get("atr_mid",0)
                tv    = r.get("ticks_s", 0); src = r.get("fuente","Deriv WS"); estat = r.get("estado_data","—")
                if dec=="RECOMENDAR" and dir_=="buy":
                    bg="#010d04"; bl="3px solid #00c853"; sc_c="#00e676"
                    dir_cell='<span style="background:#00e676;color:#000;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.75em">▲ COMPRA</span>'
                elif dec=="RECOMENDAR" and dir_=="sell":
                    bg="#0d0101"; bl="3px solid #c62828"; sc_c="#ff1744"
                    dir_cell='<span style="background:#ff1744;color:#fff;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.75em">▼ VENTA</span>'
                elif dec=="ESPERAR":
                    bg="#090a0e"; bl="3px solid #1a1a3a"; sc_c="#9575cd"
                    dir_cell=f'<span style="color:{"#69f0ae" if dir_=="buy" else "#ff8a80"};font-size:.75em">⏳ POSIBLE {"BUY" if dir_=="buy" else "SELL"} - ESPERAR</span>'
                elif dec=="BLOQUEADA":
                    bg="#080808"; bl="3px solid #111"; sc_c="#1e1e30"
                    dir_cell='<span style="color:#1e1e30;font-size:.72em">🔒 SIN DATOS</span>'
                else:
                    bg="#09090f"; bl="3px solid #181828"; sc_c="#2a2a48"
                    dir_cell='<span style="color:#2a2a48;font-size:.75em">⚫ NO OPERAR</span>'
                p_str  = f"{p:.4f}" if p and p<100 else (f"{p:,.2f}" if p else "—")
                atr_str= f"{atr:.4f}" if atr and atr<10 else (f"{atr:.2f}" if atr else "—")
                tv_str = f"{tv:.1f}/s" if tv else "—"
                es_c = "#00e676" if estat=="OK" else ("#ff5252" if estat=="SIN DATOS" else "#ffd600")
                rows_s += (f'<tr style="background:{bg};border-left:{bl}">'
                    f'<td style="padding:5px 8px;color:#aaa;font-weight:700;font-size:.78em">{key}</td>'
                    f'<td style="padding:5px 8px;color:#666;font-size:.7em">{nombre[:22]}</td>'
                    f'<td style="padding:5px 8px;color:#888;font-family:monospace;font-size:.78em">{p_str}</td>'
                    f'<td style="padding:5px 8px">{dir_cell}</td>'
                    f'<td style="padding:5px 8px;color:{sc_c};font-weight:800">{sc}/100</td>'
                    f'<td style="padding:5px 8px;color:#555;font-size:.72em;font-family:monospace">{atr_str}</td>'
                    f'<td style="padding:5px 8px;color:#444;font-size:.72em">{tv_str}</td>'
                    f'<td style="padding:5px 8px;color:#26c6da;font-size:.65em">{src}</td>'
                    f'<td style="padding:5px 8px;color:{es_c};font-size:.65em;font-weight:700">{estat}</td></tr>')
            if rows_s:
                st.markdown(f"""<table class="radar-tbl"><thead><tr>
<th>Símbolo</th><th>Nombre</th><th>Precio</th><th>Señal</th>
<th>Score</th><th>ATR</th><th>Ticks/s</th><th>Fuente</th><th>Estado</th>
</tr></thead><tbody>{rows_s}</tbody></table>""", unsafe_allow_html=True)
    else:
        st.markdown('<div class="no-signals">Activa Sintéticos Deriv en el sidebar para verlos aquí.</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: ⚡ WELTRADE
# ══════════════════════════════════════════════════════════════════════════════
with tab_welt:
    resultados_welt = st.session_state.get("resultados_welt", {})
    if usar_weltrade:
        st.markdown('<div class="sec-hdr">🟠 Índices Weltrade (MT5)</div>', unsafe_allow_html=True)
        st.markdown('<span style="color:#ff9800;font-size:.7em">◆ Fuente: MT5 Weltrade-Real</span>', unsafe_allow_html=True)
        if not _mt5_status.get("connected"):
            st.warning("MT5 desconectado — presiona 🔌 Conectar MT5 en el sidebar")
        elif not resultados_welt:
            st.markdown('<div class="no-signals">⏳ Presiona ▶ INICIAR para analizar índices Weltrade.</div>', unsafe_allow_html=True)
        else:
            rows_w = ""
            for key, r in sorted(resultados_welt.items(), key=lambda x: x[1].get("score",0), reverse=True):
                dec=r.get("decision","—"); sc=r.get("score",0); dir_=r.get("dir")
                nombre=WELTRADE_SINTETICOS.get(key,(key,"—"))[0]
                tipo=WELTRADE_SINTETICOS.get(key,(key,"volatility"))[1]
                p=r.get("price"); atr=r.get("atr",0)
                if dec=="RECOMENDAR" and dir_=="buy":
                    bg="#010d04"; bl="3px solid #00c853"; sc_c="#00e676"
                    dir_cell='<span style="background:#00e676;color:#000;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.75em">▲ COMPRA</span>'
                elif dec=="RECOMENDAR" and dir_=="sell":
                    bg="#0d0101"; bl="3px solid #c62828"; sc_c="#ff1744"
                    dir_cell='<span style="background:#ff1744;color:#fff;padding:2px 8px;border-radius:3px;font-weight:900;font-size:.75em">▼ VENTA</span>'
                elif dec=="ESPERAR":
                    bg="#090a0e"; bl="3px solid #1a1a3a"; sc_c="#9575cd"
                    dir_cell=f'<span style="color:{"#69f0ae" if dir_=="buy" else "#ff8a80"};font-size:.75em">⏳ {"BUY" if dir_=="buy" else "SELL"} - ESPERAR</span>'
                elif dec=="BLOQUEADA":
                    bg="#080808"; bl="3px solid #111"; sc_c="#1e1e30"
                    dir_cell='<span style="color:#555;font-size:.72em">🔒 SIN DATOS</span>'
                else:
                    bg="#09090f"; bl="3px solid #181828"; sc_c="#2a2a48"
                    dir_cell='<span style="color:#2a2a48;font-size:.75em">⚫ NO OPERAR</span>'
                p_str=f"{p:,.4f}" if p and p<100 else (f"{p:,.2f}" if p else "—")
                atr_str=f"{atr:.4f}" if atr and atr<10 else (f"{atr:.2f}" if atr else "—")
                tipo_badge={"gain":"🟢","pain":"🔴","flip":"🔄","trend":"📈","break":"💥","switch":"🔃","volatility":"〰️","special":"⭐"}.get(tipo,"◆")
                rows_w+=(f'<tr style="background:{bg};border-left:{bl}">'
                    f'<td style="padding:5px 8px;color:#ff9800;font-weight:700;font-size:.78em">{tipo_badge} {nombre}</td>'
                    f'<td style="padding:5px 8px;color:#888;font-family:monospace;font-size:.78em">{p_str}</td>'
                    f'<td style="padding:5px 8px">{dir_cell}</td>'
                    f'<td style="padding:5px 8px;color:{sc_c};font-weight:800">{sc}/100</td>'
                    f'<td style="padding:5px 8px;color:#555;font-size:.72em;font-family:monospace">{atr_str}</td>'
                    f'<td style="padding:5px 8px;color:#ff9800;font-size:.65em">{r.get("estado_data","—")}</td></tr>')
            if rows_w:
                st.markdown(f"""<table class="radar-tbl"><thead><tr>
<th>Índice</th><th>Precio</th><th>Señal</th><th>Score</th><th>ATR</th><th>Estado</th>
</tr></thead><tbody>{rows_w}</tbody></table>""", unsafe_allow_html=True)
    else:
        st.markdown('<div class="no-signals">Activa Weltrade MT5 en el sidebar para verlo aquí.</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: 📜 HISTORIAL
# ══════════════════════════════════════════════════════════════════════════════
with tab_hist:
    if stats["total"] > 0:
        wins=stats["wins"]; losses=stats["losses"]; total=stats["total"]
        pnl=stats["pnl_usd"]; tasa=wins/total*100 if total>0 else 0.0
        tasa_txt=f"{tasa:.1f}%" if total>=30 else f"{tasa:.1f}%*" if total>0 else "—"
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Efectividad", tasa_txt, f"{wins}G · {losses}P")
        c2.metric("P&L Total",   f"${pnl:+.2f}", f"{total} cerradas")
        c3.metric("Abiertas",    f"{len(abiertas)}/{max_ab}")
        c4.metric("Mejor racha", f"{stats.get('mejor_racha',0)} ✓")

    if spm:
        st.markdown('<div class="sec-hdr">📊 Efectividad por mercado</div>', unsafe_allow_html=True)
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

    cerradas = [s for s in stats["señales"] if s["estado"] in ("GANADA","PERDIDA","EXPIRADA")]
    if cerradas:
        st.markdown('<div class="sec-hdr">📜 HISTORIAL DE SEÑALES</div>', unsafe_allow_html=True)
        wins_h=stats["wins"]; losses_h=stats["losses"]; total_h=stats["total"]
        pnl_h=stats["pnl_usd"]; tasa_h=wins_h/total_h*100 if total_h>0 else 0.0
        tasa_txt_h=f"{tasa_h:.1f}%" if total_h>=30 else f"{tasa_h:.1f}%*" if total_h>0 else "—"
        st.markdown(f'<div style="display:flex;gap:20px;font-size:.8em;padding:6px 0;margin-bottom:6px;flex-wrap:wrap">'
            f'<span style="color:#252540">Total: <b style="color:#888">{total_h}</b></span>'
            f'<span style="color:#252540">✅ Ganadas: <b style="color:#00e676">{wins_h}</b></span>'
            f'<span style="color:#252540">❌ Perdidas: <b style="color:#ff5252">{losses_h}</b></span>'
            f'<span style="color:#252540">Win Rate: <b style="color:#ffd600">{tasa_txt_h}</b></span>'
            f'<span style="color:#252540">P&L: <b style="color:{"#00e676" if pnl_h>=0 else "#ff5252"}">'
            f'{"+" if pnl_h>=0 else ""}${pnl_h:.2f}</b></span></div>', unsafe_allow_html=True)
        for s in cerradas[:25]:
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
            dt = "▲ BUY" if s["dir"]=="buy" else "▼ SELL"
            sc = s.get("score",0)
            t_op = s["ts_open"][11:16]
            t_cl = ((s.get("ts_close") or ""))[11:16] or "—"
            st.markdown(f"""<div class="{css}">
<div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px">
  <div style="display:flex;align-items:center;gap:8px">
    {badge}
    <b style="color:{dc};font-size:.85em">{dt}</b>
    <b style="color:#c0c0e0">{s['nombre'].split()[0]}</b>
    <span style="color:#252540;font-size:.7em">{sc}/100</span>
  </div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;font-size:.76em">
    <span style="color:#444">Entrada: <b style="color:#82b1ff">{fmt(s['entry'],s['key'])}</b></span>
    <span style="color:#444">SL: <b style="color:#ff5252">{fmt(s['sl'],s['key'])}</b></span>
    <span style="color:#444">TP1: <b style="color:#69f0ae">{fmt(s['tp1'],s['key'])}</b></span>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    {res}
    <span style="color:#1e1e38;font-size:.7em">{t_op} → {t_cl}</span>
  </div>
</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown('<div class="no-signals">Sin señales cerradas todavía.</div>', unsafe_allow_html=True)

    if es_avanzado and _nsyms_main > 0:
        with st.expander("📋 Símbolos MT5 detectados", expanded=False):
            _sym_rows=""
            for _ak in list(ACTIVOS.keys()):
                _r = find_mt5_symbol(_ak)
                _c = "#00e676" if _r["found"] else "#ff5252"
                _sym_rows += (f'<tr><td style="color:#aaa;padding:4px 8px">{_ak}</td>'
                    f'<td style="color:{_c};font-weight:700;padding:4px 8px">{_r["symbol"] or "No encontrado"}</td>'
                    f'<td style="color:{_c};padding:4px 8px">{"MT5 ✅" if _r["found"] else "Fallback"}</td>'
                    f'<td style="color:#444;font-size:.82em;padding:4px 8px">{_r["reason"][:35]}</td></tr>')
            st.markdown('<table class="radar-tbl"><tr><th>Activo</th><th>Símbolo MT5</th><th>Estado</th><th>Detalle</th></tr>'
                + _sym_rows + "</table>", unsafe_allow_html=True)

if _usar_gold_ui:
    st.markdown('<div class="sec-hdr">🟡 ORO / XAUUSD M5 &nbsp;<span style="color:#ffd600;font-size:.75em">◆ MT5 / Weltrade</span></div>', unsafe_allow_html=True)
    _gd_ok      = _gd.get("ok", False)
    _gd_dec     = _gd.get("decision", "—")
    _gd_price   = _gd.get("price")
    _gd_bid     = _gd.get("bid")
    _gd_ask     = _gd.get("ask")
    _gd_spread  = _gd.get("spread")
    _gd_sym     = _gd.get("mt5_symbol", "—")
    _gd_tend    = _gd.get("tendencia_m15", "neutral")
    _gd_setup   = _gd.get("setup_m5", "—")
    _gd_conf    = _gd.get("conf_m1", "—")
    _gd_score   = _gd.get("score", 0)
    _gd_dir     = _gd.get("dir")
    _gd_patron  = _gd.get("patron", "—")
    _gd_motivo  = _gd.get("motivo", "—")
    _gd_ia      = _gd.get("ia_nota", "")
    _gd_ts      = _gd.get("ts", "—")
    _gd_clase   = _gd.get("clase", "—")
    _gd_nciclo  = _gd.get("nuevo_ciclo", False)
    _gd_m1b     = _gd.get("m1_bars", 0)
    _gd_m5b     = _gd.get("m5_bars", 0)
    _gd_m15b    = _gd.get("m15_bars", 0)
    _gd_error   = _gd.get("error") or ("" if _gd_ok else _gd_motivo)

    # Estado general
    if not _gd:
        _estado_gold = "SIN DATOS"; _estado_c = "#555"
    elif not _gd_ok:
        _estado_gold = "SIN DATOS / ERROR"; _estado_c = "#ff5252"
    elif _gd_dec == "BLOQUEADA":
        _estado_gold = "BLOQUEADA"; _estado_c = "#ff9800"
    elif _gd_dec == "ESPERAR":
        _estado_gold = "ESPERAR"; _estado_c = "#ffd600"
    elif _gd_dec == "RECOMENDAR":
        _estado_gold = "SEÑAL ACTIVA"; _estado_c = "#00e676"
    elif _gd_dec == "OBSERVAR":
        _estado_gold = "OBSERVAR"; _estado_c = "#42a5f5"
    else:
        _estado_gold = "NO OPERAR"; _estado_c = "#444"

    _tend_icon = "▲" if _gd_tend == "buy" else ("▼" if _gd_tend == "sell" else "◆")
    _tend_c    = "#00e676" if _gd_tend == "buy" else ("#ff5252" if _gd_tend == "sell" else "#555")
    _spread_ok = _gd_spread is not None and _gd_spread <= st.session_state.get("gold_spread_max_val", 3.0)
    _spread_c  = "#00e676" if _spread_ok else "#ff9800"
    _price_str = f"{_gd_price:,.2f}" if _gd_price else "—"
    _bid_str   = f"{_gd_bid:,.2f}"   if _gd_bid   else "—"
    _ask_str   = f"{_gd_ask:,.2f}"   if _gd_ask   else "—"
    _spread_str= f"{_gd_spread:.2f}" if _gd_spread is not None else "—"
    _ciclo_tag = '<span style="color:#ffd600;font-size:.65em">🕯 Nueva vela M5</span>' if _gd_nciclo else ""

    # Tarjeta estado
    st.markdown(f"""<div style="background:linear-gradient(135deg,#0a0800,#15120000);
border:1px solid #3a2d00;border-left:5px solid #ffd600;border-radius:12px;
padding:14px 20px;margin:6px 0;box-shadow:0 0 18px rgba(255,214,0,.12)">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px">
  <div>
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:2px">🟡 XAUUSD · ORO M5 &nbsp; {_ciclo_tag}</div>
    <div style="color:#ffd600;font-size:1.3em;font-weight:900;margin:3px 0">
      {f"{'▲ LONG' if _gd_dir=='buy' else '▼ SHORT'}" if _gd_dir else "◆ Sin señal"}
      &nbsp;<span style="font-size:.65em;color:#888">{_gd_clase} · {_gd_score}/100</span>
    </div>
    <div style="color:#555;font-size:.72em;margin-top:2px">
      Patrón: <b style="color:#ffd600">{_gd_patron}</b> &nbsp;·&nbsp;
      <span style="color:{_estado_c};font-weight:800">{_estado_gold}</span>
    </div>
  </div>
  <div style="text-align:right">
    <div style="color:#888;font-size:.65em">📡 {_gd_sym if _gd_sym and _gd_sym != '—' else 'buscando...'}</div>
    <div style="color:#fff;font-size:1.5em;font-weight:900;font-family:'Courier New',mono">{_price_str}</div>
    <div style="color:{_spread_c};font-size:.75em">Spread: {_spread_str}</div>
    <div style="color:#252540;font-size:.63em">Actualizado: {_gd_ts}</div>
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px;
padding-top:10px;border-top:1px solid #1a1600">
  <div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;padding:8px 12px">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:1.5px">M15 Tendencia</div>
    <div style="color:{_tend_c};font-weight:800;font-size:.9em">{_tend_icon} {_gd_tend.upper()}</div>
  </div>
  <div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;padding:8px 12px">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:1.5px">M5 Setup</div>
    <div style="color:#ffd600;font-size:.78em;font-weight:700">{_gd_setup[:30] if _gd_setup else '—'}</div>
  </div>
  <div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;padding:8px 12px">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:1.5px">M1 Confirmación</div>
    <div style="color:#82b1ff;font-size:.78em;font-weight:700">{_gd_conf}</div>
  </div>
</div>
<div style="display:flex;gap:14px;margin-top:8px;font-size:.7em;flex-wrap:wrap">
  <span style="color:#333">Bid: <b style="color:#aaa">{_bid_str}</b></span>
  <span style="color:#333">Ask: <b style="color:#aaa">{_ask_str}</b></span>
  <span style="color:#333">M1: <b style="color:#444">{_gd_m1b}v</b></span>
  <span style="color:#333">M5: <b style="color:#444">{_gd_m5b}v</b></span>
  <span style="color:#333">M15: <b style="color:#444">{_gd_m15b}v</b></span>
  {f'<span style="color:#ff9800">⚠ {_gd_error[:60]}</span>' if _gd_error and not _gd_ok else ""}
  {f'<span style="color:#444;font-style:italic">{_gd_motivo[:50]}</span>' if _gd_motivo and _gd_dec not in ("RECOMENDAR",) else ""}
</div>
</div>""", unsafe_allow_html=True)

    # Tarjeta de señal activa (si RECOMENDAR)
    if _gd_dir and _gd_dec == "RECOMENDAR":
        _gc = "#00e676" if _gd_dir == "buy" else "#ff1744"
        _gbg = "sig-premium" if _gd_score >= 90 else "sig-alta" if _gd_score >= 80 else "sig-obs"
        _gentry = _gd.get("entry", 0); _gsl = _gd.get("sl", 0)
        _gtp1 = _gd.get("tp1", 0); _gtp2 = _gd.get("tp2", 0)
        _gtp3 = _gd.get("tp3", 0); _gtp4 = _gd.get("tp4", 0)
        _gatr = _gd.get("ind_m5", {}).get("atr", 0)
        st.markdown(f"""<div class="{_gbg}">
<div style="display:flex;align-items:stretch;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.06)">
  <div style="background:{_gc};padding:14px 22px;display:flex;align-items:center;min-width:170px">
    <div>
      <div style="color:{'#000' if _gd_dir=='buy' else '#fff'};font-size:.58em;text-transform:uppercase;letter-spacing:2px;font-weight:700">✅ ORO · XAUUSD M5</div>
      <div style="color:{'#000' if _gd_dir=='buy' else '#fff'};font-size:1.2em;font-weight:900;margin-top:2px">{'▲ LONG / BUY' if _gd_dir=='buy' else '▼ SHORT / SELL'}</div>
      <div style="color:{'#00000077' if _gd_dir=='buy' else '#ffffff55'};font-size:.6em">Scalping · {_gd_patron}</div>
    </div>
  </div>
  <div style="padding:12px 18px;flex:1">
    <div style="color:#252540;font-size:.6em;text-transform:uppercase;letter-spacing:2px">📈 XAUUSD / ORO · M5</div>
    <div style="color:#ffd600;font-size:1.1em;font-weight:900;margin:2px 0">XAU/USD Oro</div>
    <div style="display:flex;gap:8px;align-items:center;margin-top:4px;flex-wrap:wrap">
      <span style="color:{_gc};font-size:.75em;font-weight:800;background:rgba(255,255,255,.04);padding:2px 8px;border-radius:3px">⭐ {_gd_clase} · {_gd_score}/100</span>
      <span style="background:#12082a;border:1px solid #3d1278;color:#ce93d8;padding:2px 8px;border-radius:3px;font-size:.7em">🕯 {_gd_patron}</span>
      <span style="color:#ffd600;font-size:.68em">🟡 MT5 / Weltrade</span>
    </div>
    {f'<div style="color:#888;font-size:.72em;margin-top:6px;font-style:italic">{_gd_ia[:90]}</div>' if _gd_ia else ""}
  </div>
  <div style="padding:12px 20px;text-align:right;border-left:1px solid rgba(255,255,255,.05)">
    <div class="px-lbl">📍 PRECIO ACTUAL</div>
    <div style="color:#ffd600;font-size:1.4em;font-weight:900;font-family:'Courier New',mono">{_price_str}</div>
    <div style="color:{_spread_c};font-size:.72em">Spread: {_spread_str}</div>
  </div>
</div>
<div style="padding:4px 20px 10px">
  <div style="display:grid;grid-template-columns:120px 1fr;align-items:center;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04)">
    <div style="color:#383858;font-size:.68em;font-weight:700;text-transform:uppercase">🎯 ENTRADA</div>
    <div style="color:#ffd600;font-size:1.1em;font-weight:800;font-family:'Courier New',mono">{_gentry:,.2f}</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr;align-items:center;padding:7px 0;border-bottom:2px solid rgba(255,255,255,.07)">
    <div style="color:#ff5252;font-size:.68em;font-weight:700;text-transform:uppercase">🛑 STOP LOSS</div>
    <div style="color:#ff5252;font-size:1.1em;font-weight:800;font-family:'Courier New',mono">{_gsl:,.2f}</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr 1fr;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#388e3c;font-size:.67em;font-weight:700;text-transform:uppercase">🎯 TP 1</div>
    <div style="color:#69f0ae;font-size:1em;font-weight:700;font-family:'Courier New',mono">{_gtp1:,.2f}</div>
    <div style="color:#2e7d32;font-size:.72em">ATR×0.8 ({abs(_gtp1-_gentry):.2f})</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr 1fr;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#43a047;font-size:.67em;font-weight:700;text-transform:uppercase">🎯 TP 2</div>
    <div style="color:#69f0ae;font-size:1em;font-weight:700;font-family:'Courier New',mono">{_gtp2:,.2f}</div>
    <div style="color:#2e7d32;font-size:.72em">ATR×2.0 ({abs(_gtp2-_gentry):.2f})</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr 1fr;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.03)">
    <div style="color:#66bb6a;font-size:.67em;font-weight:700;text-transform:uppercase">🎯 TP 3</div>
    <div style="color:#69f0ae;font-size:1em;font-weight:700;font-family:'Courier New',mono">{_gtp3:,.2f}</div>
    <div style="color:#2e7d32;font-size:.72em">ATR×3.5 ({abs(_gtp3-_gentry):.2f})</div>
  </div>
  <div style="display:grid;grid-template-columns:120px 1fr 1fr;align-items:center;padding:7px 0">
    <div style="color:#ffd600;font-size:.67em;font-weight:900;text-transform:uppercase">💎 TP 4</div>
    <div style="color:#ffd600;font-size:1.1em;font-weight:900;font-family:'Courier New',mono">{_gtp4:,.2f}</div>
    <div style="color:#a37900;font-size:.72em">ATR×5.5 ({abs(_gtp4-_gentry):.2f})</div>
  </div>
  <div style="display:flex;gap:12px;margin-top:6px;font-size:.7em;flex-wrap:wrap">
    <span style="color:#383858">Score: <b style="color:#ffd600">{_gd_score}/100</b></span>
    <span style="color:#383858">M15: <b style="color:{_tend_c}">{_tend_icon} {_gd_tend}</b></span>
    <span style="color:#383858">M5: <b style="color:#ffd600">{_gd_setup[:28] if _gd_setup else '—'}</b></span>
    <span style="color:#383858">M1: <b style="color:#82b1ff">{_gd_conf}</b></span>
    <span style="color:#383858">ATR: <b style="color:#555">{_gatr:.2f}</b></span>
    <span style="color:#383858">Fuente: <b style="color:#ffd600">MT5 / Weltrade</b></span>
  </div>
</div>
</div>""", unsafe_allow_html=True)

    # Estadísticas Gold
    _g_stats = stats_gold_summary(stats)
    if _g_stats["total"] > 0:
        _wr_g = _g_stats["winrate"]
        _wrc  = "#00e676" if _wr_g >= 60 else ("#ffd600" if _wr_g >= 50 else "#ff5252")
        st.markdown(f'<div style="background:#0a0800;border:1px solid #1a1400;border-radius:6px;'
            f'padding:8px 14px;margin-top:4px;display:flex;gap:16px;flex-wrap:wrap;font-size:.72em">'
            f'<span style="color:#444">XAUUSD señales: <b style="color:#aaa">{_g_stats["total"]}</b></span>'
            f'<span style="color:#444">✅ <b style="color:#00e676">{_g_stats["wins"]}</b></span>'
            f'<span style="color:#444">❌ <b style="color:#ff5252">{_g_stats["losses"]}</b></span>'
            f'<span style="color:#444">WR: <b style="color:{_wrc}">{_wr_g:.1f}%</b></span>'
            f'<span style="color:#444">Score ganador: <b style="color:#555">{_g_stats["score_avg_win"]:.0f}</b></span>'
            f'</div>', unsafe_allow_html=True)

    # Debug Gold en modo avanzado
    if es_avanzado:
        with st.expander("🪙 Debug XAUUSD / Oro", expanded=False):
            _ms_g = _mt5_status
            _gld  = st.session_state.get("gold_live_data", {})
            _clr_mt5 = "#00e676" if _ms_g.get("connected") else "#ff5252"
            st.markdown(f'<div style="font-size:.72em;line-height:1.9;color:#555">'
                f'<b style="color:{_clr_mt5}">MT5: {"CONECTADO" if _ms_g.get("connected") else "DESCONECTADO"}</b><br>'
                f'Broker: {_ms_g.get("broker","—")}<br>Cuenta: {_ms_g.get("account","—")}<br>'
                f'Símbolo real: <b style="color:#ffd600">{_gld.get("mt5_symbol","no encontrado")}</b><br>'
                f'Bid: {_gld.get("bid","—")} · Ask: {_gld.get("ask","—")} · '
                f'Spread: {_gld.get("spread","—")}<br>'
                f'Velas M1: <b>{_gd.get("m1_bars",0)}</b> · '
                f'M5: <b>{_gd.get("m5_bars",0)}</b> · '
                f'M15: <b>{_gd.get("m15_bars",0)}</b><br>'
                f'Último score: <b style="color:#ffd600">{_gd.get("score",0)}/100</b> · '
                f'Decisión: <b>{_gd.get("decision","—")}</b><br>'
                f'Patrón: {_gd.get("patron","—")}<br>'
                f'Tendencia M15: {_gd.get("tendencia_m15","—")}<br>'
                f'Setup M5: {_gd.get("setup_m5","—")}<br>'
                f'Conf M1: {_gd.get("conf_m1","—")}<br>'
                f'Error: <span style="color:#ff9800">{_gld.get("error","—")}</span><br>'
                f'Última act: {_gd.get("ts","—")}'
                f'</div>', unsafe_allow_html=True)
            # Score breakdown
            _sbd = _gd.get("score_bd", {})
            if _sbd:
                _sbd_html = "".join([
                    f'<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid #0e0e1e">'
                    f'<span style="color:#444;font-size:.7em">{k}</span>'
                    f'<span style="color:#ffd600;font-size:.7em">{v} pts</span></div>'
                    for k, v in _sbd.items()])
                st.markdown(f'<div style="background:#08080f;border:1px solid #12121e;border-radius:6px;'
                    f'padding:8px 10px;margin-top:6px">{_sbd_html}</div>', unsafe_allow_html=True)

# (señales activas integradas en tabs por mercado arriba)



# ── AUTO-REFRESH ───────────────────────────────────────────────────────────────
if st.session_state["scanning"]:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=intervalo*1000, key="rf")
    except:
        st.caption(f"Instala streamlit-autorefresh para auto-scan cada {intervalo}s")
