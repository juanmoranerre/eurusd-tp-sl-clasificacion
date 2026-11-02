"""
setup_detector.py — Detector de setups Sistema A (V1)

Un setup es válido cuando confluyen simultáneamente:
  1. La barra M15 está dentro de una ventana operativa (London KZ o NY AM)
  2. Hay un POI activo (FRESH o TOUCHED) de cualquier dirección
  3. La barra de confirmación toca o entra en el POI
  4. La barra de confirmación cierra en la dirección del POI
     (close > open para BUY; close < open para SELL)
  5. El cuerpo de la barra de confirmación tiene body_ratio >= CONF_MIN_BODY_RATIO
     (P-A: 0.0 — sin filtro de cuerpo mínimo; body_range_ratio se conserva como predictor)
  6. El retroceso de Fibonacci en la barra de confirmación >= 50% (PD-014)

H1 alignment no es filtro obligatorio (P-B: HTF_FILTER = False).
Se registra h1_alignment como variable categórica con 4 categorías:
  "aligned"     — dirección del setup coincide con el sesgo H1
  "counter"     — dirección del setup es contraria al sesgo H1
  "neutral"     — H1 está en rango (sesgo "ranging")
  "unavailable" — no hay datos H1 disponibles para la barra (NaN)

Entrada: apertura de la barra siguiente (modo conservador, PD-015)
SL: distal del POI ± SL_BUFFER_PIPS (provisional V1: 0.5 pips; P-C)
TP: entry ± 2R (R = distancia entry→SL)
Time exit: 90 minutos desde la entrada efectiva (PD-019, implementado en trade_simulator)

Decisiones vigentes V1:
  CONF_MIN_BODY_RATIO  = 0.0   — sin filtro de cuerpo mínimo (P-A, 2026-11-02)
  SL_BUFFER_PIPS       = 0.5   — buffer más allá del distal del POI (P-C provisional)
  HTF_FILTER           = False — no se requiere alineación H1 (P-B, 2026-11-02)
  POI_MAX_STATE        = TOUCHED — solo FRESH y TOUCHED para entrada; PARTIALLY_MITIGATED excluido

Sobre distancia_estructura:
  Para BUY: (close - pivot_high_st) / PIP — siempre negativo (close < swing high de referencia).
  Para SELL: (pivot_low_st - close) / PIP — siempre negativo (close > swing low de referencia).
  El valor absoluto representa la profundidad del retroceso desde el nivel de estructura.
  Un valor más negativo indica un retroceso más profundo dentro de la zona de descuento/premium.
  El signo no codifica información direccional adicional (la dirección se conoce por 'direccion').

Parámetros PENDING de V2 no implementados aquí:
  DISPLACEMENT_THRESHOLD (PD-005b) — el score se registra pero no filtra
  OB_GROUP_MAX_CANDLES (PD-005c)   — solo última vela OB
  SL_BUFFER_PIPS sensitivity (V2-016) — sensibilidad a 0.2, 0.5, 1.0 pips
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

# ── Parámetros V1 (vigentes tras decisiones P-A, P-B, P-C de 2026-11-02) ─────
CONF_MIN_BODY_RATIO = 0.0    # P-A: sin filtro de cuerpo mínimo
SL_BUFFER_PIPS      = 0.5    # P-C: provisional, configurable (ver roadmap_v2 V2-016)
HTF_FILTER          = False  # P-B: no se requiere alineación H1
MIN_RISK_PIPS       = 5.0    # riesgo mínimo aceptable
PIP                 = 0.0001


# ── Tipos de salida ────────────────────────────────────────────────────────────

@dataclass
class SetupRecord:
    """Una fila del dataset de setups antes de la simulación de trades."""

    # ── Metadatos de identificación
    fecha:               pd.Timestamp
    bar_index:           int
    entry_bar_index:     int
    poi_id:              int            # identificador único del POI (C2)

    # ── Variables del dataset (columnas del CSV)
    direccion:           str            # "compra" | "venta"
    sesion:              str            # "london_killzone" | "newyork_am_open"
    cambio_estructura:   str            # "bos_bull" | "bos_bear" | "choch_bull" | "choch_bear"
    h1_alignment:        str            # "aligned" | "counter" | "neutral" | "unavailable"
    atr:                 float
    volatilidad:         float
    volumen_rel:         float
    distancia_estructura: float         # pips (siempre < 0; ver docstring del módulo)

    # ── Precios operativos (metadata, no van al CSV)
    entry_bid:           float
    sl_price:            float
    tp_price:            float
    risk_pips:           float

    # ── Features adicionales (predictores en el CSV)
    fib_retracement:     float
    fib_in_entry_zone:   int            # siempre 1 (fib >= 0.50 es filtro); no va al CSV
    fib_in_pref_zone:    int
    poi_type:            int            # 0=fvg, 1=order_block
    poi_state_at_entry:  int            # 0=fresh, 1=touched
    poi_size_pips:       float
    body_range_ratio:    float
    displacement_score:  float
    h1_bias:             str            # sesgo H1 raw; en metadata, no en CSV

    # ── Resultado (asignado después por el simulador)
    resultado:           int | None = None
    exit_reason:         str | None = None


def _pois_from_features(df: pd.DataFrame) -> list[POI]:
    """Extrae todos los POIs detectados en el DataFrame M15."""
    pois: list[POI] = []
    datetime_col = df["datetime"].values if "datetime" in df.columns else None
    poi_id = 0

    n = len(df)
    for i in range(n):
        ts = pd.Timestamp(datetime_col[i]) if datetime_col is not None else pd.Timestamp(df.index[i])

        if df["fvg_bull"].iat[i]:
            pois.append(POI(
                poi_type=POIType.FVG,
                direction=POIDirection.BULLISH,
                proximal=df["fvg_high"].iat[i],
                distal=df["fvg_low"].iat[i],
                created_at=ts,
                poi_id=poi_id,
            ))
            poi_id += 1

        if df["fvg_bear"].iat[i]:
            pois.append(POI(
                poi_type=POIType.FVG,
                direction=POIDirection.BEARISH,
                proximal=df["fvg_low"].iat[i],
                distal=df["fvg_high"].iat[i],
                created_at=ts,
                poi_id=poi_id,
            ))
            poi_id += 1

        if df["ob_bull"].iat[i]:
            pois.append(POI(
                poi_type=POIType.ORDER_BLOCK,
                direction=POIDirection.BULLISH,
                proximal=df["ob_high"].iat[i],
                distal=df["ob_low"].iat[i],
                created_at=ts,
                poi_id=poi_id,
            ))
            poi_id += 1

        if df["ob_bear"].iat[i]:
            pois.append(POI(
                poi_type=POIType.ORDER_BLOCK,
                direction=POIDirection.BEARISH,
                proximal=df["ob_low"].iat[i],
                distal=df["ob_high"].iat[i],
                created_at=ts,
                poi_id=poi_id,
            ))
            poi_id += 1

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
    return "bos_bull"


def _h1_alignment(bias: object, direction: str) -> str:
    """
    Clasifica la alineación entre el sesgo H1 y la dirección del setup.

    Categorías (no deben mezclarse en el modelo sin one-hot):
      "aligned"     — setup en la dirección del sesgo H1
      "counter"     — setup contra el sesgo H1
      "neutral"     — H1 en rango (bias == "ranging")
      "unavailable" — sin datos H1 para la barra
    """
    if bias is None or (isinstance(bias, float) and np.isnan(bias)):
        return "unavailable"
    bias_str = str(bias).lower().strip()
    if bias_str in ("nan", "", "none"):
        return "unavailable"
    if bias_str == "ranging":
        return "neutral"
    if bias_str == "bullish":
        return "aligned" if direction == "buy" else "counter"
    if bias_str == "bearish":
        return "aligned" if direction == "sell" else "counter"
    return "unavailable"


def _fib_retracement(price: float, last_high: float, last_low: float, direction: str) -> float:
    """Calcula el retroceso Fibonacci del precio en la vela de confirmación."""
    rng = last_high - last_low
    if rng <= 0:
        return 0.0
    if direction == "buy":
        return (last_high - price) / rng
    else:
        return (price - last_low) / rng


def build_m15_features(m15: pd.DataFrame) -> pd.DataFrame:
    """
    Construye el DataFrame M15 completo con todas las features necesarias
    para la detección de setups.
    """
    df = m15.copy()
    if "datetime" not in df.columns:
        raise ValueError("m15 debe tener columna 'datetime'")

    df = df.set_index("datetime")
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)

    df["london_killzone"] = london_killzone(df)
    df["newyork_am_open"] = newyork_am_open(df)
    df["any_session"]     = df["london_killzone"] | df["newyork_am_open"]

    df = add_market_structure(df, n=1, level="short_term")

    df["atr14"] = compute_atr(df, period=14)
    df["volatility20"] = rolling_volatility(df, period=20)

    # volumen_rel: tick count de Dukascopy — no es volumen centralizado de mercado
    if "volume" in df.columns:
        df["volume_mean20"] = df["volume"].rolling(20, min_periods=1).mean()
        df["volumen_rel"]   = df["volume"] / df["volume_mean20"].replace(0, np.nan)
    else:
        df["volumen_rel"] = np.nan

    df["body_range_ratio_col"] = body_to_range_ratio(df)
    df["displacement_score"]   = compute_displacement(df)

    df = detect_fvg(df)
    df = detect_order_blocks(df)

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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Escanea el DataFrame M15 y devuelve todos los setups detectados.

    Con HTF_FILTER=False (P-B), la dirección del setup viene del POI
    (BULLISH→buy, BEARISH→sell). h1_alignment registra la relación entre
    el sesgo H1 y la dirección adoptada, sin actuar como filtro.

    Con HTF_FILTER=True, solo pasan setups donde h1_alignment == "aligned".
    """
    m15_feat = build_m15_features(m15)

    if start_date:
        m15_feat = m15_feat[m15_feat["datetime"] >= pd.Timestamp(start_date)]
    if end_date:
        m15_feat = m15_feat[m15_feat["datetime"] <= pd.Timestamp(end_date)]
    m15_feat = m15_feat.reset_index(drop=True)

    h1_ctx = build_h1_context(m15_feat, h1, n=1, level="short_term")
    m15_feat = h1_ctx

    all_pois = _pois_from_features(m15_feat)

    n = len(m15_feat)
    datetimes  = m15_feat["datetime"].values
    opens      = m15_feat["open"].values
    closes     = m15_feat["close"].values
    lows       = m15_feat["low"].values
    highs      = m15_feat["high"].values

    in_london      = m15_feat["london_killzone"].values
    in_ny          = m15_feat["newyork_am_open"].values
    in_session_arr = (in_london | in_ny)

    last_highs = m15_feat["pivot_high_st"].ffill().values
    last_lows  = m15_feat["pivot_low_st"].ffill().values

    h1_bias_arr = m15_feat["h1_structure_bias"].values

    atr_vals   = m15_feat["atr14"].values
    vol_vals   = m15_feat["volatility20"].values
    volrel     = m15_feat["volumen_rel"].values
    body_ratio = m15_feat["body_range_ratio_col"].values
    disp_score = m15_feat["displacement_score"].values

    setups: list[SetupRecord] = []
    c2_excluded_rows: list[dict] = []

    for i in range(1, n - 1):
        if not in_session_arr[i]:
            continue
        if i + 1 >= n:
            break

        bar_ts    = pd.Timestamp(datetimes[i])
        bar_low   = lows[i]
        bar_high  = highs[i]
        bar_close = closes[i]
        raw_bias  = h1_bias_arr[i]

        # POIs activos de cualquier dirección (la dirección viene del POI)
        active_pois = [
            poi for poi in all_pois
            if poi.created_at < bar_ts
            and poi.state not in (POIState.FULLY_MITIGATED, POIState.INVALIDATED)
            and poi.state != POIState.PARTIALLY_MITIGATED
        ]

        if not active_pois:
            for poi in all_pois:
                if poi.created_at < bar_ts and poi.state not in (
                    POIState.FULLY_MITIGATED, POIState.INVALIDATED
                ):
                    poi.update_state(bar_low, bar_high, bar_close)
                    # C2: trackear episodios — precio sale completamente de la zona
                    if poi.touches > 0 and poi.state not in (POIState.FULLY_MITIGATED, POIState.INVALIDATED):
                        poi_lo_ep = min(poi.proximal, poi.distal)
                        poi_hi_ep = max(poi.proximal, poi.distal)
                        if poi.direction == POIDirection.BULLISH and bar_low > poi_hi_ep:
                            poi.episode_count += 1
                        elif poi.direction == POIDirection.BEARISH and bar_high < poi_lo_ep:
                            poi.episode_count += 1
            continue

        setup_found = False
        for poi in active_pois:
            direction = "buy" if poi.direction == POIDirection.BULLISH else "sell"

            # HTF_FILTER: omitir setups no alineados si está activo
            if htf_filter:
                if _h1_alignment(raw_bias, direction) != "aligned":
                    continue

            poi_lo = min(poi.proximal, poi.distal)
            poi_hi = max(poi.proximal, poi.distal)

            touches_zone = (bar_low <= poi_hi) if direction == "buy" else (bar_high >= poi_lo)
            if not touches_zone:
                continue

            if direction == "buy" and not (bar_close > opens[i]):
                continue
            if direction == "sell" and not (bar_close < opens[i]):
                continue

            if body_ratio[i] < conf_min_body:
                continue

            lh = last_highs[i]
            ll = last_lows[i]
            fib_ret = _fib_retracement(bar_close, lh, ll, direction)
            if np.isnan(fib_ret) or fib_ret < fib_min_retracement or fib_ret > 1.0:
                continue

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

            # C2: un solo setup por POI por episodio continuo de contacto
            if poi.last_setup_episode == poi.episode_count:
                c2_excluded_rows.append({
                    "fecha":            pd.Timestamp(datetimes[i]),
                    "entry_bid":        entry_bid,
                    "sl_price":         sl_price,
                    "tp_price":         tp_price,
                    "risk_pips":        risk_pips,
                    "h1_alignment":     _h1_alignment(raw_bias, direction),
                    "h1_bias":          str(raw_bias),
                    "direccion":        "compra" if direction == "buy" else "venta",
                    "sesion":           "london_killzone" if in_london[i] else "newyork_am_open",
                    "poi_id":           poi.poi_id,
                    "motivo_exclusion": "C2_POI_REUSE",
                    "exit_reason":      "C2_POI_REUSE",
                })
                continue

            h1_align     = _h1_alignment(raw_bias, direction)
            session_lbl  = "london_killzone" if in_london[i] else "newyork_am_open"
            struct_event = _last_structure_event(m15_feat, i)

            # distancia_estructura siempre negativa (ver docstring del módulo)
            if direction == "buy":
                dist_struct = (bar_close - lh) / PIP if not np.isnan(lh) else np.nan
            else:
                dist_struct = (ll - bar_close) / PIP if not np.isnan(ll) else np.nan

            atr_val = float(atr_vals[i]) if not np.isnan(atr_vals[i]) else 0.0
            vol_val = float(vol_vals[i]) if not np.isnan(vol_vals[i]) else 0.0
            volr    = float(volrel[i])   if not np.isnan(volrel[i])   else 1.0
            disp    = float(disp_score[i]) if not np.isnan(disp_score[i]) else 0.0

            bias_label = "unavailable" if (
                raw_bias is None
                or (isinstance(raw_bias, float) and np.isnan(raw_bias))
                or str(raw_bias).lower() in ("nan", "", "none")
            ) else str(raw_bias)

            setup = SetupRecord(
                fecha                = pd.Timestamp(datetimes[i]),
                bar_index            = i,
                entry_bar_index      = i + 1,
                poi_id               = poi.poi_id,
                direccion            = "compra" if direction == "buy" else "venta",
                sesion               = session_lbl,
                cambio_estructura    = struct_event,
                h1_alignment         = h1_align,
                atr                  = atr_val,
                volatilidad          = vol_val,
                volumen_rel          = volr,
                distancia_estructura = dist_struct,
                entry_bid            = entry_bid,
                sl_price             = sl_price,
                tp_price             = tp_price,
                risk_pips            = risk_pips,
                fib_retracement      = fib_ret,
                fib_in_entry_zone    = int(fib_ret >= 0.50),
                fib_in_pref_zone     = int(0.60 <= fib_ret <= 0.70),
                poi_type             = 0 if poi.poi_type == POIType.FVG else 1,
                poi_state_at_entry   = 0 if poi.state == POIState.FRESH else 1,
                poi_size_pips        = poi.size / PIP,
                body_range_ratio     = body_ratio[i],
                displacement_score   = disp,
                h1_bias              = bias_label,
            )
            poi.last_setup_episode = poi.episode_count
            setups.append(setup)
            setup_found = True
            break

        for poi in all_pois:
            if poi.created_at < bar_ts and poi.state not in (
                POIState.FULLY_MITIGATED, POIState.INVALIDATED
            ):
                poi.update_state(bar_low, bar_high, bar_close)
                # C2: trackear episodios — precio sale completamente de la zona
                if poi.touches > 0 and poi.state not in (POIState.FULLY_MITIGATED, POIState.INVALIDATED):
                    poi_lo_ep = min(poi.proximal, poi.distal)
                    poi_hi_ep = max(poi.proximal, poi.distal)
                    if poi.direction == POIDirection.BULLISH and bar_low > poi_hi_ep:
                        poi.episode_count += 1
                    elif poi.direction == POIDirection.BEARISH and bar_high < poi_lo_ep:
                        poi.episode_count += 1

    valid_df = pd.DataFrame([vars(s) for s in setups]) if setups else pd.DataFrame()
    c2_excluded_df = pd.DataFrame(c2_excluded_rows) if c2_excluded_rows else pd.DataFrame()
    return valid_df, c2_excluded_df
