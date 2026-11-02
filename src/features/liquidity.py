"""
liquidity.py — Detección de niveles de liquidez (BSL / SSL)

Implementa las zonas de liquidez confirmadas por el trader (PD-011/012):

  Buy-Side Liquidity (BSL): niveles por encima de precios relevantes
    • Equal Highs (EQH)
    • Swing Highs (STH)
    • Previous Day High (PDH)
    • Previous Week High (PWH)
    • Session High

  Sell-Side Liquidity (SSL): niveles por debajo de precios relevantes
    • Equal Lows (EQL)
    • Swing Lows (STL)
    • Previous Day Low (PDL)
    • Previous Week Low (PWL)
    • Session Low

Detección de barridos (PD-012):
  sweep_candidate    — la mecha supera el nivel (wick breach)
  rejection_confirm  — la mecha supera y el cierre vuelve al lado contrario

IMPORTANTE: estos niveles son zonas inferidas a partir de la acción del precio,
no órdenes reales observadas. El histórico BID de Dukascopy no proporciona
información de libro de órdenes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.strategy_config import EQUAL_HLS_TOLERANCE_PIPS

# ── Niveles estáticos: día anterior y semana anterior ────────────────────────

def prev_day_levels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade PDH (Previous Day High) y PDL (Previous Day Low).

    Los niveles se calculan desde los datos del día anterior (UTC).
    No-lookahead: PDH/PDL se conocen al inicio del día actual.
    """
    _check_datetime_index(df)
    out = df.copy()

    # Agrupar por día UTC
    daily = df.resample("1D")["high"].max().rename("pdh_raw")
    daily_l = df.resample("1D")["low"].min().rename("pdl_raw")

    # Desplazar 1 día hacia adelante para no-lookahead
    pdh = daily.shift(1).reindex(df.index, method="ffill")
    pdl = daily_l.shift(1).reindex(df.index, method="ffill")

    out["pdh"] = pdh.values
    out["pdl"] = pdl.values

    return out


def prev_week_levels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade PWH (Previous Week High) y PWL (Previous Week Low).

    No-lookahead: niveles del lunes de la semana anterior disponibles desde
    el primer lunes de la semana actual.
    """
    _check_datetime_index(df)
    out = df.copy()

    weekly_h = df.resample("1W")["high"].max()
    weekly_l = df.resample("1W")["low"].min()

    # Desplazar 1 semana
    pwh = weekly_h.shift(1).reindex(df.index, method="ffill")
    pwl = weekly_l.shift(1).reindex(df.index, method="ffill")

    out["pwh"] = pwh.values
    out["pwl"] = pwl.values

    return out


# ── Niveles de sesión ─────────────────────────────────────────────────────────

def session_levels(df: pd.DataFrame, session_col: str = "any_session") -> pd.DataFrame:
    """
    Calcula el high y low de la sesión en curso para cada barra.

    Requiere que ``session_col`` esté presente en df (booleano).
    Los niveles se acumulan dentro de la misma sesión usando expanding max/min.

    Si session_col no está presente, devuelve NaN en las columnas.
    """
    out = df.copy()

    if session_col not in df.columns:
        out["session_high"] = np.nan
        out["session_low"]  = np.nan
        return out

    in_session = df[session_col].values
    h = df["high"].values
    l = df["low"].values
    n = len(df)

    sess_high = np.full(n, np.nan)
    sess_low  = np.full(n, np.nan)

    current_high = np.nan
    current_low  = np.nan

    for i in range(n):
        if in_session[i]:
            if np.isnan(current_high):
                current_high = h[i]
                current_low  = l[i]
            else:
                current_high = max(current_high, h[i])
                current_low  = min(current_low,  l[i])
            sess_high[i] = current_high
            sess_low[i]  = current_low
        else:
            current_high = np.nan
            current_low  = np.nan

    out["session_high"] = sess_high
    out["session_low"]  = sess_low

    return out


# ── Equal Highs / Equal Lows ──────────────────────────────────────────────────

def detect_equal_levels(
    df: pd.DataFrame,
    *,
    lookback: int = 20,
    tolerance_pips: float = EQUAL_HLS_TOLERANCE_PIPS,
    pip_size: float = 0.0001,
) -> pd.DataFrame:
    """
    Detecta Equal Highs (EQH) y Equal Lows (EQL).

    Una vela forma un EQH si su high está dentro de ``tolerance_pips`` de
    algún high anterior en las últimas ``lookback`` barras.

    Añade:
      eqh          — bool: equal high en esta barra
      eql          — bool: equal low en esta barra
      eqh_level    — float: nivel del equal high
      eql_level    — float: nivel del equal low
    """
    _check_ohlc_columns(df)
    n = len(df)
    h = df["high"].values
    l = df["low"].values
    tol = tolerance_pips * pip_size

    eqh       = np.zeros(n, dtype=bool)
    eql       = np.zeros(n, dtype=bool)
    eqh_level = np.full(n, np.nan)
    eql_level = np.full(n, np.nan)

    for i in range(1, n):
        start = max(0, i - lookback)
        # EQH: ¿el high[i] coincide con algún high en [start, i-1]?
        prior_highs = h[start:i]
        matches_h = np.abs(prior_highs - h[i]) <= tol
        if matches_h.any():
            eqh[i]       = True
            eqh_level[i] = h[i]

        prior_lows = l[start:i]
        matches_l = np.abs(prior_lows - l[i]) <= tol
        if matches_l.any():
            eql[i]       = True
            eql_level[i] = l[i]

    out = df.copy()
    out["eqh"]       = eqh
    out["eql"]       = eql
    out["eqh_level"] = eqh_level
    out["eql_level"] = eql_level

    return out


# ── Swing Highs/Lows como BSL/SSL ─────────────────────────────────────────────

def swing_liquidity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrae BSL/SSL a partir de swings detectados por structure.py.

    Requiere las columnas ``swing_high_st``, ``swing_low_st``,
    ``pivot_high_st``, ``pivot_low_st`` (de detect_swing_hierarchy).

    Si no están presentes, las detecta automáticamente con n=1.

    Añade:
      bsl_swing    — float: nivel de BSL de swing más reciente (forward-filled)
      ssl_swing    — float: nivel de SSL de swing más reciente (forward-filled)
    """
    if "swing_high_st" not in df.columns:
        from src.features.structure import detect_pivots
        df = detect_pivots(df, n=1)

    out = df.copy()
    out["bsl_swing"] = df["pivot_high_st"].ffill()
    out["ssl_swing"] = df["pivot_low_st"].ffill()

    return out


