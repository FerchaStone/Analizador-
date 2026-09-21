"""
Analizador de acciones - dashboard (Streamlit)

Se escribe uno o mas tickers de EE.UU. y muestra, para cada uno:
- 6 indicadores ordenados por importancia, cada uno con valor, calificacion
  en palabras, una frase simple y la escala de referencia
- una nota ponderada de 0 a 10
- chequeos de riesgo (reverse splits, dilucion, caja)
- grafico de precio del ultimo anio
- boton para descargar todo en Excel

Datos: Yahoo Finance via yfinance. Son orientativos: verificar antes de decidir.
"""

import html
import io
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
.block-container {padding-top: 2rem; max-width: 1200px;}
.tarjeta {background: rgba(128,128,128,0.07); border-radius: 14px; padding: 16px 18px;
  border-left: 6px solid var(--c); margin-bottom: 14px; min-height: 230px;}
.tarjeta .top {display:flex; justify-content:space-between; align-items:center; gap:8px;}
.tarjeta .rank {font-size: 12px; opacity: .6; text-transform: uppercase; letter-spacing: .05em;}
.tarjeta .nombre {font-size: 16px; font-weight: 600; margin: 4px 0 6px;}
.tarjeta .valor {font-size: 30px; font-weight: 700; line-height: 1.1;}
.badge {background: var(--c); color: #fff; border-radius: 999px; padding: 3px 12px;
  font-size: 13px; font-weight: 600; white-space: nowrap;}
.frase {font-size: 14px; margin-top: 8px;}
.escala {font-size: 12px; opacity: .65; margin-top: 10px;}
.nota {border-radius: 16px; padding: 18px 22px; background: rgba(128,128,128,0.07);
  border: 2px solid var(--c); margin: 8px 0 18px;}
