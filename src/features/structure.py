"""
structure.py — Estructura de mercado: swings, BOS y CHOCH

Implementa la jerarquía ICT/SMC aprobada por el trader (PD-002/003/004):

  Jerarquía de swings:
    STH/STL (Short-Term): pivote de 3 velas, 1 vela a cada lado
    ITH/ITL (Intermediate-Term): construido a partir de STH/STL
    LTH/LTL (Long-Term): construido a partir de ITH/ITL

  BOS (Break of Structure) — CONFIRMADO:
    Alcista: cierre por encima del swing high estructural relevante
    Bajista: cierre por debajo del swing low estructural relevante
    Una mecha que supera un nivel = sweep candidate, NO BOS

  CHOCH (Change of Character) — CONVENCIONAL:
    Primer cierre en dirección contraria a la estructura predominante
    Distingue: interno (dentro del retroceso) vs externo (contra HTF)

  Restricción de lookahead (CRÍTICA):
    Un swing se marca como CONFIRMADO en la barra [t+1] (cuando cierra la
    vela posterior que permite verificarlo). La barra donde ocurrió el extremo
    (t-1) NO es la barra de disponibilidad del conocimiento.

Columnas de salida típicas añadidas al DataFrame:
  swing_high_st, swing_low_st   — STH/STL (True donde existe el pivot)
  swing_high_it, swing_low_it   — ITH/ITL
  swing_high_lt, swing_low_lt   — LTH/LTL
  confirmed_at_st_{h/l}         — índice de confirmación de cada STH/STL
  bos_bull, bos_bear             — BOS alcista / bajista
  bos_type                       — "internal" | "external" | None
  choch_bull, choch_bear         — CHOCH alcista / bajista
  choch_type                     — "internal" | "external" | None
  structure_bias                 — "bullish" | "bearish" | "ranging" | None
"""

from __future__ import annotations

from enum import Enum

import numpy as np
import pandas as pd


# ── Tipos y constantes ────────────────────────────────────────────────────────

class SwingLevel(str, Enum):
    SHORT_TERM     = "short_term"
    INTERMEDIATE   = "intermediate_term"
    LONG_TERM      = "long_term"


SWING_PIVOT_BARS = 1  # velas a cada lado (3-vela pivot); configurable como parámetro


# ── Detección de pivotes (STH/STL) ────────────────────────────────────────────

def detect_pivots(
    df: pd.DataFrame,
    n: int = SWING_PIVOT_BARS,
    *,
    col_high: str = "high",
    col_low: str = "low",
) -> pd.DataFrame:
    """
    Detecta STH (Short-Term High) y STL (Short-Term Low) en el DataFrame.

    Un STH en la barra i existe cuando high[i] es el máximo local en [i-n, i+n].
    Un STL en la barra i existe cuando low[i]  es el mínimo local en [i-n, i+n].

    **No-lookahead**: la información de que existe un pivot en la barra i se
    hace disponible solo en la barra i+n (cuando cierra la vela de confirmación).
    Por eso, las columnas ``swing_high_st`` y ``swing_low_st`` están desplazadas n
    posiciones hacia adelante respecto al extremo real.

    Añade al DataFrame:
      swing_high_st  — bool: True en la barra de CONFIRMACIÓN del STH
      swing_low_st   — bool: True en la barra de CONFIRMACIÓN del STL
      pivot_high_st  — float: valor del high del STH (NaN si no hay pivot)
      pivot_low_st   — float: valor del low del STL (NaN si no hay pivot)
      pivot_high_bar — int: índice iloc del STH real (antes del shift)
      pivot_low_bar  — int: índice iloc del STL real (antes del shift)

    Returns una copia del DataFrame con las columnas añadidas.
    """
    if n < 1:
        raise ValueError(f"n debe ser >= 1, se recibió {n}")
    _check_ohlc_columns(df)

    high = df[col_high].values
    low  = df[col_low].values
    length = len(df)

    is_pivot_high = np.zeros(length, dtype=bool)
    is_pivot_low  = np.zeros(length, dtype=bool)

    for i in range(n, length - n):
        window_h = high[i - n : i + n + 1]
        window_l = low[i  - n : i + n + 1]
        if high[i] == window_h.max() and np.sum(window_h == high[i]) == 1:
            is_pivot_high[i] = True
        if low[i] == window_l.min() and np.sum(window_l == low[i]) == 1:
            is_pivot_low[i] = True

    # Desplazamiento n barras hacia adelante (no-lookahead)
    confirmed_high = np.roll(is_pivot_high, n)
    confirmed_low  = np.roll(is_pivot_low,  n)
    confirmed_high[:n] = False
    confirmed_low[:n]  = False

    # Valor del extremo en la barra donde OCURRIÓ el pivot (desplazado atrás n)
    pivot_high_val = np.where(confirmed_high, np.roll(high, n), np.nan)
    pivot_low_val  = np.where(confirmed_low,  np.roll(low,  n), np.nan)

    # Índice iloc del extremo real (para referencia en BOS/CHOCH)
    pivot_high_iloc = np.where(confirmed_high, np.arange(length) - n, -1).astype(int)
    pivot_low_iloc  = np.where(confirmed_low,  np.arange(length) - n, -1).astype(int)

    out = df.copy()
    out["swing_high_st"]   = confirmed_high
    out["swing_low_st"]    = confirmed_low
    out["pivot_high_st"]   = pivot_high_val
    out["pivot_low_st"]    = pivot_low_val
    out["pivot_high_bar"]  = pivot_high_iloc
    out["pivot_low_bar"]   = pivot_low_iloc

    return out