# ── Detección de sweeps de liquidez ───────────────────────────────────────────

def detect_liquidity_sweeps(
    df: pd.DataFrame,
    level_col: str,
    *,
    direction: str = "bsl",
) -> pd.DataFrame:
    """
    Detecta barridos de liquidez sobre el nivel especificado.

    Para BSL (buy-side): sweep = high > level. Rejection = close < level.
    Para SSL (sell-side): sweep = low  < level. Rejection = close > level.

    Añade:
      {level_col}_sweep_candidate   — bool: mecha supera el nivel
      {level_col}_rejection_confirm — bool: mecha supera Y cierre de vuelta
    """
    if level_col not in df.columns:
        raise ValueError(f"Columna '{level_col}' no encontrada en el DataFrame")

    level = df[level_col].values
    h     = df["high"].values
    l     = df["low"].values
    c     = df["close"].values
    n     = len(df)

    sweep_cand = np.zeros(n, dtype=bool)
    reject_con = np.zeros(n, dtype=bool)

    for i in range(n):
        lv = level[i]
        if np.isnan(lv):
            continue
        if direction == "bsl":
            if h[i] > lv:
                sweep_cand[i] = True
                if c[i] < lv:
                    reject_con[i] = True
        elif direction == "ssl":
            if l[i] < lv:
                sweep_cand[i] = True
                if c[i] > lv:
                    reject_con[i] = True
        else:
            raise ValueError(f"direction debe ser 'bsl' o 'ssl', se recibió '{direction}'")

    prefix = level_col
    out = df.copy()
    out[f"{prefix}_sweep_candidate"]   = sweep_cand
    out[f"{prefix}_rejection_confirm"] = reject_con

    return out


# ── Pipeline completo de liquidez ─────────────────────────────────────────────

def add_liquidity_features(
    df: pd.DataFrame,
    *,
    eqh_lookback: int = 20,
    tolerance_pips: float = EQUAL_HLS_TOLERANCE_PIPS,
    session_col: str | None = None,
) -> pd.DataFrame:
    """
    Añade todas las features de liquidez al DataFrame.

    Incluye: PDH/PDL, PWH/PWL, EQH/EQL, BSL/SSL de swings.
    Opcionalmente niveles de sesión si session_col está disponible.
    Sweeps se calculan sobre PDH (BSL) y PDL (SSL) como ejemplo.

    Returns copia del DataFrame enriquecida.
    """
    _check_datetime_index(df)
    out = df.copy()
    out = prev_day_levels(out)
    out = prev_week_levels(out)
    out = detect_equal_levels(out, lookback=eqh_lookback, tolerance_pips=tolerance_pips)
    out = swing_liquidity(out)

    if session_col is not None and session_col in df.columns:
        out = session_levels(out, session_col=session_col)

    # Sweeps sobre PDH (BSL) y PDL (SSL) como referencia
    if "pdh" in out.columns:
        out = detect_liquidity_sweeps(out, "pdh", direction="bsl")
    if "pdl" in out.columns:
        out = detect_liquidity_sweeps(out, "pdl", direction="ssl")

    return out


# ── Utilidades ────────────────────────────────────────────────────────────────

def _check_ohlc_columns(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas OHLC: {missing}")


def _check_datetime_index(df: pd.DataFrame) -> None:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(
            f"El índice debe ser DatetimeIndex, se recibió {type(df.index).__name__}"
        )
