"""
Trading Scanner Pro — Señales reales en vivo
Escanea múltiples activos en paralelo cada 60 segundos.
Solo genera señal cuando mínimo 5 de 7 indicadores confluyen.
"""

import streamlit as st
import yfinance as yf
import ta
import pandas as pd
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import websocket
import time

st.set_page_config(
    page_title="Scanner Pro",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
body { background: #0e0e1a; }
.header { font-size:2em; font-weight:bold; color:#e0e0ff; margin-bottom:5px; }
.subh   { color:#888; font-size:0.9em; margin-bottom:15px; }
.buy-row  { background:#003d1a; border-left:4px solid #00e676; padding:12px; border-radius:8px; margin:6px 0; }
.sell-row { background:#3d0000; border-left:4px solid #ff1744; padding:12px; border-radius:8px; margin:6px 0; }
.wait-row { background:#1a1a1a; border-left:4px solid #555; padding:10px; border-radius:8px; margin:4px 0; color:#aaa; }
.badge-buy  { background:#00e676; color:#000; padding:3px 10px; border-radius:20px; font-weight:bold; font-size:0.85em; }
.badge-sell { background:#ff1744; color:#fff; padding:3px 10px; border-radius:20px; font-weight:bold; font-size:0.85em; }
.badge-wait { background:#333; color:#aaa; padding:3px 10px; border-radius:20px; font-size:0.85em; }
.stat { color:#7c7cff; font-size:0.8em; }
.tp { color:#00e676; font-weight:bold; }
.sl { color:#ff5252; font-weight:bold; }
.entry { color:#82b1ff; font-weight:bold; }
.alert-box { background:#1a1a00; border:2px solid #ffd600; color:#ffd600; padding:15px; border-radius:10px; font-size:1.1em; text-align:center; margin:10px 0; }
</style>
""", unsafe_allow_html=True)

# ── Activos a escanear ─────────────────────────────────────────────────────────

ACTIVOS_REALES = {
    "XAUUSD": ("GC=F",      "🟡 Oro"),
    "BTCUSD": ("BTC-USD",   "₿ Bitcoin"),
    "ETHUSD": ("ETH-USD",   "Ξ Ethereum"),
    "SOLUSD": ("SOL-USD",   "◎ Solana"),
    "XRPUSD": ("XRP-USD",   "⬡ XRP"),
    "BNBUSD": ("BNB-USD",   "🔵 BNB"),
    "DOGEUSD":("DOGE-USD",  "Ð Dogecoin"),
    "ADAUSD": ("ADA-USD",   "◈ Cardano"),
}

ACTIVOS_SINTETICOS = {
    "V10":   ("R_10",        "📊 Volatility 10"),
    "V25":   ("R_25",        "📊 Volatility 25"),
    "V50":   ("R_50",        "📊 Volatility 50"),
    "V75":   ("R_75",        "📊 Volatility 75"),
    "V100":  ("R_100",       "📊 Volatility 100"),
    "CR1000":("CRASH_1000E", "🔴 Crash 1000"),
    "CR500": ("CRASH_500",   "🔴 Crash 500"),
    "BM1000":("BOOM_1000E",  "🟢 Boom 1000"),
    "BM500": ("BOOM_500",    "🟢 Boom 500"),
    "JD75":  ("JD75",        "↗ Jump 75"),
    "JD100": ("JD100",       "↗ Jump 100"),
}

# ── Formato de precio ──────────────────────────────────────────────────────────

def fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if v >= 1000:  return f"${v:,.2f}"
    if v >= 1:     return f"${v:,.4f}"
    return f"${v:.6f}"

# ── Obtener datos ──────────────────────────────────────────────────────────────

def datos_yfinance(symbol: str, interval: str = "15m") -> pd.DataFrame:
    try:
        df = yf.Ticker(symbol).history(period="5d", interval=interval)
        return df if len(df) >= 50 else pd.DataFrame()
    except:
        return pd.DataFrame()

def datos_deriv(symbol: str, granularity: int = 300, count: int = 300) -> pd.DataFrame:
    result = {"data": None}
    def on_msg(ws, msg):
        d = json.loads(msg)
        if "candles" in d:
            result["data"] = d["candles"]
            ws.close()
    def on_open(ws):
        ws.send(json.dumps({
            "ticks_history": symbol,
            "granularity": granularity,
            "count": count,
            "end": "latest",
            "style": "candles"
        }))
    try:
        ws = websocket.WebSocketApp(
            "wss://ws.binaryws.com/websockets/v3?app_id=1089",
            on_message=on_msg, on_open=on_open
        )
        ws.run_forever(ping_timeout=12)
    except:
        return pd.DataFrame()
    if not result["data"]:
        return pd.DataFrame()
    df = pd.DataFrame(result["data"])
    df["epoch"] = pd.to_datetime(df["epoch"], unit="s")
    df = df.rename(columns={"epoch":"Date","open":"Open","high":"High","low":"Low","close":"Close"})
    df[["Open","High","Low","Close"]] = df[["Open","High","Low","Close"]].astype(float)
    df["Volume"] = 0.0
    return df.set_index("Date")

# ── Análisis técnico estricto ──────────────────────────────────────────────────

def analizar(df: pd.DataFrame) -> dict:
    """
    Devuelve señal SOLO cuando mínimo 5 de 7 condiciones confluyen.
    Criterio estricto para evitar señales falsas.
    """
    if df.empty or len(df) < 55:
        return {"senal": "SIN DATOS", "dir": None, "fuerza": 0, "ind": {}}

    close = df["Close"].astype(float)
    high  = df["High"].astype(float)
    low   = df["Low"].astype(float)

    # Indicadores
    rsi       = ta.momentum.RSIIndicator(close, 14).rsi()
    macd_obj  = ta.trend.MACD(close)
    macd_h    = macd_obj.macd_diff()
    bb        = ta.volatility.BollingerBands(close, 20)
    ema20     = ta.trend.EMAIndicator(close, 20).ema_indicator()
    ema50     = ta.trend.EMAIndicator(close, 50).ema_indicator()
    ema200    = ta.trend.EMAIndicator(close, min(200, len(close)-1)).ema_indicator()
    atr       = ta.volatility.AverageTrueRange(high, low, close, 14).average_true_range()
    stoch     = ta.momentum.StochasticOscillator(high, low, close)
    stoch_k   = stoch.stoch()
    stoch_d   = stoch.stoch_signal()

    p       = close.iloc[-1]
    r       = rsi.iloc[-1]
    mh      = macd_h.iloc[-1]
    mhp     = macd_h.iloc[-2]
    bb_up   = bb.bollinger_hband().iloc[-1]
    bb_lo   = bb.bollinger_lband().iloc[-1]
    bb_rng  = bb_up - bb_lo
    e20     = ema20.iloc[-1]
    e50     = ema50.iloc[-1]
    e200    = ema200.iloc[-1]
    sk      = stoch_k.iloc[-1]
    at      = atr.iloc[-1]

    # EMA20 pendiente (comparar últimas 3 velas)
    ema20_slope = ema20.iloc[-1] - ema20.iloc[-3]

    ind = {
        "price": p, "rsi": r, "macd_h": mh, "macd_hp": mhp,
        "bb_up": bb_up, "bb_lo": bb_lo, "bb_mid": bb.bollinger_mavg().iloc[-1],
        "ema20": e20, "ema50": e50, "ema200": e200,
        "stoch_k": sk, "stoch_d": stoch_d.iloc[-1], "atr": at,
    }

    # ── Condiciones de COMPRA (7 criterios) ───────────────────────────────────
    cond_buy = [
        r < 45,                                # 1. RSI no sobrecomprado
        r > 25,                                # 2. RSI no extremo (evita cuchillo)
        mh > 0 or (mh > mhp and mhp < 0),     # 3. MACD positivo o cruzando al alza
        (bb_rng > 0 and (p - bb_lo) / bb_rng < 0.4),  # 4. Precio en mitad baja BB
        p > e200,                              # 5. Tendencia macro alcista (EMA200)
        sk < 55,                               # 6. Estocástico no sobrecomprado
        ema20_slope >= 0 or p > e20,           # 7. EMA20 plana/alcista o precio sobre ella
    ]

    # ── Condiciones de VENTA (7 criterios) ───────────────────────────────────
    cond_sell = [
        r > 55,                                # 1. RSI no sobrevendido
        r < 75,                                # 2. RSI no extremo
        mh < 0 or (mh < mhp and mhp > 0),     # 3. MACD negativo o cruzando a la baja
        (bb_rng > 0 and (p - bb_lo) / bb_rng > 0.6),  # 4. Precio en mitad alta BB
        p < e200,                              # 5. Tendencia macro bajista (EMA200)
        sk > 45,                               # 6. Estocástico no sobrevendido
        ema20_slope <= 0 or p < e20,           # 7. EMA20 plana/bajista o precio bajo ella
    ]

    buy_score  = sum(cond_buy)
    sell_score = sum(cond_sell)
    total      = len(cond_buy)  # 7

    # Señal solo con 5+ de 7 condiciones
    MINIMO = 5
    if buy_score >= MINIMO and buy_score > sell_score:
        fuerza = int((buy_score / total) * 100)
        return {"senal": "COMPRAR", "dir": "buy", "fuerza": fuerza, "ind": ind, "score": buy_score}
    elif sell_score >= MINIMO and sell_score > buy_score:
        fuerza = int((sell_score / total) * 100)
        return {"senal": "VENDER", "dir": "sell", "fuerza": fuerza, "ind": ind, "score": sell_score}
    else:
        max_score = max(buy_score, sell_score)
        return {"senal": "ESPERAR", "dir": None, "fuerza": 0, "ind": ind,
                "score": max_score, "faltan": MINIMO - max_score}

# ── Plan de trade ──────────────────────────────────────────────────────────────

def calcular_plan(resultado: dict, balance: float, riesgo_pct: float) -> dict:
    ind = resultado.get("ind", {})
    if not ind or resultado["dir"] is None:
        return {}
    p   = ind["price"]
    at  = ind["atr"]
    d   = resultado["dir"]
    riesgo_usd = balance * riesgo_pct / 100
    if d == "buy":
        entry, sl = p, p - at * 1.5
        tp1, tp2, tp3 = p + at*2, p + at*3.5, p + at*5.5
    else:
        entry, sl = p, p + at * 1.5
        tp1, tp2, tp3 = p - at*2, p - at*3.5, p - at*5.5
    dist = abs(entry - sl)
    units = riesgo_usd / dist if dist > 0 else 0
    rr = lambda tp: abs(tp - entry) / dist if dist > 0 else 0
    return {
        "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "dist": dist, "units": units, "riesgo_usd": riesgo_usd,
        "g1": units * abs(tp1-entry), "g2": units * abs(tp2-entry), "g3": units * abs(tp3-entry),
        "rr1": rr(tp1), "rr2": rr(tp2), "rr3": rr(tp3),
    }

# ── Escanear un activo ─────────────────────────────────────────────────────────

def escanear_activo(key: str, sym: str, nombre: str, es_sint: bool, tf_real: str, tf_sint_gran: int) -> dict:
    df = datos_deriv(sym, tf_sint_gran) if es_sint else datos_yfinance(sym, tf_real)
    resultado = analizar(df)
    resultado["key"]    = key
    resultado["sym"]    = sym
    resultado["nombre"] = nombre
    resultado["ts"]     = datetime.now().strftime("%H:%M:%S")
    return resultado

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Scanner Pro")
    escanear_reales = st.checkbox("🌎 Mercados reales", value=True)
    escanear_sint   = st.checkbox("🤖 Sintéticos Deriv", value=False)
    st.divider()
    tf_real = st.selectbox("Temporalidad reales:", ["5m","15m","60m"], index=1,
                           format_func=lambda x: {"5m":"5 minutos","15m":"15 minutos","60m":"1 hora"}[x])
    tf_sint = st.selectbox("Temporalidad sintéticos:", [60, 300, 900],
                           format_func=lambda x: {60:"1 minuto",300:"5 minutos",900:"15 minutos"}[x])
    st.divider()
    st.subheader("💰 Gestión de capital")
    balance  = st.number_input("Saldo ($):", min_value=1.0, value=500.0, step=10.0)
    riesgo   = st.slider("Riesgo por trade (%):", 0.5, 5.0, 1.0, 0.5)
    st.info(f"Riesgo por trade: **${balance * riesgo / 100:.2f}**")
    st.divider()
    solo_señales = st.checkbox("Mostrar solo señales activas", value=False)
    intervalo = st.slider("Auto-scan cada (seg):", 30, 300, 60, 30)
    iniciar = st.button("🚀 Iniciar Scanner", type="primary", use_container_width=True)
    detener = st.button("⏹ Detener", use_container_width=True)

# ── Estado del scanner ─────────────────────────────────────────────────────────

if "scanning"    not in st.session_state: st.session_state["scanning"]    = False
if "resultados"  not in st.session_state: st.session_state["resultados"]  = {}
if "historial"   not in st.session_state: st.session_state["historial"]   = []
if "ultimo_scan" not in st.session_state: st.session_state["ultimo_scan"] = None

if iniciar: st.session_state["scanning"] = True
if detener: st.session_state["scanning"] = False

# ── Header ─────────────────────────────────────────────────────────────────────

col_t, col_s = st.columns([3,1])
with col_t:
    st.markdown('<div class="header">🔍 Trading Scanner Pro — Señales en Vivo</div>', unsafe_allow_html=True)
    estado = "🟢 ACTIVO" if st.session_state["scanning"] else "🔴 DETENIDO"
    ultimo = st.session_state.get("ultimo_scan") or "—"
    st.markdown(f'<div class="subh">Estado: {estado} &nbsp;|&nbsp; Último scan: {ultimo} &nbsp;|&nbsp; Mín. confluencia: 5/7 indicadores</div>', unsafe_allow_html=True)
with col_s:
    señales_activas = [r for r in st.session_state["resultados"].values() if r.get("dir")]
    st.metric("Señales activas", len(señales_activas))

# ── Función de scan ────────────────────────────────────────────────────────────

def ejecutar_scan():
    activos = {}
    if escanear_reales:
        for k,(s,n) in ACTIVOS_REALES.items():
            activos[k] = (s, n, False)
    if escanear_sint:
        for k,(s,n) in ACTIVOS_SINTETICOS.items():
            activos[k] = (s, n, True)
    if not activos:
        return

    resultados_nuevos = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {
            ex.submit(escanear_activo, k, s, n, sint, tf_real, tf_sint):k
            for k,(s,n,sint) in activos.items()
        }
        for fut in as_completed(futures):
            try:
                r = fut.result(timeout=30)
                resultados_nuevos[r["key"]] = r
            except:
                pass

    # Guardar historial de señales nuevas
    for k, r in resultados_nuevos.items():
        if r.get("dir"):
            old = st.session_state["resultados"].get(k, {})
            if old.get("dir") != r["dir"]:  # señal nueva
                st.session_state["historial"].insert(0, {
                    "hora": r["ts"], "activo": r["nombre"],
                    "senal": r["senal"], "precio": fmt(r["ind"].get("price")),
                    "fuerza": r.get("fuerza",0)
                })
                if len(st.session_state["historial"]) > 50:
                    st.session_state["historial"] = st.session_state["historial"][:50]

    st.session_state["resultados"]  = resultados_nuevos
    st.session_state["ultimo_scan"] = datetime.now().strftime("%H:%M:%S")

# ── Escanear si está activo ────────────────────────────────────────────────────

placeholder_scan = st.empty()

if st.session_state["scanning"]:
    ejecutar_scan()

# ── Mostrar resultados ─────────────────────────────────────────────────────────

resultados = st.session_state["resultados"]

if not resultados:
    if st.session_state["scanning"]:
        st.info("⏳ Escaneando mercados... tarda unos segundos.")
    else:
        st.warning("👆 Presiona **Iniciar Scanner** para comenzar.")
else:
    # ── Alertas de señales activas ─────────────────────────────────────────────
    señales = [r for r in resultados.values() if r.get("dir")]
    if señales:
        for s in señales:
            emoji = "🟢" if s["dir"] == "buy" else "🔴"
            st.markdown(
                f'<div class="alert-box">{emoji} SEÑAL DETECTADA: <b>{s["nombre"]}</b> → '
                f'{s["senal"]} a {fmt(s["ind"].get("price"))} | Fuerza: {s["fuerza"]}% '
                f'({s.get("score",0)}/7 indicadores) | {s["ts"]}</div>',
                unsafe_allow_html=True
            )

    # ── Tabla de todos los activos ─────────────────────────────────────────────
    st.subheader("📋 Estado del mercado")

    orden = sorted(resultados.values(), key=lambda r: (0 if r.get("dir") else 1, -r.get("fuerza",0)))

    for r in orden:
        if solo_señales and not r.get("dir"):
            continue
        ind  = r.get("ind", {})
        p    = ind.get("price")
        rsi  = ind.get("rsi")
        sk   = ind.get("stoch_k")

        if r["dir"] == "buy":
            cls, badge = "buy-row", '<span class="badge-buy">● COMPRAR</span>'
        elif r["dir"] == "sell":
            cls, badge = "sell-row", '<span class="badge-sell">● VENDER</span>'
        else:
            cls, badge = "wait-row", '<span class="badge-wait">○ ESPERAR</span>'
            faltan = r.get("faltan", "")
            if faltan:
                badge += f' <span style="color:#666;font-size:0.8em">({faltan} cond. faltan)</span>'

        rsi_str = f"{rsi:.1f}" if rsi else "—"
        sk_str  = f"{sk:.0f}"  if sk  else "—"
        f_str   = f"{r['fuerza']}%" if r.get("fuerza") else "—"

        st.markdown(f"""
        <div class="{cls}">
            <b>{r['nombre']}</b> &nbsp; {badge} &nbsp;
            <span style="color:#ccc">{fmt(p)}</span> &nbsp;|&nbsp;
            <span class="stat">RSI {rsi_str} | Stoch {sk_str} | Fuerza {f_str}</span> &nbsp;
            <span style="color:#444;font-size:0.75em">{r['ts']}</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Detalle de la mejor señal ──────────────────────────────────────────────
    mejor = next((r for r in orden if r.get("dir")), None)
    if mejor:
        st.divider()
        plan = calcular_plan(mejor, balance, riesgo)
        st.subheader(f"📐 Plan de trading — {mejor['nombre']}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div class="entry">🎯 ENTRADA: {fmt(plan["entry"])}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="sl">🛑 STOP LOSS: {fmt(plan["sl"])} (distancia: {fmt(plan["dist"])})</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="tp">✅ TP1 — R:R 1:{plan["rr1"]:.1f} → {fmt(plan["tp1"])} (+${plan["g1"]:.2f})</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="tp">✅ TP2 — R:R 1:{plan["rr2"]:.1f} → {fmt(plan["tp2"])} (+${plan["g2"]:.2f})</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="tp">✅ TP3 — R:R 1:{plan["rr3"]:.1f} → {fmt(plan["tp3"])} (+${plan["g3"]:.2f})</div>', unsafe_allow_html=True)

        with col2:
            df_plan = pd.DataFrame({
                "Concepto": ["Dirección","Saldo","Riesgo %","En riesgo ($)","Unidades","Pérdida máx","Ganancia TP1","Ganancia TP2","Ganancia TP3"],
                "Valor": [
                    "COMPRA 🟢" if mejor["dir"]=="buy" else "VENTA 🔴",
                    f"${balance:,.2f}", f"{riesgo}%",
                    f"${plan['riesgo_usd']:.2f}",
                    f"{plan['units']:.5f}",
                    f"-${plan['riesgo_usd']:.2f}",
                    f"+${plan['g1']:.2f}",
                    f"+${plan['g2']:.2f}",
                    f"+${plan['g3']:.2f}",
                ]
            })
            st.dataframe(df_plan, hide_index=True, use_container_width=True)

    # ── Historial de señales ───────────────────────────────────────────────────
    if st.session_state["historial"]:
        st.divider()
        st.subheader("📜 Historial de señales")
        hist_df = pd.DataFrame(st.session_state["historial"])
        st.dataframe(hist_df, hide_index=True, use_container_width=True)

# ── Auto-refresh ───────────────────────────────────────────────────────────────

if st.session_state["scanning"]:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=intervalo * 1000, key="scanner_refresh")
    except:
        st.info(f"🔄 Próximo scan en {intervalo}s — recarga la página manualmente si no se actualiza.")
