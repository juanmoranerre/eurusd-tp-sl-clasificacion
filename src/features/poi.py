"""
poi.py — Detección de Points of Interest (POI): FVG y Order Blocks

Tipos de POI confirmados por el trader (PD-007):
  FVG (Fair Value Gap / Imbalance): desequilibrio de 3 velas
    Alcista: high(c1) < low(c3)
    Bajista: low(c1) > high(c3)

  Order Block (OB): última vela contraria antes de un impulso relevante
    Bullish OB: última vela bajista antes de desplazamiento alcista
    Bearish OB: última vela alcista antes de desplazamiento bajista

Estados de un POI (PD-010):
  fresh             → zona no visitada
  touched           → primer contacto con el precio
  partially_mitigated → penetración parcial
  fully_mitigated   → precio atravesó completamente la zona
  invalidated       → cierre más allá del extremo distal

Cada POI queda registrado con su zona (proximal, distal), dirección,
timestamp de creación y estado actual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd


# ── Constantes y tipos ────────────────────────────────────────────────────────

class POIType(str, Enum):
    FVG          = "fvg"
    ORDER_BLOCK  = "order_block"


class POIDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class POIState(str, Enum):
    FRESH               = "fresh"
    TOUCHED             = "touched"
    PARTIALLY_MITIGATED = "partially_mitigated"
    FULLY_MITIGATED     = "fully_mitigated"
    INVALIDATED         = "invalidated"


@dataclass
class POI:
    """Representación de un Point of Interest."""
    poi_type:   POIType
    direction:  POIDirection
    proximal:   float           # nivel más cercano al precio actual
    distal:     float           # nivel más alejado del precio actual
    created_at: pd.Timestamp    # barra donde se confirmó el POI
    state:      POIState = POIState.FRESH
    touches:    int      = 0
    source_bar: pd.Timestamp | None = None  # barra del extremo origen (no disponibilidad)

    @property
    def midpoint(self) -> float:
        return (self.proximal + self.distal) / 2

    @property
    def size(self) -> float:
        return abs(self.distal - self.proximal)

    def contains(self, price: float) -> bool:
        lo = min(self.proximal, self.distal)
        hi = max(self.proximal, self.distal)
        return lo <= price <= hi

    def update_state(self, low: float, high: float, close: float) -> None:
        """Actualiza el estado del POI dado el OHLC de la barra actual."""
        if self.state == POIState.INVALIDATED:
            return

        lo = min(self.proximal, self.distal)
        hi = max(self.proximal, self.distal)

        # Invalidación: cierre más allá del extremo distal (PD-010)
        if self.direction == POIDirection.BULLISH and close < self.distal:
            self.state = POIState.INVALIDATED
            return
        if self.direction == POIDirection.BEARISH and close > self.distal:
            self.state = POIState.INVALIDATED
            return

        # Contacto con la zona
        if low <= hi and high >= lo:
            self.touches += 1

            # Distinción TOUCHED vs PARTIALLY_MITIGATED por posición del close:
            #   TOUCHED:              wick entra en la zona, close cierra fuera del proximal
            #   PARTIALLY_MITIGATED:  close cierra dentro de la zona (entre distal y proximal)
            #   FULLY_MITIGATED:      wick alcanza o cruza el distal (no cierra más allá)
            if self.direction == POIDirection.BULLISH:
                # proximal = hi (techo de la zona), distal = lo (suelo)
                if low <= lo:
                    self.state = POIState.FULLY_MITIGATED
                elif close < hi:
                    # close dentro de la zona → mitigación parcial
                    self.state = POIState.PARTIALLY_MITIGATED
                elif self.state == POIState.FRESH:
                    # wick toca zona pero close vuelve sobre el proximal
                    self.state = POIState.TOUCHED
            else:
                # BEARISH: proximal = lo (suelo de la zona), distal = hi (techo)
                if high >= hi:
                    self.state = POIState.FULLY_MITIGATED
                elif close > lo:
                    self.state = POIState.PARTIALLY_MITIGATED
                elif self.state == POIState.FRESH:
                    self.state = POIState.TOUCHED


# ── FVG (Fair Value Gap) ──────────────────────────────────────────────────────

def detect_fvg(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detecta Fair Value Gaps (imbalances de 3 velas) en el DataFrame.

    FVG alcista: high(c1) < low(c3)   → zona: [high(c1), low(c3)]
    FVG bajista: low(c1) > high(c3)   → zona: [high(c3), low(c1)]

    No-lookahead: el FVG se confirma al cierre de c3 (barra central + 2 barras).
    La columna se marca en la barra donde se puede conocer el FVG (índice de c3).

    Añade:
      fvg_bull         — bool
      fvg_bear         — bool
      fvg_high         — float: extremo superior del gap (o NaN)
      fvg_low          — float: extremo inferior del gap (o NaN)
      fvg_size         — float: tamaño del gap (fvg_high - fvg_low, o NaN)
    """
    _check_ohlc_columns(df)
    n = len(df)
    h = df["high"].values
    l = df["low"].values

    fvg_bull = np.zeros(n, dtype=bool)
    fvg_bear = np.zeros(n, dtype=bool)
    fvg_h    = np.full(n, np.nan)
    fvg_l    = np.full(n, np.nan)

    for i in range(2, n):
        # Alcista: gap entre high de c1 (i-2) y low de c3 (i=c3)
        if h[i - 2] < l[i]:
            fvg_bull[i] = True
            fvg_l[i]    = h[i - 2]
            fvg_h[i]    = l[i]
        # Bajista: gap entre low de c1 (i-2) y high de c3 (i=c3)
        if l[i - 2] > h[i]:
            fvg_bear[i] = True
            fvg_h[i]    = l[i - 2]
            fvg_l[i]    = h[i]

    out = df.copy()
    out["fvg_bull"] = fvg_bull
    out["fvg_bear"] = fvg_bear
    out["fvg_high"] = fvg_h
    out["fvg_low"]  = fvg_l
    out["fvg_size"] = np.where(fvg_bull | fvg_bear, fvg_h - fvg_l, np.nan)

    return out


