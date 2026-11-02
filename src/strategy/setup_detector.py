"""
setup_detector.py — Detector de setups Sistema A (V1)

Un setup es válido cuando confluyen simultáneamente:
  1. La barra M15 está dentro de una ventana operativa (London KZ o NY AM)
  2. H1 structure_bias = "bullish" (BUY) o "bearish" (SELL)
  3. Hay un POI activo (FRESH o TOUCHED) en la dirección del sesgo H1
  4. La barra de confirmación toca o entra en el POI
  5. La barra de confirmación cierra en la dirección de la operación
     (close > open para BUY; close < open para SELL)
  6. El cuerpo de la barra de confirmación tiene body_ratio >= CONF_MIN_BODY_RATIO
     (provisional V1: 0.20; ver comentario al final del archivo)
  7. El retroceso de Fibonacci en la barra de confirmación >= 50% (PD-014)

Entrada: apertura de la barra siguiente (modo conservador, PD-015)
SL: distal del POI ± SL_BUFFER_PIPS (provisional V1: 0.5 pips; ver abajo)
TP: entry ± 2R (R = distancia entry→SL)
Time exit: 6 barras M15 desde la barra de entrada (= 90 min, PD-019)

Decisiones provisionales V1 (consultar al trader para V2):
  CONF_MIN_BODY_RATIO  = 0.20  — cuerpo mínimo de la vela de confirmación
  SL_BUFFER_PIPS       = 0.5   — buffer más allá del distal del POI
  HTF_FILTER           = True  — se requiere alineación H1 (skip "ranging" y contrario)
  POI_MAX_STATE        = TOUCHED — solo FRESH y TOUCHED para entrada; PARTIALLY_MITIGATED excluido

Parámetros PENDING de V2 no implementados aquí:
  DISPLACEMENT_THRESHOLD (PD-005b) — el score se registra pero no filtra
  OB_GROUP_MAX_CANDLES (PD-005c)   — solo última vela OB
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from src.features.auxiliary import atr as compute_atr, rolling_volatility
from src.features.fibonacci import fib_levels_from_swing
from src.features.momentum import displacement_score as compute_displacement, body_to_range_ratio
from src.features.poi import (
    POI, POIDirection, POIState, POIType,
    detect_fvg, detect_order_blocks,
)
from src.features.sessions import london_killzone, newyork_am_open
from src.features.structure import add_market_structure, last_swing_highs, last_swing_lows
from src.strategy.context import build_h1_context

# ── Parámetros V1 (provisionales, pendiente confirmación del trader) ──────────
CONF_MIN_BODY_RATIO = 0.20   # cuerpo mínimo de la vela de confirmación
SL_BUFFER_PIPS      = 0.5    # pips de buffer más allá del distal del POI
HTF_FILTER          = True   # requiere alineación H1
MIN_RISK_PIPS       = 5.0    # riesgo mínimo aceptable (evitar SL absurdamente ajustados)
PIP                 = 0.0001


# ── Tipos de salida ────────────────────────────────────────────────────────────

@dataclass
class SetupRecord:
    """Una fila del dataset de setups antes de la simulación de trades."""

    # ── Metadatos de identificación
    fecha:               pd.Timestamp
    bar_index:           int            # índice de la barra de confirmación en M15
    entry_bar_index:     int            # índice de la barra de entrada (i+1)

    # ── Variables del dataset (columnas del CSV)
    direccion:           str            # "compra" | "venta"
    sesion:              str            # "london_killzone" | "newyork_am_open"
    cambio_estructura:   str            # "bos_bull" | "bos_bear" | "choch_bull" | "choch_bear"
    atr:                 float
    volatilidad:         float
    volumen_rel:         float
    distancia_estructura: float         # pips desde el close al nivel de BOS/CHOCH

    # ── Precios operativos (no van al CSV; solo para el simulador)
    entry_bid:           float          # open del bar i+1 (precio BID)
    sl_price:            float          # precio de SL (en términos de BID)
    tp_price:            float          # precio de TP (en términos de BID)
    risk_pips:           float          # tamaño del riesgo en pips

    # ── Features adicionales (se incluyen en el CSV como predictores)
    fib_retracement:     float
    fib_in_entry_zone:   int            # 0/1
    fib_in_pref_zone:    int            # 0/1
    poi_type:            int            # 0=fvg, 1=order_block
    poi_state_at_entry:  int            # 0=fresh, 1=touched
    poi_size_pips:       float
    body_range_ratio:    float
    displacement_score:  float
    h1_bias:             str            # "bullish" | "bearish"

    # ── Resultado (asignado después por el simulador)
    resultado:           str | None = None
    exit_reason:         str | None = None  # TP | SL | TIME_EXIT | BE | AMBIGUOUS


def _pois_from_features(df: pd.DataFrame) -> list[POI]:
    """Extrae todos los POIs detectados en el DataFrame M15."""
    pois: list[POI] = []
    datetime_col = df["datetime"].values if "datetime" in df.columns else None

    n = len(df)
    for i in range(n):
        ts = pd.Timestamp(datetime_col[i]) if datetime_col is not None else pd.Timestamp(df.index[i])

        # FVG alcista
        if df["fvg_bull"].iat[i]:
            pois.append(POI(
                poi_type=POIType.FVG,
                direction=POIDirection.BULLISH,
                proximal=df["fvg_high"].iat[i],  # techo de la zona
                distal=df["fvg_low"].iat[i],      # suelo de la zona
                created_at=ts,
            ))

        # FVG bajista
        if df["fvg_bear"].iat[i]:
            pois.append(POI(
                poi_type=POIType.FVG,
                direction=POIDirection.BEARISH,
                proximal=df["fvg_low"].iat[i],    # suelo = proximal para bearish
                distal=df["fvg_high"].iat[i],     # techo = distal para bearish
                created_at=ts,
            ))

        # OB alcista
        if df["ob_bull"].iat[i]:
            pois.append(POI(
                poi_type=POIType.ORDER_BLOCK,
                direction=POIDirection.BULLISH,
                proximal=df["ob_high"].iat[i],
                distal=df["ob_low"].iat[i],
                created_at=ts,
            ))

        # OB bajista
        if df["ob_bear"].iat[i]:
            pois.append(POI(
                poi_type=POIType.ORDER_BLOCK,
                direction=POIDirection.BEARISH,
                proximal=df["ob_low"].iat[i],
                distal=df["ob_high"].iat[i],
                created_at=ts,
            ))

    return pois


def _last_structure_event(df: pd.DataFrame, at_index: int) -> str:
    """Devuelve el tipo de evento estructural M15 más reciente antes de `at_index`."""
    for j in range(at_index - 1, -1, -1):
        if df["bos_bull"].iat[j]:
            return "bos_bull"
        if df["bos_bear"].iat[j]:
            return "bos_bear"
        if df["choch_bull"].iat[j]:
            return "choch_bull"
        if df["choch_bear"].iat[j]:
            return "choch_bear"
    return "bos_bull"  # fallback si no hay evento previo (inicio de dataset)


def _session_label(df_idx: pd.DataFrame, bar_index: int) -> str:
    """Devuelve 'london_killzone' o 'newyork_am_open' para la barra dada."""
    if df_idx["london_killzone"].iat[bar_index]:
        return "london_killzone"
    return "newyork_am_open"


def _fib_retracement(price: float, last_high: float, last_low: float, direction: str) -> float:
    """Calcula el retroceso Fibonacci del precio en la vela de confirmación."""
    rng = last_high - last_low
    if rng <= 0:
        return 0.0
    if direction == "buy":
        # Impulso alcista: 0%=máximo, 100%=mínimo; retroceso = (high - price) / rng
        return (last_high - price) / rng
    else:
        # Impulso bajista: 0%=mínimo, 100%=máximo; retroceso = (price - low) / rng
        return (price - last_low) / rng


def build_m15_features(m15: pd.DataFrame) -> pd.DataFrame:
    """
    Construye el DataFrame M15 completo con todas las features necesarias
    para la detección de setups.

    Espera m15 con columna 'datetime' (no como índice) y OHLC.
    Devuelve copia con el índice fijado como DatetimeIndex para funciones de sesión.
    """
    # Necesitamos DatetimeIndex para las funciones de sesión y estructura
    df = m15.copy()
    if "datetime" not in df.columns:
        raise ValueError("m15 debe tener columna 'datetime'")

    # Backup del datetime column para restaurarlo después
    dt_col = df["datetime"].copy()

    # Poner datetime como índice (UTC, tz-naive)
    df = df.set_index("datetime")
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)

    # ── Sesiones
    df["london_killzone"] = london_killzone(df)
    df["newyork_am_open"] = newyork_am_open(df)
    df["any_session"]     = df["london_killzone"] | df["newyork_am_open"]

    # ── Estructura (BOS, CHOCH, swings)
    df = add_market_structure(df, n=1, level="short_term")

    # ── ATR
    df["atr14"] = compute_atr(df, period=14)

    # ── Volatilidad rolling (rolling std de log returns, 20 barras)
    df["volatility20"] = rolling_volatility(df, period=20)

    # ── Volumen relativo (tick count / mean de últimas 20 barras)
    if "volume" in df.columns:
        df["volume_mean20"] = df["volume"].rolling(20, min_periods=1).mean()
        df["volumen_rel"]   = df["volume"] / df["volume_mean20"].replace(0, np.nan)
    else:
        df["volumen_rel"] = np.nan

    # ── Body ratio de cada vela
    df["body_range_ratio_col"] = body_to_range_ratio(df)

    # ── Displacement score
    df["displacement_score"] = compute_displacement(df)

    # ── POI features (FVG + OB)
    df = detect_fvg(df)
    df = detect_order_blocks(df)

    # Restaurar datetime como columna
    df = df.reset_index().rename(columns={"index": "datetime"}) if "datetime" not in df.columns else df.reset_index()

    return df


def detect_setups(
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    *,
    start_date: str | None = "2020-01-01",
    end_date: str | None = "2026-10-16",
    htf_filter: bool = HTF_FILTER,
    conf_min_body: float = CONF_MIN_BODY_RATIO,
    sl_buffer_pips: float = SL_BUFFER_PIPS,
    fib_min_retracement: float = 0.50,
) -> pd.DataFrame:
    """
    Escanea el DataFrame M15 y devuelve todos los setups detectados.

    Parámetros
    ----------
    m15 : DataFrame M15 con columna 'datetime' (UTC, no índice) y OHLC.
    h1  : DataFrame H1 con columna 'datetime' (UTC, no índice) y OHLC.
    start_date / end_date : filtro de período (inclusive).
    htf_filter : si True, requiere alineación H1.
    conf_min_body : body_range_ratio mínimo de la vela de confirmación (provisional).
    sl_buffer_pips : pips de buffer más allá del distal del POI (provisional).
    fib_min_retracement : retroceso mínimo de Fibonacci para la entrada (PD-014).

    Devuelve
    --------
    DataFrame con una fila por setup detectado (sin columna 'resultado' aún).
    """
    # ── 1. Preparar features M15
    m15_feat = build_m15_features(m15)

    # Filtro de fechas
    if start_date:
        m15_feat = m15_feat[m15_feat["datetime"] >= pd.Timestamp(start_date)]
    if end_date:
        m15_feat = m15_feat[m15_feat["datetime"] <= pd.Timestamp(end_date)]
    m15_feat = m15_feat.reset_index(drop=True)

    # ── 2. Contexto H1 (mergeado en el M15)
    h1_ctx = build_h1_context(m15_feat, h1, n=1, level="short_term")
    # build_h1_context devuelve M15 con columnas h1_structure_bias, h1_bos_bull, h1_bos_bear
    m15_feat = h1_ctx

    # ── 3. Construir lista de POIs desde features M15
    all_pois = _pois_from_features(m15_feat)

    # ── 4. Valores de arrays para acceso rápido
    n = len(m15_feat)
    datetimes      = m15_feat["datetime"].values
    opens          = m15_feat["open"].values
    closes         = m15_feat["close"].values
    lows           = m15_feat["low"].values
    highs          = m15_feat["high"].values

    # Columnas de sesión
    in_london = m15_feat["london_killzone"].values
    in_ny     = m15_feat["newyork_am_open"].values
    in_session_arr = (in_london | in_ny)

    # Columnas de estructura (swing pivots ffilled)
    last_highs = m15_feat["pivot_high_st"].ffill().values
    last_lows  = m15_feat["pivot_low_st"].ffill().values

    # Columnas de estructura (eventos)
    bos_bull   = m15_feat["bos_bull"].values
    bos_bear   = m15_feat["bos_bear"].values
    choch_bull = m15_feat["choch_bull"].values if "choch_bull" in m15_feat.columns else np.zeros(n, bool)
    choch_bear = m15_feat["choch_bear"].values if "choch_bear" in m15_feat.columns else np.zeros(n, bool)

    # Contexto H1
    h1_bias    = m15_feat["h1_structure_bias"].values

    # ATR y volatilidad
    atr_vals   = m15_feat["atr14"].values
    vol_vals   = m15_feat["volatility20"].values
    volrel     = m15_feat["volumen_rel"].values
    body_ratio = m15_feat["body_range_ratio_col"].values
    disp_score = m15_feat["displacement_score"].values

    # ── 5. Escaneo cronológico
    setups: list[SetupRecord] = []

    for i in range(1, n - 1):  # necesitamos i+1 para la entrada
        # Filtro de sesión
        if not in_session_arr[i]:
            continue

        # Filtro de fecha límite para entrada
        if i + 1 >= n:
            break

        # H1 bias
        bias = h1_bias[i]
        if htf_filter:
            if bias not in ("bullish", "bearish"):
                continue
        direction = "buy" if bias == "bullish" else "sell"

        # Actualizar estados de todos los POIs creados ANTES de esta barra
        # Solo actualizamos los que aún no están invalidados/fully_mitigated
        bar_ts   = pd.Timestamp(datetimes[i])
        bar_low  = lows[i]
        bar_high = highs[i]
        bar_close = closes[i]

        active_pois = []
        for poi in all_pois:
            # No usar POIs creados en esta misma barra o posteriores (no-lookahead)
            if poi.created_at >= bar_ts:
                continue
            if poi.state in (POIState.FULLY_MITIGATED, POIState.INVALIDATED):
                continue
            if poi.direction == POIDirection.BULLISH and direction != "buy":
                continue
            if poi.direction == POIDirection.BEARISH and direction != "sell":
                continue
            # Solo FRESH y TOUCHED (no PARTIALLY_MITIGATED para V1)
            if poi.state == POIState.PARTIALLY_MITIGATED:
                continue
            active_pois.append(poi)

        if not active_pois:
            # Aún actualizamos estados de todos los POIs activos globales
            for poi in all_pois:
                if poi.created_at < bar_ts and poi.state not in (
                    POIState.FULLY_MITIGATED, POIState.INVALIDATED
                ):
                    poi.update_state(bar_low, bar_high, bar_close)
            continue

        # ── Check de confirmación sobre los POIs activos
        setup_found = False
        for poi in active_pois:
            # Verificar contacto con el POI en esta barra
            poi_lo = min(poi.proximal, poi.distal)
            poi_hi = max(poi.proximal, poi.distal)

            if direction == "buy":
                # Vela toca zona alcista desde arriba
                touches_zone = bar_low <= poi_hi
            else:
                # Vela toca zona bajista desde abajo
                touches_zone = bar_high >= poi_lo

            if not touches_zone:
                continue

            # Confirmación: vela cierra en dirección correcta
            if direction == "buy" and not (bar_close > opens[i]):
                continue
            if direction == "sell" and not (bar_close < opens[i]):
                continue

            # Cuerpo mínimo
            if body_ratio[i] < conf_min_body:
                continue

            # Fibonacci: retracement en zona de descuento [fib_min, 1.0]
            lh = last_highs[i]
            ll = last_lows[i]
            fib_ret = _fib_retracement(bar_close, lh, ll, direction)
            if np.isnan(fib_ret) or fib_ret < fib_min_retracement or fib_ret > 1.0:
                continue

            # ── Setup válido — calcular precios operativos
            entry_bid = opens[i + 1]
            sl_buffer = sl_buffer_pips * PIP

            if direction == "buy":
                sl_price = poi.distal - sl_buffer
                risk     = entry_bid - sl_price
                tp_price = entry_bid + 2.0 * risk
            else:
                sl_price = poi.distal + sl_buffer
                risk     = sl_price - entry_bid
                tp_price = entry_bid - 2.0 * risk

            if risk <= 0:
                continue

            risk_pips = risk / PIP
            if risk_pips < MIN_RISK_PIPS:
                continue

            # Sesión label
            session_lbl = "london_killzone" if in_london[i] else "newyork_am_open"

            # Evento estructural más reciente
            struct_event = _last_structure_event(m15_feat, i)

            # Distancia al nivel de estructura en pips
            # Para BUY: distancia del close al swing high más cercano (nivel que se rompió)
            # Para SELL: distancia del close al swing low más cercano
            if direction == "buy":
                dist_struct = (bar_close - lh) / PIP if not np.isnan(lh) else np.nan
            else:
                dist_struct = (ll - bar_close) / PIP if not np.isnan(ll) else np.nan

            # ATR y volatilidad (con fallback)
            atr_val = atr_vals[i] if not np.isnan(atr_vals[i]) else 0.0
            vol_val = vol_vals[i] if not np.isnan(vol_vals[i]) else 0.0
            volr    = volrel[i] if not np.isnan(volrel[i]) else 1.0
            disp    = disp_score[i] if not np.isnan(disp_score[i]) else 0.0

            setup = SetupRecord(
                fecha               = pd.Timestamp(datetimes[i]),
                bar_index           = i,
                entry_bar_index     = i + 1,
                direccion           = "compra" if direction == "buy" else "venta",
                sesion              = session_lbl,
                cambio_estructura   = struct_event,
                atr                 = atr_val,
                volatilidad         = vol_val,
                volumen_rel         = volr,
                distancia_estructura = dist_struct,
                entry_bid           = entry_bid,
                sl_price            = sl_price,
                tp_price            = tp_price,
                risk_pips           = risk_pips,
                fib_retracement     = fib_ret,
                fib_in_entry_zone   = int(fib_ret >= 0.50),
                fib_in_pref_zone    = int(0.60 <= fib_ret <= 0.70),
                poi_type            = 0 if poi.poi_type == POIType.FVG else 1,
                poi_state_at_entry  = 0 if poi.state == POIState.FRESH else 1,
                poi_size_pips       = poi.size / PIP,
                body_range_ratio    = body_ratio[i],
                displacement_score  = disp,
                h1_bias             = str(bias),
            )
            setups.append(setup)
            setup_found = True
            break  # un setup por barra (primera confluencia válida)

        # Actualizar estados de todos los POIs activos globales (incluyendo los que no dieron setup)
        for poi in all_pois:
            if poi.created_at < bar_ts and poi.state not in (
                POIState.FULLY_MITIGATED, POIState.INVALIDATED
            ):
                poi.update_state(bar_low, bar_high, bar_close)

    # ── 6. Convertir a DataFrame
    if not setups:
        return pd.DataFrame()

    rows = [vars(s) for s in setups]
    return pd.DataFrame(rows)


# ── Nota sobre decisiones provisionales ──────────────────────────────────────
# CONF_MIN_BODY_RATIO = 0.20
#   Motivo provisional: evitar velas doji como señales de confirmación.
#   Una vela con body/range < 20% no muestra dirección clara.
#   Para consultar con el trader y ajustar en V2.
#
# SL_BUFFER_PIPS = 0.5
#   Motivo provisional: mismo valor que EQUAL_HLS_TOLERANCE_PIPS en strategy_config.
#   Evita que el SL sea exactamente igual al nivel, dejando algo de margen.
#   Para consultar con el trader y ajustar en V2.
#
# HTF_FILTER = True
#   Motivo: reduce la muestra pero aumenta la calidad de los setups.
#   Operaciones contra el sesgo H1 se omiten.
#   Si el trader prefiere registrar TODO (incluso contra el sesgo) como feature,
#   cambiar a False y añadir columna "h1_alignment" = 0/1.
