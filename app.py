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
import io
import json
import re
import time
import urllib.request
from datetime import datetime, time as dtime, timedelta, timezone

import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Analizador de acciones", page_icon="📊", layout="wide")

# Los ratios de CEDEAR se bajan solos del listado oficial de Comafi (una vez por dia).
# Solo hace falta cargar aca los que Comafi no publica (por ejemplo, CEDEARs emitidos
# por Caja de Valores) o si queres forzar uno. Formato: RATIOS = {"GLD": 50}
# (ese numero es solo un ejemplo de formato, no un dato real).
RATIOS = {}

COMAFI_PAGINA = "https://www.comafi.com.ar/custodiaglobal/programas.aspx"

# Supuestos del "crecimiento que descuenta el precio" (tarjeta de valuacion).
TASA_DESCUENTO = 0.10  # rendimiento anual pedido: Treasury ~5% + prima de riesgo ~5%
PER_SALIDA = 18        # PER al que se supone que cotiza dentro de 5 anios

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------
st.markdown(
    """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stTextInput, button {font-family: 'Inter', sans-serif !important;}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {visibility: hidden;}
.block-container {padding-top: 1.5rem; max-width: 1180px;}

.hero {background: linear-gradient(135deg, #1f2937 0%, #334155 100%);
  border-radius: 18px; padding: 26px 30px; color: #fff; margin-bottom: 18px;}
.hero h1 {font-size: 34px; font-weight: 800; margin: 0; color: #fff; padding: 0;}
.hero p {margin: 6px 0 0; opacity: .85; font-size: 15px;}

div[data-testid="stForm"] {border: none; padding: 0;}
.stTextInput input {border-radius: 12px !important; font-size: 16px !important; padding: 12px 14px !important;}
div[data-testid="stFormSubmitButton"] button {width: 100%; min-width: 110px; border-radius: 12px;
  border: none; background: #334155; color: #fff; font-weight: 600; padding: 11px 0;
  white-space: nowrap; transition: background .15s;}
div[data-testid="stFormSubmitButton"] button:hover {background: #1f2937; color: #fff;}
div[data-testid="stFormSubmitButton"] button p {white-space: nowrap;}

.empresa {display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;
  gap: 18px; margin: 10px 0 18px;}
.empresa .titulo {font-size: 28px; font-weight: 800; line-height: 1.15;}
.empresa .sub {opacity: .65; font-size: 14px; margin-top: 4px;}
.tick {display:inline-block; background: rgba(82,98,122,.12); color: #52627a; border-radius: 8px;
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
  border: 1px solid rgba(128,128,128,.14); border-top: 3px solid var(--c);
  margin-bottom: 16px; min-height: 300px; transition: transform .15s, box-shadow .15s;}
.tarjeta:hover {box-shadow: 0 6px 18px rgba(0,0,0,.06);}
.tarjeta .top {display:flex; justify-content:space-between; align-items:center; gap:8px;}
.tarjeta .rank {font-size: 11px; opacity: .55; text-transform: uppercase; letter-spacing: .06em; font-weight: 600;}
.tarjeta .nombre {font-size: 15px; font-weight: 600; margin: 8px 0 4px;}
.tarjeta .valor {font-size: 32px; font-weight: 800; line-height: 1.1;}
.badge {color: var(--c); background: color-mix(in srgb, var(--c) 13%, transparent);
  border: 1px solid color-mix(in srgb, var(--c) 30%, transparent); border-radius: 999px;
  padding: 3px 11px; font-size: 12px; font-weight: 600; white-space: nowrap;}
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
.pill {display:inline-block; border-radius: 999px; padding: 3px 10px; font-size: 12px; font-weight: 600;
  color: var(--c); background: color-mix(in srgb, var(--c) 13%, transparent);
  border: 1px solid color-mix(in srgb, var(--c) 30%, transparent); white-space: nowrap;}
.links {display:flex; gap: 8px; flex-wrap: wrap;}
.links a {text-decoration: none !important; font-size: 13px; font-weight: 600; color: #52627a !important;
  border: 1px solid rgba(82,98,122,.35); border-radius: 10px; padding: 6px 12px;}
.links a:hover {background: rgba(82,98,122,.08);}
.fechas {font-size: 12px; opacity: .6; margin-top: -4px;}
.tag {display:inline-block; font-size: 12px; font-weight: 600; opacity: .75; border-radius: 8px;
  padding: 2px 9px; margin-left: 6px; vertical-align: middle; border: 1px solid rgba(128,128,128,.35);}
.franja {display:grid; grid-template-columns: repeat(auto-fit, minmax(170px,1fr)); gap: 10px; margin-bottom: 18px;}
.franja .stat .v {font-size: 19px;}
.franja .stat .d {font-size: 12px; opacity: .6; margin-top: 2px;}
.ced {border-radius: 16px; padding: 16px 20px; background: rgba(128,128,128,.07);
  border: 1px solid rgba(128,128,128,.15); margin: 6px 0 14px;}
.ced .grande {font-size: 24px; font-weight: 800; color: var(--c);}
.ced .fila {display:flex; gap: 28px; flex-wrap: wrap; margin-top: 8px;}
.ced .fila div {font-size: 14px;}
.ced .fila b {display:block; font-size: 18px;}
.tabla-wrap {overflow-x: auto; margin-bottom: 18px;}
</style>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Colores y utilidades
# ---------------------------------------------------------------------------
VERDE_OSC = "#2e7d5b"
VERDE = "#4a9a72"
VERDE_CLARO = "#8aa05a"
AMARILLO = "#bf9a3e"
NARANJA = "#c47a4c"
ROJO = "#b5524e"
GRIS = "#8a8f98"
ACENTO = "#52627a"
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
    base = {"nombre": "Rentabilidad (margen neto)", "icono": "💰", "corto": "Rentabilidad", "peso": 25,
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
    base = {"nombre": "Crecimiento de ventas (último trimestre)", "icono": "📈", "corto": "Crecimiento", "peso": 15,
            "escala": "Negativo: malo · 0-5%: flojo · 5-10%: aceptable · 10-20%: bueno · "
                      "20-40%: muy bueno · +40%: excelente"}
    v = num(info.get("revenueGrowth"))
    if v is None:
        return sin_dato(base)
    et, p, c = escalon(v, [(0, "Malo", 0, ROJO), (0.05, "Flojo", 3, NARANJA),
                           (0.10, "Aceptable", 5, AMARILLO), (0.20, "Bueno", 7, VERDE_CLARO),
                           (0.40, "Muy bueno", 9, VERDE), (INF, "Excelente", 10, VERDE_OSC)])
    if v < 0:
        frase = (f"En el último trimestre vendió {fmt_pct(abs(v))} menos que en el mismo "
                 "trimestre del año anterior.")
    else:
        frase = (f"En el último trimestre vendió {fmt_pct(v)} más que en el mismo "
                 "trimestre del año anterior.")
    return resultado(base, fmt_pct(v), et, p, c, frase)


def m_valuacion(info):
    base = {"nombre": "Valuación (PER)", "icono": "🏷️", "corto": "Valuación", "peso": 20,
            "escala": "-10x: muy barato (ojo trampas) · 10-15x: barato · 15-22x: razonable · "
                      "22-30x: exigente · 30-45x: caro · +45x: muy caro. El crecimiento descontado supone "
                      "un 10% anual de rendimiento pedido y un PER de 18x dentro de 5 años."}
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

    # Crecimiento que descuenta el precio (DCF inverso simple, a 5 anios).
    # El dividendo cubre parte del rendimiento pedido, asi que se descuenta de la tasa.
    precio = num(info.get("currentPrice")) or num(info.get("regularMarketPrice"))
    div = num(info.get("dividendRate"))
    rinde = div / precio if (div and precio) else 0.0
    r = max(0.02, TASA_DESCUENTO - rinde)
    g = (pe * (1 + r) ** 5 / PER_SALIDA) ** (1 / 4) - 1
    frase += (f" El precio actual descuenta que sus ganancias crezcan ~{fmt_pct(g, 0)} "
              "por año durante 5 años.")
    crec = num(info.get("revenueGrowth"))
    if crec is not None:
        frase += f" Hoy sus ventas crecen {fmt_pct(crec, 0)}."
    return resultado(base, fmt_x(pe), et, p, c, frase)


def m_deuda(info):
    base = {"nombre": "Deuda / Patrimonio", "icono": "🏦", "corto": "Deuda", "peso": 10,
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
    base = {"nombre": "ROE (retorno sobre capital)", "icono": "⚙️", "corto": "ROE", "peso": 10,
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
    base = {"nombre": "Dividendo", "icono": "💵", "corto": "Dividendo", "peso": 5,
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
def m_fscore(fs, info):
    base = {"nombre": "Salud del balance (Piotroski F-Score)", "icono": "🩺", "corto": "Salud",
            "peso": 15,
            "escala": "0-3: débil · 4-5: regular · 6-7: sólida · 8-9: muy sólida. "
                      "Compara el último año contra el anterior."}
    if info.get("sector") in SECTORES_FINANCIEROS:
        return resultado(base, "—", "No aplica", None, GRIS,
                         "Está pensado para empresas industriales y comerciales, no para bancos.")
    if not fs or fs["total"] < 7:
        return sin_dato(base)
    ok, total = fs["ok"], fs["total"]
    score9 = ok / total * 9
    et, p, c = escalon(score9, [(4, "Débil", 2, ROJO), (6, "Regular", 5, AMARILLO),
                                (8, "Sólida", 8, VERDE), (INF, "Muy sólida", 10, VERDE_OSC)])
    frase = f"Pasa {ok} de {total} pruebas de salud: rentabilidad, deuda y eficiencia, año contra año."
    valor = f"{ok}/{total}"
    return {**resultado(base, valor, et, p, c, frase), "pruebas": fs["pruebas"]}


def chequeos(info, reverse_splits, dilucion, z=None):
    chips = []
    if z is not None and info.get("sector") not in SECTORES_FINANCIEROS:
        if z < 1.81:
            chips.append((f"Riesgo de quiebra alto (Altman Z {fmt_num(z, 2)})", ROJO))
        elif z < 2.99:
            chips.append((f"Zona gris de Altman (Z {fmt_num(z, 2)})", AMARILLO))
        else:
            chips.append((f"Bajo riesgo de quiebra (Altman Z {fmt_num(z, 2)})", VERDE))
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
        chips.append(("Genera caja", VERDE))
    else:
        if caja:
            runway = caja / -fcf
            color = ROJO if runway < 1.5 else AMARILLO
            chips.append((f"Quema caja: le alcanza para ~{fmt_num(runway)} años (aprox.)", color))
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

    try:
        fin, bal, caja = tk.financials, tk.balance_sheet, tk.cashflow
        fscore = calcular_fscore(fin, bal, caja)
        zscore = calcular_zscore(fin, bal, info)
    except Exception:
        fscore, zscore = None, None

    return info, precio, hist, reverse, dilucion, parcial, fscore, zscore


ARGENTINA = timezone(timedelta(hours=-3))


def hora_arg(texto):
    """Convierte la fecha ISO de DolarApi a hora argentina legible."""
    try:
        dt = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(ARGENTINA)
        hoy = datetime.now(ARGENTINA).date()
        if dt.date() == hoy:
            return f"hoy {dt:%H:%M}"
        return f"{dt:%d/%m %H:%M}"
    except Exception:
        return None


def fila(df, nombres, col):
    """Valor de la primera fila que exista, en la columna col (0 = ultimo anio)."""
    if df is None or getattr(df, "empty", True) or df.shape[1] <= col:
        return None
    for n in nombres:
        if n in df.index:
            return num(df.loc[n].iloc[col])
    return None


def calcular_fscore(fin, bal, caja):
    """Piotroski F-Score con los dos ultimos balances anuales. Omite las pruebas sin datos."""
    NI = ["Net Income", "Net Income Common Stockholders"]
    TA = ["Total Assets"]
    CFO = ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]
    LTD = ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]
    CA, CL = ["Current Assets"], ["Current Liabilities"]
    SH = ["Ordinary Shares Number", "Share Issued"]
    REV = ["Total Revenue", "Operating Revenue"]
    GP = ["Gross Profit"]

    def g(df, n, c):
        return fila(df, n, c)

    def div(a, b):
        return a / b if a is not None and b not in (None, 0) else None

    ni0, ni1 = g(fin, NI, 0), g(fin, NI, 1)
    ta0, ta1 = g(bal, TA, 0), g(bal, TA, 1)
    cfo0 = g(caja, CFO, 0)
    roa0, roa1 = div(ni0, ta0), div(ni1, ta1)
    lev0, lev1 = div(g(bal, LTD, 0), ta0), div(g(bal, LTD, 1), ta1)
    cr0, cr1 = div(g(bal, CA, 0), g(bal, CL, 0)), div(g(bal, CA, 1), g(bal, CL, 1))
    sh0, sh1 = g(bal, SH, 0), g(bal, SH, 1)
    rev0, rev1 = g(fin, REV, 0), g(fin, REV, 1)
    gm0, gm1 = div(g(fin, GP, 0), rev0), div(g(fin, GP, 1), rev1)
    at0, at1 = div(rev0, ta0), div(rev1, ta1)

    candidatas = [
        ("Gana plata (resultado positivo)", None if roa0 is None else roa0 > 0),
        ("Genera caja operativa", None if cfo0 is None else cfo0 > 0),
        ("Mejoró su rentabilidad sobre activos", None if None in (roa0, roa1) else roa0 > roa1),
        ("La caja que genera supera a la ganancia contable",
         None if None in (cfo0, ni0) else cfo0 > ni0),
        ("Bajó su deuda de largo plazo (sobre activos)",
         None if None in (lev0, lev1) else lev0 <= lev1),
        ("Mejoró su liquidez de corto plazo", None if None in (cr0, cr1) else cr0 > cr1),
        ("No emitió acciones nuevas", None if None in (sh0, sh1) else sh0 <= sh1 * 1.005),
        ("Mejoró su margen bruto", None if None in (gm0, gm1) else gm0 > gm1),
        ("Vende más por cada peso de activos", None if None in (at0, at1) else at0 > at1),
    ]
    pruebas = [(t, bool(r)) for t, r in candidatas if r is not None]
    if not pruebas:
        return None
    return {"ok": sum(1 for _, r in pruebas if r), "total": len(pruebas), "pruebas": pruebas}


def calcular_zscore(fin, bal, info):
    """Altman Z-Score original (1968), con el ultimo balance anual."""
    ta = fila(bal, ["Total Assets"], 0)
    ca, cl = fila(bal, ["Current Assets"], 0), fila(bal, ["Current Liabilities"], 0)
    wc = fila(bal, ["Working Capital"], 0)
    if wc is None and None not in (ca, cl):
        wc = ca - cl
    re_ = fila(bal, ["Retained Earnings"], 0)
    ebit = fila(fin, ["EBIT", "Operating Income"], 0)
    pasivo = fila(bal, ["Total Liabilities Net Minority Interest", "Total Liabilities"], 0)
    ventas = fila(fin, ["Total Revenue", "Operating Revenue"], 0)
    mcap = num(info.get("marketCap"))
    if None in (ta, wc, re_, ebit, pasivo, ventas, mcap) or ta == 0 or pasivo == 0:
        return None
    return (1.2 * wc / ta + 1.4 * re_ / ta + 3.3 * ebit / ta
            + 0.6 * mcap / pasivo + 1.0 * ventas / ta)


@st.cache_data(ttl=600, show_spinner=False)
def dolar(tipo):
    """(venta, hora de actualizacion) desde DolarApi. tipo: 'contadoconliqui' o 'bolsa' (MEP)."""
    for url in (f"https://dolarapi.com/v1/dolares/{tipo}",
                f"https://dolarapi.com/v1/ambito/dolares/{tipo}"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                d = json.loads(resp.read().decode())
            v = num(d.get("venta"))
            if v:
                return v, hora_arg(d.get("fechaActualizacion"))
        except Exception:
            continue
    return None, None


def bajar(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def leer_ratio(v):
    """Convierte '120:1', 120 o una celda que Excel tomo como hora (3:1 -> 03:01) en numero."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        v = v.time()
    if isinstance(v, dtime):
        return v.hour / v.minute if v.minute else None
    if isinstance(v, timedelta):
        horas, resto = divmod(int(v.total_seconds()), 3600)
        minutos = resto // 60
        return horas / minutos if minutos else None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    m = re.match(r"\s*([\d.,]+)\s*:\s*([\d.,]+)", str(v))
    if m:
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", "."))
        return a / b if b else None
    return None


def ratios_de_planilla(contenido):
    ratios = {}
    hojas = pd.read_excel(io.BytesIO(contenido), sheet_name=None, header=None)
    for df in hojas.values():
        fila_titulo, col_tick, col_ratio = None, None, None
        for i in range(min(len(df), 40)):
            celdas = [str(x) for x in df.iloc[i].tolist()]
            ct = next((j for j, c in enumerate(celdas) if "Identificaci" in c), None)
            cr = next((j for j, c in enumerate(celdas) if "Ratio" in c), None)
            if ct is not None and cr is not None:
                fila_titulo, col_tick, col_ratio = i, ct, cr
                break
        if fila_titulo is None:
            continue
        for i in range(fila_titulo + 1, len(df)):
            tick = df.iat[i, col_tick]
            ratio = leer_ratio(df.iat[i, col_ratio])
            if isinstance(tick, str) and tick.strip() and ratio:
                ratios[tick.strip().upper()] = ratio
    return ratios


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def ratios_comafi():
    """Ratios oficiales de Comafi. Lanza excepcion si falla (no queda cacheado)."""
    pagina = bajar(COMAFI_PAGINA).decode("utf-8", "ignore")
    links = re.findall(r'["\']([^"\']*Multimedios/otros/\d+\.xlsx[^"\']*)["\']', pagina)
    ratios = {}
    for link in dict.fromkeys(l.replace("&amp;", "&") for l in links):
        url = link if link.startswith("http") else "https://www.comafi.com.ar" + (
            link if link.startswith("/") else "/custodiaglobal/" + link)
        try:
            ratios.update(ratios_de_planilla(bajar(url)))
        except Exception:
            continue
    if not ratios:
        raise ValueError("No se pudieron leer los ratios de Comafi")
    return {"ratios": ratios, "fecha": datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m")}


def ratio_oficial(ticker):
    """(ratio, origen) buscando primero en RATIOS y despues en Comafi."""
    for t in (ticker, ticker.replace("-", ""), ticker.replace("-", ".")):
        if t in RATIOS:
            return float(RATIOS[t]), "cargado por vos en el código"
    try:
        datos = ratios_comafi()
    except Exception:
        return None, None
    for t in (ticker, ticker.replace("-", ""), ticker.replace("-", ".")):
        if t in datos["ratios"]:
            return datos["ratios"][t], f"el listado oficial de Comafi, bajado el {datos['fecha']}"
    return None, None


@st.cache_data(ttl=600, show_spinner=False)
def serie(simbolo, periodo="1y"):
    """Serie de cierres. Lanza excepcion si falla (no queda cacheada)."""
    h = con_reintentos(lambda: yf.Ticker(simbolo).history(period=periodo))["Close"].dropna()
    if len(h) == 0:
        raise ValueError(f"Sin datos para {simbolo}")
    h.index = h.index.tz_localize(None)
    return h


@st.cache_data(ttl=900, show_spinner=False)
def precio_cedear(ticker):
    """Ultimo cierre del CEDEAR en Buenos Aires (Yahoo, simbolo .BA). None si no lo encuentra."""
    for simbolo in dict.fromkeys([f"{ticker}.BA", f"{ticker.replace('-', '')}.BA"]):
        try:
            h = yf.Ticker(simbolo).history(period="5d")["Close"].dropna()
            if len(h):
                return {"simbolo": simbolo, "precio": float(h.iloc[-1]),
                        "fecha": h.index[-1].strftime("%d/%m/%Y")}
        except Exception:
            continue
    return None


def contexto_mercado():
    ccl, ccl_hora = dolar("contadoconliqui")
    mep, mep_hora = dolar("bolsa")
    try:
        tnx = serie("^TNX", "5d")
        tasa = float(tnx.iloc[-1])
        cambio = float(tnx.iloc[-1] - tnx.iloc[-2]) if len(tnx) > 1 else None
        tasa_fecha = tnx.index[-1].strftime("%d/%m")
    except Exception:
        tasa, cambio, tasa_fecha = None, None, None
    return {"ccl": ccl, "ccl_hora": ccl_hora, "mep": mep, "mep_hora": mep_hora,
            "tasa": tasa, "cambio": cambio, "tasa_fecha": tasa_fecha}


def analizar(ticker):
    try:
        info, precio, hist, reverse, dilucion, parcial, fscore, zscore = traer_datos(ticker)
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

    # Orden = peso en la nota (de mayor a menor)
    metricas = [m_margen(info), m_valuacion(info), m_crecimiento(info), m_fscore(fscore, info),
                m_deuda(info), m_roe(info), m_dividendo(info, precio)]
    validas = [m for m in metricas if m["puntos"] is not None]
    chips = chequeos(info, reverse, dilucion, zscore)

    # Penalizacion por riesgos: cada alerta roja resta 1,5 y cada amarilla 0,5
    penalizacion = sum(1.5 if c == ROJO else 0.5 if c == AMARILLO else 0 for _, c in chips)
    if validas:
        base = sum(m["puntos"] * m["peso"] for m in validas) / sum(m["peso"] for m in validas)
        nota = max(0.0, base - penalizacion)
    else:
        nota = None

    tipo = {"ETF": "ETF", "EQUITY": "Acción"}.get(info.get("quoteType"), None)
    try:
        spx = serie("^GSPC")
    except Exception:
        spx = pd.Series(dtype=float)

    return {"ticker": ticker, "error": None, "info": info, "precio": precio, "hist": hist,
            "tipo": tipo, "cedear": precio_cedear(ticker), "spx": spx,
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
        f'<div class="top"><span class="rank">#{rank} · peso {m["peso"]}%</span>'
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
    t = r["ticker"]
    etiquetas = ""
    if r["tipo"]:
        etiquetas += f'<span class="tag">{r["tipo"]}</span>'
    if r["cedear"]:
        etiquetas += '<span class="tag">Tiene CEDEAR</span>'
    links = (
        f'<div class="links">'
        f'<a href="https://finance.yahoo.com/quote/{e(t)}/key-statistics" target="_blank">'
        f"Verificar en Yahoo ↗</a>"
        f'<a href="https://stockanalysis.com/stocks/{e(t.lower())}/statistics/" target="_blank">'
        f"Verificar en StockAnalysis ↗</a></div>"
    )
    return (
        f'<div class="empresa"><div><div class="titulo">{e(nombre)}'
        f'<span class="tick">{e(t)}</span>{etiquetas}</div>'
        f'<div class="sub">{e(sub)}</div></div>{links}</div>'
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
    n = len(r["metricas"])
    for inicio in range(0, n, 4):
        cols = st.columns(4)
        for j in range(4):
            i = inicio + j
            if i < n:
                with cols[j]:
                    st.markdown(html_tarjeta(r["metricas"][i], i + 1), unsafe_allow_html=True)

    fs = next((m for m in r["metricas"] if m.get("pruebas")), None)
    if fs:
        with st.expander(f"Ver las pruebas del F-Score ({fs['valor']})"):
            st.markdown("\n".join(f"- {'✅' if ok else '❌'} {t}" for t, ok in fs["pruebas"]))

    st.markdown('<div class="seccion">Chequeos de riesgo</div>', unsafe_allow_html=True)
    st.markdown("".join(f'<span class="chip" style="--c:{c}">{e(t)}</span>'
                        for t, c in r["chips"]), unsafe_allow_html=True)

    bloque_cedear(r)
    grafico(r)


def bloque_cedear(r):
    c = r["cedear"]
    t = r["ticker"]
    st.markdown('<div class="seccion" style="margin-top:22px">Si lo comprás como CEDEAR</div>',
                unsafe_allow_html=True)
    if not c:
        st.caption("No encontré cotización de este CEDEAR en Yahoo. Puede que no exista, que "
                   "tenga otro ticker en BYMA o que Yahoo no lo cubra.")
        return

    h = r["hist"]
    precio_usa = float(h.iloc[-1]) if len(h) else r["precio"]
    fecha_usa = h.index[-1].strftime("%d/%m/%Y") if len(h) else "hoy"
    ccl, ccl_hora = dolar("contadoconliqui")

    oficial, origen = ratio_oficial(t)
    ratio = st.number_input(
        f"Ratio del CEDEAR de {t} (cuántos CEDEARs = 1 acción)",
        min_value=0.0, value=float(oficial or 0), step=1.0, key=f"ratio_{t}",
        help="Se completa solo con el listado oficial de Comafi. Si lo cambiás a mano, "
             "se usa el tuyo. Si figura 20:1, es 20.")
    if oficial and ratio == oficial:
        st.caption(f"Ratio {fmt_num(oficial, 0 if oficial == int(oficial) else 2)}:1 según {origen}.")
    elif oficial:
        st.caption(f"Estás usando un ratio cargado a mano. El oficial es "
                   f"{fmt_num(oficial, 0 if oficial == int(oficial) else 2)}:1 ({origen}).")
    elif ccl:
        pista = round(precio_usa * ccl / c["precio"])
        st.caption(f"No encontré el ratio oficial. Por los precios, parece ser {pista}:1 "
                   "(deducido, no oficial): confirmalo en tu broker antes de cargarlo.")

    base = (f'<div class="fila"><div>CEDEAR en BYMA<b>$ {fmt_num(c["precio"], 2)}</b>'
            f'cierre {c["fecha"]}</div><div>Acción en EE.UU.<b>USD {fmt_num(precio_usa, 2)}</b>'
            f'cierre {fecha_usa}</div>')

    if not ratio:
        st.markdown(f'<div class="ced" style="--c:{GRIS}">{base}</div>'
                    f'<div style="font-size:14px;opacity:.75">Cargá el ratio para ver a qué '
                    f"dólar estás comprando.</div></div>", unsafe_allow_html=True)
        return

    implicito = c["precio"] * ratio / precio_usa
    fila_ccl = (f'<div>CCL del mercado<b>$ {fmt_num(ccl, 2)}</b>'
                f'DolarApi{" · " + ccl_hora if ccl_hora else ""}</div>' if ccl else "")
    fila_imp = f'<div>Dólar implícito<b>$ {fmt_num(implicito, 2)}</b>precio × ratio / precio EE.UU.</div>'

    if not ccl:
        titulo, color = "No pude traer el CCL para comparar", GRIS
    else:
        prima = implicito / ccl - 1
        if abs(prima) > 0.25:
            titulo, color = ("El ratio parece incorrecto (¿cambió por un split?). "
                             "Revisalo en tu broker."), ROJO
        elif prima > 0.03:
            titulo, color = f"Sobreprecio alto: pagás {fmt_pct(prima)} más que el CCL", ROJO
        elif prima > 0.01:
            titulo, color = f"Sobreprecio leve: pagás {fmt_pct(prima)} más que el CCL", AMARILLO
        elif prima < -0.01:
            titulo, color = (f"Descuento: pagás {fmt_pct(abs(prima))} menos que el CCL "
                             "(chequeá que el precio no sea viejo)"), VERDE
        else:
            titulo, color = f"Precio en línea con el CCL ({fmt_pct(prima)})", VERDE

    aviso = ""
    if c["fecha"] != fecha_usa:
        aviso = ('<div style="font-size:12px;opacity:.65;margin-top:8px">Los cierres son de '
                 "días distintos: la comparación puede estar desfasada.</div>")
    st.markdown(
        f'<div class="ced" style="--c:{color}"><div class="grande">{e(titulo)}</div>'
        f'{base}{fila_imp}{fila_ccl}</div>{aviso}'
        f'<div style="font-size:12px;opacity:.65;margin-top:8px">Usa el último precio operado. '
        f"Si el CEDEAR tiene poco volumen, mirá las puntas en tu broker antes de comprar.</div></div>",
        unsafe_allow_html=True)


def grafico(r):
    h = r["hist"]
    if len(h) < 2:
        return
    st.markdown('<div class="seccion" style="margin-top:22px">Último año contra el S&amp;P 500 '
                "(base 100)</div>", unsafe_allow_html=True)
    spx = r["spx"]
    if len(spx) > 1:
        df = pd.concat([h.rename(r["ticker"]), spx.rename("S&P 500")], axis=1).dropna()
    else:
        df = h.rename(r["ticker"]).to_frame()
    df = df / df.iloc[0] * 100

    var_t = df.iloc[-1, 0] / 100 - 1
    texto = f"Del {df.index[0]:%d/%m/%Y} al {df.index[-1]:%d/%m/%Y} · {r['ticker']} {fmt_pct(var_t)}"
    if df.shape[1] > 1:
        var_s = df.iloc[-1, 1] / 100 - 1
        dif = (var_t - var_s) * 100
        lado = "arriba" if dif >= 0 else "abajo"
        texto += (f" vs S&amp;P {fmt_pct(var_s)} → quedó {fmt_num(abs(dif))} puntos {lado} "
                  "del índice")
    st.markdown(f'<div class="fechas">{texto}</div>', unsafe_allow_html=True)
    colores = ["#52627a", "#bf9a3e"][: df.shape[1]]
    st.line_chart(df, height=260, color=colores)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="hero"><h1>📊 Analizador de acciones</h1>'
    "<p>Escribí uno o más tickers de EE.UU. separados por coma (MELI, no MELI.BA). "
    "Datos de Yahoo Finance: orientativos, verificá antes de decidir.</p></div>",
    unsafe_allow_html=True,
)

col_franja, col_boton = st.columns([6, 1], vertical_alignment="center")
with col_boton:
    if st.button("🔄 Actualizar", use_container_width=True,
                 help="Vuelve a pedir todos los datos: dólar, tasa y acciones."):
        st.cache_data.clear()

ctx = contexto_mercado()


def detalle(uso, hora):
    return f"{uso} · {hora}" if hora else f"{uso} · hora s/d"


tasa_det = ""
if ctx["cambio"] is not None:
    signo = "+" if ctx["cambio"] >= 0 else ""
    tasa_det = f"{signo}{fmt_num(ctx['cambio'], 2)} pp · cierre {ctx['tasa_fecha']}"
franja = [
    ("Dólar CCL", f"$ {fmt_num(ctx['ccl'], 2)}" if ctx["ccl"] else "s/d",
     detalle("Para CEDEARs", ctx["ccl_hora"])),
    ("Dólar MEP", f"$ {fmt_num(ctx['mep'], 2)}" if ctx["mep"] else "s/d",
     detalle("Para dolarizar", ctx["mep_hora"])),
    ("Treasury 10 años", f"{fmt_num(ctx['tasa'], 2)}%" if ctx["tasa"] is not None else "s/d",
     tasa_det),
]
with col_franja:
    st.markdown(
        '<div class="franja">' + "".join(
            f'<div class="stat"><div class="l">{l}</div><div class="v">{v}</div>'
            f'<div class="d">{d}</div></div>' for l, v, d in franja) + "</div>",
        unsafe_allow_html=True,
    )

with st.form("buscar", border=False):
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
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

with st.expander("¿Cómo se calcula la nota?"):
    st.markdown(
        "Cada indicador se pasa a un puntaje de 0 a 10 según su escala, y se promedian con "
        "estos pesos:\n\n"
        "1. **Rentabilidad — 25%.** Es lo que más respaldo tiene en la investigación: las "
        "empresas más rentables rindieron más históricamente.\n"
        "2. **Valuación — 20%.** Comprar barato funcionó a largo plazo, aunque anduvo flojo en "
        "los últimos años. La tarjeta también muestra cuánto crecimiento de ganancias ya está "
        "incluido en el precio: si es mucho más que lo que crece hoy, el precio es exigente. "
        "Ese dato es informativo y no suma ni resta a la nota.\n"
        "3. **Crecimiento — 15%.** Importa para tu objetivo, pero por sí solo no predice "
        "retornos.\n"
        "4. **Salud del balance (F-Score) — 15%.** Nueve pruebas que miran si la empresa mejora "
        "o empeora año contra año.\n"
        "5. **Deuda — 10%.** El riesgo de quiebra lo cubre además el Altman Z en los chequeos.\n"
        "6. **ROE — 10%.** Se superpone con rentabilidad y se infla con recompras.\n"
        "7. **Dividendo — 5%.** No predice retornos; si no paga, no resta.\n\n"
        "Lo que no aplica (deuda y F-Score en bancos, dividendo si no paga) se saca y el resto "
        "se re-reparte. Después se restan 1,5 puntos por cada alerta roja y 0,5 por cada "
        "amarilla de los chequeos de riesgo.\n\n"
        "**Importante:** los pesos y las escalas son criterio propio basado en la evidencia "
        "general, no están probados con datos históricos. La nota resume la salud financiera; "
        "no predice si la acción va a subir."
    )