# ── Order Block ───────────────────────────────────────────────────────────────

def detect_order_blocks(
    df: pd.DataFrame,
    *,
    impulse_min_size: float | None = None,
    impulse_atr_multiplier: float = 1.0,
    atr_period: int = 14,
) -> pd.DataFrame:
    """
    Detecta Order Blocks (OB): última vela contraria antes de un impulso relevante.

    Bullish OB: última vela bajista (close < open) inmediatamente antes de
                una vela alcista de tamaño relevante.
    Bearish OB: última vela alcista (close > open) inmediatamente antes de
                una vela bajista de tamaño relevante.

    Si ``impulse_min_size`` es None, el tamaño mínimo del impulso se deriva de
    ``impulse_atr_multiplier`` × ATR(``atr_period``). Si ambos son None, se
    usa la vela más grande del 75th percentil del rango como umbral.

    No-lookahead: el OB se confirma al cierre de la vela impulso (barra i),
    marcado en i. La vela OB fue la barra i-1.

    Añade:
      ob_bull          — bool: OB alcista en la barra de confirmación
      ob_bear          — bool: OB bajista en la barra de confirmación
      ob_high          — float: high de la vela OB
      ob_low           — float: low de la vela OB
      ob_open          — float: open de la vela OB (para definir la zona exacta)
      ob_close         — float: close de la vela OB
    """
    _check_ohlc_columns(df)
    n = len(df)

    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    rng = h - l

    # Umbral de impulso
    if impulse_min_size is not None:
        threshold = np.full(n, impulse_min_size)
    else:
        # ATR rolling para umbral dinámico
        from src.features.auxiliary import true_range
        tr = true_range(df).values
        atr_arr = pd.Series(tr).ewm(
            alpha=1.0 / atr_period, adjust=False, min_periods=atr_period
        ).mean().values
        threshold = np.where(np.isnan(atr_arr), np.nanmedian(rng), atr_arr) * impulse_atr_multiplier

    ob_bull  = np.zeros(n, dtype=bool)
    ob_bear  = np.zeros(n, dtype=bool)
    ob_h_out = np.full(n, np.nan)
    ob_l_out = np.full(n, np.nan)
    ob_o_out = np.full(n, np.nan)
    ob_c_out = np.full(n, np.nan)

    for i in range(1, n):
        impulse_size = rng[i]
        if impulse_size < threshold[i]:
            continue

        # Bullish OB: vela i-1 bajista + vela i alcista grande
        if c[i - 1] < o[i - 1] and c[i] > o[i]:
            ob_bull[i]  = True
            ob_h_out[i] = h[i - 1]
            ob_l_out[i] = l[i - 1]
            ob_o_out[i] = o[i - 1]
            ob_c_out[i] = c[i - 1]

        # Bearish OB: vela i-1 alcista + vela i bajista grande
        if c[i - 1] > o[i - 1] and c[i] < o[i]:
            ob_bear[i]  = True
            ob_h_out[i] = h[i - 1]
            ob_l_out[i] = l[i - 1]
            ob_o_out[i] = o[i - 1]
            ob_c_out[i] = c[i - 1]

    out = df.copy()
    out["ob_bull"]  = ob_bull
    out["ob_bear"]  = ob_bear
    out["ob_high"]  = ob_h_out
    out["ob_low"]   = ob_l_out
    out["ob_open"]  = ob_o_out
    out["ob_close"] = ob_c_out

    return out


# ── Pipeline POI completo ─────────────────────────────────────────────────────

def add_poi_features(
    df: pd.DataFrame,
    *,
    impulse_atr_multiplier: float = 1.0,
    atr_period: int = 14,
) -> pd.DataFrame:
    """
    Añade todas las features de POI (FVG + OB) al DataFrame.

    Returns copia del DataFrame con columnas de FVG y Order Block.
    """
    out = detect_fvg(df)
    out = detect_order_blocks(
        out,
        impulse_atr_multiplier=impulse_atr_multiplier,
        atr_period=atr_period,
    )
    return out


# ── Tracking de estados activos ────────────────────────────────────────────────

def track_poi_states(df: pd.DataFrame, pois: list[POI]) -> pd.DataFrame:
    """
    Recorre el DataFrame barra a barra y actualiza el estado de cada POI.

    Returns el mismo DataFrame con una columna adicional:
      active_pois_count — número de POIs activos (fresh/touched/partially) en esa barra
    """
    n = len(df)
    active_count = np.zeros(n, dtype=int)

    for i in range(n):
        lo = df["low"].iat[i]
        hi = df["high"].iat[i]
        cl = df["close"].iat[i]
        for poi in pois:
            poi.update_state(lo, hi, cl)
        active = sum(
            1 for p in pois
            if p.state in (POIState.FRESH, POIState.TOUCHED, POIState.PARTIALLY_MITIGATED)
        )
        active_count[i] = active

    out = df.copy()
    out["active_pois_count"] = active_count
    return out


# ── Utilidades ────────────────────────────────────────────────────────────────

def _check_ohlc_columns(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas OHLC: {missing}")
