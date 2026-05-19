import streamlit as st
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone
import time

st.set_page_config(page_title="RAVEN TRADE IDEAS · Oro & DJ30", page_icon="🥇",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#07070f}
[data-testid="stHeader"]{background:transparent}
.block-container{padding:1.2rem 2rem;max-width:1300px}
.card-buy{background:linear-gradient(135deg,#001a0d,#002a14);border:1px solid #00c853;
  border-left:4px solid #00e676;border-radius:10px;padding:1.2rem 1.5rem;margin-bottom:.8rem}
.card-sell{background:linear-gradient(135deg,#1a0000,#2a0000);border:1px solid #c62828;
  border-left:4px solid #ff5252;border-radius:10px;padding:1.2rem 1.5rem;margin-bottom:.8rem}
.news-bar{background:#0d0d1a;border:1px solid #1a1a40;border-radius:8px;
  padding:.6rem 1.2rem;margin-bottom:1rem;font-size:.88em}
.badge-safe{background:#00c853;color:#000;padding:2px 10px;border-radius:20px;font-size:.78em;font-weight:700}
.badge-caution{background:#ff9800;color:#000;padding:2px 10px;border-radius:20px;font-size:.78em;font-weight:700}
.badge-danger{background:#c62828;color:#fff;padding:2px 10px;border-radius:20px;font-size:.78em;font-weight:700}
.no-signal{background:#0d0d1a;border:1px dashed #1a1a40;border-radius:10px;
  padding:2.5rem;text-align:center;color:#444;font-size:1.1em;margin-top:2rem}
div[data-testid="stButton"]>button{background:#1a1a30;color:#d8d8f8;border:1px solid #333;
  border-radius:6px;font-size:.82em;padding:4px 14px}
div[data-testid="stButton"]>button:hover{background:#2a2a50;border-color:#555}
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
SYMBOL    = "XAUUSD"
MIN_SCORE = 62
REFRESH   = 60

def _clase(score):
    if score >= 90: return "ÉLITE",    "#ffd600", "⭐⭐⭐⭐⭐"
    if score >= 80: return "FUERTE",   "#00e676", "⭐⭐⭐⭐"
    if score >= 70: return "BUENA",    "#42a5f5", "⭐⭐⭐"
    return               "MODERADA",  "#ff9800", "⭐⭐"

def _sesion():
    h = datetime.now(timezone.utc).hour
    if   h <  7: return "🌏 ASIÁTICA",    "#42a5f5"
    elif h < 12: return "🇬🇧 LONDRE S",   "#00e676"
    elif h < 17: return "🇺🇸 NUEVA YORK",  "#ff9800"
    else:        return "🌙 CERRADO",     "#666"

# ─── MT5 ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def _init_mt5():
    return mt5.initialize()

def _bars(tf, n=400):
    rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, n)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.set_index("time")

def _precio():
    t = mt5.symbol_info_tick(SYMBOL)
    return (t.bid + t.ask) / 2 if t else None

# ─── NOTICIAS (ForexFactory) ──────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_news():
    eventos = []
    for url in [
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
    ]:
        try:
            r = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue
            for e in r.json():
                if e.get("impact") == "High" and e.get("country") == "USD":
                    try:
                        dt = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
                        eventos.append({"dt": dt, "titulo": e.get("title", "")})
                    except Exception:
                        pass
        except Exception:
            pass
    return sorted(eventos, key=lambda x: x["dt"])

def _riesgo_news(eventos):
    ahora = datetime.now(timezone.utc)
    for e in eventos:
        d = (e["dt"] - ahora).total_seconds() / 60
        if -30 <= d <= 30:
            return "PELIGRO",   f"🔴 PELIGRO — {e['titulo']} {'+' if d>0 else ''}{int(d)} min"
        elif 30 < d <= 120:
            return "PRECAUCIÓN", f"🟡 PRECAUCIÓN — {e['titulo']} en {int(d)} min"
    futuros = [e for e in eventos if (e["dt"]-ahora).total_seconds() > 0]
    if futuros:
        p = futuros[0]; m = int((p["dt"]-ahora).total_seconds()/60)
        return "SEGURO", f"🟢 SEGURO — Próximo: {p['titulo']} en {m} min"
    return "SEGURO", "🟢 SEGURO — Sin eventos de alto impacto hoy"

# ─── INDICADORES ─────────────────────────────────────────────────────────────
def _ema(s, n): return s.ewm(span=n, adjust=False).mean()
def _sma(s, n): return s.rolling(n).mean()

def _atr(df, n=14):
    h, l, c = df.high, df.low, df.close
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def _rsi(s, n=14):
    d = s.diff()
    g = d.where(d > 0, 0).rolling(n).mean()
    lo = (-d.where(d < 0, 0)).rolling(n).mean()
    rs = g / lo.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def _bb(s, n=20, k=2):
    ma = _sma(s, n); std = s.rolling(n).std()
    return ma + k*std, ma, ma - k*std

def _kc(df, n=20, m=1.5):
    mid = _ema(df.close, n); a = _atr(df, n)
    return mid + m*a, mid, mid - m*a

def _swing_lows(df, n=3):
    return [i for i in range(n, len(df)-n)
            if df.low.iloc[i] == df.low.iloc[i-n:i+n+1].min()]

def _swing_highs(df, n=3):
    return [i for i in range(n, len(df)-n)
            if df.high.iloc[i] == df.high.iloc[i-n:i+n+1].max()]

# ─── RISK ─────────────────────────────────────────────────────────────────────
def _risk(entry, sl, direction, pp=10):
    d = abs(entry - sl)
    if d < 0.01:
        return None
    s = 1 if direction == "buy" else -1
    return dict(
        sl_d=d,
        tp1=entry + s*d*1.5,  rr1=1.5, g1=d*1.5*pp,
        tp2=entry + s*d*2.5,  rr2=2.5, g2=d*2.5*pp,
        tp3=entry + s*d*4.0,  rr3=4.0, g3=d*4.0*pp,
        tp4=entry + s*d*6.0,  rr4=6.0, g4=d*6.0*pp,
        riesgo=d*pp,
    )

def _fmt(v, decimals=2): return f"${v:,.{decimals}f}"

DJ30_NAMES = ["US30", "DJ30", "DJIA", "US30Cash", "DJ30Cash", "WallSt30", "WallStreet30"]

@st.cache_data(ttl=300, show_spinner=False)
def _find_dj30():
    for name in DJ30_NAMES:
        info = mt5.symbol_info(name)
        if info is not None:
            return name
    return None

def _pip_val(symbol):
    """Valor aproximado en USD por punto por lote estándar"""
    info = mt5.symbol_info(symbol)
    if info:
        tv = info.trade_tick_value
        ts = info.trade_tick_size
        if ts > 0:
            return tv / ts  # USD por punto por lote
    return 10  # fallback oro

# ═══════════════════════════════════════════════════════════════════════════════
# ESTRATEGIAS
# ═══════════════════════════════════════════════════════════════════════════════

def strat_london_breakout(df_h1, precio):
    """Ruptura del rango asiático al abrir Londres (07:00–10:00 UTC)"""
    ahora = datetime.now(timezone.utc)
    h = ahora.hour
    if not (7 <= h < 10):
        return None
    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    asian = df_h1[(df_h1.index >= hoy) & (df_h1.index < hoy.replace(hour=7))]
    if len(asian) < 3:
        return None
    a_hi = asian.high.max(); a_lo = asian.low.min()
    a_rng = a_hi - a_lo
    if a_rng < 5:
        return None
    at = _atr(df_h1).iloc[-1]
    thr = a_rng * 0.12

    for direction, cond, sl_ref in [
        ("buy",  precio > a_hi + thr, a_lo - at * 0.5),
        ("sell", precio < a_lo - thr, a_hi + at * 0.5),
    ]:
        if not cond:
            continue
        r = _risk(precio, sl_ref, direction)
        if r is None:
            continue
        score = 58
        # Rango limpio
        body_sum = (asian.close - asian.open).abs().sum()
        rng_sum  = (asian.high - asian.low).sum()
        if rng_sum > 0 and body_sum / rng_sum > 0.55:
            score += 8
        # Primera ruptura
        ld = df_h1[df_h1.index >= hoy.replace(hour=7)]
        breaks = (ld.high > a_hi).sum() if direction == "buy" else (ld.low < a_lo).sum()
        if breaks <= 1:
            score += 10
        # ATR elevado
        at_avg = _atr(df_h1).rolling(20).mean().iloc[-1]
        if at > at_avg * 1.15:
            score += 6
        return dict(estrategia="LONDON BREAKOUT", icon="🇬🇧", dir=direction,
                    entry=precio, sl=sl_ref, score_base=min(score, 88),
                    contexto=f"Rango asiático ${a_lo:.2f}–${a_hi:.2f} ({a_rng:.1f} pts). ATR H1: {at:.1f}",
                    **r)
    return None


def strat_trend_pullback(df_d1, df_h4, df_h1, df_m15, precio):
    """Tendencia MTF alineada D1+H4+H1 + pullback a EMA en M15"""
    for df, n in [(df_d1, 30), (df_h4, 50), (df_h1, 60), (df_m15, 30)]:
        if df is None or len(df) < n:
            return None

    e20d = _ema(df_d1.close, 20).iloc[-1];  e50d = _ema(df_d1.close, 50).iloc[-1]
    e20h4= _ema(df_h4.close, 20).iloc[-1];  e50h4= _ema(df_h4.close, 50).iloc[-1]
    e20h = _ema(df_h1.close, 20).iloc[-1];  e50h = _ema(df_h1.close, 50).iloc[-1]
    e200h= _ema(df_h1.close,200).iloc[-1]

    d1_bull  = df_d1.close.iloc[-1]  > e20d  > e50d
    h4_bull  = e20h4 > e50h4
    h1_stack = e20h  > e50h  > e200h
    d1_bear  = df_d1.close.iloc[-1]  < e20d  < e50d
    h4_bear  = e20h4 < e50h4
    h1_down  = e20h  < e50h  < e200h

    bull = sum([d1_bull, h4_bull, h1_stack])
    bear = sum([d1_bear, h4_bear, h1_down])
    if bull < 2 and bear < 2:
        return None

    at  = _atr(df_h1).iloc[-1]
    rs  = _rsi(df_m15.close).iloc[-1]
    direction = "buy" if bull >= bear else "sell"

    if direction == "buy":
        dist = precio - e20h
        if not (-at * 0.9 <= dist <= at * 0.4):
            return None
        if not (35 <= rs <= 55):
            return None
        sl = e50h - at * 0.3
        score = 62 + bull * 9
        if 40 <= rs <= 50: score += 5
    else:
        dist = e20h - precio
        if not (-at * 0.9 <= dist <= at * 0.4):
            return None
        if not (45 <= rs <= 65):
            return None
        sl = e50h + at * 0.3
        score = 62 + bear * 9
        if 50 <= rs <= 60: score += 5

    r = _risk(precio, sl, direction)
    if r is None:
        return None
    td = f"D1:{'▲' if d1_bull else '▼' if d1_bear else '–'}  H4:{'▲' if h4_bull else '▼' if h4_bear else '–'}  H1:{'▲' if h1_stack else '▼' if h1_down else '–'}"
    return dict(estrategia="PULLBACK TENDENCIA MTF", icon="📐", dir=direction,
                entry=precio, sl=sl, score_base=min(score, 93),
                contexto=f"{td} · RSI M15: {rs:.0f} · EMA20 H1: ${e20h:.2f}",
                **r)


def strat_ema_momentum(df_h1, df_m15, precio):
    """Cruce EMA9/21 en H1 con RSI confirmando momentum"""
    if df_h1 is None or len(df_h1) < 30 or df_m15 is None or len(df_m15) < 20:
        return None
    e9  = _ema(df_h1.close, 9)
    e21 = _ema(df_h1.close, 21)
    e50 = _ema(df_h1.close, 50)
    at  = _atr(df_h1).iloc[-1]
    at_avg = _atr(df_h1).rolling(20).mean().iloc[-1]
    if at < at_avg * 0.65:
        return None  # mercado dormido

    rh = _rsi(df_h1.close).iloc[-1]
    rm = _rsi(df_m15.close).iloc[-1]

    cross_b = e9.iloc[-2] < e21.iloc[-2] and e9.iloc[-1] > e21.iloc[-1]
    cross_s = e9.iloc[-2] > e21.iloc[-2] and e9.iloc[-1] < e21.iloc[-1]
    # Cruce reciente (≤ 2 barras atrás)
    if not cross_b and not cross_s:
        cross_b = e9.iloc[-3] < e21.iloc[-3] and e9.iloc[-2] > e21.iloc[-2] and precio > e9.iloc[-1]
        cross_s = e9.iloc[-3] > e21.iloc[-3] and e9.iloc[-2] < e21.iloc[-2] and precio < e9.iloc[-1]
    if not cross_b and not cross_s:
        return None

    if cross_b and 48 <= rh <= 72 and precio > e21.iloc[-1] * 0.998:
        sl = e21.iloc[-1] - at * 0.5
        score = 63
        if precio > e50.iloc[-1]: score += 8
        if 52 < rh < 65:          score += 5
        if 52 < rm < 65:          score += 4
        r = _risk(precio, sl, "buy")
        if r is None: return None
        return dict(estrategia="CRUCE EMA MOMENTUM", icon="⚡", dir="buy",
                    entry=precio, sl=sl, score_base=min(score, 85),
                    contexto=f"Cruce alcista EMA9/21 H1 · RSI H1:{rh:.0f}  M15:{rm:.0f} · ATR:{at:.1f}",
                    **r)

    if cross_s and 28 <= rh <= 52 and precio < e21.iloc[-1] * 1.002:
        sl = e21.iloc[-1] + at * 0.5
        score = 63
        if precio < e50.iloc[-1]: score += 8
        if 35 < rh < 48:          score += 5
        if 35 < rm < 48:          score += 4
        r = _risk(precio, sl, "sell")
        if r is None: return None
        return dict(estrategia="CRUCE EMA MOMENTUM", icon="⚡", dir="sell",
                    entry=precio, sl=sl, score_base=min(score, 85),
                    contexto=f"Cruce bajista EMA9/21 H1 · RSI H1:{rh:.0f}  M15:{rm:.0f} · ATR:{at:.1f}",
                    **r)
    return None


def strat_supply_demand(df_h4, df_h1, precio):
    """Precio en zona de oferta/demanda H4 confirmada con RSI"""
    if df_h4 is None or len(df_h4) < 50 or df_h1 is None or len(df_h1) < 20:
        return None
    at4 = _atr(df_h4).iloc[-1]
    at1 = _atr(df_h1).iloc[-1]
    rh  = _rsi(df_h1.close).iloc[-1]

    for idx in _swing_lows(df_h4, n=4)[-10:]:
        z = df_h4.low.iloc[idx]
        zt, zb = z + at4, z - at4 * 0.3
        if zb <= precio <= zt and rh < 42:
            sl = z - at4 * 0.45
            r  = _risk(precio, sl, "buy")
            if r is None: continue
            tests = sum(1 for i in range(len(df_h4)) if zb <= df_h4.low.iloc[i] <= zt)
            score = 66 + (10 if tests <= 2 else 0) + (10 if rh < 35 else 0)
            return dict(estrategia="ZONA DE DEMANDA (S&D)", icon="🏛️", dir="buy",
                        entry=precio, sl=sl, score_base=min(score, 92),
                        contexto=f"Zona demanda H4: ${z:.2f} · RSI H1:{rh:.0f} · Testeada {tests}x",
                        **r)

    for idx in _swing_highs(df_h4, n=4)[-10:]:
        z = df_h4.high.iloc[idx]
        zb, zt = z - at4, z + at4 * 0.3
        if zb <= precio <= zt and rh > 58:
            sl = z + at4 * 0.45
            r  = _risk(precio, sl, "sell")
            if r is None: continue
            tests = sum(1 for i in range(len(df_h4)) if zb <= df_h4.high.iloc[i] <= zt)
            score = 66 + (10 if tests <= 2 else 0) + (10 if rh > 65 else 0)
            return dict(estrategia="ZONA DE OFERTA (S&D)", icon="🏛️", dir="sell",
                        entry=precio, sl=sl, score_base=min(score, 92),
                        contexto=f"Zona oferta H4: ${z:.2f} · RSI H1:{rh:.0f} · Testeada {tests}x",
                        **r)
    return None


def strat_bb_squeeze(df_h1, precio):
    """Bollinger Bands dentro de Keltner Channel → liberación con dirección"""
    if df_h1 is None or len(df_h1) < 30:
        return None
    bb_u, bb_m, bb_d = _bb(df_h1.close, 20, 2)
    kc_u, kc_m, kc_d = _kc(df_h1, 20, 1.5)
    at = _atr(df_h1).iloc[-1]
    rh = _rsi(df_h1.close).iloc[-1]

    # Squeeze activo en barra -2
    sq = bb_u.iloc[-2] < kc_u.iloc[-2] and bb_d.iloc[-2] > kc_d.iloc[-2]
    if not sq:
        sq = bb_u.iloc[-3] < kc_u.iloc[-3] and bb_d.iloc[-3] > kc_d.iloc[-3]
    if not sq:
        return None
    # Liberación en barra -1
    released = bb_u.iloc[-1] > kc_u.iloc[-1] or bb_d.iloc[-1] < kc_d.iloc[-1]
    if not released:
        return None

    roc = (df_h1.close.iloc[-1] / df_h1.close.iloc[-6] - 1) * 100

    if roc > 0.1 and precio > bb_m.iloc[-1] and rh > 50:
        sl = bb_m.iloc[-1] - at * 0.5
        r  = _risk(precio, sl, "buy")
        if r is None: return None
        score = 68 + (7 if roc > 0.3 else 0) + (5 if rh > 55 else 0)
        return dict(estrategia="BB SQUEEZE BREAKOUT", icon="💥", dir="buy",
                    entry=precio, sl=sl, score_base=min(score, 88),
                    contexto=f"Squeeze liberado ↑ · ROC5: +{roc:.2f}% · RSI H1:{rh:.0f}",
                    **r)

    if roc < -0.1 and precio < bb_m.iloc[-1] and rh < 50:
        sl = bb_m.iloc[-1] + at * 0.5
        r  = _risk(precio, sl, "sell")
        if r is None: return None
        score = 68 + (7 if roc < -0.3 else 0) + (5 if rh < 45 else 0)
        return dict(estrategia="BB SQUEEZE BREAKOUT", icon="💥", dir="sell",
                    entry=precio, sl=sl, score_base=min(score, 88),
                    contexto=f"Squeeze liberado ↓ · ROC5: {roc:.2f}% · RSI H1:{rh:.0f}",
                    **r)
    return None


def strat_precio_accion(df_h1, precio, df_d1=None):
    """Patrones de vela en H1: Engulfing y Pin Bar"""
    if df_h1 is None or len(df_h1) < 5:
        return None
    at = _atr(df_h1).iloc[-1]
    rh = _rsi(df_h1.close).iloc[-1]
    o2,h2,l2,c2 = df_h1[["open","high","low","close"]].iloc[-2].values
    o1,h1_,l1,c1 = df_h1[["open","high","low","close"]].iloc[-1].values
    b1 = abs(c1-o1); rng1 = h1_-l1
    if rng1 < at * 0.3:
        return None

    bull_eng = (c2 < o2) and (c1 > o1) and (c1 > o2) and (o1 < c2) and b1 > abs(c2-o2)*1.1
    bear_eng = (c2 > o2) and (c1 < o1) and (c1 < o2) and (o1 > c2) and b1 > abs(c2-o2)*1.1
    hammer   = (b1 > 0) and (c1-l1) > b1*2 and (c1 > o1) and (h1_-c1) < b1*0.5
    shooting = (b1 > 0) and (h1_-c1) > b1*2 and (c1 < o1) and (c1-l1) < b1*0.5

    # Verificar nivel clave (redondo $50/$100 o prev-day H/L)
    near_key = False
    for step in [50, 100]:
        rnd = round(precio / step) * step
        if abs(precio - rnd) <= at * 1.2:
            near_key = True; break
    if df_d1 is not None and len(df_d1) >= 2:
        pd_h = df_d1.high.iloc[-2]; pd_l = df_d1.low.iloc[-2]
        if abs(precio - pd_h) <= at * 1.2 or abs(precio - pd_l) <= at * 1.2:
            near_key = True

    if (bull_eng or hammer) and rh < 62:
        sl = l1 - at * 0.3
        r  = _risk(c1, sl, "buy")
        if r is None: return None
        patron = "Engulfing Alcista" if bull_eng else "Martillo"
        score  = 63 + (8 if bull_eng else 0) + (12 if near_key else 0) + (5 if rh < 40 else 0)
        return dict(estrategia=f"PRECIO ACCIÓN — {patron}", icon="🕯️", dir="buy",
                    entry=c1, sl=sl, score_base=min(score, 91),
                    contexto=f"{patron} H1 · RSI:{rh:.0f} · {'✓ Nivel clave' if near_key else 'Sin nivel'}",
                    **r)

    if (bear_eng or shooting) and rh > 38:
        sl = h1_ + at * 0.3
        r  = _risk(c1, sl, "sell")
        if r is None: return None
        patron = "Engulfing Bajista" if bear_eng else "Estrella Fugaz"
        score  = 63 + (8 if bear_eng else 0) + (12 if near_key else 0) + (5 if rh > 60 else 0)
        return dict(estrategia=f"PRECIO ACCIÓN — {patron}", icon="🕯️", dir="sell",
                    entry=c1, sl=sl, score_base=min(score, 91),
                    contexto=f"{patron} H1 · RSI:{rh:.0f} · {'✓ Nivel clave' if near_key else 'Sin nivel'}",
                    **r)
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════════════════════
def _news_badge(nivel):
    m = {"PELIGRO": "badge-danger", "PRECAUCIÓN": "badge-caution", "SEGURO": "badge-safe"}
    return f'<span class="{m.get(nivel,"badge-safe")}">{nivel}</span>'

def _card(s, news_nivel, news_txt):
    cls, col, stars = _clase(s["score"])
    dc = "#00e676" if s["dir"] == "buy" else "#ff5252"
    dt = "▲ COMPRA" if s["dir"] == "buy" else "▼ VENTA"
    cc = "card-buy" if s["dir"] == "buy" else "card-sell"
    nb = _news_badge(news_nivel)
    return f"""
<div class="{cc}">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div>
      <span style="color:{dc};font-size:1.25em;font-weight:900">{dt}</span>
      <span style="color:#aaa;margin-left:10px;font-size:.9em">{s['icon']} {s['estrategia']}</span>
    </div>
    <div style="display:flex;gap:8px;align-items:center">{nb}</div>
  </div>
  <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:10px">
    <div>
      <div style="color:#555;font-size:.72em">SCORE</div>
      <div style="color:{col};font-size:1.5em;font-weight:900">{s['score']}/100</div>
      <div style="color:{col};font-size:.78em">{cls} {stars[:2]}</div>
    </div>
    <div style="border-left:1px solid #222;padding-left:20px">
      <div style="color:#555;font-size:.72em">ENTRADA</div>
      <div style="color:#fff;font-size:1.2em;font-weight:700">{_fmt(s['entry'])}</div>
    </div>
    <div style="border-left:1px solid #222;padding-left:20px">
      <div style="color:#555;font-size:.72em">STOP LOSS</div>
      <div style="color:#ff5252;font-size:1.1em;font-weight:700">{_fmt(s['sl'])}</div>
      <div style="color:#555;font-size:.76em">−{s['sl_d']:.1f} pts</div>
    </div>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
    <div style="background:#0a1a0a;border:1px solid #1a3a1a;border-radius:6px;padding:5px 12px">
      <div style="color:#555;font-size:.68em">TP1 · 1:{s['rr1']:.1f}</div>
      <div style="color:#00e676;font-weight:700;font-size:.95em">{_fmt(s['tp1'])}</div>
    </div>
    <div style="background:#0a1a0a;border:1px solid #1a3a1a;border-radius:6px;padding:5px 12px">
      <div style="color:#555;font-size:.68em">TP2 · 1:{s['rr2']:.1f}</div>
      <div style="color:#00e676;font-weight:700;font-size:.95em">{_fmt(s['tp2'])}</div>
    </div>
    <div style="background:#0a1a0a;border:1px solid #1a3a1a;border-radius:6px;padding:5px 12px">
      <div style="color:#555;font-size:.68em">TP3 · 1:{s['rr3']:.1f}</div>
      <div style="color:#00e676;font-weight:700;font-size:.95em">{_fmt(s['tp3'])}</div>
    </div>
    <div style="background:#1a1000;border:1px solid #3a2a00;border-radius:6px;padding:5px 12px">
      <div style="color:#555;font-size:.68em">TP4 · 1:{s['rr4']:.1f}</div>
      <div style="color:#ffd600;font-weight:700;font-size:.95em">{_fmt(s['tp4'])}</div>
    </div>
  </div>
  <div style="color:#666;font-size:.82em">{s['contexto']}</div>
</div>"""

def _texto(s, news_txt):
    dt = "▲ BUY  /  COMPRA" if s["dir"] == "buy" else "▼ SELL  /  VENTA"
    ts = datetime.now(timezone.utc).strftime("%d/%m/%Y  %H:%M UTC")
    return (
        f"🥇 RAVEN TRADE IDEAS · XAUUSD ORO\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{dt}\n"
        f"{s['icon']}  {s['estrategia']}\n"
        f"Score: {s['score']}/100  ·  {s['clase']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Entrada:  {_fmt(s['entry'])}\n"
        f"🛑 Stop:     {_fmt(s['sl'])}   (−{s['sl_d']:.1f} pts)\n"
        f"🎯 TP1:      {_fmt(s['tp1'])}   1:{s['rr1']:.1f}\n"
        f"🎯 TP2:      {_fmt(s['tp2'])}   1:{s['rr2']:.1f}\n"
        f"🎯 TP3:      {_fmt(s['tp3'])}   1:{s['rr3']:.1f}\n"
        f"💎 TP4:      {_fmt(s['tp4'])}   1:{s['rr4']:.1f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📰 Noticias: {news_txt}\n"
        f"ℹ️  {s['contexto']}\n"
        f"⏰  {ts}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def _bars_sym(symbol, tf, n=400):
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.set_index("time")

def _precio_sym(symbol):
    t = mt5.symbol_info_tick(symbol)
    return (t.bid + t.ask) / 2 if t else None


def _render_senales(symbol, n_nivel, n_txt, pen, decimals, tab_prefix):
    precio = _precio_sym(symbol)
    if precio is None:
        st.warning(f"⚠️ Sin precio para {symbol}.")
        return

    with st.spinner(f"Analizando {symbol}…"):
        df_m15 = _bars_sym(symbol, mt5.TIMEFRAME_M15, 400)
        df_h1  = _bars_sym(symbol, mt5.TIMEFRAME_H1,  400)
        df_h4  = _bars_sym(symbol, mt5.TIMEFRAME_H4,  300)
        df_d1  = _bars_sym(symbol, mt5.TIMEFRAME_D1,  200)

    pp = _pip_val(symbol)

    at_h1  = _atr(df_h1).iloc[-1]       if df_h1 is not None else 0
    rsi_h1 = _rsi(df_h1.close).iloc[-1] if df_h1 is not None else 50
    e200   = _ema(df_h1.close, 200).iloc[-1] if df_h1 is not None else precio
    tend   = "▲ ALCISTA" if precio > e200 else "▼ BAJISTA"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"💰 {symbol}", _fmt(precio, decimals))
    c2.metric("📊 ATR H1",       f"{at_h1:.1f} pts")
    c3.metric("📈 RSI H1",       f"{rsi_h1:.0f}")
    c4.metric("🧭 TENDENCIA H1", tend)
    st.markdown("<hr style='border:none;border-top:1px solid #1a1a30;margin:.8rem 0'>",
                unsafe_allow_html=True)

    # Estrategias — DJ30 no usa London Breakout (sin sesión asiática relevante)
    is_gold = symbol == "XAUUSD"

    def r(entry, sl, direction):
        return _risk(entry, sl, direction, pp)

    candidatos = []
    if is_gold:
        candidatos.append(strat_london_breakout(df_h1, precio))
    candidatos += [
        strat_trend_pullback(df_d1, df_h4, df_h1, df_m15, precio),
        strat_ema_momentum(df_h1, df_m15, precio),
        strat_supply_demand(df_h4, df_h1, precio),
        strat_bb_squeeze(df_h1, precio),
        strat_precio_accion(df_h1, precio, df_d1),
    ]

    senales = []
    for s in candidatos:
        if s is None:
            continue
        # Recalcular ganancias con pp correcto
        d = s["sl_d"]
        pp_local = pp
        s.update(g1=d*1.5*pp_local, g2=d*2.5*pp_local,
                 g3=d*4.0*pp_local, g4=d*6.0*pp_local, riesgo=d*pp_local)
        s["score"] = max(s["score_base"] - pen, 0)
        if s["score"] < MIN_SCORE:
            continue
        cls, col, st_s = _clase(s["score"])
        s["clase"] = cls; s["color"] = col; s["stars"] = st_s
        senales.append(s)

    senales.sort(key=lambda x: x["score"], reverse=True)
    ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    n_strats = 6 if is_gold else 5

    if n_nivel == "PELIGRO":
        st.markdown(f"""
        <div style="background:#1a0000;border:2px solid #c62828;border-radius:10px;
             padding:1.2rem;text-align:center;margin-bottom:1rem">
          <div style="color:#ff5252;font-size:1.2em;font-weight:900">🔴 ZONA DE PELIGRO — NOTICIAS ACTIVAS</div>
          <div style="color:#888;margin-top:4px;font-size:.9em">{n_txt}</div>
        </div>""", unsafe_allow_html=True)

    if not senales:
        st.markdown(f"""
        <div class="no-signal">
          <div style="font-size:2em;margin-bottom:6px">🔍</div>
          <div style="color:#666">Sin señales activas en este momento</div>
          <div style="color:#333;font-size:.82em;margin-top:6px">
            {n_strats} estrategias monitoreando {symbol} · {ts_str}
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='color:#555;font-size:.82em;margin-bottom:6px'>"
                    f"✅ {len(senales)} señal{'es' if len(senales)>1 else ''} activa{'s' if len(senales)>1 else ''} "
                    f"· {ts_str}</div>", unsafe_allow_html=True)
        for i, s in enumerate(senales):
            st.markdown(_card(s, n_nivel, n_txt), unsafe_allow_html=True)
            key = f"{tab_prefix}_{i}_{s['estrategia'].replace(' ','_')}_{int(s['score'])}"
            if st.button("📋 Copiar señal", key=key):
                st.session_state[f"show_{key}"] = not st.session_state.get(f"show_{key}", False)
            if st.session_state.get(f"show_{key}", False):
                st.code(_texto(s, n_txt), language=None)


def main():
    sesion, ses_color = _sesion()
    eventos  = _fetch_news()
    n_nivel, n_txt = _riesgo_news(eventos)
    pen = {"PELIGRO": 30, "PRECAUCIÓN": 10, "SEGURO": 0}.get(n_nivel, 0)

    # ── Header ────────────────────────────────────────────────────────────────
    nb = _news_badge(n_nivel)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#07070f,#150a00);border:1px solid #3d2b00;
         border-radius:12px;padding:1.2rem 1.8rem;margin-bottom:1rem;
         display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="color:#ffd600;font-size:1.5em;font-weight:900">🥇 RAVEN TRADE IDEAS · ORO &amp; DJ30</div>
        <div style="color:#555;font-size:.85em;margin-top:2px">
          XAUUSD + DJ30 · 6 estrategias · Filtro noticias en tiempo real
        </div>
      </div>
      <div style="text-align:right">
        <div style="color:{ses_color};font-size:1em;font-weight:700">{sesion}</div>
        <div style="margin-top:4px">{nb}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Barra noticias ────────────────────────────────────────────────────────
    nc = {"PELIGRO": "#c62828", "PRECAUCIÓN": "#ff9800", "SEGURO": "#00c853"}
    st.markdown(f"""
    <div class="news-bar">
      <span style="color:#555">📰 NOTICIAS USD (afectan Oro y DJ30):</span>
      <span style="color:{nc.get(n_nivel,'#00c853')};font-weight:700;margin-left:8px">{n_txt}</span>
    </div>""", unsafe_allow_html=True)

    ahora = datetime.now(timezone.utc)
    prox = [e for e in eventos if (e["dt"]-ahora).total_seconds() > 0][:3]
    if prox:
        html_ev = "  ".join(
            f'<span style="color:#3a3a5a;font-size:.78em">⏰ {e["titulo"]} {e["dt"].strftime("%d/%m %H:%M")} UTC</span>'
            for e in prox)
        st.markdown(f'<div style="margin-bottom:.8rem">{html_ev}</div>', unsafe_allow_html=True)

    # ── MT5 ───────────────────────────────────────────────────────────────────
    if not _init_mt5():
        st.error("❌ No se pudo conectar a MetaTrader 5. Abre MT5 primero.")
        return

    # ── Tabs ──────────────────────────────────────────────────────────────────
    dj30_sym = _find_dj30()
    tab_labels = ["🥇 XAUUSD · ORO"]
    if dj30_sym:
        tab_labels.append(f"📈 {dj30_sym} · DJ30")
    else:
        tab_labels.append("📈 DJ30 (no disponible)")

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _render_senales("XAUUSD", n_nivel, n_txt, pen, decimals=2, tab_prefix="oro")

    with tabs[1]:
        if dj30_sym:
            _render_senales(dj30_sym, n_nivel, n_txt, pen, decimals=0, tab_prefix="dj30")
        else:
            st.markdown(f"""
            <div class="no-signal">
              <div style="font-size:1.8em;margin-bottom:6px">📈</div>
              <div style="color:#555">DJ30 no encontrado en esta cuenta MT5</div>
              <div style="color:#333;font-size:.82em;margin-top:6px">
                Símbolos buscados: {', '.join(DJ30_NAMES)}
              </div>
            </div>""", unsafe_allow_html=True)

    # ── Footer + Refresh ──────────────────────────────────────────────────────
    st.markdown("""
    <div style="color:#1a1a30;font-size:.72em;text-align:center;margin-top:2rem;
         padding-top:1rem;border-top:1px solid #0d0d20">
      RAVEN TRADE IDEAS · Solo educativo · Gestiona siempre tu riesgo
    </div>""", unsafe_allow_html=True)

    time.sleep(REFRESH)
    st.rerun()


if __name__ == "__main__":
    main()