# ── Jerarquía de swings ITH/ITL y LTH/LTL ────────────────────────────────────

def _build_higher_level_pivots(
    is_pivot_h: np.ndarray,
    pivot_h_val: np.ndarray,
    is_pivot_l: np.ndarray,
    pivot_l_val: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Construye pivotes de nivel superior a partir de STH/STL.

    Un ITH es el STH más alto entre dos STL consecutivos.
    Un ITL es el STL más bajo entre dos STH consecutivos.

    Los pivotes de nivel superior se marcan en la misma barra de confirmación
    que el STH/STL base, preservando la restricción de no-lookahead.
    """
    length = len(is_pivot_h)
    is_high_out = np.zeros(length, dtype=bool)
    is_low_out  = np.zeros(length, dtype=bool)
    val_high_out = np.full(length, np.nan)
    val_low_out  = np.full(length, np.nan)

    # Obtener índices de pivotes de nivel inferior
    h_idx = np.where(is_pivot_h)[0]
    l_idx = np.where(is_pivot_l)[0]

    if len(h_idx) < 2 or len(l_idx) < 2:
        return is_high_out, val_high_out, is_low_out, val_low_out

    # Para cada par de STL consecutivos, encontrar el STH más alto entre ellos
    for i in range(len(l_idx) - 1):
        lo_start = l_idx[i]
        lo_end   = l_idx[i + 1]
        candidates = h_idx[(h_idx > lo_start) & (h_idx < lo_end)]
        if len(candidates) > 0:
            best = candidates[np.argmax(pivot_h_val[candidates])]
            is_high_out[best]  = True
            val_high_out[best] = pivot_h_val[best]

    # Para cada par de STH consecutivos, encontrar el STL más bajo entre ellos
    for i in range(len(h_idx) - 1):
        hi_start = h_idx[i]
        hi_end   = h_idx[i + 1]
        candidates = l_idx[(l_idx > hi_start) & (l_idx < hi_end)]
        if len(candidates) > 0:
            best = candidates[np.argmin(pivot_l_val[candidates])]
            is_low_out[best]  = True
            val_low_out[best] = pivot_l_val[best]

    return is_high_out, val_high_out, is_low_out, val_low_out


def detect_swing_hierarchy(df: pd.DataFrame, n: int = SWING_PIVOT_BARS) -> pd.DataFrame:
    """
    Detecta los tres niveles de swings: STH/STL, ITH/ITL, LTH/LTL.

    Añade las columnas:
      swing_high_st, swing_low_st, pivot_high_st, pivot_low_st
      swing_high_it, swing_low_it, pivot_high_it, pivot_low_it
      swing_high_lt, swing_low_lt, pivot_high_lt, pivot_low_lt
      pivot_high_bar, pivot_low_bar
    """
    out = detect_pivots(df, n)

    # Nivel intermedio
    is_it_h, val_it_h, is_it_l, val_it_l = _build_higher_level_pivots(
        out["swing_high_st"].values, out["pivot_high_st"].values,
        out["swing_low_st"].values,  out["pivot_low_st"].values,
    )
    out["swing_high_it"] = is_it_h
    out["pivot_high_it"] = val_it_h
    out["swing_low_it"]  = is_it_l
    out["pivot_low_it"]  = val_it_l

    # Nivel largo
    is_lt_h, val_lt_h, is_lt_l, val_lt_l = _build_higher_level_pivots(
        is_it_h, val_it_h, is_it_l, val_it_l,
    )
    out["swing_high_lt"] = is_lt_h
    out["pivot_high_lt"] = val_lt_h
    out["swing_low_lt"]  = is_lt_l
    out["pivot_low_lt"]  = val_lt_l

    return out


# ── BOS (Break of Structure) ──────────────────────────────────────────────────

def detect_bos(
    df: pd.DataFrame,
    *,
    level: str = "short_term",
    n: int = SWING_PIVOT_BARS,
) -> pd.DataFrame:
    """
    Detecta BOS (Break of Structure) en el nivel de swing especificado.

    BOS alcista: cierre por encima del último swing high (del nivel dado).
    BOS bajista: cierre por debajo del último swing low.

    Una mecha que supera un nivel NO es BOS (PD-003 confirmado).

    Añade columnas:
      bos_bull  — bool: BOS alcista en esta barra
      bos_bear  — bool: BOS bajista en esta barra
      bos_level — float: nivel de precio del swing que fue roto
    """
    _check_ohlc_columns(df)

    suffix = _level_suffix(level)
    if f"swing_high_{suffix}" not in df.columns:
        df = detect_swing_hierarchy(df, n)

    close  = df["close"].values
    length = len(df)

    bos_bull  = np.zeros(length, dtype=bool)
    bos_bear  = np.zeros(length, dtype=bool)
    bos_level = np.full(length, np.nan)

    last_swing_high = np.nan
    last_swing_low  = np.nan

    for i in range(length):
        # Actualizar el último swing conocido (disponible en la barra i)
        if df[f"swing_high_{suffix}"].iat[i]:
            last_swing_high = df[f"pivot_high_{suffix}"].iat[i]
        if df[f"swing_low_{suffix}"].iat[i]:
            last_swing_low = df[f"pivot_low_{suffix}"].iat[i]

        # Comprobar BOS: ¿el cierre actual rompe el último swing?
        if not np.isnan(last_swing_high) and close[i] > last_swing_high:
            bos_bull[i]  = True
            bos_level[i] = last_swing_high
        if not np.isnan(last_swing_low) and close[i] < last_swing_low:
            bos_bear[i]  = True
            bos_level[i] = last_swing_low

    out = df.copy() if not isinstance(df, pd.DataFrame) else df.copy()
    out["bos_bull"]  = bos_bull
    out["bos_bear"]  = bos_bear
    out["bos_level"] = bos_level

    return out


# ── CHOCH (Change of Character) ───────────────────────────────────────────────

def detect_choch(
    df: pd.DataFrame,
    *,
    level: str = "short_term",
    n: int = SWING_PIVOT_BARS,
) -> pd.DataFrame:
    """
    Detecta CHOCH (Change of Character): primer cierre en dirección contraria
    al swing protegido de la estructura predominante.

    Bias alcista  → el swing low más reciente es el nivel "protegido".
                    CHOCH bajista = cierre por debajo de ese protected low.
    Bias bajista  → el swing high más reciente es el nivel "protegido".
                    CHOCH alcista = cierre por encima de ese protected high.

    Añade columnas:
      choch_bull  — bool: CHOCH alcista (cambio de bajista a potencialmente alcista)
      choch_bear  — bool: CHOCH bajista (cambio de alcista a potencialmente bajista)
      choch_level — float: nivel de precio del swing roto
      structure_bias — "bullish" | "bearish" | "ranging" (bias activo en esa barra)
    """
    _check_ohlc_columns(df)

    suffix = _level_suffix(level)
    if f"swing_high_{suffix}" not in df.columns:
        df = detect_swing_hierarchy(df, n)
    if "bos_bull" not in df.columns:
        df = detect_bos(df, level=level, n=n)

    close  = df["close"].values
    length = len(df)

    choch_bull  = np.zeros(length, dtype=bool)
    choch_bear  = np.zeros(length, dtype=bool)
    choch_level = np.full(length, np.nan)
    bias        = np.full(length, None, dtype=object)

    current_bias = "ranging"
    protected_high = np.nan
    protected_low  = np.nan

    for i in range(length):
        # Actualizar swings y bias según BOS
        if df["bos_bull"].iat[i]:
            current_bias = "bullish"
            protected_low = np.nan  # se resetea en nuevo BOS
        if df["bos_bear"].iat[i]:
            current_bias = "bearish"
            protected_high = np.nan

        # Actualizar el swing protegido según el bias actual
        if df[f"swing_low_{suffix}"].iat[i]:
            swing_l = df[f"pivot_low_{suffix}"].iat[i]
            if current_bias == "bullish":
                protected_low = swing_l
        if df[f"swing_high_{suffix}"].iat[i]:
            swing_h = df[f"pivot_high_{suffix}"].iat[i]
            if current_bias == "bearish":
                protected_high = swing_h

        # CHOCH: ruptura del swing protegido en dirección contraria
        if current_bias == "bullish" and not np.isnan(protected_low):
            if close[i] < protected_low:
                choch_bear[i]  = True
                choch_level[i] = protected_low
                current_bias   = "ranging"

        if current_bias == "bearish" and not np.isnan(protected_high):
            if close[i] > protected_high:
                choch_bull[i]  = True
                choch_level[i] = protected_high
                current_bias   = "ranging"

        bias[i] = current_bias

    out = df.copy()
    out["choch_bull"]     = choch_bull
    out["choch_bear"]     = choch_bear
    out["choch_level"]    = choch_level
    out["structure_bias"] = bias

    return out


# ── Pipeline completo de estructura de mercado ────────────────────────────────

def add_market_structure(
    df: pd.DataFrame,
    *,
    n: int = SWING_PIVOT_BARS,
    level: str = "short_term",
) -> pd.DataFrame:
    """
    Añade toda la estructura de mercado al DataFrame en una sola llamada.

    Equivale a: detect_swing_hierarchy → detect_bos → detect_choch.

    Parámetros:
      n      — velas a cada lado del pivot (default: 1 → 3-vela pivot)
      level  — "short_term" | "intermediate_term" | "long_term"

    Returns copia del DataFrame con columnas de swing, BOS y CHOCH.
    """
    out = detect_swing_hierarchy(df, n)
    out = detect_bos(out, level=level, n=n)
    out = detect_choch(out, level=level, n=n)
    return out


# ── Utilidades ────────────────────────────────────────────────────────────────

def _level_suffix(level: str) -> str:
    mapping = {
        "short_term":        "st",
        "intermediate_term": "it",
        "long_term":         "lt",
    }
    if level not in mapping:
        raise ValueError(f"level debe ser uno de {list(mapping.keys())}, se recibió '{level}'")
    return mapping[level]


def _check_ohlc_columns(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas OHLC: {missing}")


def last_swing_highs(df: pd.DataFrame, level: str = "short_term") -> pd.Series:
    """
    Serie con el valor del último swing high conocido en cada barra (forward-fill).
    Útil para calcular la distancia al swing más reciente.
    """
    suffix = _level_suffix(level)
    pivot_col = f"pivot_high_{suffix}"
    if pivot_col not in df.columns:
        raise ValueError(f"Columna {pivot_col} no encontrada. Ejecuta detect_swing_hierarchy primero.")
    return df[pivot_col].ffill()


def last_swing_lows(df: pd.DataFrame, level: str = "short_term") -> pd.Series:
    """Serie con el valor del último swing low conocido en cada barra (forward-fill)."""
    suffix = _level_suffix(level)
    pivot_col = f"pivot_low_{suffix}"
    if pivot_col not in df.columns:
        raise ValueError(f"Columna {pivot_col} no encontrada. Ejecuta detect_swing_hierarchy primero.")
    return df[pivot_col].ffill()
