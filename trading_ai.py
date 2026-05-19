import streamlit as st
import yfinance as yf
import ta
import requests
import json
from datetime import datetime

st.set_page_config(page_title="Trading AI", page_icon="📈", layout="wide")
st.title("📈 Trading AI — Powered by Ollama")

OLLAMA_URL = "http://localhost:11434/api/chat"
MODELO = "llama3.2:3b"

def get_market_data(symbol: str) -> str:
    try:
        ticker = yf.Ticker(symbol.upper())
        hist = ticker.history(period="3mo")
        if hist.empty:
            return f"No se encontró el símbolo: {symbol}"
        close = hist["Close"]
        current = close.iloc[-1]
        prev = close.iloc[-2]
        change = ((current - prev) / prev) * 100
        volume = hist["Volume"].iloc[-1]
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
        macd_ind = ta.trend.MACD(close)
        macd = macd_ind.macd().iloc[-1]
        macd_sig = macd_ind.macd_signal().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        high_52 = hist["High"].max()
        low_52 = hist["Low"].min()
        return f"""
DATOS DE MERCADO PARA {symbol.upper()} (actualizado {datetime.now().strftime('%d/%m/%Y %H:%M')}):
- Precio actual: ${current:,.2f}
- Cambio hoy: {change:+.2f}%
- Volumen: {volume:,.0f}
- RSI(14): {rsi:.1f} {"[SOBRECOMPRADO]" if rsi > 70 else "[SOBREVENDIDO]" if rsi < 30 else "[NEUTRAL]"}
- MACD: {macd:.4f} | Señal: {macd_sig:.4f} | {"[ALCISTA]" if macd > macd_sig else "[BAJISTA]"}
- MA20: ${ma20:,.2f} | MA50: ${ma50:,.2f}
- Máximo 3 meses: ${high_52:,.2f}
- Mínimo 3 meses: ${low_52:,.2f}
"""
    except Exception as e:
        return f"Error obteniendo datos: {e}"

def get_market_summary() -> str:
    assets = {
        "S&P 500": "^GSPC", "NASDAQ": "^IXIC", "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD", "AAPL": "AAPL", "NVDA": "NVDA",
        "EUR/USD": "EURUSD=X", "USD/MXN": "MXN=X"
    }
    lines = [f"RESUMEN DE MERCADO — {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"]
    for name, sym in assets.items():
        try:
            hist = yf.Ticker(sym).history(period="2d")
            if hist.empty: continue
            current = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2] if len(hist) > 1 else current
            chg = ((current - prev) / prev) * 100
            lines.append(f"- {name}: ${current:,.2f} ({chg:+.2f}%)")
        except:
            pass
    return "\n".join(lines)

def detectar_simbolos(texto: str) -> list:
    import re
    palabras = texto.upper().split()
    simbolos_conocidos = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD",
                          "BITCOIN": "BTC-USD", "ETHEREUM": "ETH-USD"}
    resultado = []
    for p in palabras:
        limpio = re.sub(r"[^A-Z0-9\-\^]", "", p)
        if limpio in simbolos_conocidos:
            resultado.append(simbolos_conocidos[limpio])
        elif 2 <= len(limpio) <= 5 and limpio.isalpha():
            resultado.append(limpio)
    return list(set(resultado))[:3]

def chat_ollama(mensajes: list) -> str:
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": MODELO,
            "messages": mensajes,
            "stream": False
        }, timeout=300)
        return resp.json()["message"]["content"]
    except Exception as e:
        return f"Error conectando con Ollama: {e}"

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "system",
        "content": "Eres un experto analista de trading y mercados financieros. Analizas datos de mercado en tiempo real y das recomendaciones claras basadas en análisis técnico. Responde siempre en español."
    }]

with st.sidebar:
    st.header("🔧 Herramientas")
    if st.button("📊 Ver resumen de mercado"):
        with st.spinner("Obteniendo datos..."):
            resumen = get_market_summary()
        st.code(resumen)

    st.divider()
    simbolo_input = st.text_input("Analizar símbolo:", placeholder="AAPL, BTC-USD...")
    if st.button("🔍 Analizar") and simbolo_input:
        with st.spinner(f"Analizando {simbolo_input}..."):
            datos = get_market_data(simbolo_input)
        st.code(datos)

    st.divider()
    if st.button("🗑️ Limpiar chat"):
        st.session_state.messages = [st.session_state.messages[0]]
        st.rerun()

for msg in st.session_state.messages[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Pregunta sobre trading, acciones, crypto..."):
    contexto_mercado = ""
    palabras_mercado = ["precio", "análisis", "analiza", "cotiza", "vale", "está", "mercado", "resumen", "como va"]
    necesita_datos = any(p in prompt.lower() for p in palabras_mercado)

    simbolos = detectar_simbolos(prompt)
    if simbolos:
        with st.spinner(f"Obteniendo datos de {', '.join(simbolos)}..."):
            for sym in simbolos:
                contexto_mercado += get_market_data(sym) + "\n"
    elif necesita_datos and "mercado" in prompt.lower():
        with st.spinner("Obteniendo resumen de mercado..."):
            contexto_mercado = get_market_summary()

    mensaje_usuario = prompt
    if contexto_mercado:
        mensaje_usuario = f"{contexto_mercado}\n\nPregunta del usuario: {prompt}"

    st.session_state.messages.append({"role": "user", "content": mensaje_usuario})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando..."):
            respuesta = chat_ollama(st.session_state.messages)
        st.markdown(respuesta)

    st.session_state.messages.append({"role": "assistant", "content": respuesta})
