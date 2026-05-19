"""
Trading Tool para Open WebUI
Instrucciones de instalación:
1. Abre Open WebUI → http://localhost:8080
2. Ve a Workspace > Tools
3. Haz clic en "+" para crear nueva herramienta
4. Pega todo este código y guarda
"""

import yfinance as yf
import json
from datetime import datetime, timedelta
from typing import Callable, Any


class Tools:
    def __init__(self):
        pass

    def get_stock_price(self, symbol: str) -> str:
        """
        Obtiene el precio actual y datos básicos de una acción o crypto.
        :param symbol: Símbolo del activo (ej: AAPL, TSLA, BTC-USD, ETH-USD)
        :return: Precio actual, cambio y volumen
        """
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.fast_info
            hist = ticker.history(period="2d")
            if hist.empty:
                return f"No se encontró el símbolo: {symbol}"

            current = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2] if len(hist) > 1 else current
            change = ((current - prev) / prev) * 100
            volume = hist["Volume"].iloc[-1]

            return (
                f"📊 {symbol.upper()}\n"
                f"Precio: ${current:,.2f}\n"
                f"Cambio: {change:+.2f}%\n"
                f"Volumen: {volume:,.0f}\n"
                f"Actualizado: {datetime.now().strftime('%H:%M:%S')}"
            )
        except Exception as e:
            return f"Error obteniendo datos de {symbol}: {str(e)}"

    def get_technical_analysis(self, symbol: str, period: str = "3mo") -> str:
        """
        Realiza análisis técnico con RSI, MACD y Medias Móviles.
        :param symbol: Símbolo del activo (ej: AAPL, BTC-USD)
        :param period: Período de tiempo (1mo, 3mo, 6mo, 1y)
        :return: Indicadores técnicos y señales
        """
        try:
            import ta

            ticker = yf.Ticker(symbol.upper())
            df = ticker.history(period=period)

            if df.empty or len(df) < 20:
                return f"No hay suficientes datos para {symbol}"

            close = df["Close"]

            rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
            macd_ind = ta.trend.MACD(close)
            macd = macd_ind.macd().iloc[-1]
            macd_signal = macd_ind.macd_signal().iloc[-1]
            ma20 = close.rolling(20).mean().iloc[-1]
            ma50 = close.rolling(min(50, len(close))).mean().iloc[-1]
            current_price = close.iloc[-1]

            rsi_signal = "SOBRECOMPRADO ⚠️" if rsi > 70 else ("SOBREVENDIDO 🟢" if rsi < 30 else "NEUTRAL ⚖️")
            macd_signal_txt = "ALCISTA 🟢" if macd > macd_signal else "BAJISTA 🔴"
            ma_signal = "ALCISTA 🟢" if current_price > ma20 > ma50 else ("BAJISTA 🔴" if current_price < ma20 < ma50 else "MIXTO ⚖️")

            return (
                f"📈 Análisis Técnico: {symbol.upper()} ({period})\n\n"
                f"RSI (14): {rsi:.1f} → {rsi_signal}\n"
                f"MACD: {macd:.4f} | Señal: {macd_signal:.4f} → {macd_signal_txt}\n"
                f"MA20: ${ma20:,.2f} | MA50: ${ma50:,.2f} → {ma_signal}\n"
                f"Precio actual: ${current_price:,.2f}"
            )
        except Exception as e:
            return f"Error en análisis técnico de {symbol}: {str(e)}"

    def compare_assets(self, symbols: str, period: str = "1mo") -> str:
        """
        Compara el rendimiento de varios activos.
        :param symbols: Símbolos separados por coma (ej: AAPL,TSLA,BTC-USD)
        :param period: Período (1mo, 3mo, 6mo, 1y)
        :return: Tabla comparativa de rendimientos
        """
        try:
            symbol_list = [s.strip().upper() for s in symbols.split(",")]
            results = []

            for sym in symbol_list[:5]:
                ticker = yf.Ticker(sym)
                hist = ticker.history(period=period)
                if hist.empty:
                    continue
                start = hist["Close"].iloc[0]
                end = hist["Close"].iloc[-1]
                change = ((end - start) / start) * 100
                results.append((sym, end, change))

            results.sort(key=lambda x: x[2], reverse=True)

            output = f"🏆 Comparativa ({period}):\n\n"
            for sym, price, chg in results:
                emoji = "🟢" if chg > 0 else "🔴"
                output += f"{emoji} {sym}: ${price:,.2f} ({chg:+.2f}%)\n"

            return output
        except Exception as e:
            return f"Error comparando activos: {str(e)}"

    def get_market_summary(self) -> str:
        """
        Muestra un resumen del mercado: índices principales, crypto top y forex.
        :return: Resumen completo del mercado
        """
        try:
            assets = {
                "Índices": ["^GSPC", "^IXIC", "^DJI"],
                "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD"],
                "Forex": ["EURUSD=X", "MXN=X"],
            }

            names = {
                "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones",
                "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana",
                "EURUSD=X": "EUR/USD", "MXN=X": "USD/MXN",
            }

            output = f"🌍 Resumen de Mercado — {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"

            for category, symbols in assets.items():
                output += f"── {category} ──\n"
                for sym in symbols:
                    try:
                        hist = yf.Ticker(sym).history(period="2d")
                        if hist.empty:
                            continue
                        current = hist["Close"].iloc[-1]
                        prev = hist["Close"].iloc[-2] if len(hist) > 1 else current
                        change = ((current - prev) / prev) * 100
                        emoji = "🟢" if change > 0 else "🔴"
                        name = names.get(sym, sym)
                        output += f"{emoji} {name}: ${current:,.2f} ({change:+.2f}%)\n"
                    except:
                        pass
                output += "\n"

            return output
        except Exception as e:
            return f"Error obteniendo resumen: {str(e)}"
