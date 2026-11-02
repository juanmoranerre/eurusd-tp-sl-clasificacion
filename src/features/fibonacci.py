"""
fibonacci.py — Niveles Fibonacci para EUR/USD Trading Intelligence System

Configuración confirmada por el trader (PD-013/014):
  Anclaje: último impulso relevante
    Alcista: 0% = máximo del impulso, 100% = mínimo (retroceso hacia abajo)
    Bajista: 0% = mínimo del impulso, 100% = máximo (retroceso hacia arriba)

  Niveles activos: 0%, 50%, 60%, 75%, 90%, 100%
  Zona mínima de entrada: 50%
  Zona preferida: 60%–70%
  Zona de riesgo aumentado: 75%–90%
  Origen: 100%

Cada set de niveles queda anclado a timestamps conocidos para preservar
la restricción de no-lookahead.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.strategy_config import (
    FIB_ENTRY_MIN,
    FIB_ENTRY_PREF_HIGH,
    FIB_ENTRY_PREF_LOW,
    FIB_LEVELS,
)


# ── Estructura de un set de niveles Fibonacci ─────────────────────────────────

@dataclass
class FibSet:
    """Un set de niveles Fibonacci anclado a un impulso."""
    direction:   str           # "bullish" | "bearish"
    origin:      float         # 100% (inicio del impulso)
    extreme:     float         # 0%    (fin del impulso)
    anchor_from: pd.Timestamp  # timestamp disponibilidad del punto de origen
    anchor_to:   pd.Timestamp  # timestamp disponibilidad del punto extremo
    levels:      list[float] = None  # niveles activos (fracción, e.g. 0.5)

    def __post_init__(self):
        if self.levels is None:
            self.levels = FIB_LEVELS

    @property
    def range(self) -> float:
        return abs(self.extreme - self.origin)

    def price_at(self, fib_level: float) -> float:
        """Precio en el nivel Fibonacci dado (0=extreme, 1=origin)."""
        return self.extreme + fib_level * (self.origin - self.extreme)

    def all_prices(self) -> dict[float, float]:
        """Mapa {nivel: precio} para todos los niveles activos."""
        return {lvl: self.price_at(lvl) for lvl in self.levels}

    def in_entry_zone(self, price: float) -> bool:
        """True si el precio está en la zona mínima de entrada (≥ FIB_ENTRY_MIN)."""
        if self.range == 0:
            return False
        ratio = abs(price - self.extreme) / self.range
        return ratio >= FIB_ENTRY_MIN

    def in_preferred_zone(self, price: float) -> bool:
        """True si el precio está en la zona preferida (60%–70%)."""
        if self.range == 0:
            return False
        ratio = abs(price - self.extreme) / self.range
        return FIB_ENTRY_PREF_LOW <= ratio <= FIB_ENTRY_PREF_HIGH

    def retracement_ratio(self, price: float) -> float | None:
        """Retroceso del precio como fracción [0, 1]. None si range=0."""
        if self.range == 0:
            return None
        return abs(price - self.extreme) / self.range


# ── Cálculo de niveles Fibonacci desde swings ─────────────────────────────────

def fib_levels_from_swing(
    origin: float,
    extreme: float,
    direction: str,
    anchor_from: pd.Timestamp,
    anchor_to: pd.Timestamp,
    levels: list[float] | None = None,
) -> FibSet:
    """
    Construye un FibSet a partir de los puntos de anclaje.

    origin  → 100% del retroceso (inicio del impulso)
    extreme → 0%   del retroceso (fin del impulso)
    """
    if levels is None:
        levels = FIB_LEVELS
    if direction not in ("bullish", "bearish"):
        raise ValueError(f"direction debe ser 'bullish' o 'bearish', se recibió '{direction}'")
    return FibSet(
        direction=direction,
        origin=origin,
        extreme=extreme,
        anchor_from=anchor_from,
        anchor_to=anchor_to,
        levels=levels,
    )


# ── Cálculo sobre DataFrame ───────────────────────────────────────────────────

def add_fibonacci_features(
    df: pd.DataFrame,
    fib_set: FibSet,
    *,
    prefix: str = "fib",
) -> pd.DataFrame:
    """
    Añade features de Fibonacci al DataFrame basadas en un FibSet.

    Columnas añadidas:
      {prefix}_retracement   — retroceso actual del close respecto al FibSet [0,1]
      {prefix}_in_entry_zone — bool: close en zona de entrada (≥ FIB_ENTRY_MIN)
      {prefix}_in_pref_zone  — bool: close en zona preferida (60%–70%)
      {prefix}_level_0       — precio del nivel 0%  (extreme)
      {prefix}_level_50      — precio del nivel 50%
      {prefix}_level_60      — precio del nivel 60%
      {prefix}_level_75      — precio del nivel 75%
      {prefix}_level_90      — precio del nivel 90%
      {prefix}_level_100     — precio del nivel 100% (origin)
    """
    out = df.copy()
    close = df["close"].values
    n = len(df)

    # Retroceso del close
    if fib_set.range > 0:
        retrace = np.abs(close - fib_set.extreme) / fib_set.range
    else:
        retrace = np.full(n, np.nan)

    out[f"{prefix}_retracement"]  = retrace
    out[f"{prefix}_in_entry_zone"] = retrace >= FIB_ENTRY_MIN
    out[f"{prefix}_in_pref_zone"]  = (retrace >= FIB_ENTRY_PREF_LOW) & (retrace <= FIB_ENTRY_PREF_HIGH)

    # Precios de cada nivel
    all_prices = fib_set.all_prices()
    label_map = {0.0: "0", 0.5: "50", 0.6: "60", 0.75: "75", 0.9: "90", 1.0: "100"}
    for lvl, price in all_prices.items():
        label = label_map.get(lvl, str(int(lvl * 100)))
        out[f"{prefix}_level_{label}"] = price

    return out


def build_fib_sets_from_structure(
    df: pd.DataFrame,
    *,
    swing_level: str = "short_term",
) -> list[FibSet]:
    """
    Construye FibSets a partir de los swings detectados en el DataFrame.

    Requiere columnas de swing (de detect_swing_hierarchy).
    Un FibSet se crea para cada par (swing_high, swing_low) consecutivo.

    Returns lista de FibSet ordenados por anchor_to (más reciente último).
    """
    from src.features.structure import _level_suffix
    suffix = _level_suffix(swing_level)

    sh_col   = f"swing_high_{suffix}"
    sl_col   = f"swing_low_{suffix}"
    ph_col   = f"pivot_high_{suffix}"
    pl_col   = f"pivot_low_{suffix}"

    for col in [sh_col, sl_col, ph_col, pl_col]:
        if col not in df.columns:
            raise ValueError(f"Columna {col} no encontrada. Ejecuta detect_swing_hierarchy primero.")

    fib_sets = []
    h_times   = df.index[df[sh_col]]
    l_times   = df.index[df[sl_col]]

    # Para cada high, buscar el low anterior más reciente → impulso bajista
    for ht in h_times:
        prior_lows = l_times[l_times < ht]
        if prior_lows.empty:
            continue
        lt = prior_lows[-1]
        low_val  = df.loc[lt, pl_col]
        high_val = df.loc[ht, ph_col]
        if np.isnan(low_val) or np.isnan(high_val):
            continue
        # Impulso alcista: origin=low, extreme=high
        fib_sets.append(FibSet(
            direction="bullish",
            origin=low_val,
            extreme=high_val,
            anchor_from=lt,
            anchor_to=ht,
        ))

    # Para cada low, buscar el high anterior más reciente → impulso alcista luego bajista
    for lt in l_times:
        prior_highs = h_times[h_times < lt]
        if prior_highs.empty:
            continue
        ht = prior_highs[-1]
        high_val = df.loc[ht, ph_col]
        low_val  = df.loc[lt, pl_col]
        if np.isnan(high_val) or np.isnan(low_val):
            continue
        # Impulso bajista: origin=high, extreme=low
        fib_sets.append(FibSet(
            direction="bearish",
            origin=high_val,
            extreme=low_val,
            anchor_from=ht,
            anchor_to=lt,
        ))

    fib_sets.sort(key=lambda f: f.anchor_to)
    return fib_sets


def retracement_features(df: pd.DataFrame, fib_set: FibSet) -> pd.Series:
    """
    Calcula el retroceso del close respecto a un FibSet para cada barra.
    Solo disponible desde la barra anchor_to en adelante.
    """
    n = len(df)
    retrace = np.full(n, np.nan)

    if fib_set.range == 0:
        return pd.Series(retrace, index=df.index, name="fib_retracement")

    available_mask = df.index >= fib_set.anchor_to
    close_vals = df["close"].values
    retrace[available_mask] = np.abs(
        close_vals[available_mask] - fib_set.extreme
    ) / fib_set.range

    return pd.Series(retrace, index=df.index, name="fib_retracement")
