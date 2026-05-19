import streamlit as st
import yfinance as yf
import ta
import pandas as pd
import numpy as np
from datetime import datetime
import json
import websocket

st.set_page_config(page_title="Trading Signals Pro", page_icon="📊", layout="wide")

st.markdown("""
<style>
.buy  { background:#00c853; color:white; padding:18px; border-radius:12px; text-align:center; font-size:2em; font-weight:bold; margin-bottom:10px; }
.sell { background:#d50000; color:white; padding:18px; border-radius:12px; text-align:center; font-size:2em; font-weight:bold; margin-bottom:10px; }
.wait { background:#e65100; color:white; padding:18px; border-radius:12px; text-align:center; font-size:2em; font-weight:bold; margin-bottom:10px; }
.card { background:#1a1a2e; color:#eee; padding:14px; border-radius:10px; margin:6px 0; border-left:4px solid #7c4dff; }
.tp   { background:#0d3b1e; color:#69f0ae; padding:10px; border-radius:8px; margin:4px 0; font-weight:bold; }
.sl   { background:#3b0d0d; color:#ff5252; padding:10px; border-radius:8px; margin:4px 0; font-weight:bold; }
.entry{ background:#0d1f3b; color:#82b1ff; padding:10px; border-radius:8px; margin:4px 0; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

# ── Activos disponibles ────────────────────────────────────────────────────────

REALES = {
    "🟡 Oro (XAU/USD)":    "GC=F",
    "₿  Bitcoin (BTC)":    "BTC-USD",
    "Ξ  Ethereum (ETH)":   "ETH-USD",
    "◎  Solana (SOL)":     "SOL-USD",
    "⬡  XRP":              "XRP-USD",
    "Ð  Dogecoin (DOGE)":  "DOGE-USD",
    "🔵 BNB":              "BNB-USD",
    "◈  Cardano (ADA)":    "ADA-USD",
}

SINTETICOS = {
    "📊 Volatility 10 (V10)":   "R_10",
    "📊 Volatility 25 (V25)":   "R_25",
    "📊 Volatility 50 (V50)":   "R_50",
    "📊 Volatility 75 (V75)":   "R_75",
    "📊 Volatility 100 (V100)": "R_100",
    "🔴 Crash 1000":            "CRASH_1000E",
    "🔴 Crash 500":             "CRASH_500",
    "🟢 Boom 1000":             "BOOM_1000E",
    "🟢 Boom 500":              "BOOM_500",
    "↗  Jump 75":               "JD75",
    "↗  Jump 100":              "JD100",
}

TIMEFRAMES_REALES = {"5 minutos": "5m", "15 minutos": "15m", "1 hora": "60m", "4 horas": "1h"}
GRANULARIDAD_DERIV = {"1 minuto": 60, "5 minutos": 300, "15 minutos": 900, "1 hora": 3600}

# ── Datos ──────────────────────────────────────────────────────────────────────

def fmt(price: float) -> str:
    if price >= 1000:   return f"${price:,.2f}"
    if price >= 1:      return f"${price:,.4f}"
    return f"${price:.6f}"

def get_deriv_candles(symbol: str, granularity: int = 60, count: int = 300) -> pd.DataFrame:
    result = {"data": None}

    def on_message(ws, msg):
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
            on_message=on_message, on_open=on_open
        )
        ws.run_forever(ping_timeout=15)
    except Exception:
        return pd.DataFrame()

    if not result["data"]:
        return pd.DataFrame()

    df = pd.DataFrame(result["data"])
    df["epoch"] = pd.to_datetime(df["epoch"], unit="s")
    df = df.rename(columns={"epoch":"Date","open":"Open","high":"High","low":"Low","close":"Close"})
    df[["Open","High","Low","Close"]] = df[["Open","High","Low","Close"]].astype(float)
    df["Volume"] = 0.0
    return df.set_index("Date")


def get_real_data(symbol: str, interval: str = "15m") -> pd.DataFrame:
    period = "5d" if interval in ["5m","15m"] else "60d"
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        return df if not df.empty else pd.DataFrame()
    except:
        return pd.DataFrame()

# ── Análisis técnico ───────────────────────────────────────────────────────────

def calcular_indicadores(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 30:
        return {}
    close = df["Close"].astype(float)
    high  = df["High"].astype(float)
    low   = df["Low"].astype(float)

    rsi_s       = ta.momentum.RSIIndicator(close, 14).rsi()
    macd_obj    = ta.trend.MACD(close)
    macd_hist   = macd_obj.macd_diff()
    bb          = ta.volatility.BollingerBands(close, 20)
    ema20       = ta.trend.EMAIndicator(close, 20).ema_indicator()
    ema50       = ta.trend.EMAIndicator(close, 50).ema_indicator()
    ema200      = ta.trend.EMAIndicator(close, min(200, len(close)-1)).ema_indicator()
    atr         = ta.volatility.AverageTrueRange(high, low, close, 14).average_true_range()
    stoch       = ta.momentum.StochasticOscillator(high, low, close)

    return {
        "price":      close.iloc[-1],
        "open":       df["Open"].iloc[-1],
        "high_d":     high.iloc[-1],
        "low_d":      low.iloc[-1],
        "rsi":        rsi_s.iloc[-1],
        "rsi_prev":   rsi_s.iloc[-2],
        "macd_h":     macd_hist.iloc[-1],
        "macd_hp":    macd_hist.iloc[-2],
        "bb_up":      bb.bollinger_hband().iloc[-1],
        "bb_lo":      bb.bollinger_lband().iloc[-1],
        "bb_mid":     bb.bollinger_mavg().iloc[-1],
        "ema20":      ema20.iloc[-1],
        "ema50":      ema50.iloc[-1],
        "ema200":     ema200.iloc[-1],
        "atr":        atr.iloc[-1],
        "stoch_k":    stoch.stoch().iloc[-1],
        "stoch_d":    stoch.stoch_signal().iloc[-1],
    }


def generar_senal(ind: dict) -> dict:
    if not ind:
        return {"signal": "SIN DATOS", "dir": "neutral", "fuerza": 0, "razones": []}

    buy, sell = 0, 0
    razones_b, razones_s = [], []
    p = ind["price"]

    # RSI
    if ind["rsi"] < 30:
        buy += 3; razones_b.append(f"RSI sobrevendido {ind['rsi']:.1f}")
    elif ind["rsi"] < 45:
        buy += 1; razones_b.append(f"RSI bajo {ind['rsi']:.1f}")
    elif ind["rsi"] > 70:
        sell += 3; razones_s.append(f"RSI sobrecomprado {ind['rsi']:.1f}")
    elif ind["rsi"] > 55:
        sell += 1; razones_s.append(f"RSI alto {ind['rsi']:.1f}")

    # MACD cruce
    if ind["macd_h"] > 0 and ind["macd_hp"] <= 0:
        buy += 3; razones_b.append("Cruce alcista MACD")
    elif ind["macd_h"] > 0:
        buy += 1; razones_b.append("MACD positivo")
    elif ind["macd_h"] < 0 and ind["macd_hp"] >= 0:
        sell += 3; razones_s.append("Cruce bajista MACD")
    elif ind["macd_h"] < 0:
        sell += 1; razones_s.append("MACD negativo")

    # Bollinger Bands
    rng = ind["bb_up"] - ind["bb_lo"]
    if rng > 0:
        pos = (p - ind["bb_lo"]) / rng
        if pos < 0.15:
            buy += 2; razones_b.append("Precio en banda baja BB")
        elif pos > 0.85:
            sell += 2; razones_s.append("Precio en banda alta BB")

    # EMAs
    if p > ind["ema20"] > ind["ema50"]:
        buy += 2; razones_b.append("Tendencia alcista EMA20>EMA50")
    elif p < ind["ema20"] < ind["ema50"]:
        sell += 2; razones_s.append("Tendencia bajista EMA20<EMA50")

    if p > ind["ema200"]:
        buy += 1; razones_b.append("Precio sobre EMA200")
    else:
        sell += 1; razones_s.append("Precio bajo EMA200")

    # Estocástico
    if ind["stoch_k"] < 20:
        buy += 2; razones_b.append(f"Estocástico sobrevendido {ind['stoch_k']:.0f}")
    elif ind["stoch_k"] > 80:
        sell += 2; razones_s.append(f"Estocástico sobrecomprado {ind['stoch_k']:.0f}")

    total = buy + sell
    if total == 0:
        return {"signal": "ESPERAR ⏳", "dir": "neutral", "fuerza": 0, "razones": ["Sin señal clara — espera confirmación"]}

    if buy > sell and buy >= 5:
        return {"signal": "COMPRAR 🟢", "dir": "buy", "fuerza": min(100, buy * 9), "razones": razones_b}
    elif sell > buy and sell >= 5:
        return {"signal": "VENDER 🔴", "dir": "sell", "fuerza": min(100, sell * 9), "razones": razones_s}
    return {"signal": "ESPERAR ⏳", "dir": "neutral", "fuerza": 0, "razones": ["Señales mixtas — sin entrada clara"]}


def plan_trading(ind: dict, senal: dict, balance: float, riesgo_pct: float) -> dict:
    if not ind or senal["dir"] == "neutral":
        return {}

    p   = ind["price"]
    atr = ind["atr"]
    d   = senal["dir"]
    riesgo_usd = balance * riesgo_pct / 100

    if d == "buy":
        entry = p
        sl  = entry - atr * 1.5
        tp1 = entry + atr * 2.0
        tp2 = entry + atr * 3.5
        tp3 = entry + atr * 5.0
    else:
        entry = p
        sl  = entry + atr * 1.5
        tp1 = entry - atr * 2.0
        tp2 = entry - atr * 3.5
        tp3 = entry - atr * 5.0

    dist_sl = abs(entry - sl)
    unidades = riesgo_usd / dist_sl if dist_sl > 0 else 0

    return {
        "entry":  entry,
        "sl":     sl,
        "tp1":    tp1,
        "tp2":    tp2,
        "tp3":    tp3,
        "dist_sl":    dist_sl,
        "unidades":   unidades,
        "riesgo_usd": riesgo_usd,
        "ganancia_tp1": unidades * abs(tp1 - entry),
        "ganancia_tp2": unidades * abs(tp2 - entry),
        "ganancia_tp3": unidades * abs(tp3 - entry),
        "rr1": abs(tp1 - entry) / dist_sl if dist_sl > 0 else 0,
        "rr2": abs(tp2 - entry) / dist_sl if dist_sl > 0 else 0,
        "rr3": abs(tp3 - entry) / dist_sl if dist_sl > 0 else 0,
    }

# ── UI Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Configuración")

    categoria = st.radio("Tipo de mercado:", ["🌎 Mercados Reales", "🤖 Sintéticos (Deriv)"])

    if categoria == "🌎 Mercados Reales":
        activo_nombre = st.selectbox("Activo:", list(REALES.keys()))
        activo_sym    = REALES[activo_nombre]
        tf_nombre     = st.selectbox("Temporalidad:", list(TIMEFRAMES_REALES.keys()), index=1)
        tf_val        = TIMEFRAMES_REALES[tf_nombre]
        es_sintetico  = False
    else:
        activo_nombre = st.selectbox("Activo sintético:", list(SINTETICOS.keys()))
        activo_sym    = SINTETICOS[activo_nombre]
        tf_nombre     = st.selectbox("Temporalidad:", list(GRANULARIDAD_DERIV.keys()), index=1)
        tf_val        = GRANULARIDAD_DERIV[tf_nombre]
        es_sintetico  = True

    st.divider()
    st.subheader("💰 Gestión de Capital")
    balance   = st.number_input("Saldo de cuenta ($):", min_value=1.0, value=1000.0, step=10.0)
    riesgo    = st.slider("Riesgo por operación (%):", 0.5, 5.0, 1.0, 0.5)
    riesgo_usd = balance * riesgo / 100
    st.info(f"Arriesgas: **${riesgo_usd:.2f}** por trade")

    st.divider()
    analizar = st.button("🔄 Analizar ahora", use_container_width=True, type="primary")
    auto = st.checkbox("Auto-refresh cada 30s")

# ── Auto-refresh ───────────────────────────────────────────────────────────────

if auto:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=30000, key="autoref")
    except:
        pass

# ── Main ───────────────────────────────────────────────────────────────────────

st.title(f"📊 Trading Signals Pro")
st.caption(f"Activo: **{activo_nombre}** | Temporalidad: **{tf_nombre}** | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

if analizar or "df_cache" not in st.session_state or st.session_state.get("sym_cache") != activo_sym:
    with st.spinner(f"Obteniendo datos de {activo_nombre}..."):
        if es_sintetico:
            df = get_deriv_candles(activo_sym, tf_val, 300)
        else:
            df = get_real_data(activo_sym, tf_val)
        st.session_state["df_cache"]  = df
        st.session_state["sym_cache"] = activo_sym
else:
    df = st.session_state["df_cache"]

ind   = calcular_indicadores(df)
senal = generar_senal(ind)
plan  = plan_trading(ind, senal, balance, riesgo)

# ── Señal principal ────────────────────────────────────────────────────────────

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    css_class = "buy" if senal["dir"] == "buy" else ("sell" if senal["dir"] == "sell" else "wait")
    st.markdown(f'<div class="{css_class}">{senal["signal"]}</div>', unsafe_allow_html=True)
    st.progress(senal["fuerza"] / 100, text=f"Fuerza de señal: {senal['fuerza']}%")

with col2:
    if ind:
        st.metric("Precio", fmt(ind["price"]))
        st.metric("RSI", f"{ind['rsi']:.1f}")
        st.metric("Estocástico K", f"{ind['stoch_k']:.1f}")

with col3:
    if ind:
        st.metric("EMA 20", fmt(ind["ema20"]))
        st.metric("EMA 50", fmt(ind["ema50"]))
        atr_pct = (ind["atr"] / ind["price"] * 100) if ind["price"] > 0 else 0
        st.metric("ATR", f"{atr_pct:.2f}%")

# ── Razones de la señal ────────────────────────────────────────────────────────

st.divider()
col_r, col_bb = st.columns(2)

with col_r:
    st.subheader("📋 Razones de la señal")
    for r in senal.get("razones", []):
        st.markdown(f'<div class="card">✅ {r}</div>', unsafe_allow_html=True)

with col_bb:
    if ind:
        st.subheader("📉 Bollinger Bands")
        st.markdown(f'<div class="card">🔴 Banda Superior: {fmt(ind["bb_up"])}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card">⚪ Banda Media: {fmt(ind["bb_mid"])}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card">🟢 Banda Inferior: {fmt(ind["bb_lo"])}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card">📍 Precio actual: {fmt(ind["price"])}</div>', unsafe_allow_html=True)

# ── Plan de trading ────────────────────────────────────────────────────────────

st.divider()
st.subheader("📐 Plan de Trading")

if plan:
    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.markdown("**Niveles de precio:**")
        st.markdown(f'<div class="entry">🎯 ENTRADA: {fmt(plan["entry"])}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sl">🛑 STOP LOSS: {fmt(plan["sl"])} &nbsp;|&nbsp; Distancia: {fmt(plan["dist_sl"])}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="tp">✅ TP1 (R:R 1:{plan["rr1"]:.1f}): {fmt(plan["tp1"])} → +${plan["ganancia_tp1"]:.2f}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="tp">✅ TP2 (R:R 1:{plan["rr2"]:.1f}): {fmt(plan["tp2"])} → +${plan["ganancia_tp2"]:.2f}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="tp">✅ TP3 (R:R 1:{plan["rr3"]:.1f}): {fmt(plan["tp3"])} → +${plan["ganancia_tp3"]:.2f}</div>', unsafe_allow_html=True)

    with col_p2:
        st.markdown("**Gestión de capital:**")
        dir_txt = "COMPRA 🟢" if senal["dir"] == "buy" else "VENTA 🔴"
        data = {
            "Concepto": ["Dirección", "Saldo cuenta", "Riesgo (%)", "Riesgo ($)", "Tamaño posición", "Pérdida máxima", "Ganancia TP1", "Ganancia TP2", "Ganancia TP3"],
            "Valor": [
                dir_txt,
                f"${balance:,.2f}",
                f"{riesgo}%",
                f"${plan['riesgo_usd']:.2f}",
                f"{plan['unidades']:.4f} unidades",
                f"-${plan['riesgo_usd']:.2f}",
                f"+${plan['ganancia_tp1']:.2f}",
                f"+${plan['ganancia_tp2']:.2f}",
                f"+${plan['ganancia_tp3']:.2f}",
            ]
        }
        st.dataframe(pd.DataFrame(data), hide_index=True, use_container_width=True)

        if riesgo > 2:
            st.warning("⚠️ Riesgo mayor al 2% — considera reducirlo")
        else:
            st.success("✅ Gestión de riesgo adecuada")

else:
    if ind:
        st.info("⏳ No hay señal de entrada ahora mismo. El sistema detectará la próxima oportunidad automáticamente.")
    else:
        st.error("❌ No se pudieron obtener datos. Verifica tu conexión a internet.")

# ── Historial de indicadores ───────────────────────────────────────────────────

if ind and not df.empty:
    st.divider()
    st.subheader("📈 Gráfico de precios recientes")
    chart_df = df["Close"].tail(100).to_frame()
    st.line_chart(chart_df)