.nota .num {font-size: 46px; font-weight: 800; color: var(--c); line-height: 1;}
.chip {display:inline-block; border-radius: 999px; padding: 5px 13px; margin: 4px 6px 4px 0;
  font-size: 13px; font-weight: 500; background: var(--c); color: #fff;}
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
    base = {"nombre": "Rentabilidad (margen neto)", "peso": 20,
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
    base = {"nombre": "Crecimiento de ventas", "peso": 20,
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
    base = {"nombre": "Valuación (PER)", "peso": 20,
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
    base = {"nombre": "Deuda / Patrimonio", "peso": 15,
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
    base = {"nombre": "ROE (retorno sobre capital)", "peso": 15,
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
    base = {"nombre": "Dividendo", "peso": 10,
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
@st.cache_data(ttl=3600, show_spinner=False)
def traer_datos(ticker):
    """Lanza excepcion si falla (asi los errores no quedan cacheados)."""
    tk = yf.Ticker(ticker)
    info = dict(tk.info or {})
    precio = num(info.get("currentPrice")) or num(info.get("regularMarketPrice"))
    if precio is None:
        raise ValueError("Sin datos. Revisá el ticker (usá el de EE.UU., no el .BA).")

    try:
        hist = tk.history(period="1y")["Close"]
        hist.index = hist.index.tz_localize(None)
    except Exception:
        hist = pd.Series(dtype=float)

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

    return info, precio, hist, reverse, dilucion


def analizar(ticker):
    try:
        info, precio, hist, reverse, dilucion = traer_datos(ticker)
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
            "penalizacion": penalizacion, "chips": chips}


def calificacion_global(nota):
    if nota is None:
        return "Sin datos suficientes", GRIS
    return escalon(nota, [(3.5, "Fundamentos muy débiles", 0, ROJO),
                          (5, "Fundamentos débiles", 0, NARANJA),
                          (6.5, "Fundamentos mixtos", 0, AMARILLO),
                          (8, "Buenos fundamentos", 0, VERDE),
                          (INF, "Fundamentos sólidos", 0, VERDE_OSC)])[0::2]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def html_tarjeta(m, rank):
    return (
        f'<div class="tarjeta" style="--c:{m["color"]}">'
        f'<div class="top"><span class="rank">#{rank} de 6 en importancia</span>'
        f'<span class="badge">{html.escape(m["etiqueta"])}</span></div>'
        f'<div class="nombre">{html.escape(m["nombre"])}</div>'
        f'<div class="valor">{html.escape(m["valor"])}</div>'
        f'<div class="frase">{html.escape(m["frase"])}</div>'
        f'<div class="escala">Escala: {html.escape(m["escala"])}</div>'
        f"</div>"
    )


def mostrar(r):
    if r["error"]:
        st.error(f"{r['ticker']}: {r['error']}")
        return

    info, hist = r["info"], r["hist"]
    nombre = info.get("shortName") or r["ticker"]
    st.subheader(f"{nombre} ({r['ticker']})")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Precio", f"USD {fmt_num(r['precio'], 2)}")
    mcap = num(info.get("marketCap"))
    c2.metric("Tamaño (market cap)",
              f"USD {fmt_num(mcap / 1e9, 1)} mil MM" if mcap else "s/d")
    if len(hist) > 1:
        var = hist.iloc[-1] / hist.iloc[0] - 1
        c3.metric("Último año", fmt_pct(var))
    else:
        c3.metric("Último año", "s/d")
    c4.metric("Sector", info.get("sector") or "s/d")

    etiqueta, color = calificacion_global(r["nota"])
    nota_txt = fmt_num(r["nota"]) if r["nota"] is not None else "—"
    castigo = (f", con {fmt_num(r['penalizacion'])} puntos menos por los chequeos de riesgo"
               if r["penalizacion"] else "")
    st.markdown(
        f'<div class="nota" style="--c:{color}"><div style="display:flex;align-items:center;'
        f'gap:22px;flex-wrap:wrap"><div class="num">{nota_txt}</div><div>'
        f'<div style="font-size:20px;font-weight:700">{etiqueta}</div>'
        f'<div style="opacity:.7;font-size:14px">Nota ponderada de 0 a 10 sobre '
        f'{r["n_validas"]} de 6 indicadores{castigo}. Resume los números: no dice si comprar.</div>'
        f"</div></div></div>",
        unsafe_allow_html=True,
    )

    for fila in range(2):
        cols = st.columns(3)
        for j in range(3):
            i = fila * 3 + j
            with cols[j]:
                st.markdown(html_tarjeta(r["metricas"][i], i + 1), unsafe_allow_html=True)

    st.markdown("**Chequeos de riesgo**")
    st.markdown(
        "".join(f'<span class="chip" style="--c:{c}">{html.escape(t)}</span>'
                for t, c in r["chips"]),
        unsafe_allow_html=True,
    )

    if len(hist) > 1:
        st.markdown("**Precio del último año (USD)**")
        st.line_chart(hist, height=240)


def excel(resultados):
    filas = []
    for r in resultados:
        if r["error"]:
            filas.append({"Ticker": r["ticker"], "Error": r["error"]})
            continue
        etiqueta, _ = calificacion_global(r["nota"])
        fila = {"Ticker": r["ticker"], "Nombre": r["info"].get("shortName"),
                "Precio USD": r["precio"],
                "Nota (0-10)": round(r["nota"], 1) if r["nota"] is not None else None,
                "Calificación": etiqueta}
        for m in r["metricas"]:
            fila[m["nombre"]] = m["valor"]
            fila[m["nombre"] + " - evaluación"] = m["etiqueta"]
        fila["Chequeos de riesgo"] = " | ".join(t for t, _ in r["chips"])
        filas.append(fila)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as w:
        pd.DataFrame(filas).to_excel(w, index=False, sheet_name="Analisis")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
st.title("📊 Analizador de acciones")
st.caption("Escribí uno o más tickers de EE.UU. separados por coma (MELI, no MELI.BA). "
           "Datos de Yahoo Finance: orientativos, verificá antes de decidir.")

entrada = st.text_input("Tickers", placeholder="Ej: MELI, NU, CLX")
if st.button("Analizar", type="primary") and entrada.strip():
    vistos, tickers = set(), []
    for t in entrada.replace(";", ",").replace(" ", ",").split(","):
        t = t.strip().upper().replace("$", "")
        if t and t not in vistos:
            vistos.add(t)
            tickers.append(t)
    st.session_state["tickers"] = tickers

tickers = st.session_state.get("tickers", [])

with st.expander("¿Por qué este orden de importancia?"):
    st.markdown(
        "1. **Rentabilidad** — si no gana plata, todo lo demás es promesa.\n"
        "2. **Crecimiento** — una empresa rentable que no crece se estanca.\n"
        "3. **Valuación** — una gran empresa comprada carísima puede ser una mala inversión.\n"
        "4. **Deuda** — con tasas altas, estar muy endeudada pesa más.\n"
        "5. **ROE** — útil, pero se infla con recompras y deuda.\n"
        "6. **Dividendo** — solo importa si buscás renta; si no paga, no resta."
    )

if tickers:
    resultados = []
    with st.spinner("Buscando datos en Yahoo Finance..."):
        for t in tickers:
            resultados.append(analizar(t))

    if len(resultados) == 1:
        mostrar(resultados[0])
    else:
        for tab, r in zip(st.tabs([r["ticker"] for r in resultados]), resultados):
            with tab:
                mostrar(r)

    st.divider()
    st.download_button("⬇️ Descargar Excel", data=excel(resultados),
                       file_name=f"analisis_{datetime.now():%Y%m%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
