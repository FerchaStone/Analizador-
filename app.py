"""
Analizador de acciones - dashboard (Streamlit)

Se escribe uno o mas tickers de EE.UU. y muestra, para cada uno:
- una nota de 0 a 10 con anillo de color
- 6 indicadores ordenados por importancia, con valor, calificacion en palabras,
  barra de puntaje, frase simple y escala de referencia
- chequeos de riesgo (reverse splits, dilucion, caja)
- grafico de precio del ultimo anio
- si hay varios tickers, una tabla comparativa arriba

Datos: Yahoo Finance via yfinance. Son orientativos: verificar antes de decidir.
"""

import html
import time
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Analizador de acciones", page_icon="📊", layout="wide")

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------
st.markdown(
    """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stTextInput, button {font-family: 'Inter', sans-serif !important;}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {visibility: hidden;}
.block-container {padding-top: 1.5rem; max-width: 1180px;}

.hero {background: linear-gradient(135deg, #312e81 0%, #6d28d9 55%, #db2777 100%);
  border-radius: 20px; padding: 28px 32px; color: #fff; margin-bottom: 18px;
  box-shadow: 0 10px 30px rgba(109,40,217,.25);}
.hero h1 {font-size: 34px; font-weight: 800; margin: 0; color: #fff; padding: 0;}
.hero p {margin: 6px 0 0; opacity: .85; font-size: 15px;}

div[data-testid="stForm"] {border: none; padding: 0;}
.stTextInput input {border-radius: 12px !important; font-size: 16px !important; padding: 12px 14px !important;}
div[data-testid="stFormSubmitButton"] button {width: 100%; border-radius: 12px; border: none;
  background: linear-gradient(135deg, #6d28d9, #db2777); color: #fff; font-weight: 700;
  padding: 11px 0; transition: transform .15s, box-shadow .15s;}
div[data-testid="stFormSubmitButton"] button:hover {transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(219,39,119,.35); color: #fff;}

.empresa {display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;
  gap: 18px; margin: 10px 0 18px;}
.empresa .titulo {font-size: 28px; font-weight: 800; line-height: 1.15;}
.empresa .sub {opacity: .65; font-size: 14px; margin-top: 4px;}
.tick {display:inline-block; background: rgba(109,40,217,.12); color: #6d28d9; border-radius: 8px;
  padding: 2px 10px; font-size: 14px; font-weight: 700; margin-left: 8px; vertical-align: middle;}

.stats {display:grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr)); gap: 12px; margin-bottom: 18px;}
.stat {background: rgba(128,128,128,.07); border-radius: 14px; padding: 14px 16px;}
.stat .l {font-size: 12px; opacity: .6; text-transform: uppercase; letter-spacing: .05em;}
.stat .v {font-size: 22px; font-weight: 700; margin-top: 4px;}

.notabox {display:flex; align-items:center; gap: 26px; flex-wrap: wrap; border-radius: 18px;
  padding: 20px 24px; background: rgba(128,128,128,.07); margin-bottom: 20px;
  border: 1px solid rgba(128,128,128,.15);}
.anillo {position: relative; width: 120px; height: 120px; flex-shrink: 0;}
.anillo .ring {position:absolute; inset:0; border-radius:50%;
  background: conic-gradient(var(--c) calc(var(--p) * 1%), rgba(128,128,128,.18) 0);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 13px), #000 calc(100% - 12px));
          mask: radial-gradient(farthest-side, transparent calc(100% - 13px), #000 calc(100% - 12px));}
.anillo .n {position:absolute; inset:0; display:flex; flex-direction:column; align-items:center;
  justify-content:center; font-size: 34px; font-weight: 800; color: var(--c); line-height: 1;}
.anillo .n small {font-size: 12px; opacity: .6; font-weight: 600; margin-top: 4px; color: inherit;}
.notabox .et {font-size: 22px; font-weight: 800; color: var(--c);}
.notabox .ex {opacity: .7; font-size: 14px; margin-top: 6px; max-width: 620px;}

.tarjeta {background: rgba(128,128,128,.07); border-radius: 16px; padding: 18px 18px 16px;
  border: 1px solid rgba(128,128,128,.14); border-top: 5px solid var(--c);
  margin-bottom: 16px; min-height: 270px; transition: transform .15s, box-shadow .15s;}
.tarjeta:hover {transform: translateY(-2px); box-shadow: 0 8px 22px rgba(0,0,0,.08);}
.tarjeta .top {display:flex; justify-content:space-between; align-items:center; gap:8px;}
.tarjeta .rank {font-size: 11px; opacity: .55; text-transform: uppercase; letter-spacing: .06em; font-weight: 600;}
.tarjeta .nombre {font-size: 15px; font-weight: 600; margin: 8px 0 4px;}
.tarjeta .valor {font-size: 32px; font-weight: 800; line-height: 1.1;}
.badge {background: var(--c); color: #fff; border-radius: 999px; padding: 4px 12px;
  font-size: 12px; font-weight: 700; white-space: nowrap;}
.barra {height: 7px; border-radius: 99px; background: rgba(128,128,128,.18); margin: 12px 0 4px; overflow: hidden;}
.barra div {height: 100%; border-radius: 99px; background: var(--c);}
.frase {font-size: 14px; margin-top: 10px; line-height: 1.45;}
.escala {font-size: 11.5px; opacity: .6; margin-top: 10px; line-height: 1.4;}

.seccion {font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
  opacity: .6; margin: 10px 0 8px;}
.chip {display:inline-block; border-radius: 999px; padding: 6px 14px; margin: 4px 6px 4px 0;
  font-size: 13px; font-weight: 600; color: var(--c); background: color-mix(in srgb, var(--c) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--c) 35%, transparent);}

.tabla {width:100%; border-collapse: separate; border-spacing: 0 6px; font-size: 14px;}
.tabla th {text-align:left; font-size: 11.5px; text-transform: uppercase; letter-spacing: .05em;
  opacity: .6; font-weight: 600; padding: 4px 10px;}
.tabla td {background: rgba(128,128,128,.07); padding: 10px;}
.tabla td:first-child {border-radius: 10px 0 0 10px; font-weight: 700;}
.tabla td:last-child {border-radius: 0 10px 10px 0;}
.pill {display:inline-block; border-radius: 999px; padding: 3px 10px; font-size: 12px; font-weight: 700;
  color: #fff; background: var(--c); white-space: nowrap;}
.tabla-wrap {overflow-x: auto; margin-bottom: 18px;}
</style>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Colores y utilidades
# ---------------------------------------------------------------------------
VERDE_OSC = "#15803d"
VERDE = "#16a34a"
VERDE_CLARO = "#65a30d"
AMARILLO = "#ca8a04"
NARANJA = "#ea580c"
ROJO = "#dc2626"
GRIS = "#6b7280"
INF = float("inf")

SECTORES_FINANCIEROS = {"Financial Services", "Financial"}


def num(x):
    try:
        if x is None:
            return None
        v = float(x)
        return None if pd.isna(v) else v
    except (TypeError, ValueError):
        return None


def fmt_num(x, dec=1):
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(x, dec=1):
    return fmt_num(x * 100, dec) + "%"


def fmt_x(x):
    return fmt_num(x, 1) + "x"


def escalon(v, tramos):
    """tramos: lista de (limite_superior, etiqueta, puntos, color). Usa el primero con v < limite."""
    for limite, etiqueta, puntos, color in tramos:
        if v < limite:
            return etiqueta, puntos, color
    _, etiqueta, puntos, color = tramos[-1]
    return etiqueta, puntos, color


def resultado(base, valor, etiqueta, puntos, color, frase):
    return {**base, "valor": valor, "etiqueta": etiqueta, "puntos": puntos,
            "color": color, "frase": frase}


def sin_dato(base):
    return resultado(base, "s/d", "Sin dato", None, GRIS,
                     "Yahoo no informa este dato para esta empresa.")


# ---------------------------------------------------------------------------
# Los 6 indicadores, en orden de importancia
# ---------------------------------------------------------------------------
def m_margen(info):
    base = {"nombre": "Rentabilidad (margen neto)", "icono": "💰", "corto": "Rentabilidad", "peso": 20,
            "escala": "Negativo: malo · 0-5%: flojo · 5-10%: aceptable · 10-20%: bueno · "
                      "20-30%: muy bueno · +30%: excelente"}
    v = num(info.get("profitMargins"))
    if v is None:
        return sin_dato(base)
    et, p, c = escalon(v, [(0, "Malo", 0, ROJO), (0.05, "Flojo", 3, NARANJA),
                           (0.10, "Aceptable", 5, AMARILLO), (0.20, "Bueno", 7, VERDE_CLARO),
                           (0.30, "Muy bueno", 9, VERDE), (INF, "Excelente", 10, VERDE_OSC)])
    if v < 0:
        frase = f"Pierde USD {fmt_num(abs(v) * 100)} por cada USD 100 que vende."
    else:
        frase = f"De cada USD 100 que vende, le quedan USD {fmt_num(v * 100)} de ganancia."
    return resultado(base, fmt_pct(v), et, p, c, frase)


def m_crecimiento(info):
    base = {"nombre": "Crecimiento de ventas", "icono": "📈", "corto": "Crecimiento", "peso": 20,
            "escala": "Negativo: malo · 0-5%: flojo · 5-10%: aceptable · 10-20%: bueno · "
                      "20-40%: muy bueno · +40%: excelente"}
    v = num(info.get("revenueGrowth"))
    if v is None:
        return sin_dato(base)
    et, p, c = escalon(v, [(0, "Malo", 0, ROJO), (0.05, "Flojo", 3, NARANJA),
                           (0.10, "Aceptable", 5, AMARILLO), (0.20, "Bueno", 7, VERDE_CLARO),
                           (0.40, "Muy bueno", 9, VERDE), (INF, "Excelente", 10, VERDE_OSC)])
    if v < 0:
        frase = f"Vende {fmt_pct(abs(v))} menos que hace un año."
    else:
        frase = f"Vende {fmt_pct(v)} más que hace un año."
    return resultado(base, fmt_pct(v), et, p, c, frase)


def m_valuacion(info):
    base = {"nombre": "Valuación (PER)", "icono": "🏷️", "corto": "Valuación", "peso": 20,
            "escala": "-10x: muy barato (ojo trampas) · 10-15x: barato · 15-22x: razonable · "
                      "22-30x: exigente · 30-45x: caro · +45x: muy caro. Tech suele cotizar más caro."}
    forward = num(info.get("forwardPE"))
    trailing = num(info.get("trailingPE"))
    pe = forward if forward is not None else trailing
    margen = num(info.get("profitMargins"))
    if pe is None or pe <= 0:
        if (margen is not None and margen < 0) or (pe is not None and pe <= 0):
            return resultado(base, "—", "Sin ganancias", 2, NARANJA,
                             "Todavía no gana plata: el precio se sostiene solo por expectativas.")
        return sin_dato(base)
    et, p, c = escalon(pe, [(10, "Muy barato", 8, VERDE), (15, "Barato", 9, VERDE_OSC),
                            (22, "Razonable", 7, VERDE_CLARO), (30, "Exigente", 5, AMARILLO),
                            (45, "Caro", 3, NARANJA), (INF, "Muy caro", 1, ROJO)])
    tipo = "esperadas" if forward is not None else "actuales"
    frase = f"Pagás {fmt_num(pe, 0)} años de ganancias {tipo}."
    if pe < 10:
        frase += " Tan bajo a veces significa que el mercado espera problemas."
    return resultado(base, fmt_x(pe), et, p, c, frase)


def m_deuda(info):
    base = {"nombre": "Deuda / Patrimonio", "icono": "🏦", "corto": "Deuda", "peso": 15,
            "escala": "-0,3x: excelente · 0,3-0,7x: muy bueno · 0,7-1,2x: bueno · "
                      "1,2-2x: aceptable · 2-3x: flojo · +3x: alto. Con tasas altas pesa más."}
    if info.get("sector") in SECTORES_FINANCIEROS:
        return resultado(base, "—", "No aplica", None, GRIS,
                         "En bancos y financieras la deuda es parte del negocio: "
                         "este ratio no sirve para evaluarlos.")
    de = num(info.get("debtToEquity"))
    if de is None:
        return sin_dato(base)
    de = de / 100  # yfinance lo informa en porcentaje
    if de < 0:
        return resultado(base, fmt_x(de), "Patrimonio negativo", 3, NARANJA,
                         "Su patrimonio contable es negativo (suele pasar por recompras "
                         "agresivas). Mirá la deuda contra la caja que genera.")
    et, p, c = escalon(de, [(0.3, "Excelente", 10, VERDE_OSC), (0.7, "Muy bueno", 8, VERDE),
                            (1.2, "Bueno", 7, VERDE_CLARO), (2, "Aceptable", 5, AMARILLO),
                            (3, "Flojo", 3, NARANJA), (INF, "Alto", 1, ROJO)])
    frase = f"Debe USD {fmt_num(de, 2)} por cada USD 1 de patrimonio."
    return resultado(base, fmt_x(de), et, p, c, frase)


def m_roe(info):
    base = {"nombre": "ROE (retorno sobre capital)", "icono": "⚙️", "corto": "ROE", "peso": 15,
            "escala": "Negativo: malo · 0-8%: flojo · 8-15%: aceptable · 15-20%: bueno · "
                      "20-30%: muy bueno · +30%: excelente. Arriba de 60% suele ser engañoso."}
    v = num(info.get("returnOnEquity"))
    if v is None:
        return sin_dato(base)
    if v > 0.60:
        return resultado(base, fmt_pct(v), "Engañoso", 6, AMARILLO,
                         "Tan alto casi siempre es porque el patrimonio es chico "
                         "(recompras o deuda), no porque el negocio sea extraordinario.")
    et, p, c = escalon(v, [(0, "Malo", 0, ROJO), (0.08, "Flojo", 3, NARANJA),
                           (0.15, "Aceptable", 5, AMARILLO), (0.20, "Bueno", 7, VERDE_CLARO),
                           (0.30, "Muy bueno", 9, VERDE), (INF, "Excelente", 10, VERDE_OSC)])
    frase = f"Por cada USD 100 de los accionistas, genera USD {fmt_num(v * 100)} por año."
    return resultado(base, fmt_pct(v), et, p, c, frase)


def m_dividendo(info, precio):
    base = {"nombre": "Dividendo", "icono": "💵", "corto": "Dividendo", "peso": 10,
            "escala": "Se evalúa el payout (qué parte de la ganancia reparte): -50%: muy "
                      "sostenible · 50-70%: sostenible · 70-90%: ajustado · +90%: en riesgo"}
    rate = num(info.get("dividendRate"))
    y = rate / precio if (rate and precio) else None
    if not y:
        return resultado(base, "0%", "No paga", None, GRIS,
                         "No reparte dividendos: reinvierte la ganancia. Normal en empresas "
                         "que crecen; no suma ni resta a la nota.")
    payout = num(info.get("payoutRatio"))
    if not payout:
        return resultado(base, fmt_pct(y), "Sin dato de payout", None, GRIS,
                         f"Rinde {fmt_pct(y)} anual, pero no hay dato para saber si es sostenible.")
    et, p, c = escalon(payout, [(0.5, "Muy sostenible", 10, VERDE_OSC),
                                (0.7, "Sostenible", 8, VERDE),
                                (0.9, "Ajustado", 4, AMARILLO), (INF, "En riesgo", 1, ROJO)])
    frase = f"Rinde {fmt_pct(y)} anual y reparte el {fmt_pct(payout, 0)} de su ganancia."
    if payout >= 0.9:
        frase += " Si la ganancia baja, lo más probable es que lo recorten."
    return resultado(base, fmt_pct(y), et, p, c, frase)


# ---------------------------------------------------------------------------
# Chequeos de riesgo
# ---------------------------------------------------------------------------
def chequeos(info, reverse_splits, dilucion):
    chips = []
    if reverse_splits is None:
        chips.append(("Reverse splits: sin dato", GRIS))
    elif reverse_splits == 0:
        chips.append(("Sin reverse splits en 5 años", VERDE))
    else:
        chips.append((f"{reverse_splits} reverse split(s) en 5 años", ROJO))

    if dilucion is None:
        chips.append(("Dilución: sin dato", GRIS))
    elif dilucion < -0.005:
        chips.append((f"Recompra acciones ({fmt_pct(abs(dilucion))}/año)", VERDE))
    elif dilucion <= 0.03:
        chips.append(("Sin dilución relevante", VERDE))
    elif dilucion <= 0.10:
        chips.append((f"Dilución moderada ({fmt_pct(dilucion)}/año)", AMARILLO))
    else:
        chips.append((f"Dilución alta ({fmt_pct(dilucion)}/año)", ROJO))

    fcf = num(info.get("freeCashflow"))
    caja = num(info.get("totalCash"))
    if fcf is None:
        chips.append(("Flujo de caja: sin dato", GRIS))
    elif fcf >= 0:
        chips.append((f"Genera caja (USD {fmt_num(fcf / 1e6, 0)} MM/año)", VERDE))
    else:
        if caja:
            runway = caja / -fcf
            color = ROJO if runway < 1.5 else AMARILLO
            chips.append((f"Quema caja: le alcanza para {fmt_num(runway)} años", color))
        else:
            chips.append(("Quema caja", ROJO))
    return chips


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def con_reintentos(fn, intentos=3):
    """Reintenta ante cortes o limites de consultas de Yahoo."""
    ultimo = None
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:
            ultimo = e
            time.sleep(1.5 * (i + 1))
    raise ultimo


@st.cache_data(ttl=3600, show_spinner=False)
def traer_datos(ticker):
    """Lanza excepcion si no consigue ni el precio (asi los errores no quedan cacheados)."""
    tk = yf.Ticker(ticker)

    info, detalle = {}, ""
    try:
        info = dict(con_reintentos(lambda: tk.info) or {})
    except Exception as e:
        detalle = f"{type(e).__name__}: {e}"

    try:
        hist = con_reintentos(lambda: tk.history(period="1y"))["Close"]
        hist.index = hist.index.tz_localize(None)
    except Exception:
        hist = pd.Series(dtype=float)

    precio = num(info.get("currentPrice")) or num(info.get("regularMarketPrice"))
    if precio is None:
        try:
            precio = num(tk.fast_info["lastPrice"])
        except Exception:
            precio = None
    if precio is None and len(hist):
        precio = float(hist.iloc[-1])
    if precio is None:
        raise ValueError(
            "Yahoo no devolvió datos. Puede ser el ticker (usá el de EE.UU., no el .BA) "
            "o un límite de consultas de Yahoo: probá de nuevo en unos minutos."
            + (f" Detalle técnico: {detalle}" if detalle else "")
        )

    parcial = not any(info.get(k) is not None for k in
                      ("profitMargins", "revenueGrowth", "forwardPE", "trailingPE"))

    try:
        s = tk.splits
        if s is None or len(s) == 0:
            reverse = 0
        else:
            limite = pd.Timestamp.now(tz=s.index.tz) - pd.DateOffset(years=5)
            reverse = int((s[s.index >= limite] < 1).sum())
    except Exception:
        reverse = None

    try:
        inicio = (datetime.now() - timedelta(days=3 * 365)).strftime("%Y-%m-%d")
        sh = tk.get_shares_full(start=inicio)
        sh = sh[~sh.index.duplicated(keep="last")].sort_index()
        primero, ultimo = float(sh.iloc[0]), float(sh.iloc[-1])
        anios = (sh.index[-1] - sh.index[0]).days / 365.25
        dilucion = (ultimo / primero) ** (1 / anios) - 1 if primero > 0 and anios >= 0.5 else None
    except Exception:
        dilucion = None

    return info, precio, hist, reverse, dilucion, parcial


def analizar(ticker):
    try:
        info, precio, hist, reverse, dilucion, parcial = traer_datos(ticker)
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

    metricas = [m_margen(info), m_crecimiento(info), m_valuacion(info),
                m_deuda(info), m_roe(info), m_dividendo(info, precio)]
    validas = [m for m in metricas if m["puntos"] is not None]
    chips = chequeos(info, reverse, dilucion)

    # Penalizacion por riesgos: cada alerta roja resta 1,5 y cada amarilla 0,5
    penalizacion = sum(1.5 if c == ROJO else 0.5 if c == AMARILLO else 0 for _, c in chips)
    if validas:
        base = sum(m["puntos"] * m["peso"] for m in validas) / sum(m["peso"] for m in validas)
        nota = max(0.0, base - penalizacion)
    else:
        nota = None

    return {"ticker": ticker, "error": None, "info": info, "precio": precio, "hist": hist,
            "metricas": metricas, "nota": nota, "n_validas": len(validas),
            "penalizacion": penalizacion, "chips": chips, "parcial": parcial}


def calificacion_global(nota):
    if nota is None:
        return "Sin datos suficientes", GRIS
    etiqueta, _, color = escalon(nota, [(3.5, "Fundamentos muy débiles", 0, ROJO),
                                        (5, "Fundamentos débiles", 0, NARANJA),
                                        (6.5, "Fundamentos mixtos", 0, AMARILLO),
                                        (8, "Buenos fundamentos", 0, VERDE),
                                        (INF, "Fundamentos sólidos", 0, VERDE_OSC)])
    return etiqueta, color


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def e(x):
    return html.escape(str(x))


def html_tarjeta(m, rank):
    barra = ""
    if m["puntos"] is not None:
        barra = f'<div class="barra"><div style="width:{m["puntos"] * 10:.0f}%"></div></div>'
    return (
        f'<div class="tarjeta" style="--c:{m["color"]}">'
        f'<div class="top"><span class="rank">#{rank} en importancia</span>'
        f'<span class="badge">{e(m["etiqueta"])}</span></div>'
        f'<div class="nombre">{m["icono"]} {e(m["nombre"])}</div>'
        f'<div class="valor">{e(m["valor"])}</div>'
        f"{barra}"
        f'<div class="frase">{e(m["frase"])}</div>'
        f'<div class="escala">{e(m["escala"])}</div>'
        f"</div>"
    )


def html_nota(r):
    etiqueta, color = calificacion_global(r["nota"])
    if r["nota"] is None:
        n, p = "—", 0
    else:
        n, p = fmt_num(r["nota"]), r["nota"] * 10
    castigo = (f" Incluye {fmt_num(r['penalizacion'])} puntos menos por los chequeos de riesgo."
               if r["penalizacion"] else "")
    return (
        f'<div class="notabox" style="--c:{color};--p:{p:.0f}">'
        f'<div class="anillo"><div class="ring"></div><div class="n">{n}<small>de 10</small></div></div>'
        f'<div><div class="et">{e(etiqueta)}</div>'
        f'<div class="ex">Nota ponderada sobre {r["n_validas"]} de 6 indicadores.{castigo} '
        f"Resume los números: no dice si comprar.</div></div></div>"
    )


def html_empresa(r):
    info, hist = r["info"], r["hist"]
    nombre = info.get("shortName") or info.get("longName") or r["ticker"]
    sector = info.get("sector") or "Sector s/d"
    industria = info.get("industry")
    sub = sector + (f" · {industria}" if industria else "")

    mcap = num(info.get("marketCap"))
    mcap_txt = f"USD {fmt_num(mcap / 1e9, 1)} mil MM" if mcap else "s/d"
    if len(hist) > 1:
        var = hist.iloc[-1] / hist.iloc[0] - 1
        color_var = VERDE if var >= 0 else ROJO
        signo = "+" if var >= 0 else ""
        var_txt = f'<span style="color:{color_var}">{signo}{fmt_pct(var)}</span>'
    else:
        var_txt = "s/d"
    maximo = num(info.get("fiftyTwoWeekHigh"))
    desde_max = (f"{fmt_pct(r['precio'] / maximo - 1)}" if maximo else "s/d")

    stats = [("Precio", f"USD {fmt_num(r['precio'], 2)}"), ("Tamaño", mcap_txt),
             ("Último año", var_txt), ("Desde el máximo", desde_max)]
    grid = "".join(f'<div class="stat"><div class="l">{l}</div><div class="v">{v}</div></div>'
                   for l, v in stats)
    return (
        f'<div class="empresa"><div><div class="titulo">{e(nombre)}'
        f'<span class="tick">{e(r["ticker"])}</span></div>'
        f'<div class="sub">{e(sub)}</div></div></div>'
        f'<div class="stats">{grid}</div>'
    )


def html_comparativa(resultados):
    validos = [r for r in resultados if not r["error"]]
    if len(validos) < 2:
        return ""
    validos.sort(key=lambda r: -1 if r["nota"] is None else r["nota"], reverse=True)
    cortos = [m["corto"] for m in validos[0]["metricas"]]
    cab = "<tr><th>Ticker</th><th>Nota</th>" + "".join(f"<th>{c}</th>" for c in cortos) + "</tr>"
    filas = ""
    for r in validos:
        _, color = calificacion_global(r["nota"])
        n = fmt_num(r["nota"]) if r["nota"] is not None else "—"
        celdas = "".join(
            f'<td><span class="pill" style="--c:{m["color"]}">{e(m["etiqueta"])}</span></td>'
            for m in r["metricas"])
        filas += (f'<tr><td>{e(r["ticker"])}</td>'
                  f'<td><span class="pill" style="--c:{color}">{n}</span></td>{celdas}</tr>')
    return (f'<div class="seccion">Comparativa (ordenada por nota)</div>'
            f'<div class="tabla-wrap"><table class="tabla">{cab}{filas}</table></div>')


def mostrar(r):
    if r["error"]:
        st.error(f"**{r['ticker']}** — {r['error']}")
        return

    st.markdown(html_empresa(r), unsafe_allow_html=True)
    if r["parcial"]:
        st.warning("Yahoo devolvió el precio pero no los datos de balance (suele ser un límite "
                   "de consultas). Probá de nuevo en unos minutos.")
    st.markdown(html_nota(r), unsafe_allow_html=True)

    st.markdown('<div class="seccion">Indicadores, de más a menos importante</div>',
                unsafe_allow_html=True)
    for fila in range(2):
        cols = st.columns(3)
        for j in range(3):
            i = fila * 3 + j
            with cols[j]:
                st.markdown(html_tarjeta(r["metricas"][i], i + 1), unsafe_allow_html=True)

    st.markdown('<div class="seccion">Chequeos de riesgo</div>', unsafe_allow_html=True)
    st.markdown("".join(f'<span class="chip" style="--c:{c}">{e(t)}</span>'
                        for t, c in r["chips"]), unsafe_allow_html=True)

    if len(r["hist"]) > 1:
        st.markdown('<div class="seccion" style="margin-top:22px">Precio del último año (USD)</div>',
                    unsafe_allow_html=True)
        st.area_chart(r["hist"], height=240, color="#7c3aed")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="hero"><h1>📊 Analizador de acciones</h1>'
    "<p>Escribí uno o más tickers de EE.UU. separados por coma (MELI, no MELI.BA). "
    "Datos de Yahoo Finance: orientativos, verificá antes de decidir.</p></div>",
    unsafe_allow_html=True,
)

with st.form("buscar", border=False):
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    entrada = c1.text_input("Tickers", placeholder="Ej: MELI, NU, CLX",
                            label_visibility="collapsed")
    enviar = c2.form_submit_button("Analizar")

if enviar and entrada.strip():
    vistos, tickers = set(), []
    for t in entrada.replace(";", ",").replace(" ", ",").split(","):
        t = t.strip().upper().replace("$", "")
        if t and t not in vistos:
            vistos.add(t)
            tickers.append(t)
    st.session_state["tickers"] = tickers

tickers = st.session_state.get("tickers", [])

if tickers:
    resultados = []
    with st.spinner("Buscando datos en Yahoo Finance..."):
        for t in tickers:
            resultados.append(analizar(t))

    comparativa = html_comparativa(resultados)
    if comparativa:
        st.markdown(comparativa, unsafe_allow_html=True)

    if len(resultados) == 1:
        mostrar(resultados[0])
    else:
        for tab, r in zip(st.tabs([r["ticker"] for r in resultados]), resultados):
            with tab:
                mostrar(r)

with st.expander("¿Por qué este orden de importancia?"):
    st.markdown(
        "1. **Rentabilidad** — si no gana plata, todo lo demás es promesa.\n"
        "2. **Crecimiento** — una empresa rentable que no crece se estanca.\n"
        "3. **Valuación** — una gran empresa comprada carísima puede ser una mala inversión.\n"
        "4. **Deuda** — con tasas altas, estar muy endeudada pesa más.\n"
        "5. **ROE** — útil, pero se infla con recompras y deuda.\n"
        "6. **Dividendo** — solo importa si buscás renta; si no paga, no resta."
    )
